#!/usr/bin/env python3
"""
STR Comp Set Map Generator
Reads an STR Excel report, extracts the comp set, geocodes addresses,
and generates an interactive Google Maps HTML file.

Usage:
    python generate_str_map.py              # auto-detect newest .xlsx in drop folder
    python generate_str_map.py "path.xlsx"  # explicit file
    python generate_str_map.py --deploy     # generate + push to GitHub Pages
"""

import argparse
import glob
import json
import os
import re
import sys
import time

import pandas as pd
import requests

# ── Configuration ──
PYTHON = sys.executable
DROP_FOLDER = r"C:\Users\acarr\OneDrive\Documents\STR Drops"
REPO_DIR = r"C:\Users\acarr\OneDrive\Documents\Claude\Projects\str-comp-maps"
GEOCACHE_PATH = os.path.join(REPO_DIR, "geocache.json")
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
API_KEY = "AIzaSyCTAmcCrmL2Z-SerlTKHoG3xPQaGcvmKcU"


def find_str_file(explicit_path=None):
    if explicit_path:
        return explicit_path
    files = glob.glob(os.path.join(DROP_FOLDER, "*.xlsx"))
    if not files:
        raise FileNotFoundError(
            f"No .xlsx files found in {DROP_FOLDER}. Drop an STR file there and try again."
        )
    newest = max(files, key=os.path.getmtime)
    print(f"Auto-detected STR file: {os.path.basename(newest)}")
    return newest


def parse_response_sheet(path, sheet_suffix=""):
    """Parse the Response sheet for hotel list and metadata.

    sheet_suffix: "" for standard files; "_1", "_2", ... for multi-comp-set
    files that have Response_1, Response_2, etc.
    """
    df = pd.read_excel(path, sheet_name=f"Response{sheet_suffix}", header=None)

    # Extract subject address from row 1, col 1
    address_raw = str(df.iloc[1, 1])
    # Format: "Capital Hilton   1001 16th St NW   Washington, DC 20036   United States   Phone: ..."
    parts = [p.strip() for p in re.split(r"\s{2,}", address_raw) if p.strip()]
    # parts[0] = hotel name, parts[1] = street, parts[2] = city/state/zip, ...
    subject_street = parts[1] if len(parts) > 1 else ""

    # Extract report period from row 3, col 1
    period_raw = str(df.iloc[3, 1])
    period_match = re.search(r"For the Month of:\s*(\w+ \d{4})", period_raw)
    report_period = period_match.group(1) if period_match else "Unknown"

    # Parse hotel rows starting at row 22
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

        is_subject = row == 22
        hotel = {
            "name": str(name).strip(),
            "str_id": str_id,
            "city_state": city_state.replace(",", ", "),
            "zip": zip_code,
            "rooms": rooms,
            "subject": is_subject,
            "address": subject_street if is_subject else "",
        }
        hotels.append(hotel)
        row += 1

    # Total comp rooms from STR total row (next row after last hotel)
    total_row = row
    if total_row < len(df) and pd.notna(df.iloc[total_row, 7]):
        comp_rooms = int(df.iloc[total_row, 7])
    else:
        comp_rooms = sum(h["rooms"] for h in hotels if not h["subject"])

    return hotels, report_period, subject_street, comp_rooms


