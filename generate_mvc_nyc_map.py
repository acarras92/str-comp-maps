#!/usr/bin/env python3
"""
Marriott Vacation Club NYC — Multi-Comp-Set Cross-Reference Map.

Subject: Marriott Vacation Club, 33 W 37th St (gold star).
Plotted on top of 4 distinct reference comp sets pulled from the drops folder:

  1. Margaritaville STR comp set       (Monthly STAR_69701)
  2. Courtyard Herald Square comp set  (Part Report + CY H Square Assets)
  3. Eastdil comp set                (ES Set Participation + Property Analytics)
  4. 960 Sixth Ave topline comps       (numbered 1–24 only)

Rules:
  - Each comp set has its own color.
  - Hotels in multiple sets are plotted ONCE; the color reflects the highest-priority
    set they belong to, and ALL memberships are shown as badges in the sidebar / info window.
  - The original "subject" of each comp set (where applicable) is highlighted as a
    comp-set anchor (larger / outlined pin in that set's color).
  - Performance data is surfaced where the source data permits it:
      * Margaritaville STR: subject R12 perf + aggregate comp perf (per STR masking)
      * CY Herald Square: composite (set-wide) R12 perf
      * Eastdil: composite (set-wide) R12 perf
      * Topline: individual per-hotel 2024 + 2025 Occ / ADR / RevPAR / RPI

Usage:
    python generate_mvc_nyc_map.py            # generate only
    python generate_mvc_nyc_map.py --deploy   # generate + commit + push + verify
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

import pandas as pd
import requests

# ── Configuration ──
REPO_DIR = r"C:\Users\acarr\OneDrive\Documents\Claude\Projects\str-comp-maps"
DROP_DIR = r"C:\Users\acarr\OneDrive\Documents\STR Drops\Marriott Vacation Club, New York City"
GEOCACHE_PATH = os.path.join(REPO_DIR, "geocache.json")
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
API_KEY = "AIzaSyCTAmcCrmL2Z-SerlTKHoG3xPQaGcvmKcU"
REPO_SLUG = "acarras92/str-comp-maps"
PAGES_BASE_URL = "https://acarras92.github.io/str-comp-maps"
WORKFLOW_NAME = "Deploy to GitHub Pages"

OUTPUT_SLUG = "marriott-vacation-club-new-york-city"

SUBJECT = {
    "name": "Marriott Vacation Club, New York City",
    "short_name": "Marriott Vacation Club NYC",
    "address": "33 W 37th St",
    "city_state": "New York, NY",
    "zip": "10018",
    "rooms": 0,
    "subject": True,
    "operator": "Marriott Vacations Worldwide",
    "brand": "Marriott Vacation Club",
}

# Color palette (priority order = membership precedence for the pin color)
COMP_SETS = [
    {
        "id": "margaritaville",
        "label": "Margaritaville STR Comp Set",
        "short": "Margaritaville",
        "color": "#d32f2f",       # red
        "priority": 1,
    },
    {
        "id": "cy_hsq",
        "label": "Courtyard Herald Square Comp Set",
        "short": "CY Herald Sq",
        "color": "#1565c0",       # blue
        "priority": 2,
    },
    {
        "id": "eastdil",
        "label": "Eastdil Comp Set",
        "short": "Eastdil",
        "color": "#7b1fa2",       # purple
        "priority": 3,
    },
    {
        "id": "topline",
        "label": "960 Sixth Ave Topline Comps (Numbered)",
        "short": "Topline",
        "color": "#00897b",       # teal
        "priority": 4,
    },
]
SET_BY_ID = {s["id"]: s for s in COMP_SETS}
SUBJECT_COLOR = "#f59e0b"  # gold/amber for MVC star

# Source files
F_MARG_STR    = os.path.join(DROP_DIR, "Monthly STAR_69701-20251200-USD-E-live (1).xlsx")
F_CY_PART     = os.path.join(DROP_DIR, "Part Report.xlsx")
F_CY_PERF     = os.path.join(DROP_DIR, "CY H Square Assets.xlsx")
F_ES_SET      = os.path.join(DROP_DIR, "ES Set (Archer, Arlo, Exec, Hendricks, Centric, Moxy, Refinery).xlsx")
F_TOPLINE     = os.path.join(DROP_DIR, "960 Sixth Ave Topline Comps.xlsx")


# ── Hotel normalization ──

def norm_key(name):
    """Loose key for matching hotels across sources (lowercase, alphanumeric only)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# Manual alias table — maps how a hotel is named across different source files
# (the topline file uses informal short names; STR/CoStar use long official names).
# Each entry: short_alias -> canonical_long_name
ALIASES = {
    "renaissancemidtown":                 "Renaissance New York Midtown Hotel",
    "renaissancetimessquare":             "Renaissance New York Times Square Hotel",
    "hamptoninnmanhattan35thstempirestatebldg": "Hampton Inn Manhattan-35th St/Empire State Bldg",
    "courtyardtimessquaresouth":          "Courtyard New York Manhattan Times Square South",
    "courtyardnewyorkmanhattantimessquaresouth": "Courtyard New York Manhattan Times Square South",
    "hyattplacenewyorkmidtownsouth":      "Hyatt Place New York/Midtown-South",
    "hiltongardeninn42street":            "Hilton Garden Inn New York Times Square Central",
    "hiltongardeninn35thstreet":          "Hilton Garden Inn New York/West 35th Street",
    "arlonomad":                          "Arlo NoMad",
    "margaritavilletimessquare":          "Margaritaville Resort Times Square",
    "margaritavilleresorttimessquare":    "Margaritaville Resort Times Square",
    "archerhotelnewyork":                 "Archer Hotel New York",
    "moxynyctimessquare":                 "MOXY NYC Times Square",
    "achotelheraldsquarehighgaterunrate": "AC Hotel New York Herald Square",
    "courtyardfifthavenue":               "Courtyard New York Manhattan/Fifth Avenue",
}

def canonical(name):
    """Return canonical long-form name for a hotel (handles short topline aliases)."""
    k = norm_key(name)
    return ALIASES.get(k, name.strip())


# Address overrides for hotels whose name alone confuses the geocoder
ADDRESS_OVERRIDES = {
    norm_key("Hampton Inn Grand Central"): "231 E 43rd St, New York, NY 10017",
    norm_key("Hampton Inn Manhattan Grand Central"): "231 E 43rd St, New York, NY 10017",
}


# ── Parsers ──

