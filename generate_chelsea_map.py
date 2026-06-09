#!/usr/bin/env python3
"""
Holiday Inn Manhattan Chelsea — STR Comp Set Map (two comp sets + supply).

Two comp sets share one subject (starred #1), switchable via a sidebar toggle:
  Set 1 — Times Square South (7 comps). Has a blended R12 composite from the
          HospitalityDataGrid export (subject + comps; no subject-vs-comp split,
          no MPI/ARI/RGI).
  Set 2 — Chelsea / Penn Station (5 comps). Roster only (names/rooms/open dates);
          no STR performance provided.

Plus the LMW / Times Square South new-supply pipeline (always-on orange layer).

Usage:
    python generate_chelsea_map.py            # generate only
    python generate_chelsea_map.py --deploy   # generate + push to GitHub Pages
"""

import argparse
import os

import generate_str_map as base

REPORT_PERIOD = "Apr 2026"  # R12 ending (Set 1 composite)
SLUG = "holiday-inn-manhattan-chelsea"

# Shared subject (starred #1 in both sets)
SUBJECT = {"name": "Holiday Inn Manhattan 6th Ave - Chelsea",
           "address": "125 W 26th St", "zip": "10001", "rooms": 226,
           "open": "Jun 2008", "str_id": ""}

# Set 1 — Times Square South. Blended R12 composite (subject + 7 comps).
PANEL = {"occ": "91.7%", "adr": "$278", "revpar": "$255"}

SET1_COMPS = [
    {"name": "Hilton Garden Inn New York Times Square South", "address": "",
     "zip": "10018", "rooms": 250, "open": "Oct 2017", "str_id": "9571683"},
    {"name": "Fairfield by Marriott Inn & Suites New York Midtown Manhattan/Penn Station",
     "address": "", "zip": "10001", "rooms": 239, "open": "Apr 2013", "str_id": "9208355"},
    {"name": "Hilton Garden Inn New York Times Square Central", "address": "",
     "zip": "10036", "rooms": 282, "open": "Sep 2014", "str_id": "6529472"},
    {"name": "Holiday Inn New York City Times Square", "address": "",
     "zip": "10018", "rooms": 271, "open": "Oct 2015", "str_id": "9569480"},
    {"name": "Delta Hotels New York Times Square", "address": "",
     "zip": "10018", "rooms": 310, "open": "Apr 2010", "str_id": "8229453"},
    {"name": "Courtyard New York Manhattan/Times Square West", "address": "",
     "zip": "10018", "rooms": 224, "open": "May 2013", "str_id": "5000125"},
    {"name": "voco Times Square South", "address": "",
     "zip": "10018", "rooms": 224, "open": "Nov 2008", "str_id": "6209181"},
]

# Set 2 — Chelsea / Penn Station. Roster only (no STR performance).
SET2_COMPS = [
    {"name": "Hampton by Hilton Manhattan-Chelsea", "address": "108 W 24th St",
     "zip": "10011", "rooms": 144, "open": "Aug 2003", "str_id": ""},
    {"name": "Hilton Garden Inn New York Chelsea", "address": "121 W 28th St",
     "zip": "10001", "rooms": 169, "open": "Oct 2007", "str_id": ""},
    {"name": "Holiday Inn Express New York City Chelsea", "address": "",
     "zip": "10001", "rooms": 228, "open": "Oct 2006", "str_id": ""},
    {"name": "TRYP by Wyndham New York City Times Square / Midtown", "address": "",
     "zip": "10001", "rooms": 173, "open": "Feb 2012", "str_id": ""},
    {"name": "Fairfield by Marriott Inn & Suites New York Midtown Manhattan/Penn Station",
     "address": "", "zip": "10001", "rooms": 239, "open": "Apr 2013", "str_id": ""},
]

SETS = [
    {"id": 1, "label": "Times Square South", "short": "TS South",
     "perf": PANEL, "comps": SET1_COMPS},
    {"id": 2, "label": "Chelsea / Penn Station", "short": "Chelsea / Penn",
     "perf": None, "comps": SET2_COMPS},
]

