#!/usr/bin/env python3
"""
AKA White House — Multi-Comp-Set Cross-Reference Map.

Subject: AKA White House, 1710 H St NW, Washington DC (gold star).
Plotted on top of 7 reference comp sets:

  1. Original AKA WH STR comp set       (from existing aka-white-house map)
  2. AKA WH Luxury                       (Participation + HospitalityDataGrid)
  3. AKA WH Large Branded                (Participation + HospitalityDataGrid)
  4. AKA WH Branded Small                (Participation + HospitalityDataGrid)
  5. AKA WH Independent                  (Participation + HospitalityDataGrid)
  6. Capital Hilton STR comp set         (Monthly STAR — Cap Hilton subject)
  7. Viceroy Washington DC STR comp set  (Monthly STAR — Viceroy DC subject)

Rules:
  - Each comp set has its own color.
  - Hotels in multiple sets are plotted ONCE; the color reflects the highest-priority
    set they belong to, and ALL memberships are shown as badges.
  - Subject (AKA White House) is always rendered as a gold star, regardless of any
    set membership.
  - Comp-set anchors (the subject of each STR pull, where applicable) get an
    outlined "anchor" pin in their set's color.
  - Per-set performance is surfaced where the data permits.

Usage:
    py -3 generate_aka_wh_multi_map.py            # generate only
    py -3 generate_aka_wh_multi_map.py --deploy   # generate + commit + push + verify
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time

import pandas as pd
import requests

# ── Configuration ──
REPO_DIR = r"C:\Users\acarr\OneDrive\Documents\Claude\Projects\str-comp-maps"
DROP_DIR = r"C:\Users\acarr\OneDrive\Documents\STR Drops\Additional AKA Sets\STR"
GEOCACHE_PATH = os.path.join(REPO_DIR, "geocache.json")
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
API_KEY = "AIzaSyCTAmcCrmL2Z-SerlTKHoG3xPQaGcvmKcU"
REPO_SLUG = "acarras92/str-comp-maps"
PAGES_BASE_URL = "https://acarras92.github.io/str-comp-maps"
WORKFLOW_NAME = "Deploy to GitHub Pages"

OUTPUT_SLUG = "aka-white-house"

SUBJECT = {
    "name": "AKA White House",
    "address": "1710 H St NW",
    "city_state": "Washington, DC",
    "zip": "20006",
    "rooms": 141,
    "str_id": "57930",
    # carry-over R12 perf from prior single-set map (R12 ending Dec 2025)
    "occ": "80.5%",
    "adr": "$302.9",
    "revpar": "$244.0",
    "mpi": "106.8",
    "ari": "119.6",
    "rgi": "127.8",
}
SUBJECT_LAT, SUBJECT_LNG = 38.9000628, -77.0404004
SUBJECT_COLOR = "#f59e0b"  # gold

# Comp sets — priority order = membership precedence for the dedup pin color
COMP_SETS = [
    {
        "id": "aka_orig",
        "label": "Original AKA WH STR Set",
        "short": "AKA Original",
        "color": "#d32f2f",  # red
        "priority": 1,
    },
    {
        "id": "aka_lux",
        "label": "AKA WH — Luxury",
        "short": "Luxury",
        "color": "#7b1fa2",  # purple
        "priority": 2,
    },
    {
        "id": "aka_largebr",
        "label": "AKA WH — Large Branded",
        "short": "Large Branded",
        "color": "#1565c0",  # navy
        "priority": 3,
    },
    {
        "id": "aka_smallbr",
        "label": "AKA WH — Branded Small",
        "short": "Branded Small",
        "color": "#2e7d32",  # green
        "priority": 4,
    },
    {
        "id": "aka_indep",
        "label": "AKA WH — Independent",
        "short": "Independent",
        "color": "#c2185b",  # magenta
        "priority": 5,
    },
    {
        "id": "cap_hilton",
        "label": "Capital Hilton STR Set",
        "short": "Cap Hilton",
        "color": "#00897b",  # teal
        "priority": 6,
    },
    {
        "id": "viceroy_dc",
        "label": "Viceroy Washington DC STR Set",
        "short": "Viceroy DC",
        "color": "#6d4c41",  # brown
        "priority": 7,
    },
    # Submarket supply-change layers (from Capital Hilton new-supply map).
    # Not comp sets — no R12 perf; rendered as distinct toggleable layers.
    {
        "id": "new_supply",
        "label": "New Supply / Pipeline",
        "short": "Pipeline",
        "color": "#e67e22",  # orange
        "priority": 8,
        "kind": "supply",
        "group": "caphilton",
        "glyph": "+",
        "supply": "add",
    },
    {
        "id": "former_supply",
        "label": "Former Supply (Closed)",
        "short": "Former Supply",
        "color": "#757575",  # grey
        "priority": 9,
        "kind": "supply",
        "group": "caphilton",
        "glyph": "✕",  # ✕
        "supply": "remove",
    },
    # DC market raw new-supply layers (CBRE Market Overview, 06/22/26).
    # Bucketed by development phase; default OFF so the base map loads unchanged.
    {
        "id": "dc_recent",
        "label": "Recently Completed (2019–25)",
        "short": "DC Completed",
        "color": "#0097a7",  # dark cyan
        "priority": 10,
        "kind": "supply",
        "group": "dc_supply",
        "glyph": "✓",  # ✓
        "supply": "add",
        "default_off": True,
    },
    {
        "id": "dc_pipeline",
        "label": "Pipeline / Under Constr. (2026–27)",
        "short": "DC Pipeline",
        "color": "#3949ab",  # indigo
        "priority": 11,
        "kind": "supply",
        "group": "dc_supply",
        "glyph": "+",
        "supply": "add",
        "default_off": True,
    },
    {
        "id": "dc_reduction",
        "label": "Supply Reduction (Closures)",
        "short": "DC Closure",
        "color": "#546e7a",  # slate
        "priority": 12,
        "kind": "supply",
        "group": "dc_supply",
        "glyph": "✕",  # ✕
        "supply": "remove",
        "default_off": True,
    },
    {
        "id": "dc_planning",
        "label": "2028+ Early Planning",
        "short": "DC 2028+",
        "color": "#7e57c2",  # violet
        "priority": 13,
        "kind": "supply",
        "group": "dc_supply",
        "glyph": "◇",  # ◇
        "supply": "add",
        "default_off": True,
    },
]
SET_BY_ID = {s["id"]: s for s in COMP_SETS}
COMP_ONLY_SETS = [s for s in COMP_SETS if s.get("kind", "comp") == "comp"]
SUPPLY_SETS = [s for s in COMP_SETS if s.get("kind") == "supply"]


# Source files
F_AKA_LUX_PART   = os.path.join(DROP_DIR, "AKA_WH_Luxury_Participation.xlsx")
F_AKA_LUX_DATA   = os.path.join(DROP_DIR, "AKA_WH_Luxury_Data.xlsx")
F_AKA_LB_PART    = os.path.join(DROP_DIR, "AKA_WH_LargeBranded_Participation.xlsx")
F_AKA_LB_DATA    = os.path.join(DROP_DIR, "AKA_WH_LargeBranded_Data.xlsx")
F_AKA_BS_PART    = os.path.join(DROP_DIR, "AKA_WH_BrandedSmall_Participation.xlsx")
F_AKA_BS_DATA    = os.path.join(DROP_DIR, "AKA_WH_BrandedSmall_Data.xlsx")
F_AKA_IND_PART   = os.path.join(DROP_DIR, "AKA_WH_Independent_Participation.xlsx")
F_AKA_IND_DATA   = os.path.join(DROP_DIR, "AKA_WH_Independent_Data.xlsx")
F_CAP_HILTON     = os.path.join(DROP_DIR, "Capital Hilton STR", "Capital Hilton - 2025 STR.xlsx")
F_VICEROY        = os.path.join(DROP_DIR, "Viceroy Sets", "Monthly STAR_7621-20260300-USD-E-live.xlsx")


# ── Hotel normalization ──

def norm_key(name):
    """Loose key for matching hotels across sources (lowercase, alphanumeric only)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def sf(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


# ── Parsers ──

def parse_aka_segment(set_id, part_path, data_path):
    """Parse an AKA WH segment Participation + HospitalityDataGrid pair.

    Returns (hotels, perf).
    """
    df = pd.read_excel(part_path, sheet_name="Participation", header=None)
    hotels = []
    # Row 0 = header. Row 1 = "Composite Property" (set-level — skip).
    # Rows 2+ = member hotels until blank Building Name.
    row = 2
    while row < len(df):
        name = df.iloc[row, 0]
        if pd.isna(name) or str(name).strip() == "":
            break
        prop_id = str(int(df.iloc[row, 1])) if pd.notna(df.iloc[row, 1]) else ""
        city = str(df.iloc[row, 2]) if pd.notna(df.iloc[row, 2]) else ""
        state = str(df.iloc[row, 3]) if pd.notna(df.iloc[row, 3]) else ""
        zipc = str(int(df.iloc[row, 4])) if pd.notna(df.iloc[row, 4]) else ""
        klass = str(df.iloc[row, 5]) if pd.notna(df.iloc[row, 5]) else ""
        rooms = int(df.iloc[row, 7]) if pd.notna(df.iloc[row, 7]) else 0
        hotels.append({
            "name": str(name).strip(),
            "str_id": prop_id,
            "city_state": f"{city}, {state}".strip(", "),
            "zip": zipc,
            "rooms": rooms,
            "klass": klass,
            "set_id": set_id,
            "is_anchor": False,
        })
        row += 1

    # Composite room count from row 1, col 7
    composite_rooms = int(df.iloc[1, 7]) if pd.notna(df.iloc[1, 7]) else sum(h["rooms"] for h in hotels)

    # HospitalityDataGrid → R12 perf at the first (most-recent) row
    g = pd.read_excel(data_path, sheet_name="HospitalityDataGrid")
    if len(g) > 0:
        top = g.iloc[0]
        occ_12 = sf(top.get("12 Mo Occupancy")) * 100
        adr_12 = sf(top.get("12 Mo ADR"))
        revpar_12 = sf(top.get("12 Mo RevPAR"))
        perf = {
            "label": f"Composite Set (R12 ending {top.get('Period')})",
            "period": f"R12 ending {top.get('Period')}",
            "occ":    f"{occ_12:.1f}%",
            "adr":    f"${adr_12:.0f}",
            "revpar": f"${revpar_12:.0f}",
            "composite_rooms": composite_rooms,
            "n_comps": len(hotels),
        }
    else:
        perf = {}

    return hotels, perf


def parse_str_monthly(set_id, path):
    """Parse a standard STR Monthly STAR file.

    Returns (hotels, perf). The subject of the STR file is marked as is_anchor=True.
    """
    df = pd.read_excel(path, sheet_name="Response", header=None)

    # Extract subject street address from row 1, col 1
    address_raw = str(df.iloc[1, 1])
    parts = [p.strip() for p in re.split(r"\s{2,}", address_raw) if p.strip()]
    subject_street = parts[1] if len(parts) > 1 else ""

    # Report period from row 3, col 1
    period_raw = str(df.iloc[3, 1])
    period_match = re.search(r"For the Month of:\s*(\w+ \d{4})", period_raw)
    report_period = period_match.group(1) if period_match else "Unknown"

    # Hotels from row 22 — first row = the STR subject (anchor)
    hotels = []
    anchor_idx = None
    row = 22
    while row < len(df):
        name = df.iloc[row, 3]
        if pd.isna(name):
            break
        str_id = str(int(df.iloc[row, 2])) if pd.notna(df.iloc[row, 2]) else ""
        city_state = str(df.iloc[row, 4]) if pd.notna(df.iloc[row, 4]) else ""
        zip_code = str(int(df.iloc[row, 5])) if pd.notna(df.iloc[row, 5]) else ""
        rooms = int(df.iloc[row, 7]) if pd.notna(df.iloc[row, 7]) else 0
        is_anchor = (row == 22)
        if is_anchor:
            anchor_idx = len(hotels)
        hotels.append({
            "name": str(name).strip(),
            "str_id": str_id,
            "city_state": city_state.replace(",", ", "),
            "zip": zip_code,
            "rooms": rooms,
            "klass": "",
            "set_id": set_id,
            "is_anchor": is_anchor,
            "anchor_address": subject_street if is_anchor else "",
        })
        row += 1

    # Total comp rooms (excludes subject) from STR total row
    if row < len(df) and pd.notna(df.iloc[row, 7]):
        comp_rooms = int(df.iloc[row, 7])
    else:
        comp_rooms = sum(h["rooms"] for h in hotels if not h["is_anchor"])

    # Glance sheet → R12 metrics (Subject + Comp Aggregate)
    g = pd.read_excel(path, sheet_name="Glance", header=None)
    r12_row = None
    for i in range(len(g)):
        v = g.iloc[i, 3] if pd.notna(g.iloc[i, 3]) else ""
        if "Running 12 Month" in str(v):
            r12_row = i
            break

    perf = {}
    if r12_row is not None:
        perf = {
            "label": f"{hotels[0]['name']} R12 vs. Comp Set",
            "period": f"R12 ending {report_period}",
            "anchor_name": hotels[0]["name"],
            "subj_occ":    f"{sf(g.iloc[r12_row, 6]):.1f}%",
            "comp_occ":    f"{sf(g.iloc[r12_row, 7]):.1f}%",
            "mpi":         f"{sf(g.iloc[r12_row, 8]):.1f}",
            "subj_adr":    f"${sf(g.iloc[r12_row, 11]):.0f}",
            "comp_adr":    f"${sf(g.iloc[r12_row, 12]):.0f}",
            "ari":         f"{sf(g.iloc[r12_row, 13]):.1f}",
            "subj_revpar": f"${sf(g.iloc[r12_row, 16]):.0f}",
            "comp_revpar": f"${sf(g.iloc[r12_row, 17]):.0f}",
            "rgi":         f"{sf(g.iloc[r12_row, 18]):.1f}",
            "comp_rooms":  comp_rooms,
            "n_comps":     len([h for h in hotels if not h["is_anchor"]]),
        }
        # Attach anchor's own R12 stats to the anchor hotel record so they
        # surface on the marker / sidebar item.
        if anchor_idx is not None:
            hotels[anchor_idx]["anchor_perf"] = {
                "set_id":  set_id,
                "period":  f"R12 ending {report_period}",
                "occ":     perf["subj_occ"],
                "adr":     perf["subj_adr"],
                "revpar":  perf["subj_revpar"],
                "mpi":     perf["mpi"],
                "ari":     perf["ari"],
                "rgi":     perf["rgi"],
            }
    return hotels, perf


def get_original_aka_set():
    """The 6-hotel comp set from the existing aka-white-house map.

    Hard-coded because the source file isn't in the 'Additional AKA Sets'
    folder — we're preserving the original layer rather than re-parsing it.
    """
    # aka_num = position in the official AKA WH STR file (Response sheet, rows 23-28).
    hotels = [
        {
            "name": "Club Quarters Washington, DC, White House",
            "str_id": "58724",
            "city_state": "Washington, DC",
            "zip": "20006",
            "rooms": 161,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 1,
            "lat": 38.9010596, "lng": -77.0391674,
        },
        {
            "name": "Sofitel Washington DC Lafayette Square",
            "str_id": "44237",
            "city_state": "Washington, DC",
            "zip": "20005",
            "rooms": 237,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 2,
            "lat": 38.90047819999999, "lng": -77.03400599999999,
        },
        {
            "name": "Hotel AKA Washington Circle",
            "str_id": "12755",
            "city_state": "Washington, DC",
            "zip": "20037",
            "rooms": 151,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 3,
            "lat": 38.9034054, "lng": -77.0497749,
        },
        {
            "name": "Residence Inn Washington DC Dupont Circle",
            "str_id": "39462",
            "city_state": "Washington, DC",
            "zip": "20037",
            "rooms": 107,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 4,
            "lat": 38.9094048, "lng": -77.0473822,
        },
        {
            "name": "Homewood Suites by Hilton Washington, D.C. Downtown",
            "str_id": "41569",
            "city_state": "Washington, DC",
            "zip": "20005",
            "rooms": 175,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 5,
            "lat": 38.90653, "lng": -77.0334506,
        },
        {
            "name": "Hampton by Hilton Inn Washington DC/ White House",
            "str_id": "61938",
            "city_state": "Washington, DC",
            "zip": "20006",
            "rooms": 116,
            "klass": "",
            "set_id": "aka_orig",
            "is_anchor": False,
            "aka_num": 6,
            "lat": 38.9006021, "lng": -77.031455,
        },
    ]
    perf = {
        "label": "AKA WH R12 vs. Comp Set",
        "period": "R12 ending Dec 2025",
        "anchor_name": "AKA White House",
        "subj_occ": SUBJECT["occ"], "comp_occ": "75.4%", "mpi": SUBJECT["mpi"],
        "subj_adr": SUBJECT["adr"], "comp_adr": "$253", "ari": SUBJECT["ari"],
        "subj_revpar": SUBJECT["revpar"], "comp_revpar": "$191", "rgi": SUBJECT["rgi"],
        "comp_rooms": 947,
        "n_comps": 6,
    }
    return hotels, perf


def get_capital_hilton_supply():
    """Capital Hilton submarket supply changes, lifted from the Capital Hilton
    new-supply pipeline map (capital-hilton/new-supply.html).

    Returns (pipeline, former). lat/lng pre-set so no geocoding is needed.
    Descriptive locations are stored in city_state; pipeline rooms are unknown (0).
    """
    pipeline = [
        {"name": "Tempo by Hilton DC Downtown", "brand": "Tempo by Hilton",
         "city_state": "1776 K Street NW, Washington, DC", "lat": 38.90212289999999, "lng": -77.0413265},
        {"name": "CitizenM Washington Georgetown", "brand": "CitizenM",
         "city_state": "Near Key Bridge, Georgetown, Washington, DC", "lat": 38.9050618, "lng": -77.0686358},
        {"name": "The Hoya Hotel", "brand": "Independent",
         "city_state": "Georgetown University, Washington, DC", "lat": 38.9076089, "lng": -77.07225849999999},
        {"name": "Aloft Hotel Mt. Vernon Triangle", "brand": "Aloft Hotels",
         "city_state": "Mt. Vernon Triangle, Washington, DC", "lat": 38.9024949, "lng": -77.01896049999999},
        {"name": "Marriott Tribute Portfolio Chinatown", "brand": "Tribute Portfolio",
         "city_state": "Near Capital One Arena, Washington, DC", "lat": 38.8981675, "lng": -77.02085679999999},
    ]
    former = [
        {"name": "Fairfax at Embassy Row", "brand": "Autograph Collection", "rooms": 259,
         "city_state": "2100 Massachusetts Ave NW, Washington, DC", "lat": 38.9105256, "lng": -77.0471161},
        {"name": "Avenue Suites", "brand": "Independent", "rooms": 124,
         "city_state": "2500 Pennsylvania Ave NW, Washington, DC", "lat": 38.90358670000001, "lng": -77.0535668},
        {"name": "Embassy Circle Guest House", "brand": "Independent", "rooms": 11,
         "city_state": "2224 R St NW, Washington, DC", "lat": 38.9124256, "lng": -77.04980759999999},
        {"name": "Georgetown Suites", "brand": "Independent", "rooms": 222,
         "city_state": "1111 30th St NW, Washington, DC", "lat": 38.9046728, "lng": -77.05837910000001},
        {"name": "Adams Inn", "brand": "Independent", "rooms": 27,
         "city_state": "1746 Lanier Pl NW, Washington, DC", "lat": 38.9245461, "lng": -77.0416122},
        {"name": "Marriott Wardman Park", "brand": "Marriott Hotels", "rooms": 1152,
         "city_state": "2660 Woodley Rd NW, Washington, DC", "lat": 38.9247051, "lng": -77.0542636},
    ]
    for h in pipeline:
        h.update({"str_id": "", "zip": "", "rooms": 0, "klass": "",
                  "set_id": "new_supply", "is_anchor": False})
    for h in former:
        h.update({"str_id": "", "zip": "", "klass": "",
                  "set_id": "former_supply", "is_anchor": False})
    return pipeline, former


def get_dc_new_supply():
    """AKA WH — Washington DC market raw new-supply master list.

    Source: CBRE '2026 & 2027 Market Overview for DC' (Supply Summary, 06/22/26),
    cross-referenced against the 1710 H St Chairman's Book OM (CBRE, 04/02/26, p.13).
    Properties span 2019 base through 2034, bucketed into four toggleable layers:
    dc_recent (Recently Completed 2019-25), dc_pipeline (2026-27 under construction),
    dc_reduction (closures), dc_planning (2028+ early planning). lat/lng pre-geocoded.

    om_flag drives the OM cross-reference line shown on click:
      in=in OM competitive-supply page, missing=omitted, base=YE2019 base year,
      horizon=beyond OM's stated horizon.
    """
    hotels = [
        {"name": "Conrad Washington DC", "brand": "", "str_id": "", "zip": "", "city_state": "950 New York Ave NW, Washington, DC", "rooms": 360, "klass": "", "product_type": "Full-Service / Luxury", "open_date": "Mar-19", "om_flag": "base", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9014786, "lng": -77.0253522},
        {"name": "Hilton Washington DC National Mall (fka L'Enfant Plaza Hotel)", "brand": "", "str_id": "", "zip": "", "city_state": "480 L'Enfant Plaza, Washington, DC", "rooms": 367, "klass": "", "product_type": "Full-Service / Luxury", "open_date": "Apr-19", "om_flag": "base", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8838109, "lng": -77.0239713},
        {"name": "Lyric Suites at Liz", "brand": "", "str_id": "", "zip": "", "city_state": "1360 R St NW, Washington, DC", "rooms": 11, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "Dec-19", "om_flag": "base", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9124032, "lng": -77.0316016},
        {"name": "AC Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "1112 19th St NW, Washington, DC", "rooms": 219, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Dec-19", "om_flag": "base", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9042043, "lng": -77.0438734},
        {"name": "Hyatt Thompson Washington DC", "brand": "", "str_id": "", "zip": "", "city_state": "221 Tingey St SE, Washington, DC", "rooms": 225, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Jan-20", "om_flag": "missing", "om_note": "Defensible exclusion — Navy Yard/ballpark submarket, ~2.5 mi from 1710 H - different demand driver (stadium/waterfront vs. federal/CBD).", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8747120, "lng": -77.0027530},
        {"name": "citizenM Washington DC Capitol", "brand": "", "str_id": "", "zip": "", "city_state": "550 School Street SW, Washington, DC", "rooms": 252, "klass": "", "product_type": "Select-Service (Lifestyle)", "open_date": "Oct-20", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8837279, "lng": -77.0194263},
        {"name": "Yotel (rebranded from Liaison Capitol Hill)", "brand": "", "str_id": "", "zip": "", "city_state": "415 New Jersey Ave NW, Washington, DC", "rooms": 34, "klass": "", "product_type": "Budget / Pod", "open_date": "Oct-20", "om_flag": "missing", "om_note": "Defensible exclusion — Budget pod-hotel tier - not a comparable product to a luxury apartment-suite asset.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8951871, "lng": -77.0105468},
        {"name": "AC Hotel Washington DC Convention Center", "brand": "", "str_id": "", "zip": "", "city_state": "601 K Street NW, Washington, DC", "rooms": 234, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Oct-20", "om_flag": "missing", "om_note": "Likely genuine miss — <1 mi away on the K St corridor. Tier is below AKA's positioning, but OM's own list includes lower-tier Holiday Inn Express & Selina elsewhere, so tier alone doesn't explain this exclusion.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9027941, "lng": -77.0201362},
        {"name": "Cambria Hotels Washington D.C. Capitol Riverfront", "brand": "", "str_id": "", "zip": "", "city_state": "69 Q St SW, Washington, DC", "rooms": 154, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Feb-21", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8709289, "lng": -77.0113068},
        {"name": "Marriott Wardman Park", "brand": "", "str_id": "", "zip": "", "city_state": "2660 Woodley Rd NW, Washington, DC", "rooms": 1153, "klass": "", "product_type": "Full-Service / Convention", "open_date": "Nov-21", "om_flag": "in", "om_note": "", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.9247051, "lng": -77.0542636},
        {"name": "Courtyard Washington, DC Dupont Circle", "brand": "", "str_id": "", "zip": "", "city_state": "1733 N Street NW, Washington, DC", "rooms": 143, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Dec-21", "om_flag": "missing", "om_note": "Ambiguous / modest — ~1 mi away, select-service tier below AKA. Reasonable submarket/tier edit, but proximity keeps it in the gray zone.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9074484, "lng": -77.0397080},
        {"name": "AC Hotel Washington DC Capitol Hill Navy Yard", "brand": "", "str_id": "", "zip": "", "city_state": "867 New Jersey Ave SE, Washington, DC", "rooms": 225, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Feb-22", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8802579, "lng": -77.0056775},
        {"name": "Selina Hotel DC", "brand": "", "str_id": "", "zip": "", "city_state": "1309 5th Street NE, Washington, DC", "rooms": 106, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Jun-22", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9080686, "lng": -76.9977870},
        {"name": "citizenM Washington DC NoMa", "brand": "", "str_id": "", "zip": "", "city_state": "1222 First St NE, Washington, DC", "rooms": 296, "klass": "", "product_type": "Select-Service (Lifestyle)", "open_date": "Aug-22", "om_flag": "missing", "om_note": "Likely genuine miss — Largest single omission (296 keys). OM includes sibling citizenM Capitol (Recently Completed) AND citizenM Georgetown (Pipeline) - NoMa is geographically closer to 1710 H than Georgetown. No principled reason for this specific gap.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9067475, "lng": -77.0065196},
        {"name": "The Pendry Washington DC - The Wharf", "brand": "", "str_id": "", "zip": "", "city_state": "655 Water St, Washington, DC", "rooms": 131, "klass": "", "product_type": "Full-Service / Luxury", "open_date": "Oct-22", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8771026, "lng": -77.0218163},
        {"name": "The Morrow Hotel, Curio Collection", "brand": "", "str_id": "", "zip": "", "city_state": "222 M Street NE, Washington, DC", "rooms": 203, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Nov-22", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9060950, "lng": -77.0022631},
        {"name": "Holiday Inn Express Washington DC Downtown", "brand": "", "str_id": "", "zip": "", "city_state": "317 K Street NW, Washington, DC", "rooms": 247, "klass": "", "product_type": "Select-Service", "open_date": "Nov-22", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9026066, "lng": -77.0160098},
        {"name": "Washington Marriott Capitol Hill", "brand": "", "str_id": "", "zip": "", "city_state": "1005 First St NE, Washington, DC", "rooms": 235, "klass": "", "product_type": "Full-Service / Upscale", "open_date": "Jan-23", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9031826, "lng": -77.0053934},
        {"name": "Royal Sonesta Washington, DC Capitol Hill", "brand": "", "str_id": "", "zip": "", "city_state": "20 Massachusetts Ave NW, Washington, DC", "rooms": 274, "klass": "", "product_type": "Full-Service / Upscale", "open_date": "Sep-23", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8975797, "lng": -77.0107773},
        {"name": "Sonder Vicino", "brand": "", "str_id": "", "zip": "", "city_state": "1324 North Capitol Street NW, Washington, DC", "rooms": 69, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "Nov-23", "om_flag": "missing", "om_note": "Defensible exclusion — Small (69 keys), peripheral North Capitol St location; Sonder's brand distress (acquired by Marriott in 2024) plausibly makes it non-comparable in CBRE's view.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9080880, "lng": -77.0093736},
        {"name": "Placemakr Cathedral Heights", "brand": "", "str_id": "", "zip": "", "city_state": "4000 Wisconsin Ave NW, Washington, DC", "rooms": 150, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "Apr-24", "om_flag": "missing", "om_note": "Defensible exclusion — Far NW submarket (~3.5 mi) near American University/Cathedral - different demand base entirely.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9420732, "lng": -77.0768762},
        {"name": "Arlo D.C", "brand": "", "str_id": "", "zip": "", "city_state": "333 G St. NW, Washington, DC", "rooms": 445, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Nov-24", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8984889, "lng": -77.0158718},
        {"name": "Canal House of Georgetown, a Tribute Portfolio Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "1023 31st St NW, Washington, DC", "rooms": 108, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Feb-25", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9032683, "lng": -77.0607925},
        {"name": "Placemakr Buzzard Point", "brand": "", "str_id": "", "zip": "", "city_state": "101 V St SW, Washington, DC", "rooms": 120, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "Mar-25", "om_flag": "missing", "om_note": "Defensible exclusion — Far SW/Buzzard Point stadium submarket (~3 mi) - different demand base.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8648017, "lng": -77.0134161},
        {"name": "I Street Capsule Hostel", "brand": "", "str_id": "", "zip": "", "city_state": "512 I Street Northwest, Washington, DC", "rooms": 75, "klass": "", "product_type": "Budget / Hostel", "open_date": "Apr-25", "om_flag": "missing", "om_note": "Defensible exclusion — Geographically close but a hostel/capsule concept - tier gap too large to be a real comp.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9006467, "lng": -77.0196615},
        {"name": "Mint House Downtown Washington D.C.", "brand": "", "str_id": "", "zip": "", "city_state": "1010 Vermont Ave NW, Washington, DC", "rooms": 85, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "May-25", "om_flag": "missing", "om_note": "Likely genuine miss — <0.7 mi from 1710 H, same downtown core, and the closest product-type match on the entire list (apartment-style extended-stay). The single most relevant comp the OM's table omits.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9030859, "lng": -77.0337180},
        {"name": "Sixty DC", "brand": "", "str_id": "", "zip": "", "city_state": "1337 Connecticut Ave NW, Washington, DC", "rooms": 73, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Jun-25", "om_flag": "in", "om_note": "", "set_id": "dc_recent", "is_anchor": False, "lat": 38.9082842, "lng": -77.0422279},
        {"name": "ROOST White House", "brand": "", "str_id": "", "zip": "", "city_state": "1425 New York Ave NW, Washington, DC", "rooms": 33, "klass": "", "product_type": "Apartment-Style (Boutique)", "open_date": "Sep-25", "om_flag": "missing", "om_note": "Likely genuine miss — Apartment-style/aparthotel concept ~0.5 mi away, opened Sep-25 (7 months before the OM), named after the same landmark as the subject. Small size (33 keys) may explain low materiality to CBRE's headline number, but it's directly on-thesis competitively.", "set_id": "dc_recent", "is_anchor": False, "lat": 38.8995260, "lng": -77.0325852},
        {"name": "Sonder Georgetown C&O Apartments Georgetown (CLOSED)", "brand": "", "str_id": "", "zip": "", "city_state": "1111 30th St NW, Washington, DC", "rooms": 134, "klass": "", "product_type": "Apartment-Style (closure)", "open_date": "Jan-26", "om_flag": "missing", "om_note": "Likely genuine miss — A closure works IN the broker's favor (less competition = more bullish for the 'high barriers to entry' story), so there's no strategic reason to hide it. Most likely explanation: too recent (Jan-26 closure vs. Apr-26 OM) or excluded because it was apartment-flagged, not hotel-flagged, in CBRE's internal supply tracker.", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.9046728, "lng": -77.0583791},
        {"name": "Tempo by Hilton DC Downtown", "brand": "", "str_id": "", "zip": "", "city_state": "1776 K St NW, Washington, DC", "rooms": 278, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Apr-26", "om_flag": "in", "om_note": "", "set_id": "dc_pipeline", "is_anchor": False, "lat": 38.9021229, "lng": -77.0413265},
        {"name": "CitizenM Washington Georgetown", "brand": "", "str_id": "", "zip": "", "city_state": "3401 Water St NW, Washington, DC", "rooms": 230, "klass": "", "product_type": "Select-Service (Lifestyle)", "open_date": "Jun-26", "om_flag": "in", "om_note": "", "set_id": "dc_pipeline", "is_anchor": False, "lat": 38.9050618, "lng": -77.0686358},
        {"name": "AC Hotel Washington, DC National Mall", "brand": "", "str_id": "", "zip": "", "city_state": "601 Indiana Ave NW, Washington, DC", "rooms": 122, "klass": "", "product_type": "Select-Service / Upscale", "open_date": "Nov-27", "om_flag": "in", "om_note": "", "set_id": "dc_pipeline", "is_anchor": False, "lat": 38.8946745, "lng": -77.0202617},
        {"name": "MOB Hotel Washington DC Union Market", "brand": "", "str_id": "", "zip": "", "city_state": "400 Florida Avenue NE, Washington, DC", "rooms": 144, "klass": "", "product_type": "Full-Service / Lifestyle", "open_date": "Dec-27", "om_flag": "missing", "om_note": "Defensible exclusion — Union Market submarket (~2 mi) - different arts/food-district demand base.", "set_id": "dc_pipeline", "is_anchor": False, "lat": 38.9137349, "lng": -77.0163293},
        {"name": "Aloft Hotel Washington, DC", "brand": "", "str_id": "", "zip": "", "city_state": "925 5th St NW, Washington, DC", "rooms": 152, "klass": "", "product_type": "Select-Service", "open_date": "May-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9020800, "lng": -77.0185343},
        {"name": "The Bazaar House by Jose Andres", "brand": "", "str_id": "", "zip": "", "city_state": "3000 M St NW, Washington, DC", "rooms": 67, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Jun-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9050350, "lng": -77.0595194},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "3071 Canal St NW, Washington, DC", "rooms": 9, "klass": "", "product_type": "TBD", "open_date": "Jun-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9043391, "lng": -77.0607260},
        {"name": "Moxy Washington, DC Southwest", "brand": "", "str_id": "", "zip": "", "city_state": "45 Q St SW, Washington, DC", "rooms": 166, "klass": "", "product_type": "Select-Service (Lifestyle)", "open_date": "Aug-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8712109, "lng": -77.0104749},
        {"name": "Moxy Washington, DC Northeast", "brand": "", "str_id": "", "zip": "", "city_state": "37 New York Ave NW, Washington, DC", "rooms": 198, "klass": "", "product_type": "Select-Service (Lifestyle)", "open_date": "Sep-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9070923, "lng": -77.0104667},
        {"name": "Residence Inn by Marriott Washington, DC/Northeast", "brand": "", "str_id": "", "zip": "", "city_state": "SWQ Michigan Ave, Washington, DC", "rooms": 161, "klass": "", "product_type": "Extended-Stay", "open_date": "Sep-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9264439, "lng": -77.0147716},
        {"name": "Courtyard By Marriott Washington, DC/Northeast", "brand": "", "str_id": "", "zip": "", "city_state": "SWQ Michigan Ave, Washington, DC", "rooms": 105, "klass": "", "product_type": "Select-Service", "open_date": "Sep-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9261676, "lng": -77.0145180},
        {"name": "Tribute Portfolio Hotel Washington, DC Downtown", "brand": "", "str_id": "", "zip": "", "city_state": "509 H St NW, Washington, DC", "rooms": 142, "klass": "", "product_type": "Full-Service / Upscale (Lifestyle)", "open_date": "Sep-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8999864, "lng": -77.0192990},
        {"name": "Registry Collection Hotels, Washington DC", "brand": "", "str_id": "", "zip": "", "city_state": "1333 G St NW, Washington, DC", "rooms": 94, "klass": "", "product_type": "Full-Service / Upscale", "open_date": "Sep-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8985949, "lng": -77.0311639},
        {"name": "Avid Downtown Washington, D.C.", "brand": "", "str_id": "", "zip": "", "city_state": "311 H St NW, Washington, DC", "rooms": 144, "klass": "", "product_type": "Select-Service (Budget-Upscale)", "open_date": "Dec-28", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9004210, "lng": -77.0157909},
        {"name": "Hotel Indigo Washington DC", "brand": "", "str_id": "", "zip": "", "city_state": "921 6th St NW, Washington, DC", "rooms": 116, "klass": "", "product_type": "Boutique / Lifestyle", "open_date": "Dec-29", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9022249, "lng": -77.0196439},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "1250 U St NW, Washington, DC", "rooms": 61, "klass": "", "product_type": "TBD", "open_date": "Dec-29", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9168714, "lng": -77.0292804},
        {"name": "Capitol Crossing Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "201 F St NW, Washington, DC", "rooms": 220, "klass": "", "product_type": "Full-Service (brand TBD)", "open_date": "Jun-31", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8976098, "lng": -77.0141618},
        {"name": "Burnham Place Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "100 Columbus Cir NE, Washington, DC", "rooms": 500, "klass": "", "product_type": "Full-Service (brand TBD)", "open_date": "Jan-34", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8960570, "lng": -77.0058219},
        {"name": "WaterWalk Extended Stay by Wyndham Capitol Hill/Navy Yard", "brand": "", "str_id": "", "zip": "", "city_state": "1220 Pennsylvania Ave SE, Washington, DC", "rooms": 100, "klass": "", "product_type": "Apartment-Style / Extended-Stay", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8822807, "lng": -76.9896129},
        {"name": "SLS Lux Hotel & Residences", "brand": "", "str_id": "", "zip": "", "city_state": "901 5th St NW, Washington, DC", "rooms": 198, "klass": "", "product_type": "Full-Service / Luxury", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9012240, "lng": -77.0181408},
        {"name": "Residence Inn Washington DC", "brand": "", "str_id": "", "zip": "", "city_state": "1901 Independence Ave SE, Washington, DC", "rooms": 150, "klass": "", "product_type": "Extended-Stay", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8868805, "lng": -76.9765900},
        {"name": "Maison Kesh", "brand": "", "str_id": "", "zip": "", "city_state": "1634 North Capitol St NW, Washington, DC", "rooms": 105, "klass": "", "product_type": "Apartment-Style / Boutique", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9121547, "lng": -77.0094005},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "25 E St NW, Washington, DC", "rooms": 100, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8963585, "lng": -77.0102829},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "901 N Capitol St NE, Washington, DC", "rooms": 106, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9015697, "lng": -77.0086426},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "Burke St, Washington, DC", "rooms": 150, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8861567, "lng": -76.9773574},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "1810-1828 Bladensburg Rd NE, Washington, DC", "rooms": 234, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9144697, "lng": -76.9751682},
        {"name": "Unnamed Hotel", "brand": "", "str_id": "", "zip": "", "city_state": "280 12th St SW, Washington, DC", "rooms": 163, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8862439, "lng": -77.0278252},
        {"name": "Unnamed Hotel @ Riverfront On The Anacostia", "brand": "", "str_id": "", "zip": "", "city_state": "100 Potomac Ave SE, Washington, DC", "rooms": 325, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.8717669, "lng": -77.0054359},
        {"name": "Meininger Hotel Washington", "brand": "", "str_id": "", "zip": "", "city_state": "35 New York Ave NE, Washington, DC", "rooms": 135, "klass": "", "product_type": "Budget / Hostel", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9075778, "lng": -77.0074229},
        {"name": "Unnamed Hotel @ Maritime Plaza", "brand": "", "str_id": "", "zip": "", "city_state": "1201 M St, Washington, DC", "rooms": 250, "klass": "", "product_type": "TBD", "open_date": "TBD", "om_flag": "horizon", "om_note": "", "set_id": "dc_planning", "is_anchor": False, "lat": 38.9058379, "lng": -77.0283510},
        {"name": "Fairfax at Embassy Row", "brand": "", "str_id": "", "zip": "", "city_state": "2100 Massachusetts Ave NW, Washington, DC", "rooms": 259, "klass": "", "product_type": "Full-Service / Luxury", "open_date": "Sep-21", "om_flag": "in", "om_note": "", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.9105256, "lng": -77.0471161},
        {"name": "Georgetown Suites", "brand": "", "str_id": "", "zip": "", "city_state": "1111 30th St NW, Washington, DC", "rooms": 222, "klass": "", "product_type": "Apartment-Style (historical, extended-stay)", "open_date": "Nov-20", "om_flag": "in", "om_note": "", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.9043965, "lng": -77.0581255},
        {"name": "Georgetown University Hotel and Conference Center (closure)", "brand": "", "str_id": "", "zip": "", "city_state": "3800 Reservoir Rd NW, Washington, DC", "rooms": 146, "klass": "", "product_type": "Full-Service (Conference)", "open_date": "2022", "om_flag": "in", "om_note": "", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.9122800, "lng": -77.0751871},
        {"name": "Hotel Harrington (closure)", "brand": "", "str_id": "", "zip": "", "city_state": "436 11th St NW, Washington, DC", "rooms": 242, "klass": "", "product_type": "Budget / Historic", "open_date": "Dec-23", "om_flag": "in", "om_note": "", "set_id": "dc_reduction", "is_anchor": False, "lat": 38.8959394, "lng": -77.0273194},
    ]
    return hotels


def dc_supply_stats(dc):
    """Per-layer key totals + OM-omission count for the DC raw-supply summary card."""
    from collections import defaultdict
    keys = defaultdict(int)
    n = defaultdict(int)
    for h in dc:
        keys[h["set_id"]] += h["rooms"]
        n[h["set_id"]] += 1
    return {
        "recent_n": n["dc_recent"], "recent_keys": keys["dc_recent"],
        "pipeline_n": n["dc_pipeline"], "pipeline_keys": keys["dc_pipeline"],
        "reduction_n": n["dc_reduction"], "reduction_keys": keys["dc_reduction"],
        "planning_n": n["dc_planning"], "planning_keys": keys["dc_planning"],
        "omitted": sum(1 for h in dc if h.get("om_flag") == "missing"),
        "total_n": len(dc),
    }


def haversine_mi(lat1, lng1, lat2, lng2):
    """Great-circle distance in statute miles."""
    R = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# Distance rings drawn around the subject (statute miles). Shared by the map
# overlay (JS) and the sidebar count table (Python) so the two never drift.
RING_RADII_MI = [0.5, 1.0, 1.5]


# ── Geocoding ──

def load_cache():
    if os.path.exists(GEOCACHE_PATH):
        with open(GEOCACHE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(GEOCACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def geocode_hotel(h, cache):
    """Geocode one hotel, mutating h with lat/lng. Uses cache."""
    if "lat" in h and "lng" in h:
        return  # already set (e.g., from get_original_aka_set)
    query = f"{h['name']}, {h.get('city_state','')} {h.get('zip','')}".strip(", ")
    if query in cache:
        h["lat"] = cache[query]["lat"]
        h["lng"] = cache[query]["lng"]
        print(f"  [cached] {h['name']}")
        return
    print(f"  [geocoding] {h['name']}...")
    resp = requests.get(GEOCODE_URL, params={"address": query, "key": API_KEY}).json()
    if resp.get("results"):
        loc = resp["results"][0]["geometry"]["location"]
        cache[query] = loc
        save_cache(cache)
        h["lat"] = loc["lat"]
        h["lng"] = loc["lng"]
        time.sleep(0.1)
    else:
        print(f"  WARNING: could not geocode {h['name']}")
        h["lat"] = 0
        h["lng"] = 0


# ── Merge / dedupe ──

def merge_hotels(all_lists):
    """Combine hotels from all sources into a deduped list with multi-set memberships."""
    merged = {}
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
                    "klass": h.get("klass", ""),
                    "memberships": [],
                    "anchor_for": [],
                }
            entry = merged[k]
            if h["set_id"] not in entry["memberships"]:
                entry["memberships"].append(h["set_id"])
            if h.get("is_anchor"):
                if h["set_id"] not in entry["anchor_for"]:
                    entry["anchor_for"].append(h["set_id"])
            # Prefer longer/canonical name and largest room count
            if len(h["name"]) > len(entry["name"]):
                entry["name"] = h["name"]
            if h.get("rooms", 0) > entry["rooms"]:
                entry["rooms"] = h["rooms"]
            if h.get("klass") and not entry["klass"]:
                entry["klass"] = h["klass"]
            # Carry over preset lat/lng (from original AKA set)
            if "lat" in h and "lat" not in entry:
                entry["lat"] = h["lat"]
                entry["lng"] = h["lng"]
            # Carry STR ID if blank
            if h.get("str_id") and not entry["str_id"]:
                entry["str_id"] = h["str_id"]
            # Carry AKA official STR-file number (only set on aka_orig members)
            if h.get("aka_num") and "aka_num" not in entry:
                entry["aka_num"] = h["aka_num"]
            # Carry brand (only set on supply-layer hotels)
            if h.get("brand") and not entry.get("brand"):
                entry["brand"] = h["brand"]
            # Carry DC raw-supply metadata (only set on dc_* layer hotels)
            for _f in ("product_type", "open_date", "om_flag", "om_note"):
                if h.get(_f) and not entry.get(_f):
                    entry[_f] = h[_f]
            if h.get("dist_mi") is not None and entry.get("dist_mi") is None:
                entry["dist_mi"] = h["dist_mi"]
            # Carry anchor address if available
            if h.get("anchor_address"):
                entry["anchor_address"] = h["anchor_address"]
            # Carry anchor R12 perf (only present for STR-subject anchors)
            if h.get("anchor_perf"):
                entry.setdefault("anchor_perfs", []).append(h["anchor_perf"])

    # Sort memberships by COMP_SETS priority
    out = []
    for entry in merged.values():
        entry["memberships"].sort(key=lambda sid: SET_BY_ID[sid]["priority"])
        # If this hotel anchors any set, color by the highest-priority anchored set
        # so the dashed-anchor pin reads "this is THAT set's STR subject."
        if entry["anchor_for"]:
            entry["anchor_for"].sort(key=lambda sid: SET_BY_ID[sid]["priority"])
            entry["primary_set_id"] = entry["anchor_for"][0]
        else:
            entry["primary_set_id"] = entry["memberships"][0]
        out.append(entry)
    return out


# ── HTML rendering ──

def build_perf_panels_html(set_perf):
    """Render the per-set performance panels for the sidebar."""
    rows = []
    for s in COMP_SETS:
        perf = set_perf.get(s["id"])
        if not perf:
            continue
        color = s["color"]
        if "subj_occ" in perf:
            # Anchor-vs-comp style (Original AKA, Cap Hilton, Viceroy)
            rows.append(f"""
      <div class="set-perf-card" data-set-id="{s['id']}">
        <div class="set-perf-header">
          <span class="set-dot" style="background:{color}"></span>
          <span class="set-perf-title">{s['label']}</span>
        </div>
        <div class="set-perf-period">{perf['period']} &middot; {perf.get('n_comps','—')} comps &middot; {perf.get('comp_rooms','—'):,} comp rooms</div>
        <div class="set-perf-grid">
          <div class="set-perf-cell">
            <div class="spc-label">Occ ({perf['anchor_name']})</div>
            <div class="spc-value">{perf['subj_occ']}</div>
            <div class="spc-vs">vs {perf['comp_occ']} comp &middot; MPI {perf['mpi']}</div>
          </div>
          <div class="set-perf-cell">
            <div class="spc-label">ADR</div>
            <div class="spc-value">{perf['subj_adr']}</div>
            <div class="spc-vs">vs {perf['comp_adr']} comp &middot; ARI {perf['ari']}</div>
          </div>
          <div class="set-perf-cell">
            <div class="spc-label">RevPAR</div>
            <div class="spc-value">{perf['subj_revpar']}</div>
            <div class="spc-vs">vs {perf['comp_revpar']} comp &middot; RGI {perf['rgi']}</div>
          </div>
        </div>
      </div>""")
        elif "occ" in perf:
            # Composite-only style (AKA segment sets — subject not in set)
            rows.append(f"""
      <div class="set-perf-card" data-set-id="{s['id']}">
        <div class="set-perf-header">
          <span class="set-dot" style="background:{color}"></span>
          <span class="set-perf-title">{s['label']}</span>
        </div>
        <div class="set-perf-period">{perf['period']} &middot; {perf.get('n_comps','—')} hotels &middot; {perf.get('composite_rooms','—'):,} rooms</div>
        <div class="set-perf-grid">
          <div class="set-perf-cell">
            <div class="spc-label">Occ</div>
            <div class="spc-value">{perf['occ']}</div>
          </div>
          <div class="set-perf-cell">
            <div class="spc-label">ADR</div>
            <div class="spc-value">{perf['adr']}</div>
          </div>
          <div class="set-perf-cell">
            <div class="spc-label">RevPAR</div>
            <div class="spc-value">{perf['revpar']}</div>
          </div>
        </div>
      </div>""")
    return "\n".join(rows)


def build_supply_summary_html(supply_stats):
    """Compact card summarizing the Capital Hilton submarket supply changes."""
    if not supply_stats:
        return ""
    ns = SET_BY_ID["new_supply"]["color"]
    fs = SET_BY_ID["former_supply"]["color"]
    return f"""
      <div class="supply-summary">
        <div class="supply-cell">
          <div class="supply-num" style="color:{ns}">+{supply_stats['pipeline_n']}</div>
          <div class="supply-cap">Pipeline hotels</div>
        </div>
        <div class="supply-cell">
          <div class="supply-num" style="color:{fs}">&minus;{supply_stats['former_n']}</div>
          <div class="supply-cap">Closed hotels</div>
        </div>
        <div class="supply-cell">
          <div class="supply-num" style="color:{fs}">&minus;{supply_stats['keys_removed']:,}</div>
          <div class="supply-cap">Keys removed</div>
        </div>
      </div>
      <div style="margin-top:6px; font-size:9px; color:#97a3bd; line-height:1.35;">
        Source: Capital Hilton new-supply pipeline map. Locations approximate; pipeline room counts TBD.
      </div>"""


def build_dc_supply_summary_html(dc):
    """Compact card summarizing the DC market raw new-supply layers (CBRE Jul '26)."""
    if not dc:
        return ""
    c_rec = SET_BY_ID["dc_recent"]["color"]
    c_pipe = SET_BY_ID["dc_pipeline"]["color"]
    c_red = SET_BY_ID["dc_reduction"]["color"]
    c_plan = SET_BY_ID["dc_planning"]["color"]
    return f"""
      <div class="supply-summary" style="grid-template-columns:1fr 1fr 1fr 1fr;">
        <div class="supply-cell">
          <div class="supply-num" style="color:{c_rec}; font-size:15px;">+{dc['recent_keys']:,}</div>
          <div class="supply-cap">Completed<br/>2019&ndash;25 &middot; {dc['recent_n']}</div>
        </div>
        <div class="supply-cell">
          <div class="supply-num" style="color:{c_pipe}; font-size:15px;">+{dc['pipeline_keys']:,}</div>
          <div class="supply-cap">Pipeline<br/>2026&ndash;27 &middot; {dc['pipeline_n']}</div>
        </div>
        <div class="supply-cell">
          <div class="supply-num" style="color:{c_red}; font-size:15px;">&minus;{dc['reduction_keys']:,}</div>
          <div class="supply-cap">Closures<br/>&middot; {dc['reduction_n']}</div>
        </div>
        <div class="supply-cell">
          <div class="supply-num" style="color:{c_plan}; font-size:15px;">+{dc['planning_keys']:,}</div>
          <div class="supply-cap">2028+ plan<br/>&middot; {dc['planning_n']}</div>
        </div>
      </div>
      <div style="margin-top:7px; font-size:9.5px; color:#5d6b85; line-height:1.4;">
        <b>{dc['omitted']}</b> of these properties are <b>omitted</b> from the OM's competitive-supply page (p.13) &mdash; click any pin for the in-OM vs. omitted status &amp; broker-omission assessment. Keys are room counts (&plusmn;); early-planning sites are low-certainty.
      </div>
      <div style="margin-top:5px; font-size:9px; color:#97a3bd; line-height:1.35;">
        Source: CBRE 2026 &amp; 2027 Market Overview for DC (Supply Summary, 06/22/26), cross-referenced vs. 1710 H St OM (04/02/26). Toggle the four layers on in the legend above.
      </div>"""


def build_radius_table_html(dc):
    """Cumulative counts of DC new-supply properties within each distance ring."""
    if not dc:
        return ""
    cats = [
        ("dc_recent", "Compl."),
        ("dc_pipeline", "Pipe"),
        ("dc_planning", "2028+"),
        ("dc_reduction", "Closed"),
    ]
    head_cells = "".join(
        f'<th style="color:{SET_BY_ID[cid]["color"]}">{lbl}</th>' for cid, lbl in cats
    )
    body = []
    for r in RING_RADII_MI:
        rlabel = {0.5: "&frac12; mi", 1.0: "1 mi", 1.5: "1&frac12; mi"}[r]
        cells = []
        for cid, _ in cats:
            c = sum(1 for h in dc if h["set_id"] == cid and h.get("dist_mi", 99) <= r)
            cells.append(f'<td>{c if c else "&middot;"}</td>')
        add_tot = sum(
            1 for h in dc if h["set_id"] != "dc_reduction" and h.get("dist_mi", 99) <= r
        )
        add_keys = sum(
            h["rooms"] for h in dc
            if h["set_id"] != "dc_reduction" and h.get("dist_mi", 99) <= r
        )
        body.append(
            f'<tr><th>&#8804;&nbsp;{rlabel}</th>{"".join(cells)}'
            f'<td class="rt-tot">{add_tot}</td>'
            f'<td class="rt-keys">{add_keys:,}</td></tr>'
        )
    return f"""
      <table class="radius-table">
        <thead><tr><th>Within</th>{head_cells}<th class="rt-tot">New&nbsp;+</th><th class="rt-keys">Keys</th></tr></thead>
        <tbody>{"".join(body)}</tbody>
      </table>
      <div style="margin-top:6px; font-size:9px; color:#97a3bd; line-height:1.35;">
        Cumulative &mdash; each row counts every property within that radius of AKA White House. &ldquo;New&nbsp;+&rdquo; = additions only (excludes closures). Toggle the amber rings in the legend to see the bands on the map; click a pin for its exact distance.
      </div>"""


def build_legend_rows():
    rows = [f"""
      <div class="legend-row legend-subject">
        <div class="leg-marker leg-star" style="background:{SUBJECT_COLOR}">★</div>
        <span class="leg-label">{SUBJECT['name']} (Subject)</span>
      </div>"""]
    for s in COMP_ONLY_SETS:
        rows.append(f"""
      <label class="legend-row toggle-row" data-set-id="{s['id']}">
        <input type="checkbox" class="set-toggle" data-set-id="{s['id']}" checked />
        <div class="leg-marker" style="background:{s['color']}"></div>
        <span class="leg-label">{s['label']}</span>
      </label>""")
    # Supply-change layers, split into their own subheaded groups.
    GROUP_TITLES = [
        ("caphilton", "Submarket Supply Changes (Capital Hilton)"),
        ("dc_supply", "Raw New Supply &mdash; DC Market (CBRE, Jul 2026)"),
    ]
    for group_id, title in GROUP_TITLES:
        group_sets = [s for s in SUPPLY_SETS if s.get("group") == group_id]
        if not group_sets:
            continue
        rows.append(f"""
      <div class="legend-subhead">{title}</div>""")
        for s in group_sets:
            checked = "" if s.get("default_off") else " checked"
            rows.append(f"""
      <label class="legend-row toggle-row" data-set-id="{s['id']}">
        <input type="checkbox" class="set-toggle" data-set-id="{s['id']}"{checked} />
        <div class="leg-marker leg-glyph" style="background:{s['color']}">{s.get('glyph','')}</div>
        <span class="leg-label">{s['label']}</span>
      </label>""")
    # Distance rings — a measurement overlay (not a hotel set), toggled on its own.
    rows.append(f"""
      <div class="legend-subhead">Distance from AKA White House</div>
      <label class="legend-row ring-row is-off" data-ring-toggle="1">
        <input type="checkbox" class="ring-toggle" />
        <div class="leg-marker" style="background:{SUBJECT_COLOR}22; border:2px solid {SUBJECT_COLOR}; box-shadow:none;"></div>
        <span class="leg-label">Radius rings (&frac12; / 1 / 1&frac12; mi)</span>
      </label>""")
    # Show All / Hide All buttons
    rows.append("""
      <div class="legend-controls">
        <button type="button" id="legend-show-all" class="legend-btn">Show all</button>
        <button type="button" id="legend-hide-all" class="legend-btn">Hide all</button>
        <button type="button" id="legend-fit" class="legend-btn">Zoom to visible</button>
      </div>""")
    return "\n".join(rows)


def build_hotels_js(merged):
    """Build the JS array for all hotels (subject + merged comps)."""
    out = ["const SUBJECT = {",
           f"  name: {json.dumps(SUBJECT['name'])},",
           f"  address: {json.dumps(SUBJECT['address'] + ', ' + SUBJECT['city_state'] + ' ' + SUBJECT['zip'])},",
           f"  rooms: {SUBJECT['rooms']},",
           f"  strId: {json.dumps(SUBJECT['str_id'])},",
           f"  lat: {SUBJECT_LAT}, lng: {SUBJECT_LNG},",
           f"  occ: {json.dumps(SUBJECT['occ'])},",
           f"  adr: {json.dumps(SUBJECT['adr'])},",
           f"  revpar: {json.dumps(SUBJECT['revpar'])},",
           "};",
           "",
           "const SETS = ["]
    for s in COMP_SETS:
        obj = {
            "id": s["id"],
            "label": s["label"],
            "short": s["short"],
            "color": s["color"],
        }
        if s.get("glyph"):
            obj["glyph"] = s["glyph"]
        if s.get("supply"):
            obj["supply"] = s["supply"]  # "add" | "remove"
        if s.get("group"):
            obj["group"] = s["group"]
        if s.get("default_off"):
            obj["defaultOff"] = True
        out.append("  " + json.dumps(obj) + ",")
    out.append("];")
    out.append("")
    out.append("const HOTELS = [")
    for h in merged:
        memberships_js = json.dumps(h["memberships"])
        anchor_js = json.dumps(h["anchor_for"])
        out.append("  {")
        out.append(f"    name: {json.dumps(h['name'])},")
        out.append(f"    strId: {json.dumps(h['str_id'])},")
        out.append(f"    cityState: {json.dumps(h['city_state'])},")
        out.append(f"    zip: {json.dumps(h['zip'])},")
        out.append(f"    rooms: {h['rooms']},")
        out.append(f"    klass: {json.dumps(h.get('klass',''))},")
        out.append(f"    lat: {h.get('lat',0)}, lng: {h.get('lng',0)},")
        out.append(f"    memberships: {memberships_js},")
        out.append(f"    primarySet: {json.dumps(h['primary_set_id'])},")
        out.append(f"    anchorFor: {anchor_js},")
        out.append(f"    anchorPerfs: {json.dumps(h.get('anchor_perfs', []))},")
        out.append(f"    akaNum: {h.get('aka_num', 0)},")
        out.append(f"    brand: {json.dumps(h.get('brand', ''))},")
        out.append(f"    productType: {json.dumps(h.get('product_type', ''))},")
        out.append(f"    openDate: {json.dumps(h.get('open_date', ''))},")
        out.append(f"    omFlag: {json.dumps(h.get('om_flag', ''))},")
        out.append(f"    omNote: {json.dumps(h.get('om_note', ''))},")
        out.append(f"    distMi: {json.dumps(h.get('dist_mi'))},")
        out.append("  },")
    out.append("];")
    return "\n".join(out)


def generate_html(merged, set_perf, supply_stats=None, dc_stats=None, dc_hotels=None):
    legend_html = build_legend_rows()
    perf_html = build_perf_panels_html(set_perf)
    supply_html = build_supply_summary_html(supply_stats)
    dc_summary_html = build_dc_supply_summary_html(dc_stats)
    radius_table_html = build_radius_table_html(dc_hotels)
    hotels_js = build_hotels_js(merged)

    n_sets = len(COMP_ONLY_SETS)
    total_unique = len(merged)
    n_dc = len(dc_hotels) if dc_hotels else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AKA White House — Multi-Comp-Set Map</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      background: #f5f5f5;
    }}
    .header {{
      background: #1a2744;
      border-bottom: 3px solid #2956b2;
      padding: 11px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      z-index: 10;
    }}
    .header-left h1 {{
      font-size: 17px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: 0.3px;
    }}
    .header-left p {{
      font-size: 11px;
      color: #8fa8d8;
      margin-top: 2px;
    }}
    .header-right {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .kpi-card {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 6px;
      padding: 7px 14px;
      text-align: center;
      min-width: 90px;
    }}
    .kpi-card .k-label {{ font-size: 9px; color: #8fa8d8; text-transform: uppercase; letter-spacing: 0.8px; }}
    .kpi-card .k-value {{ font-size: 17px; font-weight: 700; color: #ffffff; line-height: 1.2; margin: 1px 0; }}
    .kpi-card .k-index {{ font-size: 9px; color: #7ed87e; }}
    .kpi-sep {{ width: 1px; height: 36px; background: rgba(255,255,255,0.15); }}
    .str-badge {{
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 4px;
      padding: 4px 10px;
      font-size: 10px;
      color: #8fa8d8;
      margin-left: 10px;
    }}
    .main {{ display: flex; flex: 1; overflow: hidden; }}
    .sidebar {{
      width: 340px;
      background: #ffffff;
      border-right: 1px solid #dde3ed;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      flex-shrink: 0;
      box-shadow: 2px 0 8px rgba(0,0,0,0.06);
      z-index: 5;
    }}
    .sb-section {{ padding: 12px 14px; border-bottom: 1px solid #eaecf0; }}
    .sb-section h3 {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.9px;
      color: #8090b0;
      margin-bottom: 10px;
      font-weight: 600;
    }}
    .legend-row {{
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 6px; font-size: 11.5px; color: #334;
    }}
    .legend-row.toggle-row, .legend-row.ring-row {{
      cursor: pointer;
      user-select: none;
      padding: 2px 4px;
      border-radius: 4px;
      transition: background 0.12s;
    }}
    .legend-row.toggle-row:hover, .legend-row.ring-row:hover {{ background: #f3f6fc; }}
    .legend-row.toggle-row input[type="checkbox"], .legend-row.ring-row input[type="checkbox"] {{
      width: 13px; height: 13px;
      margin: 0;
      flex-shrink: 0;
      cursor: pointer;
      accent-color: #2956b2;
    }}
    .legend-row.ring-row input[type="checkbox"] {{ accent-color: #f59e0b; }}
    .legend-row.toggle-row.is-off .leg-label,
    .legend-row.toggle-row.is-off .leg-marker,
    .legend-row.ring-row.is-off .leg-label,
    .legend-row.ring-row.is-off .leg-marker {{
      opacity: 0.35;
    }}
    .radius-table {{
      width: 100%; border-collapse: collapse; margin-top: 4px;
      font-size: 10px; color: #334;
    }}
    .radius-table th, .radius-table td {{
      padding: 4px 3px; text-align: center; border-bottom: 1px solid #eef1f6;
    }}
    .radius-table thead th {{
      font-size: 9px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.2px; color: #8090b0; border-bottom: 1px solid #dde3ed;
    }}
    .radius-table tbody th {{
      text-align: left; font-weight: 700; color: #1a2744; white-space: nowrap;
    }}
    .radius-table td.rt-tot {{ font-weight: 700; color: #b45309; background: #fff8ec; }}
    .radius-table th.rt-tot {{ color: #b45309; }}
    .radius-table td.rt-keys, .radius-table th.rt-keys {{ color: #8090b0; font-size: 9px; }}
    .leg-marker {{
      width: 14px; height: 14px;
      border-radius: 50%;
      border: 2px solid #ffffff;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.15);
      flex-shrink: 0;
    }}
    .leg-marker.leg-star {{
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: #ffffff; font-size: 9px; font-weight: 700;
    }}
    .leg-label {{ line-height: 1.25; }}
    .leg-marker.leg-glyph {{
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-size: 10px; font-weight: 700; line-height: 1;
    }}
    .legend-subhead {{
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.6px;
      color: #97a3bd; font-weight: 700;
      margin: 9px 0 6px; padding-top: 8px; border-top: 1px dashed #e3e8f0;
    }}
    .legend-controls {{
      display: flex; gap: 5px; margin-top: 9px; flex-wrap: wrap;
    }}
    .legend-btn {{
      flex: 1 1 auto;
      min-width: 0;
      font-size: 10px;
      padding: 5px 7px;
      border: 1px solid #c5d0e0;
      background: #f8fafd;
      color: #1a2744;
      border-radius: 4px;
      cursor: pointer;
      font-family: inherit;
      transition: background 0.12s, border-color 0.12s;
    }}
    .legend-btn:hover {{ background: #eef3fb; border-color: #97a8c5; }}
    .legend-btn:active {{ background: #dde6f3; }}
    .set-perf-card.is-hidden, .hotel-item.is-hidden {{ display: none; }}
    .set-perf-card {{
      background: #f8fafd;
      border: 1px solid #e3e9f3;
      border-radius: 6px;
      padding: 9px 11px;
      margin-bottom: 9px;
    }}
    .set-perf-header {{ display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }}
    .set-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    .set-perf-title {{ font-size: 11.5px; font-weight: 700; color: #1a2744; }}
    .set-perf-period {{ font-size: 9.5px; color: #8090b0; margin-bottom: 6px; }}
    .set-perf-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; }}
    .set-perf-cell {{
      background: #ffffff;
      border: 1px solid #e6ebf3;
      border-radius: 4px;
      padding: 5px 4px;
      text-align: center;
    }}
    .spc-label {{ font-size: 9px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.3px; }}
    .spc-value {{ font-size: 13px; font-weight: 700; color: #1a2744; margin: 1px 0; }}
    .spc-vs {{ font-size: 8.5px; color: #5d6b85; line-height: 1.2; }}
    .hotel-item {{
      display: flex;
      align-items: flex-start;
      gap: 9px;
      padding: 8px 6px;
      border-radius: 5px;
      cursor: pointer;
      transition: background 0.15s;
      border-bottom: 1px solid #f0f2f5;
    }}
    .hotel-item:last-child {{ border-bottom: none; }}
    .hotel-item:hover {{ background: #f0f5ff; }}
    .h-pin {{
      width: 26px; height: 26px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700; color: #fff;
      flex-shrink: 0; margin-top: 1px;
      border: 2px solid #fff;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.15);
    }}
    .h-pin.anchor-pin {{ border: 2px dashed #fff; box-shadow: 0 0 0 2px rgba(0,0,0,0.25); }}
    .h-pin.subject-pin {{ background: {SUBJECT_COLOR}; }}
    .h-info h4 {{ font-size: 12px; font-weight: 600; color: #1a2744; line-height: 1.3; }}
    .h-info .h-meta {{ font-size: 10px; color: #7080a0; margin-top: 1px; }}
    .h-badges {{ margin-top: 4px; display: flex; flex-wrap: wrap; gap: 3px; }}
    .h-badge {{
      display: inline-block;
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 9.5px;
      color: #fff;
      font-weight: 600;
    }}
    .h-badge.subject-badge {{
      background: {SUBJECT_COLOR};
    }}
    .sidebar-footer {{
      padding: 8px 14px;
      font-size: 9.5px;
      color: #aabbd0;
      border-top: 1px solid #eaecf0;
      margin-top: auto;
      line-height: 1.45;
    }}
    #map {{ flex: 1; }}
    .gm-iw {{
      font-family: 'Segoe UI', Arial, sans-serif;
      min-width: 240px;
      max-width: 280px;
    }}
    .gm-iw-title {{ font-size: 14px; font-weight: 700; color: #1a2744; line-height: 1.3; margin-bottom: 2px; }}
    .gm-iw-brand {{ font-size: 10px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 4px; }}
    .gm-iw-meta {{ font-size: 11px; color: #556; margin-bottom: 3px; }}
    .gm-iw-badges {{ margin-top: 4px; display: flex; flex-wrap: wrap; gap: 3px; }}
    .gm-iw-divider {{ border: none; border-top: 1px solid #eaecf0; margin: 8px 0; }}
    .gm-iw-stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-top: 6px; }}
    .gm-stat {{ text-align: center; }}
    .gm-stat-label {{ font-size: 9px; color: #8090b0; text-transform: uppercase; }}
    .gm-stat-value {{ font-size: 14px; font-weight: 700; color: #1565c0; }}
    .gm-stat-idx {{ font-size: 8.5px; color: #2d8a2d; font-weight: 600; margin-top: 1px; }}
    .h-stats {{
      display: flex; gap: 8px; margin-top: 5px;
      font-size: 10px; color: #5d6b85;
    }}
    .h-stat b {{ color: #1565c0; font-weight: 700; }}
    .gm-iw-note {{ font-size: 9px; color: #aabbd0; margin-top: 5px; }}
    .gm-iw-masked {{ font-size: 10px; color: #8090b0; margin-top: 6px; font-style: italic; }}
    .gm-iw-status {{ font-size: 10px; color: #5d6b85; margin-top: 6px; }}
    .gm-iw-supply {{ font-size: 10.5px; color: #445; line-height: 1.5; }}
    .gm-iw-supply .sup-cat {{ font-weight: 700; color: #1a2744; }}
    .om-line {{ margin-top: 6px; font-size: 10px; font-weight: 700; padding: 3px 7px; border-radius: 4px; display: inline-block; }}
    .om-in {{ background: #e6f4ea; color: #1e7e34; }}
    .om-missing {{ background: #fdecea; color: #c0392b; }}
    .om-base, .om-horizon {{ background: #eef1f6; color: #5d6b85; }}
    .om-note {{ margin-top: 5px; font-size: 9.5px; color: #6b7688; line-height: 1.45; font-style: italic; }}
    .supply-summary {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }}
    .supply-cell {{
      background: #f8fafd; border: 1px solid #e3e9f3;
      border-radius: 6px; padding: 8px 4px; text-align: center;
    }}
    .supply-num {{ font-size: 18px; font-weight: 700; line-height: 1.1; }}
    .supply-cap {{ font-size: 8.5px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.3px; margin-top: 2px; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>AKA White House &mdash; Multi-Comp-Set Map</h1>
    <p>Washington, DC &middot; {n_sets} STR comp sets + DC raw new-supply overlay ({n_dc} properties, 2019&ndash;2034) &middot; {total_unique} hotels mapped &middot; R12 thru Mar 2026</p>
  </div>
  <div class="header-right">
    <div class="kpi-card">
      <div class="k-label">AKA WH Occ</div>
      <div class="k-value">{SUBJECT['occ']}</div>
      <div class="k-index">MPI: {SUBJECT['mpi']}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">AKA WH ADR</div>
      <div class="k-value">{SUBJECT['adr']}</div>
      <div class="k-index">ARI: {SUBJECT['ari']}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">AKA WH RevPAR</div>
      <div class="k-value">{SUBJECT['revpar']}</div>
      <div class="k-index">RGI: {SUBJECT['rgi']}</div>
    </div>
    <div class="str-badge">R12 ending Dec 2025</div>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sb-section">
      <h3>Legend</h3>
      {legend_html}
      <div style="margin-top:7px; font-size:9.5px; color:#8090b0; line-height:1.35;">
        Hotels appearing in multiple sets are plotted once, colored by the highest-priority set; all memberships shown as badges. Dashed pin border = STR subject (anchor) for that set. Numbers 1&ndash;6 on the Original AKA WH set match the official AKA WH STR file ordering.
      </div>
    </div>

    <div class="sb-section">
      <h3>R12 Performance by Set</h3>
      {perf_html}
    </div>

    <div class="sb-section">
      <h3>Capital Hilton Submarket Supply Changes</h3>
      {supply_html}
    </div>

    <div class="sb-section">
      <h3>DC Market &mdash; Raw New Supply (toggle layers above)</h3>
      {dc_summary_html}
      <div class="legend-subhead" style="margin-top:12px;">New Supply Within Radius</div>
      {radius_table_html}
    </div>

    <div class="sb-section" style="flex:1; border-bottom:none;">
      <h3>Properties &mdash; Click to Navigate</h3>
      <div id="hotel-list"></div>
    </div>

    <div class="sidebar-footer">
      Sources: STR Monthly STAR (Capital Hilton 2025, Viceroy DC Mar 2026); STR HospitalityDataGrid (AKA WH Luxury / Large Branded / Branded Small / Independent, R12 thru Mar 2026); original AKA WH STR comp set (R12 thru Dec 2025).<br/>
      Subject AKA White House perf carried over from prior single-set map. Per-comp individual perf masked per STR policy.<br/>
      Supply pipeline &amp; closures from the Capital Hilton new-supply map (locations approximate).<br/>
      DC raw new-supply overlay ({n_dc} properties): CBRE 2026 &amp; 2027 Market Overview for DC (06/22/26), cross-referenced vs. 1710 H St OM (04/02/26); addresses geocoded, early-planning/unnamed sites approximate.
    </div>
  </div>

  <div id="map"></div>
</div>

<script>
{hotels_js}

const SET_BY_ID = {{}};
SETS.forEach(s => {{ SET_BY_ID[s.id] = s; }});

let map, infoWindow;
const markers = [];

function svgPin(color, label, anchor=false, star=false) {{
  const labelText = star ? '★' : (label === '' ? '' : label);
  const fontSize = star ? 18 : 12;
  const stroke = anchor ? '3' : '1.5';
  const strokeDash = anchor ? 'stroke-dasharray="4,2"' : '';
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">
        <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/></filter>
        <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
              fill="${{color}}" stroke="white" stroke-width="${{stroke}}" ${{strokeDash}} filter="url(#s)"/>
        <text x="19" y="22" text-anchor="middle" dominant-baseline="middle"
              font-family="Arial,sans-serif" font-size="${{fontSize}}"
              font-weight="bold" fill="white">${{labelText}}</text>
      </svg>`),
    scaledSize: new google.maps.Size(38, 46),
    anchor: new google.maps.Point(19, 44)
  }};
}}

// Small amber pill label that sits on a distance ring (e.g. "1 mi").
function svgRingLabel(text) {{
  const w = 14 + text.length * 6;
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="18" viewBox="0 0 ' + w + ' 18">' +
      '<rect x="0.5" y="0.5" width="' + (w - 1) + '" height="17" rx="8.5" fill="white" stroke="{SUBJECT_COLOR}" stroke-width="1"/>' +
      '<text x="' + (w / 2) + '" y="13" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="700" fill="#b45309">' + text + '</text>' +
      '</svg>'),
    scaledSize: new google.maps.Size(w, 18),
    anchor: new google.maps.Point(w / 2, 9)
  }};
}}

// Glyph shown on the pin, driven by the set it's displayed as:
//  - supply layers      -> the set's own glyph (+ addition, ✕ removal, ✓ completed, ◇ planned)
//  - AKA Original set    -> number 1-6 (official AKA WH STR file ordering, incl. Hampton)
//  - everything else     -> blank (anchors get a dashed border instead)
function pinGlyph(h, primary) {{
  if (!primary) return '';
  if (primary.glyph) return primary.glyph;
  if (primary.id === 'aka_orig' && h.akaNum) return String(h.akaNum);
  return '';
}}

// Does a hotel belong to any *removal* supply layer (closures)? Drives strikethrough.
function isRemovalHotel(h) {{
  return (h.memberships || []).some(sid => (SET_BY_ID[sid] || {{}}).supply === 'remove');
}}
function isAdditionHotel(h) {{
  return (h.memberships || []).some(sid => (SET_BY_ID[sid] || {{}}).supply === 'add');
}}

function membershipBadges(h, inline=false, only=null) {{
  // `only` = Set<setId> of active sets; null = all memberships.
  const cls = inline ? 'gm-iw-badges' : 'h-badges';
  const mships = only
    ? h.memberships.filter(sid => only.has(sid))
    : h.memberships;
  const items = mships.map(sid => {{
    const s = SET_BY_ID[sid];
    const isAnchor = (h.anchorFor || []).includes(sid);
    const label = (isAnchor ? '★ ' : '') + s.short;
    return `<span class="h-badge" style="background:${{s.color}}">${{label}}</span>`;
  }}).join('');
  return `<div class="${{cls}}">${{items}}</div>`;
}}

// Track which sets are active. Start with all enabled EXCEPT default-off layers
// (the DC raw new-supply overlay loads off so the base map is unchanged).
const ACTIVE_SETS = new Set(SETS.filter(s => !s.defaultOff).map(s => s.id));

// Per-hotel records (populated in initMap) so we can re-render on toggle.
const HOTEL_RECORDS = [];

function visiblePrimary(h, active) {{
  // Anchor-aware: if hotel anchors any *visible* set, color by that anchor's highest-priority.
  const visAnchors = (h.anchorFor || []).filter(sid => active.has(sid));
  if (visAnchors.length) {{
    return SET_BY_ID[visAnchors[0]]; // already sorted by priority server-side
  }}
  const visMships = h.memberships.filter(sid => active.has(sid));
  return visMships.length ? SET_BY_ID[visMships[0]] : null;
}}

function refreshFromToggles() {{
  // 1. Hotels: recompute visibility + primary set + marker icon + sidebar
  HOTEL_RECORDS.forEach(rec => {{
    const primary = visiblePrimary(rec.hotel, ACTIVE_SETS);
    if (!primary) {{
      rec.marker.setMap(null);
      rec.item.classList.add('is-hidden');
      return;
    }}
    rec.marker.setMap(map);
    rec.item.classList.remove('is-hidden');
    // Anchor styling only if the anchor set is visible
    const isVisibleAnchor = (rec.hotel.anchorFor || []).some(sid => ACTIVE_SETS.has(sid));
    const glyph = pinGlyph(rec.hotel, primary);
    rec.marker.setIcon(svgPin(primary.color, glyph, isVisibleAnchor, false));
    // Refresh sidebar item color + visible badges
    const pinEl = rec.item.querySelector('.h-pin');
    pinEl.style.background = primary.color;
    pinEl.style.borderStyle = isVisibleAnchor ? 'dashed' : 'solid';
    pinEl.textContent = glyph || (isVisibleAnchor ? '★' : '');
    const badgesEl = rec.item.querySelector('.h-badges');
    badgesEl.outerHTML = membershipBadges(rec.hotel, false, ACTIVE_SETS);
    // Rebuild info window content too
    rec.refreshIw(primary, isVisibleAnchor);
  }});

  // 2. Per-set perf panels: show/hide
  document.querySelectorAll('.set-perf-card[data-set-id]').forEach(card => {{
    const sid = card.getAttribute('data-set-id');
    card.classList.toggle('is-hidden', !ACTIVE_SETS.has(sid));
  }});

  // 3. Legend row dimming
  document.querySelectorAll('.legend-row.toggle-row').forEach(row => {{
    const sid = row.getAttribute('data-set-id');
    row.classList.toggle('is-off', !ACTIVE_SETS.has(sid));
  }});
}}

function initMap() {{
  map = new google.maps.Map(document.getElementById('map'), {{
    center: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
    zoom: 14,
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

  infoWindow = new google.maps.InfoWindow({{ maxWidth: 300 }});

  new google.maps.Circle({{
    map,
    center: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
    radius: 800,
    strokeColor: '{SUBJECT_COLOR}',
    strokeOpacity: 0.4,
    strokeWeight: 1.5,
    fillColor: '{SUBJECT_COLOR}',
    fillOpacity: 0.04,
    clickable: false
  }});

  // ── Distance rings (½ / 1 / 1½ mi) — measurement overlay, default off ──
  const M_PER_MI = 1609.344;
  const RING_DEFS = [
    {{ mi: 0.5, label: '½ mi',  fill: 0.07,  strokeOp: 0.9  }},
    {{ mi: 1.0, label: '1 mi',       fill: 0.045, strokeOp: 0.7  }},
    {{ mi: 1.5, label: '1½ mi', fill: 0.03,  strokeOp: 0.55 }},
  ];
  const ringOverlays = [];
  // Draw largest first so inner rings render on top (cumulative amber shading).
  RING_DEFS.slice().reverse().forEach((rd, i) => {{
    ringOverlays.push(new google.maps.Circle({{
      map: null,
      center: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
      radius: rd.mi * M_PER_MI,
      strokeColor: '{SUBJECT_COLOR}', strokeOpacity: rd.strokeOp, strokeWeight: 1.5,
      fillColor: '{SUBJECT_COLOR}', fillOpacity: rd.fill,
      clickable: false, zIndex: i
    }}));
  }});
  const ringLabels = RING_DEFS.map(rd => new google.maps.Marker({{
    map: null,
    position: {{ lat: SUBJECT.lat + (rd.mi * M_PER_MI) / 111320, lng: SUBJECT.lng }},
    icon: svgRingLabel(rd.label),
    clickable: false, zIndex: 900
  }}));
  function setRingsVisible(on) {{
    ringOverlays.forEach(c => c.setMap(on ? map : null));
    ringLabels.forEach(m => m.setMap(on ? map : null));
  }}

  const bounds = new google.maps.LatLngBounds();
  const listEl = document.getElementById('hotel-list');

  // SUBJECT (gold star) — always rendered first, highest zIndex
  const subjMarker = new google.maps.Marker({{
    position: {{ lat: SUBJECT.lat, lng: SUBJECT.lng }},
    map,
    icon: svgPin('{SUBJECT_COLOR}', '', false, true),
    title: SUBJECT.name,
    zIndex: 1000
  }});
  bounds.extend({{ lat: SUBJECT.lat, lng: SUBJECT.lng }});
  const subjIw = `
    <div class="gm-iw">
      <div class="gm-iw-title">${{SUBJECT.name}}</div>
      <div class="gm-iw-meta">${{SUBJECT.address}}</div>
      <div class="gm-iw-meta">${{SUBJECT.rooms}} keys &middot; STR ID: ${{SUBJECT.strId}}</div>
      <div class="gm-iw-badges"><span class="h-badge subject-badge">Subject Property</span></div>
      <hr class="gm-iw-divider"/>
      <div class="gm-iw-stats">
        <div class="gm-stat"><div class="gm-stat-label">OCC</div><div class="gm-stat-value">${{SUBJECT.occ}}</div></div>
        <div class="gm-stat"><div class="gm-stat-label">ADR</div><div class="gm-stat-value">${{SUBJECT.adr}}</div></div>
        <div class="gm-stat"><div class="gm-stat-label">RevPAR</div><div class="gm-stat-value">${{SUBJECT.revpar}}</div></div>
      </div>
      <div class="gm-iw-note">R12 ending Dec 2025 &middot; Source: STR</div>
    </div>`;
  subjMarker.addListener('click', () => {{ infoWindow.setContent(subjIw); infoWindow.open(map, subjMarker); }});

  // Sidebar entry for subject
  const subjItem = document.createElement('div');
  subjItem.className = 'hotel-item';
  subjItem.innerHTML = `
    <div class="h-pin subject-pin">★</div>
    <div class="h-info">
      <h4>${{SUBJECT.name}}</h4>
      <div class="h-meta">${{SUBJECT.address}}</div>
      <div class="h-badges"><span class="h-badge subject-badge">Subject</span></div>
    </div>`;
  subjItem.addEventListener('click', () => {{
    map.panTo({{ lat: SUBJECT.lat, lng: SUBJECT.lng }});
    map.setZoom(16);
    infoWindow.setContent(subjIw);
    infoWindow.open(map, subjMarker);
  }});
  listEl.appendChild(subjItem);

  // Comps
  HOTELS.forEach((h, i) => {{
    if (!h.lat || !h.lng) return;
    const primary = SET_BY_ID[h.primarySet];
    const isAnchor = (h.anchorFor || []).length > 0;
    const isRemoval = isRemovalHotel(h);            // any closure layer
    const isPipeline = h.memberships.includes('new_supply');  // legacy Cap-Hilton pipeline
    const isDcSupply = !!h.omFlag;                   // DC raw new-supply hotel
    const roomsText = (!h.rooms)
      ? (isPipeline ? 'Rooms TBD' : '')
      : (h.rooms.toLocaleString() + ' keys' + (isRemoval ? ' removed' : ''));
    const icon = svgPin(primary.color, pinGlyph(h, primary), isAnchor, false);

    const initiallyVisible = h.memberships.some(sid => ACTIVE_SETS.has(sid));
    const marker = new google.maps.Marker({{
      position: {{ lat: h.lat, lng: h.lng }},
      map: initiallyVisible ? map : null,
      icon,
      title: h.name,
      zIndex: 100 + i
    }});
    markers.push(marker);
    // Only frame the initial view around layers that load on (DC overlay is off).
    if (initiallyVisible) bounds.extend({{ lat: h.lat, lng: h.lng }});

    let iwHtml = '';
    const refreshIw = (pri, anchorVisible) => {{
      const anchorSets = (h.anchorFor || []).filter(sid => ACTIVE_SETS.has(sid));
      // Anchor properties (Cap Hilton, Viceroy) carry their own R12 perf —
      // show it regardless of toggle state since the property's perf is intrinsic.
      let statsBlock = '';
      if (h.anchorPerfs && h.anchorPerfs.length) {{
        const p = h.anchorPerfs[0];
        const setHidden = !ACTIVE_SETS.has(p.set_id);
        statsBlock = `
          <hr class="gm-iw-divider"/>
          <div class="gm-iw-stats">
            <div class="gm-stat">
              <div class="gm-stat-label">OCC</div>
              <div class="gm-stat-value">${{p.occ}}</div>
              <div class="gm-stat-idx">MPI ${{p.mpi}}</div>
            </div>
            <div class="gm-stat">
              <div class="gm-stat-label">ADR</div>
              <div class="gm-stat-value">${{p.adr}}</div>
              <div class="gm-stat-idx">ARI ${{p.ari}}</div>
            </div>
            <div class="gm-stat">
              <div class="gm-stat-label">RevPAR</div>
              <div class="gm-stat-value">${{p.revpar}}</div>
              <div class="gm-stat-idx">RGI ${{p.rgi}}</div>
            </div>
          </div>
          <div class="gm-iw-note">${{p.period}} &middot; indices vs ${{SET_BY_ID[p.set_id].short}} comp set${{setHidden ? ' (currently hidden)' : ''}}</div>`;
      }} else if (isDcSupply) {{
        const CATLABEL = {{dc_recent:'Recently completed', dc_pipeline:'Pipeline &mdash; under construction', dc_reduction:'Supply reduction (closure)', dc_planning:'2028+ early planning'}};
        const VERB = {{dc_recent:'Opened', dc_pipeline:'Opens', dc_reduction:'Closed', dc_planning:'Target'}};
        const OMDISP = {{'in':'✔ In OM competitive-supply page', 'missing':'✖ Omitted from OM competitive-supply page', 'base':'Base year &mdash; embedded in YE2019 supply', 'horizon':'Beyond OM\\'s stated horizon'}};
        const dcSid = h.memberships.find(sid => (SET_BY_ID[sid] || {{}}).group === 'dc_supply') || h.primarySet;
        const cat = CATLABEL[dcSid] || 'DC new supply';
        const isEst = dcSid === 'dc_pipeline' || dcSid === 'dc_planning';
        const dateTxt = (h.openDate && h.openDate !== 'TBD')
          ? ((VERB[dcSid] || 'Date') + ' ' + h.openDate + (isEst ? ' (est.)' : ''))
          : 'Date TBD';
        const kw = dcSid === 'dc_reduction' ? 'removed' : (dcSid === 'dc_planning' ? 'planned' : 'added');
        const keysTxt = h.rooms ? (h.rooms.toLocaleString() + ' keys ' + kw) : '';
        statsBlock = `
          <hr class="gm-iw-divider"/>
          <div class="gm-iw-supply">
            <div><span class="sup-cat">${{cat}}</span> &middot; ${{dateTxt}}</div>
            ${{keysTxt ? '<div>' + keysTxt + '</div>' : ''}}
            ${{h.productType ? '<div>Product: ' + h.productType + '</div>' : ''}}
            ${{h.distMi != null ? '<div><b>' + h.distMi + ' mi</b> from AKA White House</div>' : ''}}
            <div class="om-line om-${{h.omFlag}}">${{OMDISP[h.omFlag] || ''}}</div>
            ${{h.omNote ? '<div class="om-note">' + h.omNote + '</div>' : ''}}
          </div>`;
      }} else if (isPipeline) {{
        statsBlock = `
          <hr class="gm-iw-divider"/>
          <div class="gm-iw-status"><b>New supply</b> &mdash; pipeline / under development. Adds keys to the submarket; room count TBD.</div>`;
      }} else if (isRemoval) {{
        statsBlock = `
          <hr class="gm-iw-divider"/>
          <div class="gm-iw-status"><b>Permanently closed</b> &mdash; ${{h.rooms ? h.rooms.toLocaleString() + ' keys removed from the submarket.' : 'supply removed from the submarket.'}}</div>`;
      }} else {{
        statsBlock = `
          <hr class="gm-iw-divider"/>
          <div class="gm-iw-masked">Individual per-comp performance masked per STR policy &mdash; see per-set R12 panels in sidebar.</div>`;
      }}
      const line2 = roomsText
        ? roomsText + (h.strId ? ' &middot; STR ID: ' + h.strId : '')
        : (h.strId ? 'STR ID: ' + h.strId : '');
      iwHtml = `
        <div class="gm-iw">
          <div class="gm-iw-title">${{isRemoval ? '<s>' + h.name + '</s>' : h.name}}</div>
          ${{h.brand ? '<div class="gm-iw-brand">' + h.brand + '</div>' : ''}}
          <div class="gm-iw-meta">${{h.cityState}}${{h.zip ? ' ' + h.zip : ''}}${{h.klass ? ' &middot; ' + h.klass : ''}}</div>
          ${{line2 ? '<div class="gm-iw-meta">' + line2 + '</div>' : ''}}
          ${{membershipBadges(h, true, ACTIVE_SETS)}}
          ${{anchorSets.length ? '<div class="gm-iw-note">★ STR subject for ' + anchorSets.map(sid => SET_BY_ID[sid].short).join(', ') + '</div>' : ''}}
          ${{statsBlock}}
        </div>`;
    }};
    refreshIw(primary, isAnchor);
    marker.addListener('click', () => {{ infoWindow.setContent(iwHtml); infoWindow.open(map, marker); }});

    const item = document.createElement('div');
    item.className = 'hotel-item';
    if (isRemoval) item.style.opacity = '0.8';
    const sidebarStats = (h.anchorPerfs && h.anchorPerfs.length)
      ? `<div class="h-stats">
           <span class="h-stat"><b>${{h.anchorPerfs[0].occ}}</b> Occ</span>
           <span class="h-stat"><b>${{h.anchorPerfs[0].adr}}</b> ADR</span>
           <span class="h-stat"><b>${{h.anchorPerfs[0].revpar}}</b> RevPAR</span>
         </div>`
      : '';
    item.innerHTML = `
      <div class="h-pin" style="background:${{primary.color}};${{isAnchor ? 'border-style:dashed;' : ''}}">${{pinGlyph(h, primary) || (isAnchor ? '★' : '')}}</div>
      <div class="h-info">
        <h4>${{isRemoval ? '<s>' + h.name + '</s>' : h.name}}</h4>
        <div class="h-meta">${{h.cityState}}${{h.zip ? ' ' + h.zip : ''}}${{roomsText ? ' &middot; ' + roomsText : ''}}</div>
        ${{membershipBadges(h, false, ACTIVE_SETS)}}
        ${{sidebarStats}}
      </div>`;
    item.addEventListener('click', () => {{
      map.panTo({{ lat: h.lat, lng: h.lng }});
      map.setZoom(16);
      infoWindow.setContent(iwHtml);
      infoWindow.open(map, marker);
    }});
    if (!initiallyVisible) item.classList.add('is-hidden');
    listEl.appendChild(item);

    HOTEL_RECORDS.push({{ hotel: h, marker, item, refreshIw }});
  }});

  map.fitBounds(bounds, {{ top: 70, right: 70, bottom: 70, left: 70 }});
  // Reconcile marker/sidebar/legend state with the default toggles (DC overlay off).
  refreshFromToggles();

  // ── Wire up the toggle controls ──
  document.querySelectorAll('.set-toggle').forEach(cb => {{
    cb.addEventListener('change', () => {{
      const sid = cb.getAttribute('data-set-id');
      if (cb.checked) ACTIVE_SETS.add(sid);
      else ACTIVE_SETS.delete(sid);
      refreshFromToggles();
    }});
  }});

  // Distance-ring toggle — independent measurement overlay, not a hotel set.
  const ringToggle = document.querySelector('.ring-toggle');
  if (ringToggle) {{
    ringToggle.addEventListener('change', () => {{
      setRingsVisible(ringToggle.checked);
      const row = ringToggle.closest('.ring-row');
      if (row) row.classList.toggle('is-off', !ringToggle.checked);
    }});
  }}

  document.getElementById('legend-show-all').addEventListener('click', () => {{
    document.querySelectorAll('.set-toggle').forEach(cb => {{
      cb.checked = true;
      ACTIVE_SETS.add(cb.getAttribute('data-set-id'));
    }});
    refreshFromToggles();
  }});

  document.getElementById('legend-hide-all').addEventListener('click', () => {{
    document.querySelectorAll('.set-toggle').forEach(cb => {{
      cb.checked = false;
      ACTIVE_SETS.delete(cb.getAttribute('data-set-id'));
    }});
    refreshFromToggles();
  }});

  document.getElementById('legend-fit').addEventListener('click', () => {{
    const b = new google.maps.LatLngBounds();
    b.extend({{ lat: SUBJECT.lat, lng: SUBJECT.lng }});
    let any = false;
    HOTEL_RECORDS.forEach(rec => {{
      if (rec.marker.getMap()) {{
        b.extend({{ lat: rec.hotel.lat, lng: rec.hotel.lng }});
        any = true;
      }}
    }});
    if (any) map.fitBounds(b, {{ top: 70, right: 70, bottom: 70, left: 70 }});
    else map.panTo({{ lat: SUBJECT.lat, lng: SUBJECT.lng }});
  }});
}}
</script>

<script
  src="https://maps.googleapis.com/maps/api/js?key={API_KEY}&callback=initMap"
  async defer>
</script>
</body>
</html>
"""
    return html


# ── Deploy helpers (subprocess wrappers) ──

def run_git(*args, check=True):
    cmd = ["git", "-C", REPO_DIR, *args]
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout: print(r.stdout.rstrip())
    if r.stderr: print(r.stderr.rstrip())
    if check and r.returncode != 0:
        raise RuntimeError(f"git failed (exit {r.returncode})")
    return r


def deploy(commit_msg):
    print("\n-- Deploying --")
    # geocache.json is gitignored (local cache) — don't stage it.
    run_git("add", f"{OUTPUT_SLUG}/index.html", "generate_aka_wh_multi_map.py")
    status = run_git("status", "--porcelain", check=False)
    if not status.stdout.strip():
        print("Nothing to commit.")
        return
    run_git("commit", "-m", commit_msg)
    run_git("push", "origin", "main")
    url = f"{PAGES_BASE_URL}/{OUTPUT_SLUG}/"
    print(f"\nPush complete. URL: {url}")
    print("GitHub Pages typically deploys within ~1-2 minutes.")


# ── Main ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", action="store_true", help="commit + push after generating")
    args = parser.parse_args()

    print("Parsing AKA WH segment files…")
    aka_lux_hotels, aka_lux_perf = parse_aka_segment("aka_lux", F_AKA_LUX_PART, F_AKA_LUX_DATA)
    aka_lb_hotels, aka_lb_perf = parse_aka_segment("aka_largebr", F_AKA_LB_PART, F_AKA_LB_DATA)
    aka_bs_hotels, aka_bs_perf = parse_aka_segment("aka_smallbr", F_AKA_BS_PART, F_AKA_BS_DATA)
    aka_ind_hotels, aka_ind_perf = parse_aka_segment("aka_indep", F_AKA_IND_PART, F_AKA_IND_DATA)

    print("Parsing Capital Hilton STR…")
    cap_hotels, cap_perf = parse_str_monthly("cap_hilton", F_CAP_HILTON)

    print("Parsing Viceroy DC STR…")
    vic_hotels, vic_perf = parse_str_monthly("viceroy_dc", F_VICEROY)

    print("Loading original AKA WH comp set…")
    orig_hotels, orig_perf = get_original_aka_set()

    print("Loading Capital Hilton submarket supply changes…")
    pipeline_hotels, former_hotels = get_capital_hilton_supply()
    supply_stats = {
        "pipeline_n": len(pipeline_hotels),
        "former_n": len(former_hotels),
        "keys_removed": sum(h["rooms"] for h in former_hotels),
    }

    print("Loading DC market raw new-supply list…")
    dc_supply = get_dc_new_supply()
    for h in dc_supply:
        h["dist_mi"] = round(haversine_mi(SUBJECT_LAT, SUBJECT_LNG, h["lat"], h["lng"]), 2)
    dc_stats = dc_supply_stats(dc_supply)

    all_lists = [orig_hotels, aka_lux_hotels, aka_lb_hotels, aka_bs_hotels,
                 aka_ind_hotels, cap_hotels, vic_hotels,
                 pipeline_hotels, former_hotels, dc_supply]
    set_perf = {
        "aka_orig":    orig_perf,
        "aka_lux":     aka_lux_perf,
        "aka_largebr": aka_lb_perf,
        "aka_smallbr": aka_bs_perf,
        "aka_indep":   aka_ind_perf,
        "cap_hilton":  cap_perf,
        "viceroy_dc":  vic_perf,
    }

    merged = merge_hotels(all_lists)
    print(f"\nMerged: {len(merged)} unique hotels across {len(all_lists)} sets")

    print("\nGeocoding hotels…")
    cache = load_cache()
    for h in merged:
        geocode_hotel(h, cache)

    html = generate_html(merged, set_perf, supply_stats, dc_stats, dc_supply)
    out_dir = os.path.join(REPO_DIR, OUTPUT_SLUG)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {out_path}")

    if args.deploy:
        deploy(
            "AKA WH map: drop Registry Collection by Wyndham (1626 N Capitol St) from DC "
            "supply overlay\n\n"
            "Removed per research, following the earlier Placemakr 1735 K St and "
            "Apartments by Marriott Bonvoy SE removals. The separate Registry Collection "
            "Hotels 2028+ site (1333 G St NW) is retained. DC overlay now 63 properties; "
            "counts, radius table, and OM-omission tally recompute automatically.\n\n"
            "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_016e56zxGMudTDk755fMnDH5"
        )


if __name__ == "__main__":
    main()