def parse_margaritaville_str():
    """Parse Monthly STAR file → roster + R12 perf for Margaritaville set."""
    df = pd.read_excel(F_MARG_STR, sheet_name="Response", header=None)

    hotels = []
    row = 22
    while row < len(df):
        name = df.iloc[row, 3]
        if pd.isna(name):
            break
        str_id = str(int(df.iloc[row, 2])) if pd.notna(df.iloc[row, 2]) else ""
        city_state = str(df.iloc[row, 4]) if pd.notna(df.iloc[row, 4]) else ""
        zip_code = str(int(df.iloc[row, 5])) if pd.notna(df.iloc[row, 5]) else ""
        rooms = int(df.iloc[row, 7]) if pd.notna(df.iloc[row, 7]) else 0
        is_anchor = row == 22  # STR subject
        hotels.append({
            "name": canonical(str(name).strip()),
            "str_id": str_id,
            "city_state": city_state.replace(",", ", "),
            "zip": zip_code,
            "rooms": rooms,
            "set_id": "margaritaville",
            "is_anchor": is_anchor,
        })
        row += 1

    # Glance sheet → R12 metrics
    g = pd.read_excel(F_MARG_STR, sheet_name="Glance", header=None)
    r12_row = None
    for i in range(len(g)):
        v = g.iloc[i, 3] if pd.notna(g.iloc[i, 3]) else ""
        if "Running 12 Month" in str(v):
            r12_row = i
            break

    def sf(v):
        try: return float(v)
        except (ValueError, TypeError): return 0.0

    perf = {}
    if r12_row is not None:
        perf = {
            "period": "R12 ending Dec 2025",
            "subject_name": hotels[0]["name"],
            "subj_occ":    f"{sf(g.iloc[r12_row, 6]):.1f}%",
            "comp_occ":    f"{sf(g.iloc[r12_row, 7]):.1f}%",
            "mpi":         f"{sf(g.iloc[r12_row, 8]):.1f}",
            "subj_adr":    f"${sf(g.iloc[r12_row, 11]):.2f}",
            "comp_adr":    f"${sf(g.iloc[r12_row, 12]):.2f}",
            "ari":         f"{sf(g.iloc[r12_row, 13]):.1f}",
            "subj_revpar": f"${sf(g.iloc[r12_row, 16]):.2f}",
            "comp_revpar": f"${sf(g.iloc[r12_row, 17]):.2f}",
            "rgi":         f"{sf(g.iloc[r12_row, 18]):.1f}",
        }
    return hotels, perf


def parse_cy_herald_square():
    """Parse Part Report (roster) + CY H Square Assets (aggregate perf)."""
    # Roster
    df = pd.read_excel(F_CY_PART, sheet_name="Participation", header=None)
    hotels = []
    row = 2  # Composite at row 1, members from row 2 onward
    while row < len(df):
        name = df.iloc[row, 0]
        if pd.isna(name):
            break
        rooms = int(df.iloc[row, 7]) if pd.notna(df.iloc[row, 7]) else 0
        city = str(df.iloc[row, 2]) if pd.notna(df.iloc[row, 2]) else ""
        state = str(df.iloc[row, 3]) if pd.notna(df.iloc[row, 3]) else ""
        zipc = str(int(df.iloc[row, 4])) if pd.notna(df.iloc[row, 4]) else ""
        prop_id = str(int(df.iloc[row, 1])) if pd.notna(df.iloc[row, 1]) else ""
        hotels.append({
            "name": canonical(str(name).strip()),
            "str_id": prop_id,
            "city_state": f"{city}, {state}".strip(", "),
            "zip": zipc,
            "rooms": rooms,
            "set_id": "cy_hsq",
            "is_anchor": False,
        })
        row += 1

    # Implied subject (anchor) — the Courtyard Herald Square itself (not in roster)
    anchor = {
        "name": "Courtyard New York Manhattan/Herald Square",
        "str_id": "",
        "city_state": "New York, NY",
        "zip": "10001",
        "rooms": 0,
        "set_id": "cy_hsq",
        "is_anchor": True,
    }
    hotels.insert(0, anchor)

    # Aggregate perf — average the most recent 12 months from HospitalityDataGrid
    perf_df = pd.read_excel(F_CY_PERF, sheet_name="HospitalityDataGrid")
    # Rows are reverse chronological. Take first 12 rows (Apr 2025–Mar 2026 inclusive)
    r12 = perf_df.head(12)
    occ = r12["Occupancy"].mean() * 100
    adr = (r12["Revenue"].sum() / r12["Demand"].sum()) if r12["Demand"].sum() else 0
    revpar = r12["RevPAR"].mean()
    perf = {
        "period": f"R12 ending {r12.iloc[0]['Period']}",
        "label": "Composite Set (incl. subject)",
        "occ":    f"{occ:.1f}%",
        "adr":    f"${adr:.2f}",
        "revpar": f"${revpar:.2f}",
    }
    return hotels, perf


def parse_eastdil():
    """Parse ES Set Participation (roster) + Property Analytics (aggregate perf)."""
    df = pd.read_excel(F_ES_SET, sheet_name="Participation", header=None)
    hotels = []
    row = 7  # Composite at row 6, members from row 7 onward
    while row < len(df):
        name = df.iloc[row, 0]
        if pd.isna(name):
            break
        rooms = int(df.iloc[row, 7]) if pd.notna(df.iloc[row, 7]) else 0
        city = str(df.iloc[row, 2]) if pd.notna(df.iloc[row, 2]) else ""
        state = str(df.iloc[row, 3]) if pd.notna(df.iloc[row, 3]) else ""
        zipc = str(int(df.iloc[row, 4])) if pd.notna(df.iloc[row, 4]) else ""
        prop_id = str(int(df.iloc[row, 1])) if pd.notna(df.iloc[row, 1]) else ""
        hotels.append({
            "name": canonical(str(name).strip()),
            "str_id": prop_id,
            "city_state": f"{city}, {state}".strip(", "),
            "zip": zipc,
            "rooms": rooms,
            "set_id": "eastdil",
            "is_anchor": False,
        })
        row += 1

    # Aggregate perf — Property Analytics monthly grid, latest 12 rows
    perf_df = pd.read_excel(F_ES_SET, sheet_name="Property Analytics", header=5)
    r12 = perf_df.head(12)
    occ = r12["Occupancy"].mean() * 100
    adr = (r12["Revenue"].sum() / r12["Demand"].sum()) if r12["Demand"].sum() else 0
    revpar = r12["RevPAR"].mean()
    perf = {
        "period": f"R12 ending {r12.iloc[0]['Period']}",
        "label": "Composite Set (Eastdil aggregate)",
        "occ":    f"{occ:.1f}%",
        "adr":    f"${adr:.2f}",
        "revpar": f"${revpar:.2f}",
    }
    return hotels, perf


def parse_topline():
    """Parse 960 Sixth Ave topline — numbered comps only (1–24), with per-hotel perf."""
    df = pd.read_excel(F_TOPLINE, sheet_name="TOP LINE COMPS", header=7)
    # Columns: ['Unnamed: 0', 'Unnamed: 1', 'No.', 'Hotel', 'Keys',
    #           'Occ', 'ADR', 'RevPAR', ' CS RPI',
    #           'Occ.1', 'ADR.1', 'RevPAR.1', ' CS RPI.1',
    #           '2024 Notes', '2025 Notes', ...]
    hotels = []
    for _, r in df.iterrows():
        no = r["No."]
        name = r["Hotel"]
        if pd.isna(no) or pd.isna(name):
            continue  # skip reference (unnumbered) hotels
        keys = int(r["Keys"]) if pd.notna(r["Keys"]) else 0

        def num(v):
            if pd.isna(v): return None
            try: return float(v)
            except (TypeError, ValueError): return None
        def fmt_pct(v):
            n = num(v); return f"{n*100:.1f}%" if n is not None else "—"
        def fmt_dol(v):
            n = num(v); return f"${n:.0f}" if n is not None else "—"
        def fmt_rpi(v):
            n = num(v); return f"{n:.2f}" if n is not None else "—"

        perf = {
            "occ_2024":    fmt_pct(r.get("Occ")),
            "adr_2024":    fmt_dol(r.get("ADR")),
            "revpar_2024": fmt_dol(r.get("RevPAR")),
            "rpi_2024":    fmt_rpi(r.get(" CS RPI")),
            "occ_2025":    fmt_pct(r.get("Occ.1")),
            "adr_2025":    fmt_dol(r.get("ADR.1")),
            "revpar_2025": fmt_dol(r.get("RevPAR.1")),
            "rpi_2025":    fmt_rpi(r.get(" CS RPI.1")),
            "notes_2024":  str(r.get("2024 Notes", "")) if pd.notna(r.get("2024 Notes")) else "",
            "notes_2025":  str(r.get("2025 Notes", "")) if pd.notna(r.get("2025 Notes")) else "",
        }
        hotels.append({
            "name": canonical(str(name).strip()),
            "str_id": "",
            "city_state": "New York, NY",
            "zip": "",
            "rooms": keys,
            "set_id": "topline",
            "is_anchor": False,
            "topline_no": int(no),
            "topline_perf": perf,
        })
    return hotels, {
        "period": "2024 (Actual / Forecast) and 2025 (Trended)",
        "label": "Individual per-hotel performance below",
    }