def parse_glance_sheet(path, sheet_suffix=""):
    """Parse the Glance sheet for R12 performance metrics."""
    df = pd.read_excel(path, sheet_name=f"Glance{sheet_suffix}", header=None)

    # Find the Running 12 Month row
    r12_row = None
    for i in range(len(df)):
        val = df.iloc[i, 3] if pd.notna(df.iloc[i, 3]) else ""
        if "Running 12 Month" in str(val):
            r12_row = i
            break

    if r12_row is None:
        print("WARNING: Could not find Running 12 Month row in Glance sheet")
        return {}

    def safe_float(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    subj_occ = safe_float(df.iloc[r12_row, 6])
    comp_occ = safe_float(df.iloc[r12_row, 7])
    mpi = safe_float(df.iloc[r12_row, 8])
    subj_adr = safe_float(df.iloc[r12_row, 11])
    comp_adr = safe_float(df.iloc[r12_row, 12])
    ari = safe_float(df.iloc[r12_row, 13])
    subj_revpar = safe_float(df.iloc[r12_row, 16])
    comp_revpar = safe_float(df.iloc[r12_row, 17])
    rgi = safe_float(df.iloc[r12_row, 18])

    return {
        "subj_occ": f"{subj_occ:.1f}%",
        "comp_occ": f"{comp_occ:.1f}%",
        "mpi": f"{mpi:.1f}",
        "subj_adr": f"${subj_adr:.1f}",
        "comp_adr": f"${comp_adr:.1f}",
        "ari": f"{ari:.1f}",
        "subj_revpar": f"${subj_revpar:.1f}",
        "comp_revpar": f"${comp_revpar:.1f}",
        "rgi": f"{rgi:.1f}",
    }


def geocode(hotel_name, address, city_state, zip_code):
    """Geocode a hotel address using Google Maps API with caching."""
    cache = {}
    if os.path.exists(GEOCACHE_PATH):
        with open(GEOCACHE_PATH, "r") as f:
            cache = json.load(f)

    query = f"{hotel_name}, {address}, {city_state} {zip_code}".strip(", ")
    if query in cache:
        print(f"  [cached] {hotel_name}")
        return cache[query]

    print(f"  [geocoding] {hotel_name}...")
    resp = requests.get(GEOCODE_URL, params={"address": query, "key": API_KEY}).json()
    if resp.get("results"):
        loc = resp["results"][0]["geometry"]["location"]
        cache[query] = loc
        with open(GEOCACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
        time.sleep(0.1)
        return loc

    print(f"  WARNING: Could not geocode {hotel_name}")
    return None


def geocode_all(hotels):
    """Geocode all hotels in the list."""
    print("\nGeocoding hotels...")
    for h in hotels:
        loc = geocode(h["name"], h.get("address", ""), h["city_state"], h["zip"])
        if loc:
            h["lat"] = loc["lat"]
            h["lng"] = loc["lng"]
        else:
            h["lat"] = 0
            h["lng"] = 0
    print(f"  All {len(hotels)} hotels geocoded.\n")


def generate_html(hotels, perf, report_period, comp_rooms):
    """Generate the Google Maps HTML file."""
    subject = next(h for h in hotels if h["subject"])
    comps = [h for h in hotels if not h["subject"]]
    hotel_name = subject["name"]

    # Build HOTELS JavaScript array
    hotels_js = "const HOTELS = [\n"
    for i, h in enumerate(hotels):
        occ_line = ""
        if h["subject"] and perf:
            occ_line = f'      occ: "{perf["subj_occ"]}", adr: "{perf["subj_adr"]}", revpar: "{perf["subj_revpar"]}",'
        hotels_js += f"""    {{
      id: {i}, subject: {'true' if h['subject'] else 'false'},
      name: "{h['name']}", brand: "",
      operator: "",
      address: "{h.get('address', '')}, {h['city_state']} {h['zip']}".trim(),
      city: "{h['city_state']}",
      rooms: {h['rooms']}, strId: "{h['str_id']}",
      lat: {h['lat']}, lng: {h['lng']},
{occ_line}
    }},\n"""
    hotels_js += "  ];"

    # Compute map center
    avg_lat = sum(h["lat"] for h in hotels) / len(hotels)
    avg_lng = sum(h["lng"] for h in hotels) / len(hotels)

    # Performance values for header and sidebar
    subj_occ = perf.get("subj_occ", "N/A")
    subj_adr = perf.get("subj_adr", "N/A")
    subj_revpar = perf.get("subj_revpar", "N/A")
    mpi = perf.get("mpi", "N/A")
    ari = perf.get("ari", "N/A")
    rgi = perf.get("rgi", "N/A")
    comp_occ = perf.get("comp_occ", "N/A")
    comp_adr = perf.get("comp_adr", "N/A")
    comp_revpar = perf.get("comp_revpar", "N/A")

    # Format ADR/RevPAR for sidebar (round to whole dollars)
    def round_dollar(val):
        if val == "N/A":
            return val
        try:
            return "$" + str(int(round(float(val.replace("$", "")))))
        except ValueError:
            return val

    subj_adr_short = round_dollar(subj_adr)
    subj_revpar_short = round_dollar(subj_revpar)
    comp_adr_short = round_dollar(comp_adr)
    comp_revpar_short = round_dollar(comp_revpar)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{hotel_name} – STR Comp Set Map</title>
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
    .kpi-card .k-label {{
      font-size: 9px;
      color: #8fa8d8;
      text-transform: uppercase;
      letter-spacing: 0.8px;
    }}
    .kpi-card .k-value {{
      font-size: 17px;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.2;
      margin: 1px 0;
    }}
    .kpi-card .k-index {{
      font-size: 9px;
      color: #7ed87e;
    }}
    .kpi-sep {{
      width: 1px;
      height: 36px;
      background: rgba(255,255,255,0.15);
    }}
    .str-badge {{
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 4px;
      padding: 4px 10px;
      font-size: 10px;
      color: #8fa8d8;
      margin-left: 10px;
    }}
    .main {{
      display: flex;
      flex: 1;
      overflow: hidden;
    }}
    .sidebar {{
      width: 290px;
      background: #ffffff;
      border-right: 1px solid #dde3ed;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      flex-shrink: 0;
      box-shadow: 2px 0 8px rgba(0,0,0,0.06);
      z-index: 5;
    }}
    .sb-section {{
      padding: 14px 14px;
      border-bottom: 1px solid #eaecf0;
    }}
    .sb-section h3 {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.9px;
      color: #8090b0;
      margin-bottom: 10px;
      font-weight: 600;
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      font-size: 12px;
      color: #334;
    }}
    .leg-dot {{
      width: 13px; height: 13px;
      border-radius: 50%;
      border: 2px solid rgba(0,0,0,0.15);
      flex-shrink: 0;
    }}
    .perf-label {{
      font-size: 10px;
      color: #8090b0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 8px 0 5px;
      font-weight: 600;
    }}
    .perf-label:first-child {{ margin-top: 0; }}
    .perf-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 5px;
    }}
    .perf-cell {{
      background: #f5f8ff;
      border: 1px solid #dce6f7;
      border-radius: 5px;
      padding: 6px 4px;
      text-align: center;
    }}
    .perf-cell.comp-cell {{
      background: #f8f8f8;
      border-color: #e0e0e0;
    }}
    .p-metric {{ font-size: 9px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.4px; }}
    .p-value {{ font-size: 13px; font-weight: 700; color: #1a2744; margin: 1px 0; }}
    .p-index {{ font-size: 9px; color: #2d8a2d; font-weight: 600; }}
    .perf-cell.comp-cell .p-value {{ color: #444; }}
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
    .hotel-item.is-subject {{ background: #fff5f5; }}
    .hotel-item.is-subject:hover {{ background: #ffe8e8; }}
    .h-pin {{
      width: 24px; height: 24px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700;
      flex-shrink: 0;
      margin-top: 1px;
    }}
    .pin-subject {{ background: #c62828; color: #fff; }}
    .pin-comp    {{ background: #1565c0; color: #fff; }}
    .h-info h4 {{
      font-size: 12px; font-weight: 600; color: #1a2744; line-height: 1.3;
    }}
    .h-info .h-meta {{
      font-size: 10px; color: #7080a0; margin-top: 1px;
    }}
    .h-badge {{
      display: inline-block;
      background: #e8f0fe;
      border: 1px solid #c5d5f5;
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 10px;
      color: #1a56c4;
      margin-top: 3px;
    }}
    .h-badge.subject-badge {{
      background: #fdecea;
      border-color: #f5c0bc;
      color: #b71c1c;
      margin-left: 4px;
    }}
    .sidebar-footer {{
      padding: 8px 14px;
      font-size: 10px;
      color: #aabbd0;
      border-top: 1px solid #eaecf0;
      margin-top: auto;
    }}
    #map {{ flex: 1; }}
    .gm-iw {{
      font-family: 'Segoe UI', Arial, sans-serif;
      min-width: 230px;
      max-width: 270px;
    }}
    .gm-iw-title {{
      font-size: 14px; font-weight: 700; color: #1a2744;
      line-height: 1.3; margin-bottom: 2px;
    }}
    .gm-iw-brand {{
      font-size: 10px; color: #8090b0; text-transform: uppercase;
      letter-spacing: 0.5px; margin-bottom: 8px;
    }}
    .gm-iw-meta {{ font-size: 11px; color: #556; margin-bottom: 3px; }}
    .gm-iw-badge {{
      display: inline-block;
      background: #e8f0fe; border: 1px solid #c5d5f5;
      border-radius: 3px; padding: 2px 6px;
      font-size: 10px; color: #1a56c4; margin-bottom: 6px;
    }}
    .gm-iw-subject-badge {{
      display: inline-block;
      background: #fdecea; border: 1px solid #f5c0bc;
      border-radius: 3px; padding: 2px 6px;
      font-size: 10px; color: #b71c1c;
      margin-left: 5px; margin-bottom: 6px;
    }}
    .gm-iw-divider {{
      border: none; border-top: 1px solid #eaecf0;
      margin: 8px 0;
    }}
    .gm-iw-stats {{
      display: grid; grid-template-columns: 1fr 1fr 1fr;
      gap: 6px; margin-top: 6px;
    }}
    .gm-stat {{ text-align: center; }}
    .gm-stat-label {{ font-size: 9px; color: #8090b0; text-transform: uppercase; }}
    .gm-stat-value {{ font-size: 15px; font-weight: 700; color: #1565c0; }}
    .gm-iw-note {{ font-size: 9px; color: #aabbd0; margin-top: 5px; }}
    .gm-iw-masked {{ font-size: 10px; color: #aabbd0; margin-top: 6px; font-style: italic; }}
    .gm-iw-str {{ font-size: 10px; color: #c0c8da; margin-top: 4px; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>{hotel_name} &mdash; STR Competitive Set Map</h1>
    <p>{subject['city_state']} &nbsp;&middot;&nbsp; STR Report: {report_period} &nbsp;&middot;&nbsp; 1 Subject + {len(comps)} Comps &nbsp;&middot;&nbsp; {comp_rooms:,} Comp Rooms</p>
  </div>
  <div class="header-right">
    <div class="kpi-card">
      <div class="k-label">Occupancy</div>
      <div class="k-value">{subj_occ}</div>
      <div class="k-index">MPI: {mpi}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">ADR</div>
      <div class="k-value">{subj_adr}</div>
      <div class="k-index">ARI: {ari}</div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-card">
      <div class="k-label">RevPAR</div>
      <div class="k-value">{subj_revpar}</div>
      <div class="k-index">RGI: {rgi}</div>
    </div>
    <div class="str-badge">Running 12-Month &middot; {report_period}</div>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sb-section">
      <h3>Legend</h3>
      <div class="legend-row"><div class="leg-dot" style="background:#c62828;"></div> Subject Property</div>
      <div class="legend-row"><div class="leg-dot" style="background:#1565c0;"></div> Competitive Set ({len(comps)} Hotels)</div>
    </div>

    <div class="sb-section">
      <h3>R12 Performance &mdash; {report_period}</h3>
      <div class="perf-label">{hotel_name} (Subject)</div>
      <div class="perf-grid">
        <div class="perf-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{subj_occ}</div>
          <div class="p-index">MPI {mpi}</div>
        </div>
        <div class="perf-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{subj_adr_short}</div>
          <div class="p-index">ARI {ari}</div>
        </div>
        <div class="perf-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{subj_revpar_short}</div>
          <div class="p-index">RGI {rgi}</div>
        </div>
      </div>
      <div class="perf-label" style="margin-top:10px;">Comp Set (Aggregate)</div>
      <div class="perf-grid">
        <div class="perf-cell comp-cell">
          <div class="p-metric">Occ</div>
          <div class="p-value">{comp_occ}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">ADR</div>
          <div class="p-value">{comp_adr_short}</div>
        </div>
        <div class="perf-cell comp-cell">
          <div class="p-metric">RevPAR</div>
          <div class="p-value">{comp_revpar_short}</div>
        </div>
      </div>
    </div>

    <div class="sb-section" style="flex:1; border-bottom:none;">
      <h3>Properties &mdash; Click to Navigate</h3>
      <div id="hotel-list"></div>
    </div>

    <div class="sidebar-footer">
      Source: STR Report &middot; Data through {report_period}<br/>
      Performance set excludes subject property per STR methodology
    </div>
  </div>

  <div id="map"></div>
</div>

<script>
  {hotels_js}

  let map, infoWindow;
  const markers = [];

  function initMap() {{
    const subj = HOTELS.find(h => h.subject);
    map = new google.maps.Map(document.getElementById('map'), {{
      center: {{ lat: {avg_lat}, lng: {avg_lng} }},
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

    infoWindow = new google.maps.InfoWindow({{ maxWidth: 290 }});

    new google.maps.Circle({{
      map,
      center: {{ lat: subj.lat, lng: subj.lng }},
      radius: 800,
      strokeColor: '#c62828',
      strokeOpacity: 0.4,
      strokeWeight: 1.5,
      fillColor: '#c62828',
      fillOpacity: 0.04,
      clickable: false
    }});

    const listEl = document.getElementById('hotel-list');
    const bounds = new google.maps.LatLngBounds();

    HOTELS.forEach((h, i) => {{
      const label = h.subject ? '\u2605' : String(i);
      const color = h.subject ? '#c62828' : '#1565c0';

      const svgIcon = {{
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">
            <filter id="s">
              <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/>
            </filter>
            <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
                  fill="${{color}}" stroke="white" stroke-width="1.5" filter="url(#s)"/>
            <text x="19" y="22" text-anchor="middle" dominant-baseline="middle"
                  font-family="Arial,sans-serif" font-size="${{h.subject ? 14 : 13}}"
                  font-weight="bold" fill="white">${{label}}</text>
          </svg>`),
        scaledSize: new google.maps.Size(38, 46),
        anchor: new google.maps.Point(19, 44)
      }};

      const marker = new google.maps.Marker({{
        position: {{ lat: h.lat, lng: h.lng }},
        map,
        icon: svgIcon,
        title: h.name,
        zIndex: h.subject ? 100 : i
      }});

      markers.push(marker);
      bounds.extend({{ lat: h.lat, lng: h.lng }});

      const statsHtml = h.subject
        ? `<hr class="gm-iw-divider"/>
           <div class="gm-iw-stats">
             <div class="gm-stat"><div class="gm-stat-label">OCC</div><div class="gm-stat-value">${{h.occ}}</div></div>
             <div class="gm-stat"><div class="gm-stat-label">ADR</div><div class="gm-stat-value">${{h.adr}}</div></div>
             <div class="gm-stat"><div class="gm-stat-label">RevPAR</div><div class="gm-stat-value">${{h.revpar}}</div></div>
           </div>
           <div class="gm-iw-note">Running 12-Month &middot; Source: STR</div>`
        : `<div class="gm-iw-masked">Individual comp performance masked per STR policy</div>`;

      const iwContent = `
        <div class="gm-iw">
          <div class="gm-iw-title">${{h.name}}</div>
          <div class="gm-iw-brand">${{h.brand}}</div>
          <div>
            <span class="gm-iw-badge">${{h.rooms.toLocaleString()}} Keys</span>
            ${{h.subject ? '<span class="gm-iw-subject-badge">Subject Property</span>' : ''}}
          </div>
          <div class="gm-iw-meta" style="margin-top:6px;">${{h.address}}</div>
          <div class="gm-iw-meta">Operator: ${{h.operator}}</div>
          <div class="gm-iw-str">STR ID: ${{h.strId}}</div>
          ${{statsHtml}}
        </div>`;

      marker.addListener('click', () => {{
        infoWindow.setContent(iwContent);
        infoWindow.open(map, marker);
      }});

      const item = document.createElement('div');
      item.className = `hotel-item${{h.subject ? ' is-subject' : ''}}`;
      item.innerHTML = `
        <div class="h-pin ${{h.subject ? 'pin-subject' : 'pin-comp'}}">${{label}}</div>
        <div class="h-info">
          <h4>${{h.name}}</h4>
          <div class="h-meta">${{h.address.split(',')[0]}}</div>
          <span class="h-badge">${{h.rooms.toLocaleString()}} keys</span>
          ${{h.subject ? '<span class="h-badge subject-badge">Subject</span>' : ''}}
        </div>`;
      item.addEventListener('click', () => {{
        map.panTo({{ lat: h.lat, lng: h.lng }});
        map.setZoom(16);
        infoWindow.setContent(iwContent);
        infoWindow.open(map, marker);
      }});
      listEl.appendChild(item);
    }});

    map.fitBounds(bounds, {{ top: 60, right: 60, bottom: 60, left: 60 }});
  }}
</script>

<script
  src="https://maps.googleapis.com/maps/api/js?key={API_KEY}&callback=initMap"
  async defer>
</script>

</body>
</html>"""

    return html


def make_slug(name):
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace(",", "").replace(".", ""))


def update_root_index(slug, hotel_name, city_state, report_period, num_comps, comp_rooms):
    """Add a new entry to the root index.html if not already present."""
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if this hotel is already listed
    if f'href="./{slug}/"' in content:
        print(f"  {hotel_name} already in root index.html")
        return

    new_entry = f"""      <li>
        <a href="./{slug}/">
          {hotel_name} &mdash; {city_state}
          <div class="meta">STR Report: {report_period} &middot; 1 Subject + {num_comps} Comps &middot; {comp_rooms:,} Comp Rooms</div>
        </a>
      </li>"""

    content = content.replace("      <!-- MAPS_END -->", f"{new_entry}\n      <!-- MAPS_END -->")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Added {hotel_name} to root index.html")


def main():
    parser = argparse.ArgumentParser(description="Generate STR Comp Set Map")
    parser.add_argument("file", nargs="?", help="Path to STR Excel file (auto-detects from drop folder if omitted)")
    parser.add_argument("--deploy", action="store_true", help="Push to GitHub Pages after generating")
    parser.add_argument("--comp-set", type=int, default=None, help="For multi-comp-set files, which set to use (1, 2, ...) — maps to Response_N/Glance_N sheets")
    args = parser.parse_args()

    suffix = f"_{args.comp_set}" if args.comp_set else ""

    # Find the STR file
    str_path = find_str_file(args.file)
    print(f"Processing: {str_path}{' [comp set ' + str(args.comp_set) + ']' if suffix else ''}\n")

    # Parse Response sheet
    print(f"Parsing Response{suffix} sheet...")
    hotels, report_period, subject_street, comp_rooms = parse_response_sheet(str_path, suffix)
    subject = next(h for h in hotels if h["subject"])
    print(f"  Subject: {subject['name']} ({subject['rooms']} rooms)")
    print(f"  Comps: {len(hotels) - 1} hotels, {comp_rooms:,} rooms")
    print(f"  Report Period: {report_period}")

    # Parse Glance sheet
    print(f"\nParsing Glance{suffix} sheet...")
    perf = parse_glance_sheet(str_path, suffix)
    if perf:
        print(f"  R12 Occ: {perf['subj_occ']} (MPI: {perf['mpi']})")
        print(f"  R12 ADR: {perf['subj_adr']} (ARI: {perf['ari']})")
        print(f"  R12 RevPAR: {perf['subj_revpar']} (RGI: {perf['rgi']})")

    # Geocode
    geocode_all(hotels)

    # Generate HTML
    print("Generating HTML...")
    html = generate_html(hotels, perf, report_period, comp_rooms)

    slug = make_slug(subject["name"])
    output_dir = os.path.join(REPO_DIR, slug)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {output_path}")

    # Update root index
    print("\nUpdating root index...")
    comps = [h for h in hotels if not h["subject"]]
    update_root_index(slug, subject["name"], subject["city_state"], report_period, len(comps), comp_rooms)

    # Deploy
    if args.deploy:
        print("\nDeploying to GitHub Pages...")
        os.chdir(REPO_DIR)
        os.system(f'git add . && git commit -m "Add {subject["name"]} comp set map - {report_period}" && git push origin main')
        print(f"\nLive at: https://acarras92.github.io/str-comp-maps/{slug}/")
    else:
        print(f"\nTo deploy, run:")
        print(f'  python generate_str_map.py --deploy')
        print(f"\nWill be live at: https://acarras92.github.io/str-comp-maps/{slug}/")


if __name__ == "__main__":
    main()