# Submarket new-supply pipeline (LMW / Times Square South). Orange "+" layer.
SUPPLY_COLOR = "#e67e22"
NEW_SUPPLY = [
    {"name": "Hotel 38 NY, Tapestry Collection", "address": "321 W 38th St",
     "status": "Opening", "open": "Apr 2026", "keys": 175},
    {"name": "Row NYC (reopening)", "address": "700 8th Ave",
     "status": "Opened", "open": "May 2026", "keys": 1331},
    # Hardcoded: geocoder mis-resolves "450 11th Ave"; verified corner of
    # 11th Ave & W 37th St (Hudson Yards, by the Javits Center).
    {"name": "Hotel Meta, Tribute Portfolio", "address": "450 11th Ave at W 37th St",
     "zip": "10018", "status": "Near Completion", "open": "Q2/Q3 2026", "keys": 379,
     "lat": 40.7576, "lng": -73.9986},
    {"name": "Jade Hotel @ Garment District", "address": "36 W 38th St",
     "status": "Under Construction", "open": "Sep 2026", "keys": 200},
    {"name": "Unbranded Hotel", "address": "319 W 35th St",
     "status": "Stalled", "open": "TBD", "keys": 166},
    {"name": "Cambria Suites", "address": "224 W 47th St",
     "status": "Opening", "open": "Jul 2026", "keys": 136},
    {"name": "Canopy by Hilton NY Midtown", "address": "255 W 34th St",
     "status": "Under Construction", "open": "Fall 2026", "keys": 365},
    {"name": "The Torch", "address": "740 8th Ave",
     "status": "Under Construction", "open": "Aug 2028", "keys": 825},
    {"name": "AC Hotel NY Midtown West", "address": "495 11th Ave",
     "status": "Planned", "open": "Sep 2029", "keys": 341},
    {"name": "Aloft Midtown West", "address": "495 11th Ave",
     "status": "Planned", "open": "Sep 2029", "keys": 220},
    {"name": "Residence Inn NY Midtown", "address": "495 11th Ave",
     "status": "Planned", "open": "Sep 2029", "keys": 96},
]
MARKET_SUPPLY = 103462      # Manhattan (NYC) keys
SUBMARKET_SUPPLY = 23930    # LMW / Times Square South keys


def _full_addr(h):
    return f"{h.get('address', '')}, New York, NY {h['zip']}".strip(", ").replace(" ,", ",")