# ── Dedup + merge ──

def merge_hotels(all_lists):
    """
    Combine hotels from all sources into a deduped list with multi-set memberships.

    Returns: list of dicts:
      {
        name, address, city_state, zip, rooms, str_id,
        memberships: [set_id, ...] sorted by priority,
        primary_set_id: first by priority,
        is_anchor_for: [set_id, ...] — sets where this hotel is the anchor,
        topline_perf: {...} if a topline numbered comp,
        topline_no: int if a topline numbered comp,
      }
    """
    merged = {}  # key = norm_key(canonical name)
    for hotels in all_lists:
        for h in hotels:
            k = norm_key(h["name"])
            if k not in merged:
                merged[k] = {
                    "name": h["name"],
                    "str_id": h.get("str_id", ""),
                    "city_state": h.get("city_state", ""),
                    "zip": h.get("zip", ""),
                    "rooms": h.get("rooms", 0),
                    "memberships": [],
                    "anchor_for": [],
                    "topline_no": None,
                    "topline_perf": None,
                }
            entry = merged[k]
            if h["set_id"] not in entry["memberships"]:
                entry["memberships"].append(h["set_id"])
            if h.get("is_anchor"):
                if h["set_id"] not in entry["anchor_for"]:
                    entry["anchor_for"].append(h["set_id"])
            # Prefer the longer/canonical name and largest room count
            if len(h["name"]) > len(entry["name"]):
                entry["name"] = h["name"]
            if h.get("rooms", 0) > entry["rooms"]:
                entry["rooms"] = h["rooms"]
            if h.get("str_id") and not entry["str_id"]:
                entry["str_id"] = h["str_id"]
            if h.get("city_state") and not entry["city_state"]:
                entry["city_state"] = h["city_state"]
            if h.get("zip") and not entry["zip"]:
                entry["zip"] = h["zip"]
            if h.get("topline_no") is not None:
                entry["topline_no"] = h["topline_no"]
                entry["topline_perf"] = h.get("topline_perf")

    # Sort memberships by priority and pick primary
    for entry in merged.values():
        entry["memberships"].sort(key=lambda sid: SET_BY_ID[sid]["priority"])
        entry["primary_set_id"] = entry["memberships"][0]

    return list(merged.values())


# ── Geocoding ──

def load_geocache():
    if os.path.exists(GEOCACHE_PATH):
        with open(GEOCACHE_PATH, "r") as f:
            return json.load(f)
    return {}

def save_geocache(cache):
    with open(GEOCACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

def geocode_one(name, address, city_state, zip_code, cache):
    override = ADDRESS_OVERRIDES.get(norm_key(name))
    if override:
        query = f"{name}, {override}"
    else:
        query = f"{name}, {address}, {city_state} {zip_code}".strip(", ")
    if query in cache:
        return cache[query]
    print(f"  [geocoding] {name}...")
    resp = requests.get(GEOCODE_URL, params={"address": query, "key": API_KEY}).json()
    if resp.get("results"):
        loc = resp["results"][0]["geometry"]["location"]
        cache[query] = loc
        save_geocache(cache)
        time.sleep(0.1)
        return loc
    print(f"  WARNING: Could not geocode {name}")
    return None


def geocode_all(hotels, subject):
    cache = load_geocache()
    print("\nGeocoding hotels...")
    for h in [subject] + hotels:
        loc = geocode_one(h["name"], h.get("address", ""), h["city_state"], h["zip"], cache)
        if loc:
            h["lat"] = loc["lat"]
            h["lng"] = loc["lng"]
        else:
            h["lat"], h["lng"] = 0, 0
    print(f"  Done — {len(hotels) + 1} hotels.\n")


# ── HTML render ──

def render_html(hotels, subject, perf_marg, perf_cy, perf_es, perf_top):
    # Map center: average of all coords (subject + comps)
    coords = [(subject["lat"], subject["lng"])] + [(h["lat"], h["lng"]) for h in hotels if h["lat"]]
    avg_lat = sum(c[0] for c in coords) / len(coords)
    avg_lng = sum(c[1] for c in coords) / len(coords)

    # Build hotels JS payload
    js_hotels = []
    for h in hotels:
        set_color = SET_BY_ID[h["primary_set_id"]]["color"]
        memberships_js = json.dumps(h["memberships"])
        anchor_for_js  = json.dumps(h["anchor_for"])
        topline_perf_js = json.dumps(h["topline_perf"]) if h["topline_perf"] else "null"
        topline_no = h["topline_no"] if h["topline_no"] is not None else "null"
        js_hotels.append(f"""    {{
      name: {json.dumps(h["name"])},
      strId: {json.dumps(h["str_id"])},
      cityState: {json.dumps(h["city_state"])},
      zip: {json.dumps(h["zip"])},
      rooms: {h["rooms"]},
      lat: {h["lat"]}, lng: {h["lng"]},
      memberships: {memberships_js},
      anchorFor: {anchor_for_js},
      primarySet: {json.dumps(h["primary_set_id"])},
      color: {json.dumps(set_color)},
      isAnchor: {str(bool(h["anchor_for"])).lower()},
      toplineNo: {topline_no},
      toplinePerf: {topline_perf_js},
    }}""")
    hotels_js = "const HOTELS = [\n" + ",\n".join(js_hotels) + "\n  ];"

    # Comp set definitions for JS
    sets_js = "const COMP_SETS = " + json.dumps({s["id"]: {"label": s["label"], "short": s["short"], "color": s["color"]} for s in COMP_SETS}, indent=2) + ";"

    # Counts per set
    set_counts = {s["id"]: 0 for s in COMP_SETS}
    for h in hotels:
        for sid in h["memberships"]:
            set_counts[sid] += 1

    # Header KPIs based on Margaritaville STR (subject of the official STR set)
    p = perf_marg
    subj_str_name = p.get("subject_name", "Margaritaville Resort Times Square")
    marg_subj_occ    = p.get("subj_occ", "—")
    marg_subj_adr    = p.get("subj_adr", "—")
    marg_subj_revpar = p.get("subj_revpar", "—")
    marg_mpi = p.get("mpi", "—")
    marg_ari = p.get("ari", "—")
    marg_rgi = p.get("rgi", "—")
    marg_comp_occ    = p.get("comp_occ", "—")
    marg_comp_adr    = p.get("comp_adr", "—")
    marg_comp_revpar = p.get("comp_revpar", "—")

    cy_period   = perf_cy.get("period", "—")
    cy_occ      = perf_cy.get("occ", "—")
    cy_adr      = perf_cy.get("adr", "—")
    cy_revpar   = perf_cy.get("revpar", "—")

    es_period   = perf_es.get("period", "—")
    es_occ      = perf_es.get("occ", "—")
    es_adr      = perf_es.get("adr", "—")
    es_revpar   = perf_es.get("revpar", "—")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{subject['name']} — Multi-Comp-Set Cross-Reference Map</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      height: 100vh;
      display: flex; flex-direction: column;
      background: #f5f5f5;
    }}
    .header {{
      background: #1a2744;
      border-bottom: 3px solid #f59e0b;
      padding: 11px 20px;
      display: flex; align-items: center; justify-content: space-between;
      flex-shrink: 0; z-index: 10;
    }}
    .header-left h1 {{ font-size: 17px; font-weight: 700; color: #fff; letter-spacing: 0.3px; }}
    .header-left p {{ font-size: 11px; color: #8fa8d8; margin-top: 2px; }}
    .header-right {{ display: flex; align-items: center; gap: 6px; }}
    .kpi-card {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 6px;
      padding: 7px 14px; text-align: center; min-width: 100px;
    }}
    .kpi-card .k-label {{ font-size: 9px; color: #8fa8d8; text-transform: uppercase; letter-spacing: 0.8px; }}
    .kpi-card .k-value {{ font-size: 17px; font-weight: 700; color: #fff; line-height: 1.2; margin: 1px 0; }}
    .kpi-card .k-index {{ font-size: 9px; color: #7ed87e; }}
    .kpi-sep {{ width: 1px; height: 36px; background: rgba(255,255,255,0.15); }}
    .str-badge {{
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 4px; padding: 4px 10px; font-size: 10px; color: #8fa8d8; margin-left: 10px;
    }}
    .main {{ display: flex; flex: 1; overflow: hidden; }}
    .sidebar {{
      width: 340px; background: #fff;
      border-right: 1px solid #dde3ed;
      display: flex; flex-direction: column; overflow-y: auto;
      flex-shrink: 0; box-shadow: 2px 0 8px rgba(0,0,0,0.06); z-index: 5;
    }}
    .sb-section {{ padding: 14px 14px; border-bottom: 1px solid #eaecf0; }}
    .sb-section h3 {{
      font-size: 10px; text-transform: uppercase; letter-spacing: 0.9px;
      color: #8090b0; margin-bottom: 10px; font-weight: 600;
    }}
    .legend-row {{
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 6px; font-size: 12px; color: #334;
    }}
    .leg-dot {{
      width: 13px; height: 13px; border-radius: 50%;
      border: 2px solid rgba(0,0,0,0.15); flex-shrink: 0;
    }}
    .leg-dot.anchor {{ border: 2px solid #1a2744; box-shadow: 0 0 0 1.5px #fff inset; }}
    .leg-dot.star {{
      width: 16px; height: 16px;
      border-radius: 50%; border: 2px solid #1a2744;
      box-shadow: 0 0 0 1px #fff inset;
    }}
    .leg-count {{ margin-left: auto; font-size: 11px; color: #8090b0; font-weight: 600; }}
    .perf-label {{
      font-size: 10px; color: #8090b0; text-transform: uppercase;
      letter-spacing: 0.5px; margin: 10px 0 4px; font-weight: 600;
    }}
    .perf-label:first-child {{ margin-top: 0; }}
    .perf-grid {{
      display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px;
    }}
    .perf-cell {{
      background: #f5f8ff; border: 1px solid #dce6f7;
      border-radius: 5px; padding: 6px 4px; text-align: center;
    }}
    .perf-cell.comp-cell {{ background: #f8f8f8; border-color: #e0e0e0; }}
    .p-metric {{ font-size: 9px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.4px; }}
    .p-value {{ font-size: 13px; font-weight: 700; color: #1a2744; margin: 1px 0; }}
    .p-index {{ font-size: 9px; color: #2d8a2d; font-weight: 600; }}
    .perf-cell.comp-cell .p-value {{ color: #444; }}
    .set-section {{ margin-bottom: 14px; }}
    .set-header {{
      display: flex; align-items: center; gap: 8px;
      padding: 6px 8px; border-radius: 5px; color: #fff;
      font-size: 12px; font-weight: 600; margin-bottom: 6px;
    }}
    .set-header .ct {{ margin-left: auto; opacity: 0.85; font-weight: 500; }}
    .set-perf-mini {{
      font-size: 11px; color: #556; margin-bottom: 6px;
      padding: 0 4px; line-height: 1.45;
    }}
    .set-perf-mini b {{ color: #1a2744; }}
    .hotel-item {{
      display: flex; align-items: flex-start; gap: 9px;
      padding: 7px 4px; border-radius: 5px;
      cursor: pointer; transition: background 0.15s;
      border-bottom: 1px solid #f0f2f5;
    }}
    .hotel-item:last-child {{ border-bottom: none; }}
    .hotel-item:hover {{ background: #f0f5ff; }}
    .h-pin {{
      width: 22px; height: 22px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 10px; font-weight: 700; color: #fff;
      flex-shrink: 0; margin-top: 1px;
      border: 2px solid transparent;
    }}
    .h-pin.anchor-pin {{ border-color: #1a2744; }}
    .h-info h4 {{ font-size: 12px; font-weight: 600; color: #1a2744; line-height: 1.3; }}
    .h-info .h-meta {{ font-size: 10px; color: #7080a0; margin-top: 1px; }}
    .h-badges {{ margin-top: 3px; display: flex; flex-wrap: wrap; gap: 3px; }}
    .h-badge {{
      display: inline-block; border-radius: 3px;
      padding: 1px 5px; font-size: 9px; font-weight: 600;
      color: #fff;
    }}
    .h-badge.gray {{ background: #e8f0fe; color: #1a56c4; border: 1px solid #c5d5f5; }}
    .h-badge.anchor {{ background: #1a2744; }}
    .sidebar-footer {{
      padding: 8px 14px; font-size: 10px; color: #aabbd0;
      border-top: 1px solid #eaecf0; margin-top: auto;
    }}
    #map {{ flex: 1; }}
    .gm-iw {{
      font-family: 'Segoe UI', Arial, sans-serif;
      min-width: 240px; max-width: 290px;
    }}
    .gm-iw-title {{
      font-size: 14px; font-weight: 700; color: #1a2744;
      line-height: 1.3; margin-bottom: 4px;
    }}
    .gm-iw-meta {{ font-size: 11px; color: #556; margin-bottom: 3px; }}
    .gm-iw-badges {{ margin: 6px 0; display: flex; flex-wrap: wrap; gap: 4px; }}
    .gm-iw-badge {{
      display: inline-block; border-radius: 3px;
      padding: 2px 6px; font-size: 10px; font-weight: 600;
      color: #fff;
    }}
    .gm-iw-badge.subject {{ background: #f59e0b; color: #1a2744; }}
    .gm-iw-badge.anchor {{ background: #1a2744; }}
    .gm-iw-badge.gray {{ background: #e8f0fe; color: #1a56c4; border: 1px solid #c5d5f5; }}
    .gm-iw-divider {{ border: none; border-top: 1px solid #eaecf0; margin: 8px 0; }}
    .gm-iw-perf {{
      display: grid; grid-template-columns: 1fr 1fr 1fr 1fr;
      gap: 4px; margin-top: 4px;
    }}
    .gm-iw-perf .cell {{
      background: #f8f9fb; border: 1px solid #eaecf0;
      border-radius: 3px; padding: 4px 2px; text-align: center;
    }}
    .gm-iw-perf .lbl {{ font-size: 8px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.4px; }}
    .gm-iw-perf .val {{ font-size: 11px; font-weight: 700; color: #1a2744; margin-top: 1px; }}
    .gm-iw-year-label {{
      font-size: 9px; color: #8090b0; text-transform: uppercase;
      letter-spacing: 0.6px; margin: 5px 0 2px; font-weight: 600;
    }}
    .gm-iw-masked {{ font-size: 10px; color: #aabbd0; margin-top: 6px; font-style: italic; }}
    .gm-iw-str {{ font-size: 10px; color: #c0c8da; margin-top: 4px; }}
    .gm-iw-note {{ font-size: 9px; color: #aabbd0; margin-top: 5px; }}

    /* Filter / visibility controls */
    .legend-row.filter-row {{
      display: flex; align-items: center; gap: 8px;
      padding: 4px 4px; border-radius: 4px;
      cursor: pointer; user-select: none;
      transition: background 0.12s;
    }}
    .legend-row.filter-row:hover {{ background: #f0f5ff; }}
    .legend-row.filter-row input[type="checkbox"] {{
      width: 13px; height: 13px;
      accent-color: #1a2744;
      cursor: pointer; flex-shrink: 0;
    }}
    .legend-row.filter-row .label-text {{ flex: 1; font-size: 12px; }}
    .legend-row.filter-row.disabled .label-text,
    .legend-row.filter-row.disabled .leg-count {{
      color: #b8bfcc; text-decoration: line-through;
    }}
    .solo-btn {{
      font-size: 9px; font-weight: 700; color: #fff;
      background: #1a2744;
      border: none; border-radius: 3px;
      padding: 2px 6px; cursor: pointer;
      letter-spacing: 0.5px; text-transform: uppercase;
      transition: background 0.12s;
    }}
    .solo-btn:hover {{ background: #2956b2; }}
    .reset-link {{
      display: inline-block; margin-left: auto;
      font-size: 10px; color: #2956b2;
      cursor: pointer; text-decoration: underline;
      font-weight: 600;
    }}
    .reset-link:hover {{ color: #1a2744; }}
    .legend-actions {{
      display: flex; align-items: center; gap: 8px;
      margin-top: 8px; padding-top: 6px;
      border-top: 1px solid #eaecf0;
    }}
    .hotel-item .hide-btn {{
      width: 18px; height: 18px;
      border-radius: 50%; border: none;
      background: transparent; color: #b8bfcc;
      cursor: pointer; font-size: 14px; line-height: 1;
      display: flex; align-items: center; justify-content: center;
      transition: all 0.12s;
      flex-shrink: 0;
    }}
    .hotel-item:hover .hide-btn {{ color: #7080a0; }}
    .hotel-item .hide-btn:hover {{ background: #fde8e8; color: #c62828; }}
    .hotel-item.hidden-asset {{ opacity: 0.45; }}
    .hotel-item.hidden-asset .h-info h4 {{ text-decoration: line-through; }}
    .hotel-item.hidden-asset .hide-btn {{ color: #c62828; }}
    .hotel-item.hidden-asset .hide-btn::before {{ content: "↻"; }}
    .hotel-item:not(.hidden-asset) .hide-btn::before {{ content: "×"; }}
    .set-section.set-disabled .hotel-item {{ opacity: 0.4; }}
    .set-section.set-disabled .set-header {{ opacity: 0.5; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>{subject['name']} &mdash; Multi-Comp-Set Cross-Reference Map</h1>
    <p>{subject['address']}, {subject['city_state']} {subject['zip']}
       &nbsp;&middot;&nbsp; Subject (gold star) plotted across 4 reference comp sets
       &nbsp;&middot;&nbsp; {len(hotels)} unique comp hotels</p>
  </div>
  <div class="header-right">
    <div class="kpi-card">
      <div class="k-label">{subj_str_name.split(',')[0][:18]} OCC (R12)</div>
      <div class="k-value">{marg_subj_occ}</div>
      <div class="k-index">MPI {marg_mpi}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">ADR</div>
      <div class="k-value">{marg_subj_adr}</div>
      <div class="k-index">ARI {marg_ari}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">RevPAR</div>
      <div class="k-value">{marg_subj_revpar}</div>
      <div class="k-index">RGI {marg_rgi}</div>
    </div>
    <div class="str-badge">Margaritaville STR R12 &middot; Dec 2025</div>
  </div>
</div>

<div class="main">
  <div class="sidebar">

    <div class="sb-section">
      <h3>Legend &amp; Filters</h3>
      <div class="legend-row"><div class="leg-dot star" style="background:{SUBJECT_COLOR};"></div> Subject &mdash; Marriott Vacation Club <span class="leg-count">★</span></div>
"""

    for s in COMP_SETS:
        sid = s["id"]
        html += (
            f'      <div class="legend-row filter-row" data-set-toggle="{sid}">\n'
            f'        <input type="checkbox" id="cb-{sid}" data-set-cb="{sid}" checked />\n'
            f'        <div class="leg-dot" style="background:{s["color"]};"></div>\n'
            f'        <span class="label-text">{s["label"]}</span>\n'
            f'        <span class="leg-count" data-set-count="{sid}">{set_counts[sid]}</span>\n'
            f'        <button class="solo-btn" data-set-solo="{sid}" title="Show only this set">Solo</button>\n'
            f'      </div>\n'
        )

    html += f"""      <div class="legend-row" style="margin-top:8px;"><div class="leg-dot anchor" style="background:#aaa;"></div> Comp set <i>anchor</i> (subject of that set)</div>
      <div class="legend-actions">
        <span style="font-size:10px; color:#8090b0;">Click a row to toggle. Click × on any hotel to hide it.</span>
        <span class="reset-link" id="reset-all">Show All</span>
      </div>
    </div>

    <div class="sb-section">
      <h3>Margaritaville STR &mdash; R12 Performance</h3>
      <div class="perf-label">{subj_str_name} (STR Anchor)</div>
      <div class="perf-grid">
        <div class="perf-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{marg_subj_occ}</div>
          <div class="p-index">MPI {marg_mpi}</div>
        </div>
        <div class="perf-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{marg_subj_adr}</div>
          <div class="p-index">ARI {marg_ari}</div>
        </div>
        <div class="perf-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{marg_subj_revpar}</div>
          <div class="p-index">RGI {marg_rgi}</div>
        </div>
      </div>
      <div class="perf-label">Margaritaville Comp Set (Aggregate)</div>
      <div class="perf-grid">
        <div class="perf-cell comp-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{marg_comp_occ}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{marg_comp_adr}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{marg_comp_revpar}</div>
        </div>
      </div>
    </div>

    <div class="sb-section">
      <h3>Courtyard Herald Square &mdash; Composite R12</h3>
      <div style="font-size:10px; color:#8090b0; margin-bottom:6px;">{cy_period}</div>
      <div class="perf-grid">
        <div class="perf-cell comp-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{cy_occ}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{cy_adr}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{cy_revpar}</div>
        </div>
      </div>
    </div>

    <div class="sb-section">
      <h3>Eastdil &mdash; Composite R12</h3>
      <div style="font-size:10px; color:#8090b0; margin-bottom:6px;">{es_period}</div>
      <div class="perf-grid">
        <div class="perf-cell comp-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{es_occ}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{es_adr}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{es_revpar}</div>
        </div>
      </div>
    </div>

    <div class="sb-section" style="flex:1; border-bottom:none;">
      <h3>Properties &mdash; Grouped by Comp Set</h3>
      <div id="hotel-list"></div>
    </div>

    <div class="sidebar-footer">
      Source: STR Monthly STAR, CoStar STR Trend (Part Report / ES Set / CY HSq), and<br/>
      960 Sixth Ave Topline (2024+2025) &middot; Compiled May 2026
    </div>
  </div>

  <div id="map"></div>
</div>

<script>
  {hotels_js}
  {sets_js}
  const SUBJECT = {{
    name: {json.dumps(subject['name'])},
    address: {json.dumps(subject['address'])},
    cityState: {json.dumps(subject['city_state'])},
    zip: {json.dumps(subject['zip'])},
    lat: {subject['lat']}, lng: {subject['lng']},
    color: {json.dumps(SUBJECT_COLOR)},
  }};

  let map, infoWindow;
  const markersByName = {{}};
  const sidebarItemsByName = {{}};
  const sectionsBySetId = {{}};

  // Visibility state
  const state = {{
    setVisible: Object.fromEntries(Object.keys(COMP_SETS).map(sid => [sid, true])),
    hiddenHotels: new Set(),  // by hotel name
  }};

  function visibleMembershipsFor(h) {{
    return h.memberships.filter(sid => state.setVisible[sid]);
  }}

  function effectiveSetFor(h) {{
    // Returns the highest-priority membership (first in h.memberships, already sorted by priority)
    // that is currently enabled. Returns null if none.
    const visible = visibleMembershipsFor(h);
    return visible.length ? visible[0] : null;
  }}

  function isHotelVisible(h) {{
    if (state.hiddenHotels.has(h.name)) return false;
    return effectiveSetFor(h) !== null;
  }}

  function pinSvg(color, label, isAnchor, isStar) {{
    const stroke = isAnchor ? '#1a2744' : 'white';
    const sw = isAnchor ? 2.5 : 1.5;
    const w = isStar ? 44 : 36;
    const h = isStar ? 54 : 44;
    const fontSize = isStar ? 18 : (label.length > 1 ? 10 : 13);
    return {{
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="${{w}}" height="${{h}}" viewBox="0 0 38 46">
          <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
          <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
                fill="${{color}}" stroke="${{stroke}}" stroke-width="${{sw}}" filter="url(#s)"/>
          <text x="19" y="22" text-anchor="middle" dominant-baseline="middle"
                font-family="Arial,sans-serif" font-size="${{fontSize}}"
                font-weight="bold" fill="white">${{label}}</text>
        </svg>`),
      scaledSize: new google.maps.Size(w, h),
      anchor: new google.maps.Point(w/2, h - 2)
    }};
  }}

  function badgesHtml(memberships, anchorFor, isSubject) {{
    let parts = [];
    if (isSubject) parts.push('<span class="gm-iw-badge subject">Subject Property</span>');
    memberships.forEach(sid => {{
      const s = COMP_SETS[sid];
      const anchor = anchorFor.includes(sid);
      parts.push(`<span class="gm-iw-badge" style="background:${{s.color}}">${{s.short}}${{anchor ? ' ★ anchor' : ''}}</span>`);
    }});
    return `<div class="gm-iw-badges">${{parts.join('')}}</div>`;
  }}

  function toplinePerfHtml(p) {{
    if (!p) return '';
    return `
      <hr class="gm-iw-divider"/>
      <div class="gm-iw-year-label">2024 (${{p.notes_2024 || 'Actual'}})</div>
      <div class="gm-iw-perf">
        <div class="cell"><div class="lbl">Occ</div><div class="val">${{p.occ_2024}}</div></div>
        <div class="cell"><div class="lbl">ADR</div><div class="val">${{p.adr_2024}}</div></div>
        <div class="cell"><div class="lbl">RevPAR</div><div class="val">${{p.revpar_2024}}</div></div>
        <div class="cell"><div class="lbl">RPI</div><div class="val">${{p.rpi_2024}}</div></div>
      </div>
      <div class="gm-iw-year-label">2025 (${{p.notes_2025 || 'Trended'}})</div>
      <div class="gm-iw-perf">
        <div class="cell"><div class="lbl">Occ</div><div class="val">${{p.occ_2025}}</div></div>
        <div class="cell"><div class="lbl">ADR</div><div class="val">${{p.adr_2025}}</div></div>
        <div class="cell"><div class="lbl">RevPAR</div><div class="val">${{p.revpar_2025}}</div></div>
        <div class="cell"><div class="lbl">RPI</div><div class="val">${{p.rpi_2025}}</div></div>
      </div>`;
  }}

  function subjectIwContent() {{
    return `
      <div class="gm-iw">
        <div class="gm-iw-title">${{SUBJECT.name}}</div>
        ${{badgesHtml([], [], true)}}
        <div class="gm-iw-meta">${{SUBJECT.address}}, ${{SUBJECT.cityState}} ${{SUBJECT.zip}}</div>
        <div class="gm-iw-note">Subject property &mdash; map center / star marker</div>
      </div>`;
  }}

  function hotelIwContent(h) {{
    const setLabels = h.memberships.map(sid => COMP_SETS[sid].label).join(', ');
    let perf;
    if (h.toplinePerf) {{
      perf = toplinePerfHtml(h.toplinePerf);
    }} else if (h.memberships.includes('margaritaville')) {{
      perf = '<div class="gm-iw-masked">Individual perf masked per STR policy &mdash; see Margaritaville aggregate in sidebar</div>';
    }} else if (h.memberships.includes('cy_hsq') || h.memberships.includes('eastdil')) {{
      perf = '<div class="gm-iw-masked">Individual perf masked &mdash; see composite aggregate in sidebar</div>';
    }} else {{
      perf = '';
    }}

    const roomTxt = h.rooms > 0 ? `${{h.rooms.toLocaleString()}} keys` : '— keys';
    const toplineNoTxt = h.toplineNo != null ? ` &middot; Topline #${{h.toplineNo}}` : '';

    return `
      <div class="gm-iw">
        <div class="gm-iw-title">${{h.name}}</div>
        ${{badgesHtml(h.memberships, h.anchorFor, false)}}
        <div class="gm-iw-meta">${{h.cityState}}${{h.zip ? ' ' + h.zip : ''}}</div>
        <div class="gm-iw-meta">${{roomTxt}}${{toplineNoTxt}}</div>
        ${{h.strId ? `<div class="gm-iw-str">STR ID: ${{h.strId}}</div>` : ''}}
        ${{perf}}
      </div>`;
  }}

  function initMap() {{
    map = new google.maps.Map(document.getElementById('map'), {{
      center: {{ lat: {avg_lat}, lng: {avg_lng} }},
      zoom: 15,
      mapTypeControl: true,
      mapTypeControlOptions: {{
        style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
        position: google.maps.ControlPosition.TOP_RIGHT
      }},
      streetViewControl: true,
      fullscreenControl: true,
      styles: [
        {{ featureType: "poi.business", stylers: [{{ visibility: "off" }}] }},
        {{ featureType: "transit", stylers: [{{ visibility: "simplified" }}] }}
      ]
    }});

    infoWindow = new google.maps.InfoWindow({{ maxWidth: 320 }});

    // Subject circle highlight
    new google.maps.Circle({{
      map,
      center: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
      radius: 600,
      strokeColor: SUBJECT.color,
      strokeOpacity: 0.5,
      strokeWeight: 1.5,
      fillColor: SUBJECT.color,
      fillOpacity: 0.06,
      clickable: false
    }});

    // Subject star marker
    const subjMarker = new google.maps.Marker({{
      position: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
      map,
      icon: pinSvg(SUBJECT.color, '★', true, true),
      title: SUBJECT.name,
      zIndex: 1000
    }});
    subjMarker.addListener('click', () => {{
      infoWindow.setContent(subjectIwContent());
      infoWindow.open(map, subjMarker);
    }});

    const bounds = new google.maps.LatLngBounds();
    bounds.extend({{ lat: SUBJECT.lat, lng: SUBJECT.lng }});

    HOTELS.forEach((h) => {{
      const label = h.toplineNo != null ? String(h.toplineNo) : '';
      const marker = new google.maps.Marker({{
        position: {{ lat: h.lat, lng: h.lng }},
        map,
        icon: pinSvg(h.color, label, h.isAnchor, false),
        title: h.name,
        zIndex: h.isAnchor ? 50 : 10
      }});
      marker.addListener('click', () => {{
        infoWindow.setContent(hotelIwContent(h));
        infoWindow.open(map, marker);
      }});
      bounds.extend({{ lat: h.lat, lng: h.lng }});
      markersByName[h.name] = marker;
    }});

    // Build sidebar grouped by comp set
    const listEl = document.getElementById('hotel-list');
    Object.keys(COMP_SETS).forEach(sid => {{
      const s = COMP_SETS[sid];
      const members = HOTELS.filter(h => h.memberships.includes(sid));
      if (members.length === 0) return;
      members.sort((a, b) => {{
        const aA = a.anchorFor.includes(sid) ? 0 : 1;
        const bA = b.anchorFor.includes(sid) ? 0 : 1;
        if (aA !== bA) return aA - bA;
        if (a.toplineNo != null && b.toplineNo != null) return a.toplineNo - b.toplineNo;
        return a.name.localeCompare(b.name);
      }});

      const section = document.createElement('div');
      section.className = 'set-section';
      section.dataset.setId = sid;
      section.innerHTML = `
        <div class="set-header" style="background:${{s.color}}">
          ${{s.label}} <span class="ct">${{members.length}}</span>
        </div>`;

      members.forEach(h => {{
        const item = document.createElement('div');
        item.className = 'hotel-item';
        const isAnchor = h.anchorFor.includes(sid);
        const label = h.toplineNo != null ? String(h.toplineNo) : (isAnchor ? '★' : '•');
        const otherBadges = h.memberships
          .filter(m => m !== sid)
          .map(m => `<span class="h-badge" style="background:${{COMP_SETS[m].color}}">${{COMP_SETS[m].short}}</span>`)
          .join('');
        const anchorBadge = isAnchor ? '<span class="h-badge anchor">★ Anchor</span>' : '';
        const roomTxt = h.rooms > 0 ? `${{h.rooms.toLocaleString()}} keys` : '';
        item.innerHTML = `
          <div class="h-pin ${{isAnchor ? 'anchor-pin' : ''}}" style="background:${{h.color}}">${{label}}</div>
          <div class="h-info">
            <h4>${{h.name}}</h4>
            <div class="h-meta">${{roomTxt}}</div>
            <div class="h-badges">${{anchorBadge}}${{otherBadges}}</div>
          </div>
          <button class="hide-btn" title="Hide / show this hotel"></button>`;

        // Main click → pan + open info window
        item.addEventListener('click', (e) => {{
          if (e.target.classList.contains('hide-btn')) return;
          if (!isHotelVisible(h)) return;  // ignore if hotel currently hidden
          map.panTo({{ lat: h.lat, lng: h.lng }});
          map.setZoom(17);
          const marker = markersByName[h.name];
          infoWindow.setContent(hotelIwContent(h));
          infoWindow.open(map, marker);
        }});

        // Hide button → toggle individual visibility
        item.querySelector('.hide-btn').addEventListener('click', (e) => {{
          e.stopPropagation();
          if (state.hiddenHotels.has(h.name)) {{
            state.hiddenHotels.delete(h.name);
          }} else {{
            state.hiddenHotels.add(h.name);
          }}
          applyVisibility();
        }});

        // Register this sidebar item — multiple rows per hotel possible (one per set)
        if (!sidebarItemsByName[h.name]) sidebarItemsByName[h.name] = [];
        sidebarItemsByName[h.name].push(item);

        section.appendChild(item);
      }});

      sectionsBySetId[sid] = section;
      listEl.appendChild(section);
    }});

    // Wire up the legend filter controls
    document.querySelectorAll('[data-set-toggle]').forEach(row => {{
      const sid = row.dataset.setToggle;
      const cb = row.querySelector('input[type="checkbox"]');
      const soloBtn = row.querySelector('.solo-btn');
      // Click anywhere on the row toggles the checkbox (except the solo button)
      row.addEventListener('click', (e) => {{
        if (e.target === cb || e.target === soloBtn) return;
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      }});
      cb.addEventListener('change', () => {{
        state.setVisible[sid] = cb.checked;
        applyVisibility();
      }});
      soloBtn.addEventListener('click', (e) => {{
        e.stopPropagation();
        Object.keys(state.setVisible).forEach(k => state.setVisible[k] = (k === sid));
        document.querySelectorAll('[data-set-cb]').forEach(c => {{
          c.checked = state.setVisible[c.dataset.setCb];
        }});
        applyVisibility();
      }});
    }});

    document.getElementById('reset-all').addEventListener('click', () => {{
      Object.keys(state.setVisible).forEach(k => state.setVisible[k] = true);
      state.hiddenHotels.clear();
      document.querySelectorAll('[data-set-cb]').forEach(c => c.checked = true);
      applyVisibility();
    }});

    applyVisibility();
    map.fitBounds(bounds, {{ top: 60, right: 60, bottom: 60, left: 60 }});
  }}

  function applyVisibility() {{
    // Update markers
    HOTELS.forEach(h => {{
      const marker = markersByName[h.name];
      if (!marker) return;
      if (!isHotelVisible(h)) {{
        marker.setMap(null);
        return;
      }}
      const effSid = effectiveSetFor(h);
      const color = COMP_SETS[effSid].color;
      const label = h.toplineNo != null ? String(h.toplineNo) : '';
      marker.setIcon(pinSvg(color, label, h.isAnchor, false));
      marker.setMap(map);
    }});

    // Update sidebar — dim set sections that are toggled off, hide individually-hidden items
    Object.keys(sectionsBySetId).forEach(sid => {{
      const section = sectionsBySetId[sid];
      if (state.setVisible[sid]) {{
        section.classList.remove('set-disabled');
      }} else {{
        section.classList.add('set-disabled');
      }}
    }});

    // Update each hotel item's hidden state + recolor its pin chip to match current effective color
    Object.keys(sidebarItemsByName).forEach(name => {{
      const h = HOTELS.find(x => x.name === name);
      if (!h) return;
      const isHidden = state.hiddenHotels.has(name);
      const effSid = effectiveSetFor(h);
      const color = effSid ? COMP_SETS[effSid].color : '#cccccc';
      sidebarItemsByName[name].forEach(item => {{
        item.classList.toggle('hidden-asset', isHidden);
        const pinChip = item.querySelector('.h-pin');
        if (pinChip) pinChip.style.background = color;
      }});
    }});

    // Update the legend row visual state
    document.querySelectorAll('[data-set-toggle]').forEach(row => {{
      const sid = row.dataset.setToggle;
      row.classList.toggle('disabled', !state.setVisible[sid]);
    }});

    // Close info window if its hotel is now hidden
    if (infoWindow && infoWindow.getMap()) {{
      // (Simplest behavior — leave existing IW open; user can re-click to dismiss)
    }}
  }}
</script>

<script
  src="https://maps.googleapis.com/maps/api/js?key={API_KEY}&callback=initMap"
  async defer>
</script>

</body>
</html>"""
    return html


# ── Root index update ──

def update_root_index(slug, hotel_name, city_state, num_comps):
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    if f'href="./{slug}/"' in content:
        print(f"  {hotel_name} already in root index.html")
        return
    new_entry = f"""      <li>
        <a href="./{slug}/">
          {hotel_name} &mdash; {city_state}
          <div class="meta">Multi-comp-set cross-reference &middot; {num_comps} unique comps across 4 sets</div>
        </a>
      </li>"""
    content = content.replace("      <!-- MAPS_END -->", f"{new_entry}\n      <!-- MAPS_END -->")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Added {hotel_name} to root index.html")


# ── Deploy helpers (mirror generate_str_map.py) ──

def _git(*args, check=True):
    return subprocess.run(["git"] + list(args), cwd=REPO_DIR, check=check,
                          capture_output=True, text=True)

def _commit_and_push(commit_message):
    _git("add", ".")
    staged = _git("diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        print("  Nothing to commit.")
        return False
    _git("commit", "-m", commit_message)
    _git("push", "origin", "main")
    print(f"  Committed + pushed: {commit_message}")
    return True

def verify_deploy(urls, timeout_seconds=180):
    local_head = _git("rev-parse", "HEAD").stdout.strip()
    short = local_head[:7]
    print(f"\nVerifying deploy for HEAD {short}...")
    try:
        subprocess.run(["gh", "workflow", "run", WORKFLOW_NAME,
                        "--repo", REPO_SLUG, "--ref", "main"],
                       check=True, capture_output=True, text=True)
    except Exception as e:
        print(f"  WARNING: workflow dispatch issue: {e}")
    start = time.time()
    ok = False
    last = ""
    while time.time() - start < timeout_seconds:
        try:
            r = subprocess.run(
                ["gh", "run", "list", "--repo", REPO_SLUG, "--workflow", WORKFLOW_NAME,
                 "--limit", "10", "--json", "status,conclusion,headSha,databaseId"],
                capture_output=True, text=True, check=True,
            )
            runs = json.loads(r.stdout)
            matches = [x for x in runs if x["headSha"] == local_head]
            if matches:
                summary = ", ".join(f"{x['databaseId']}={x['status']}/{x['conclusion']}" for x in matches)
                if summary != last:
                    print(f"  {summary}")
                    last = summary
                if any(x["status"] == "completed" and x["conclusion"] == "success" for x in matches):
                    ok = True
                    break
                if all(x["status"] == "completed" for x in matches):
                    break
        except Exception as e:
            print(f"  (poll error: {e})")
        time.sleep(5)
    if not ok:
        print(f"  Deploy did not complete successfully within {timeout_seconds}s.")
        return False
    time.sleep(4)
    print("URL health check:")
    all_ok = True
    for u in urls:
        try:
            code = requests.head(u, allow_redirects=True, timeout=10).status_code
        except Exception as e:
            code = f"err: {e}"
        ok2 = code == 200
        print(f"  [{'OK' if ok2 else 'FAIL'}] {code}  {u}")
        if not ok2: all_ok = False
    return all_ok


def main():
    ap = argparse.ArgumentParser(description="Generate MVC NYC multi-comp-set map")
    ap.add_argument("--deploy", action="store_true")
    args = ap.parse_args()

    print("\n" + "=" * 60)
    print("MVC NYC Multi-Comp-Set Map Generator")
    print("=" * 60)

    print("\nParsing Margaritaville STR set...")
    marg_hotels, marg_perf = parse_margaritaville_str()
    print(f"  {len(marg_hotels)} hotels (anchor: {marg_hotels[0]['name']})")
    print(f"  R12 perf: Subj Occ {marg_perf.get('subj_occ')}, ADR {marg_perf.get('subj_adr')}, RevPAR {marg_perf.get('subj_revpar')}")

    print("\nParsing Courtyard Herald Square set...")
    cy_hotels, cy_perf = parse_cy_herald_square()
    print(f"  {len(cy_hotels)} hotels (anchor: {cy_hotels[0]['name']})")
    print(f"  R12 perf: Occ {cy_perf['occ']}, ADR {cy_perf['adr']}, RevPAR {cy_perf['revpar']}")

    print("\nParsing Eastdil set...")
    es_hotels, es_perf = parse_eastdil()
    print(f"  {len(es_hotels)} hotels (no explicit anchor)")
    print(f"  R12 perf: Occ {es_perf['occ']}, ADR {es_perf['adr']}, RevPAR {es_perf['revpar']}")

    print("\nParsing 960 Sixth Ave Topline (numbered only)...")
    top_hotels, top_perf = parse_topline()
    print(f"  {len(top_hotels)} numbered comps")

    print("\nMerging + deduping across all sets...")
    merged = merge_hotels([marg_hotels, cy_hotels, es_hotels, top_hotels])
    print(f"  {len(merged)} unique hotels total")
    multis = [h for h in merged if len(h["memberships"]) > 1]
    print(f"  {len(multis)} hotels appear in multiple sets:")
    for h in multis:
        print(f"    - {h['name']}: {', '.join(SET_BY_ID[s]['short'] for s in h['memberships'])}")

    # Geocode (also geocodes subject)
    subj = dict(SUBJECT)
    geocode_all(merged, subj)

    print("Rendering HTML...")
    html = render_html(merged, subj, marg_perf, cy_perf, es_perf, top_perf)
    out_dir = os.path.join(REPO_DIR, OUTPUT_SLUG)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {out_path}")

    print("\nUpdating root index...")
    update_root_index(OUTPUT_SLUG, SUBJECT["name"], SUBJECT["city_state"], len(merged))

    print(f"\n{'=' * 60}")
    print(f"Map generated. Open: file:///{out_path.replace(os.sep, '/')}")
    print(f"{'=' * 60}")

    if not args.deploy:
        print(f"\nTo deploy: python generate_mvc_nyc_map.py --deploy")
        print(f"Will be live at: {PAGES_BASE_URL}/{OUTPUT_SLUG}/")
        return

    print("\nDeploying to GitHub Pages...")
    _commit_and_push(f"Add Marriott Vacation Club NYC multi-comp-set cross-reference map")
    url = f"{PAGES_BASE_URL}/{OUTPUT_SLUG}/"
    ok = verify_deploy([url])
    print("\n" + ("DEPLOY VERIFIED [OK]" if ok else "DEPLOY INCOMPLETE — see warnings"))
    print(f"  {url}")
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