def render_html(subject, sets, supply):
    hotel_name = subject["name"]

    # Combined HOTELS array: subject (set 0, idx 1) + each set's comps (idx 2..N).
    rows = [f"""    {{
      set: 0, idx: 1, subject: true,
      name: {subject['name']!r}, address: {_full_addr(subject)!r},
      rooms: {subject['rooms']}, open: {subject['open']!r}, strId: {subject['str_id']!r},
      lat: {subject['lat']}, lng: {subject['lng']},
    }},"""]
    for s in sets:
        for i, h in enumerate(s["comps"]):
            rows.append(f"""    {{
      set: {s['id']}, idx: {i + 2}, subject: false,
      name: {h['name']!r}, address: {_full_addr(h)!r},
      rooms: {h['rooms']}, open: {h['open']!r}, strId: {h['str_id']!r},
      lat: {h['lat']}, lng: {h['lng']},
    }},""")
    hotels_js = "const HOTELS = [\n" + "\n".join(rows) + "\n  ];"

    # Per-set metadata for JS-driven toggle.
    meta_rows = []
    for s in sets:
        comp_rooms = sum(h["rooms"] for h in s["comps"])
        if s["perf"]:
            meta_rows.append(f"""    {s['id']}: {{ label: {s['label']!r}, count: {len(s['comps'])}, rooms: {comp_rooms},
         perf: true, occ: {s['perf']['occ']!r}, adr: {s['perf']['adr']!r}, revpar: {s['perf']['revpar']!r},
         badge: 'Panel Composite \\u00b7 R12 {REPORT_PERIOD}',
         note: 'Blended R12 performance for the full tracked panel (subject + comps). No subject-vs-comp split or MPI/ARI/RGI in this export.' }},""")
        else:
            meta_rows.append(f"""    {s['id']}: {{ label: {s['label']!r}, count: {len(s['comps'])}, rooms: {comp_rooms},
         perf: false, occ: 'N/A', adr: 'N/A', revpar: 'N/A',
         badge: 'No STR performance for this set',
         note: 'Roster only \\u2014 names, room counts and open dates. No STR performance was provided for this comp set.' }},""")
    sets_meta_js = "const SETS_META = {\n" + "\n".join(meta_rows) + "\n  };"

    # SUPPLY array
    supply_rows = []
    for s in supply:
        supply_rows.append(f"""    {{
      name: {s['name']!r}, address: {(s['address'] + ', New York, NY')!r},
      status: {s['status']!r}, open: {s['open']!r}, keys: {s['keys']},
      lat: {s['lat']}, lng: {s['lng']},
    }},""")
    supply_js = "const SUPPLY = [\n" + "\n".join(supply_rows) + "\n  ];"

    supply_keys = sum(s["keys"] for s in supply)
    pct_market = supply_keys / MARKET_SUPPLY * 100
    pct_submkt = supply_keys / SUBMARKET_SUPPLY * 100

    all_lats = [subject["lat"]] + [h["lat"] for s in sets for h in s["comps"]]
    all_lngs = [subject["lng"]] + [h["lng"] for s in sets for h in s["comps"]]
    avg_lat = sum(all_lats) / len(all_lats)
    avg_lng = sum(all_lngs) / len(all_lngs)

    set1 = sets[0]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{hotel_name} &ndash; STR Comp Set Map</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; height: 100vh; display: flex; flex-direction: column; background: #f5f5f5; }}
    .header {{ background: #1a2744; border-bottom: 3px solid #2956b2; padding: 11px 20px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; z-index: 10; }}
    .header-left h1 {{ font-size: 17px; font-weight: 700; color: #fff; letter-spacing: 0.3px; }}
    .header-left p {{ font-size: 11px; color: #8fa8d8; margin-top: 2px; }}
    .header-right {{ display: flex; align-items: center; gap: 6px; }}
    .kpi-card {{ background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 7px 14px; text-align: center; min-width: 90px; }}
    .kpi-card .k-label {{ font-size: 9px; color: #8fa8d8; text-transform: uppercase; letter-spacing: 0.8px; }}
    .kpi-card .k-value {{ font-size: 17px; font-weight: 700; color: #fff; line-height: 1.2; margin: 1px 0; }}
    .kpi-sep {{ width: 1px; height: 36px; background: rgba(255,255,255,0.15); }}
    .str-badge {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 4px 10px; font-size: 10px; color: #8fa8d8; margin-left: 10px; }}
    .main {{ display: flex; flex: 1; overflow: hidden; }}
    .sidebar {{ width: 300px; background: #fff; border-right: 1px solid #dde3ed; display: flex; flex-direction: column; overflow-y: auto; flex-shrink: 0; box-shadow: 2px 0 8px rgba(0,0,0,0.06); z-index: 5; }}
    .sb-section {{ padding: 14px; border-bottom: 1px solid #eaecf0; }}
    .sb-section h3 {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.9px; color: #8090b0; margin-bottom: 10px; font-weight: 600; }}
    .set-toggle {{ display: flex; gap: 6px; }}
    .set-btn {{ flex: 1; padding: 8px 8px; border: 1px solid #cdd6e6; background: #f3f6fb; border-radius: 6px; font-size: 11.5px; font-weight: 700; color: #5a6b8c; cursor: pointer; text-align: center; line-height: 1.25; transition: all 0.15s; }}
    .set-btn small {{ display: block; font-size: 9px; font-weight: 500; opacity: 0.85; margin-top: 1px; }}
    .set-btn.active {{ background: #1565c0; border-color: #1565c0; color: #fff; }}
    .legend-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; color: #334; }}
    .leg-dot {{ width: 13px; height: 13px; border-radius: 50%; border: 2px solid rgba(0,0,0,0.15); flex-shrink: 0; }}
    .perf-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; }}
    .perf-cell {{ background: #f5f8ff; border: 1px solid #dce6f7; border-radius: 5px; padding: 6px 4px; text-align: center; }}
    .p-metric {{ font-size: 9px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.4px; }}
    .p-value {{ font-size: 14px; font-weight: 700; color: #1a2744; margin: 1px 0; }}
    .perf-note {{ font-size: 9px; color: #9aa6bd; margin-top: 8px; line-height: 1.4; }}
    .hotel-item {{ display: flex; align-items: flex-start; gap: 9px; padding: 8px 6px; border-radius: 5px; cursor: pointer; transition: background 0.15s; border-bottom: 1px solid #f0f2f5; }}
    .hotel-item:last-child {{ border-bottom: none; }}
    .hotel-item:hover {{ background: #f0f5ff; }}
    .hotel-item.is-subject {{ background: #fff5f5; }}
    .hotel-item.is-subject:hover {{ background: #ffe8e8; }}
    .h-pin {{ width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; margin-top: 1px; }}
    .pin-subject {{ background: #c62828; color: #fff; }}
    .pin-comp {{ background: #1565c0; color: #fff; }}
    .pin-supply {{ background: {SUPPLY_COLOR}; color: #fff; }}
    .supply-summary {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }}
    .supply-cell {{ background: #fff6ee; border: 1px solid #f5d8bf; border-radius: 5px; padding: 6px 4px; text-align: center; }}
    .supply-num {{ font-size: 16px; font-weight: 700; color: {SUPPLY_COLOR}; line-height: 1.1; }}
    .supply-cap {{ font-size: 8.5px; color: #8090b0; text-transform: uppercase; letter-spacing: 0.3px; margin-top: 2px; }}
    .h-badge.supply-badge {{ background: #fff1e3; border-color: #f5d8bf; color: #b35e12; }}
    .gm-iw-status {{ font-size: 10px; color: #5d6b85; margin-top: 6px; }}
    .h-info h4 {{ font-size: 12px; font-weight: 600; color: #1a2744; line-height: 1.3; }}
    .h-info .h-meta {{ font-size: 10px; color: #7080a0; margin-top: 1px; }}
    .h-badge {{ display: inline-block; background: #e8f0fe; border: 1px solid #c5d5f5; border-radius: 3px; padding: 1px 5px; font-size: 10px; color: #1a56c4; margin-top: 3px; }}
    .h-badge.subject-badge {{ background: #fdecea; border-color: #f5c0bc; color: #b71c1c; margin-left: 4px; }}
    .sidebar-footer {{ padding: 8px 14px; font-size: 10px; color: #aabbd0; border-top: 1px solid #eaecf0; margin-top: auto; }}
    #map {{ flex: 1; }}
    .gm-iw {{ font-family: 'Segoe UI', Arial, sans-serif; min-width: 230px; max-width: 270px; }}
    .gm-iw-title {{ font-size: 14px; font-weight: 700; color: #1a2744; line-height: 1.3; margin-bottom: 6px; }}
    .gm-iw-meta {{ font-size: 11px; color: #556; margin-bottom: 3px; }}
    .gm-iw-badge {{ display: inline-block; background: #e8f0fe; border: 1px solid #c5d5f5; border-radius: 3px; padding: 2px 6px; font-size: 10px; color: #1a56c4; margin-bottom: 6px; }}
    .gm-iw-subject-badge {{ display: inline-block; background: #fdecea; border: 1px solid #f5c0bc; border-radius: 3px; padding: 2px 6px; font-size: 10px; color: #b71c1c; margin-left: 5px; margin-bottom: 6px; }}
    .gm-iw-masked {{ font-size: 10px; color: #aabbd0; margin-top: 6px; font-style: italic; }}
    .gm-iw-str {{ font-size: 10px; color: #c0c8da; margin-top: 4px; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>{hotel_name} &mdash; STR Competitive Set Map</h1>
    <p>{SUBJECT['address']}, New York, NY &nbsp;&middot;&nbsp; <span id="sub-set">Set 1: {set1['label']}</span> &nbsp;&middot;&nbsp; 1 Subject + <span id="sub-counts">{len(set1['comps'])} Comps</span> &nbsp;&middot;&nbsp; {len(supply)} Pipeline ({supply_keys:,} keys)</p>
  </div>
  <div class="header-right">
    <div class="kpi-card"><div class="k-label">Occupancy</div><div class="k-value" id="kpi-occ">{PANEL['occ']}</div></div>
    <div class="kpi-sep"></div>
    <div class="kpi-card"><div class="k-label">ADR</div><div class="k-value" id="kpi-adr">{PANEL['adr']}</div></div>
    <div class="kpi-sep"></div>
    <div class="kpi-card"><div class="k-label">RevPAR</div><div class="k-value" id="kpi-revpar">{PANEL['revpar']}</div></div>
    <div class="str-badge" id="str-badge">Panel Composite &middot; R12 {REPORT_PERIOD}</div>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sb-section">
      <h3>Comp Set</h3>
      <div class="set-toggle">
        <div class="set-btn active" data-set="1" onclick="showSet(1)">Set 1<small>{set1['label']} &middot; {len(set1['comps'])}</small></div>
        <div class="set-btn" data-set="2" onclick="showSet(2)">Set 2<small>{sets[1]['label']} &middot; {len(sets[1]['comps'])}</small></div>
      </div>
    </div>

    <div class="sb-section">
      <h3>Legend</h3>
      <div class="legend-row"><div class="leg-dot" style="background:#c62828;"></div> Subject Property</div>
      <div class="legend-row"><div class="leg-dot" style="background:#1565c0;"></div> Competitive Set (<span id="legend-count">{len(set1['comps'])}</span> Hotels)</div>
      <div class="legend-row"><div class="leg-dot" style="background:{SUPPLY_COLOR};"></div> New Supply / Pipeline ({len(supply)} Projects)</div>
    </div>

    <div class="sb-section">
      <h3 id="perf-head">Set 1 Composite &mdash; R12 ending {REPORT_PERIOD}</h3>
      <div class="perf-grid">
        <div class="perf-cell"><div class="p-metric">Occ</div><div class="p-value" id="perf-occ">{PANEL['occ']}</div></div>
        <div class="perf-cell"><div class="p-metric">ADR</div><div class="p-value" id="perf-adr">{PANEL['adr']}</div></div>
        <div class="perf-cell"><div class="p-metric">RevPAR</div><div class="p-value" id="perf-revpar">{PANEL['revpar']}</div></div>
      </div>
      <div class="perf-note" id="perf-note">Blended R12 performance for the full tracked panel (subject + comps). No subject-vs-comp split or MPI/ARI/RGI in this export.</div>
    </div>

    <div class="sb-section">
      <h3>New Supply Pipeline &mdash; LMW / Times Square South</h3>
      <div class="supply-summary">
        <div class="supply-cell"><div class="supply-num">{len(supply)}</div><div class="supply-cap">Projects</div></div>
        <div class="supply-cell"><div class="supply-num">{supply_keys:,}</div><div class="supply-cap">New Keys</div></div>
        <div class="supply-cell"><div class="supply-num">{pct_submkt:.1f}%</div><div class="supply-cap">of Submkt</div></div>
      </div>
      <div class="perf-note">{supply_keys:,} projected new keys = {pct_market:.2f}% of Manhattan ({MARKET_SUPPLY:,}) &middot; {pct_submkt:.2f}% of the {SUBMARKET_SUPPLY:,}-key submarket. Locations approximate (geocoded from address).</div>
    </div>

    <div class="sb-section" style="flex:1; border-bottom:none;">
      <h3 id="list-head">Set 1 Properties &mdash; Click to Navigate</h3>
      <div id="hotel-list"></div>
      <h3 style="margin-top:14px;">New Supply &mdash; Click to Navigate</h3>
      <div id="supply-list"></div>
    </div>

    <div class="sidebar-footer">
      Set 1: STR HospitalityDataGrid / Participation export (R12 ending {REPORT_PERIOD}) &middot; Set 2: roster only
    </div>
  </div>

  <div id="map"></div>
</div>

<script>
  {hotels_js}

  {sets_meta_js}

  {supply_js}

  let map, infoWindow, activeSet = 1;
  const compMarkers = [];   // {{ marker, h }}
  let subjectMarker = null;
  const supplyMarkers = [];

  function compIcon(label) {{
    return {{
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">
          <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/></filter>
          <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
                fill="#1565c0" stroke="white" stroke-width="1.5" filter="url(#s)"/>
          <text x="19" y="22" text-anchor="middle" dominant-baseline="middle"
                font-family="Arial,sans-serif" font-size="13" font-weight="bold" fill="white">${{label}}</text>
        </svg>`),
      scaledSize: new google.maps.Size(38, 46), anchor: new google.maps.Point(19, 44)
    }};
  }}

  function hotelIW(h) {{
    const perfLine = h.subject
      ? `<div class="gm-iw-masked">Subject shown within Set 1 panel composite (no standalone STR figures in this export)</div>`
      : `<div class="gm-iw-masked">Individual comp performance not provided in this export</div>`;
    return `
      <div class="gm-iw">
        <div class="gm-iw-title">${{h.idx}}. ${{h.name}}</div>
        <div>
          <span class="gm-iw-badge">${{h.rooms.toLocaleString()}} Keys</span>
          ${{h.subject ? '<span class="gm-iw-subject-badge">Subject Property</span>' : ''}}
        </div>
        <div class="gm-iw-meta" style="margin-top:6px;">${{h.address}}</div>
        <div class="gm-iw-meta">Opened ${{h.open}}</div>
        ${{h.strId ? `<div class="gm-iw-str">STR ID: ${{h.strId}}</div>` : ''}}
        ${{perfLine}}
      </div>`;
  }}

  function makeHotelItem(h, marker) {{
    const label = h.subject ? '★' : String(h.idx);
    const item = document.createElement('div');
    item.className = `hotel-item${{h.subject ? ' is-subject' : ''}}`;
    item.innerHTML = `
      <div class="h-pin ${{h.subject ? 'pin-subject' : 'pin-comp'}}">${{label}}</div>
      <div class="h-info">
        <h4>${{h.idx}}. ${{h.name}}</h4>
        <div class="h-meta">${{h.address.split(',')[0] || h.address}} &middot; Opened ${{h.open}}</div>
        <span class="h-badge">${{h.rooms.toLocaleString()}} keys</span>
        ${{h.subject ? '<span class="h-badge subject-badge">Subject</span>' : ''}}
      </div>`;
    item.addEventListener('click', () => {{
      map.panTo({{ lat: h.lat, lng: h.lng }});
      map.setZoom(16);
      infoWindow.setContent(hotelIW(h));
      infoWindow.open(map, marker);
    }});
    return item;
  }}

  function showSet(n) {{
    activeSet = n;
    const meta = SETS_META[n];

    document.querySelectorAll('.set-btn').forEach(b =>
      b.classList.toggle('active', +b.dataset.set === n));

    // Header
    document.getElementById('kpi-occ').textContent = meta.occ;
    document.getElementById('kpi-adr').textContent = meta.adr;
    document.getElementById('kpi-revpar').textContent = meta.revpar;
    document.getElementById('str-badge').textContent = meta.badge;
    document.getElementById('sub-set').textContent = 'Set ' + n + ': ' + meta.label;
    document.getElementById('sub-counts').textContent = meta.count + ' Comps';

    // Performance panel
    document.getElementById('perf-head').innerHTML = meta.perf
      ? ('Set ' + n + ' Composite — R12 ending {REPORT_PERIOD}')
      : ('Set ' + n + ' — ' + meta.label);
    document.getElementById('perf-occ').textContent = meta.occ;
    document.getElementById('perf-adr').textContent = meta.adr;
    document.getElementById('perf-revpar').textContent = meta.revpar;
    document.getElementById('perf-note').textContent = meta.note;

    // Legend + list heading
    document.getElementById('legend-count').textContent = meta.count;
    document.getElementById('list-head').textContent = 'Set ' + n + ' Properties — Click to Navigate';

    // Markers + list
    const listEl = document.getElementById('hotel-list');
    listEl.innerHTML = '';
    const bounds = new google.maps.LatLngBounds();
    bounds.extend({{ lat: subjectMarker.getPosition().lat(), lng: subjectMarker.getPosition().lng() }});

    // Subject first
    const subj = HOTELS.find(h => h.subject);
    listEl.appendChild(makeHotelItem(subj, subjectMarker));

    compMarkers.forEach(({{ marker, h }}) => {{
      const visible = h.set === n;
      marker.setVisible(visible);
      if (visible) {{
        bounds.extend({{ lat: h.lat, lng: h.lng }});
        listEl.appendChild(makeHotelItem(h, marker));
      }}
    }});

    // Keep the supply pipeline in frame too
    SUPPLY.forEach(s => bounds.extend({{ lat: s.lat, lng: s.lng }}));
    map.fitBounds(bounds, {{ top: 60, right: 60, bottom: 60, left: 60 }});
  }}

  function initMap() {{
    map = new google.maps.Map(document.getElementById('map'), {{
      center: {{ lat: {avg_lat}, lng: {avg_lng} }},
      zoom: 14, mapTypeControl: true,
      mapTypeControlOptions: {{ style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR, position: google.maps.ControlPosition.TOP_RIGHT }},
      streetViewControl: true, fullscreenControl: true,
      styles: [
        {{ featureType: "poi.business", stylers: [{{ visibility: "off" }}] }},
        {{ featureType: "transit", stylers: [{{ visibility: "simplified" }}] }}
      ]
    }});
    infoWindow = new google.maps.InfoWindow({{ maxWidth: 290 }});

    HOTELS.forEach((h) => {{
      if (h.subject) {{
        const icon = {{
          url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
            <svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">
              <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/></filter>
              <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
                    fill="#c62828" stroke="white" stroke-width="1.5" filter="url(#s)"/>
              <text x="19" y="22" text-anchor="middle" dominant-baseline="middle"
                    font-family="Arial,sans-serif" font-size="14" font-weight="bold" fill="white">★</text>
            </svg>`),
          scaledSize: new google.maps.Size(38, 46), anchor: new google.maps.Point(19, 44)
        }};
        subjectMarker = new google.maps.Marker({{ position: {{ lat: h.lat, lng: h.lng }}, map, icon, title: h.name, zIndex: 100 }});
        subjectMarker.addListener('click', () => {{ infoWindow.setContent(hotelIW(h)); infoWindow.open(map, subjectMarker); }});
      }} else {{
        const marker = new google.maps.Marker({{ position: {{ lat: h.lat, lng: h.lng }}, map, icon: compIcon(h.idx), title: h.name, zIndex: h.idx }});
        marker.addListener('click', () => {{ infoWindow.setContent(hotelIW(h)); infoWindow.open(map, marker); }});
        compMarkers.push({{ marker, h }});
      }}
    }});

    // ── New supply / pipeline layer (orange "+" pins, always shown) ──
    const supplyListEl = document.getElementById('supply-list');
    SUPPLY.forEach((s) => {{
      const icon = {{
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="34" height="42" viewBox="0 0 38 46">
            <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/></filter>
            <path d="M19 2C10.16 2 3 9.16 3 18C3 30 19 44 19 44C19 44 35 30 35 18C35 9.16 27.84 2 19 2Z"
                  fill="{SUPPLY_COLOR}" stroke="white" stroke-width="1.5" filter="url(#s)"/>
            <text x="19" y="21" text-anchor="middle" dominant-baseline="middle"
                  font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="white">+</text>
          </svg>`),
        scaledSize: new google.maps.Size(34, 42), anchor: new google.maps.Point(17, 40)
      }};
      const marker = new google.maps.Marker({{ position: {{ lat: s.lat, lng: s.lng }}, map, icon, title: s.name, zIndex: 50 }});
      supplyMarkers.push(marker);

      const iwContent = `
        <div class="gm-iw">
          <div class="gm-iw-title">${{s.name}}</div>
          <div>
            <span class="gm-iw-badge" style="background:#fff1e3;border-color:#f5d8bf;color:#b35e12;">${{s.keys.toLocaleString()}} Keys</span>
            <span class="gm-iw-subject-badge" style="background:#fff1e3;border-color:#f5d8bf;color:#b35e12;">New Supply</span>
          </div>
          <div class="gm-iw-meta" style="margin-top:6px;">${{s.address}}</div>
          <div class="gm-iw-status"><b>Status:</b> ${{s.status}} &middot; <b>Open:</b> ${{s.open}}</div>
        </div>`;
      marker.addListener('click', () => {{ infoWindow.setContent(iwContent); infoWindow.open(map, marker); }});

      const item = document.createElement('div');
      item.className = 'hotel-item';
      item.innerHTML = `
        <div class="h-pin pin-supply">+</div>
        <div class="h-info">
          <h4>${{s.name}}</h4>
          <div class="h-meta">${{s.address.split(',')[0]}} &middot; ${{s.status}} &middot; ${{s.open}}</div>
          <span class="h-badge supply-badge">${{s.keys.toLocaleString()}} keys</span>
        </div>`;
      item.addEventListener('click', () => {{
        map.panTo({{ lat: s.lat, lng: s.lng }}); map.setZoom(16);
        infoWindow.setContent(iwContent); infoWindow.open(map, marker);
      }});
      supplyListEl.appendChild(item);
    }});

    showSet(1);
  }}
</script>

<script src="https://maps.googleapis.com/maps/api/js?key={base.API_KEY}&callback=initMap" async defer></script>

</body>
</html>"""


def _geocode_comps(comps):
    for h in comps:
        loc = base.geocode(h["name"], h.get("address", ""), "New York, NY", h["zip"])
        h["lat"] = loc["lat"] if loc else 0
        h["lng"] = loc["lng"] if loc else 0


def main():
    parser = argparse.ArgumentParser(description="Generate Holiday Inn Chelsea STR comp map")
    parser.add_argument("--deploy", action="store_true", help="Push to GitHub Pages after generating")
    args = parser.parse_args()

    subject = dict(SUBJECT)
    loc = base.geocode(subject["name"], subject["address"], "New York, NY", subject["zip"])
    subject["lat"], subject["lng"] = loc["lat"], loc["lng"]

    sets = [{**s, "comps": [dict(h) for h in s["comps"]]} for s in SETS]
    for s in sets:
        print(f"Geocoding Set {s['id']} ({s['label']})...")
        _geocode_comps(s["comps"])

    # Geocode supply pipeline.
    supply = [dict(s) for s in NEW_SUPPLY]
    print("Geocoding supply pipeline...")
    for s in supply:
        if "lat" in s and "lng" in s:
            continue
        gl = base.geocode(s["name"], s["address"], "New York, NY", s.get("zip", ""))
        s["lat"] = gl["lat"] if gl else 0
        s["lng"] = gl["lng"] if gl else 0

    # Fan out co-located projects (e.g. 495 11th Ave tri-brand) for clickability.
    seen = {}
    for s in supply:
        key = (round(s["lat"], 5), round(s["lng"], 5))
        n = seen.get(key, 0)
        if n:
            s["lat"] += 0.00045 * n
            s["lng"] += 0.00045 * n
        seen[key] = n + 1

    print("Generating HTML...")
    html = render_html(subject, sets, supply)

    output_dir = os.path.join(base.REPO_DIR, SLUG)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {output_path}")

    total_comps = sum(len(s["comps"]) for s in sets)
    base.update_root_index(SLUG, subject["name"], "New York, NY",
                           f"R12 {REPORT_PERIOD}", total_comps, sum(h["rooms"] for h in SET1_COMPS))

    url = f"{base.PAGES_BASE_URL}/{SLUG}/"
    if not args.deploy:
        print(f"\nGenerated. To deploy: python generate_chelsea_map.py --deploy")
        print(f"  Will be live at: {url}")
        return

    print("\nDeploying to GitHub Pages...")
    base._commit_and_push(
        f"Holiday Inn Chelsea map: add Set 2 (Chelsea/Penn Station, {len(SET2_COMPS)} comps) + comp-set toggle")
    ok = base.verify_deploy([url])
    print("\nDEPLOY VERIFIED [OK]" if ok else "\nDEPLOY INCOMPLETE — see warnings above")
    print(f"  {url}")


if __name__ == "__main__":
    main()
