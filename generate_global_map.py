#!/usr/bin/env python3
"""
Global STR Map — combines every comp set from the drop folder into a single
Google Map, with each comp set shown in its own color. The subject hotel of
each comp set is rendered as a star; comps are rendered as filled circles.

Usage:
    python generate_global_map.py           # write <repo>/global/index.html
    python generate_global_map.py --deploy  # ... then git add/commit/push
"""

import argparse
import glob
import json
import os
import sys

import pandas as pd

from generate_str_map import (
    DROP_FOLDER,
    REPO_DIR,
    GEOCACHE_PATH,
    API_KEY,
    parse_response_sheet,
    parse_glance_sheet,
    geocode,
    make_slug,
)

OUTPUT_DIR = os.path.join(REPO_DIR, "global")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "index.html")

# 24 visually distinct colors — cycled if more comp sets exist.
PALETTE = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324",
    "#800000", "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
    "#e6beff", "#ff8c00", "#008080", "#8b4513", "#2f4f4f", "#ff1493",
]


def load_cache():
    if os.path.exists(GEOCACHE_PATH):
        with open(GEOCACHE_PATH, "r") as f:
            return json.load(f)
    return {}


def coord_for(hotel, cache):
    """Look up coords from cache; try a couple of query formats."""
    addr = hotel.get("address", "") or ""
    q = f"{hotel['name']}, {addr}, {hotel['city_state']} {hotel['zip']}".strip(", ")
    if q in cache:
        return cache[q]
    # fallback: live geocode (will write cache)
    return geocode(hotel["name"], addr, hotel["city_state"], hotel["zip"])


def parse_comp_set(xlsx_path, cache):
    """Return dict with subject, comps, report_period — or None on failure.

    For multi-comp-set files (Response_1/_2/_3), falls back to _1.
    """
    suffix = ""
    try:
        hotels, report_period, _, comp_rooms = parse_response_sheet(xlsx_path)
    except Exception:
        try:
            hotels, report_period, _, comp_rooms = parse_response_sheet(xlsx_path, "_1")
            suffix = "_1"
            print(f"  (using comp set 1 for {os.path.basename(xlsx_path)})")
        except Exception as e:
            print(f"  SKIP {os.path.basename(xlsx_path)}: {e}")
            return None

    subject = next((h for h in hotels if h["subject"]), None)
    if subject is None:
        print(f"  SKIP {os.path.basename(xlsx_path)}: no subject row")
        return None

    try:
        perf = parse_glance_sheet(xlsx_path, suffix)
    except Exception:
        perf = {}

    for h in hotels:
        loc = coord_for(h, cache)
        if loc:
            h["lat"] = loc["lat"]
            h["lng"] = loc["lng"]
        else:
            h["lat"], h["lng"] = 0.0, 0.0

    return {
        "subject_name": subject["name"],
        "slug": make_slug(subject["name"]),
        "report_period": report_period,
        "comp_rooms": comp_rooms,
        "subj_occ": perf.get("subj_occ", ""),
        "subj_adr": perf.get("subj_adr", ""),
        "subj_revpar": perf.get("subj_revpar", ""),
        "mpi": perf.get("mpi", ""),
        "ari": perf.get("ari", ""),
        "rgi": perf.get("rgi", ""),
        "hotels": hotels,
    }


def build_payload():
    cache = load_cache()
    xlsx_files = sorted(
        set(glob.glob(os.path.join(DROP_FOLDER, "*.xlsx")))
        | set(glob.glob(os.path.join(DROP_FOLDER, "*.XLSX")))
    )
    comp_sets = []
    for path in xlsx_files:
        print(f"Reading {os.path.basename(path)}")
        cs = parse_comp_set(path, cache)
        if cs is None:
            continue
        comp_sets.append(cs)

    comp_sets.sort(key=lambda c: c["subject_name"].lower())
    for i, cs in enumerate(comp_sets):
        cs["color"] = PALETTE[i % len(PALETTE)]
    return comp_sets


def render_html(comp_sets):
    # Flatten for JS — keep memberships so shared hotels can show all sets
    hotels_by_key = {}  # (name.lower()) → record
    for cs in comp_sets:
        for h in cs["hotels"]:
            if not h.get("lat"):
                continue
            key = h["name"].strip().lower()
            rec = hotels_by_key.get(key)
            if rec is None:
                rec = {
                    "name": h["name"],
                    "city_state": h.get("city_state", ""),
                    "zip": h.get("zip", ""),
                    "rooms": h.get("rooms", 0),
                    "lat": h["lat"],
                    "lng": h["lng"],
                    "memberships": [],  # list of {slug, color, role}
                }
                hotels_by_key[key] = rec
            role = "subject" if h["subject"] else "comp"
            rec["memberships"].append({
                "slug": cs["slug"],
                "subject_name": cs["subject_name"],
                "color": cs["color"],
                "role": role,
            })

    hotels = list(hotels_by_key.values())

    # Compute bounds / center
    lats = [h["lat"] for h in hotels]
    lngs = [h["lng"] for h in hotels]
    center_lat = (min(lats) + max(lats)) / 2 if lats else 39.8
    center_lng = (min(lngs) + max(lngs)) / 2 if lngs else -98.5

    comp_sets_js = json.dumps([
        {
            "slug": c["slug"],
            "name": c["subject_name"],
            "color": c["color"],
            "report_period": c["report_period"],
            "comp_rooms": c["comp_rooms"],
            "subj_occ": c["subj_occ"],
            "subj_adr": c["subj_adr"],
            "subj_revpar": c["subj_revpar"],
            "mpi": c["mpi"],
            "ari": c["ari"],
            "rgi": c["rgi"],
            "hotel_count": sum(1 for h in c["hotels"] if h.get("lat")),
        }
        for c in comp_sets
    ], indent=2)

    hotels_js = json.dumps(hotels, indent=2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>STR Comp Sets — Global Map</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  #app {{ display: flex; height: 100vh; }}
  #sidebar {{ width: 320px; background: #f7f7f8; border-right: 1px solid #e5e5e7; overflow-y: auto; }}
  #sidebar header {{ padding: 16px 18px; border-bottom: 1px solid #e5e5e7; background: #fff; }}
  #sidebar h1 {{ font-size: 16px; margin: 0 0 4px; }}
  #sidebar .sub {{ font-size: 12px; color: #6b7280; }}
  #controls {{ padding: 10px 14px; border-bottom: 1px solid #e5e5e7; display: flex; gap: 8px; }}
  #controls button {{ flex: 1; padding: 6px 8px; font-size: 11px; border: 1px solid #d1d5db; background: #fff; border-radius: 6px; cursor: pointer; }}
  #controls button:hover {{ background: #f3f4f6; }}
  .legend {{ padding: 6px 0; }}
  .legend-item {{ display: flex; align-items: center; gap: 10px; padding: 8px 14px; cursor: pointer; border-bottom: 1px solid #eef0f2; font-size: 13px; }}
  .legend-item:hover {{ background: #eef2ff; }}
  .legend-item.off {{ opacity: 0.35; }}
  .legend-swatch {{ width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; border: 2px solid #fff; box-shadow: 0 0 0 1px rgba(0,0,0,0.15); }}
  .legend-text {{ flex: 1; line-height: 1.25; min-width: 0; }}
  .legend-name {{ font-weight: 600; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .legend-meta {{ font-size: 11px; color: #6b7280; }}
  #map {{ flex: 1; }}
  .iw {{ font-size: 13px; line-height: 1.4; max-width: 240px; }}
  .iw h3 {{ margin: 0 0 4px; font-size: 14px; }}
  .iw .addr {{ color: #6b7280; font-size: 12px; margin-bottom: 8px; }}
  .iw .mem {{ padding: 4px 0; display: flex; align-items: center; gap: 8px; }}
  .iw .mem .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .iw .mem .role {{ font-size: 11px; color: #6b7280; margin-left: 4px; }}
  .iw a {{ color: #2563eb; text-decoration: none; font-size: 12px; }}
  .iw a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <header>
      <h1>STR Comp Sets — Global View</h1>
      <div class="sub">{len(comp_sets)} comp sets · {len(hotels)} unique hotels</div>
    </header>
    <div id="controls">
      <button onclick="toggleAll(true)">Show all</button>
      <button onclick="toggleAll(false)">Hide all</button>
    </div>
    <div class="legend" id="legend"></div>
  </aside>
  <div id="map"></div>
</div>

<script>
const COMP_SETS = {comp_sets_js};
const HOTELS = {hotels_js};
const CENTER = {{ lat: {center_lat}, lng: {center_lng} }};
let map;
let markers = [];            // {{ marker, memberships }}
let bySet = {{}};            // slug → [markerRecord]
let infoWindow;
const activeSets = new Set(COMP_SETS.map(c => c.slug));

function buildLegend() {{
  const el = document.getElementById('legend');
  COMP_SETS.forEach(cs => {{
    const row = document.createElement('div');
    row.className = 'legend-item';
    row.dataset.slug = cs.slug;
    row.innerHTML = `
      <div class="legend-swatch" style="background:${{cs.color}}"></div>
      <div class="legend-text">
        <div class="legend-name">${{cs.name}}</div>
        <div class="legend-meta">${{cs.hotel_count}} hotels · ${{cs.report_period}}</div>
      </div>
    `;
    row.addEventListener('click', () => toggleSet(cs.slug));
    el.appendChild(row);
  }});
}}

function toggleSet(slug) {{
  if (activeSets.has(slug)) activeSets.delete(slug);
  else activeSets.add(slug);
  refresh();
}}

function toggleAll(on) {{
  activeSets.clear();
  if (on) COMP_SETS.forEach(c => activeSets.add(c.slug));
  refresh();
}}

function refresh() {{
  document.querySelectorAll('.legend-item').forEach(el => {{
    el.classList.toggle('off', !activeSets.has(el.dataset.slug));
  }});
  markers.forEach(rec => {{
    const visibleMems = rec.memberships.filter(m => activeSets.has(m.slug));
    if (visibleMems.length === 0) {{
      rec.marker.setMap(null);
      return;
    }}
    rec.marker.setMap(map);
    // Prefer a subject role for icon style, else first active comp
    const primary = visibleMems.find(m => m.role === 'subject') || visibleMems[0];
    rec.marker.setIcon(iconFor(primary, visibleMems.length > 1));
  }});
}}

function iconFor(primary, multi) {{
  if (primary.role === 'subject') {{
    return {{
      path: 'M 0,-14 L 4,-4 14,-4 6,2 9,12 0,6 -9,12 -6,2 -14,-4 -4,-4 Z',
      fillColor: primary.color,
      fillOpacity: 1.0,
      strokeColor: '#ffffff',
      strokeWeight: 2,
      scale: 1.0,
    }};
  }}
  return {{
    path: google.maps.SymbolPath.CIRCLE,
    fillColor: primary.color,
    fillOpacity: 0.95,
    strokeColor: multi ? '#111827' : '#ffffff',
    strokeWeight: multi ? 2 : 1.5,
    scale: 8,
  }};
}}

function initMap() {{
  map = new google.maps.Map(document.getElementById('map'), {{
    center: CENTER,
    zoom: 4,
    mapTypeControl: true,
    streetViewControl: false,
    fullscreenControl: true,
  }});
  infoWindow = new google.maps.InfoWindow();

  HOTELS.forEach(h => {{
    const primary = h.memberships[0];
    const marker = new google.maps.Marker({{
      position: {{ lat: h.lat, lng: h.lng }},
      map,
      title: h.name,
      icon: iconFor(primary, h.memberships.length > 1),
      zIndex: primary.role === 'subject' ? 1000 : 100,
    }});
    marker.addListener('click', () => {{
      const memsHtml = h.memberships
        .filter(m => activeSets.has(m.slug))
        .map(m => `<div class="mem">
            <span class="dot" style="background:${{m.color}}"></span>
            <a href="../${{m.slug}}/">${{m.subject_name}}</a>
            <span class="role">${{m.role}}</span>
          </div>`).join('');
      infoWindow.setContent(`
        <div class="iw">
          <h3>${{h.name}}</h3>
          <div class="addr">${{h.city_state}} ${{h.zip}} · ${{h.rooms}} rooms</div>
          <div><strong>Appears in:</strong></div>
          ${{memsHtml}}
        </div>
      `);
      infoWindow.open(map, marker);
    }});
    const rec = {{ marker, memberships: h.memberships }};
    markers.push(rec);
    h.memberships.forEach(m => {{
      (bySet[m.slug] = bySet[m.slug] || []).push(rec);
    }});
  }});

  // Fit bounds to all visible markers at load
  const bounds = new google.maps.LatLngBounds();
  HOTELS.forEach(h => bounds.extend({{ lat: h.lat, lng: h.lng }}));
  map.fitBounds(bounds);
}}

buildLegend();
</script>
<script async src="https://maps.googleapis.com/maps/api/js?key={API_KEY}&callback=initMap"></script>
</body>
</html>
"""


def update_root_index_link():
    """Add a '🌐 Global Map' tile to the root landing page if missing."""
    path = os.path.join(REPO_DIR, "index.html")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if 'href="./global/"' in content:
        print("  Global link already present in root index.html")
        return
    # Root uses <ul class="map-list"> with <li> entries. Put a banner above it.
    banner = """    <a href="./global/" class="global-banner" style="display:block; margin:0 0 18px; padding:18px 22px; background:linear-gradient(135deg,#1f2937,#0ea5e9); color:#fff; border-radius:10px; text-decoration:none;">
      <div style="font-size:18px; font-weight:600;">Global Comp Sets Map &rarr;</div>
      <div style="font-size:13px; opacity:0.9; margin-top:2px;">Every comp set on one map, color-coded by subject hotel.</div>
    </a>
"""
    marker = '<ul class="map-list">'
    if marker in content:
        content = content.replace(marker, banner + "    " + marker, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  Added Global banner to root index.html")
    else:
        print("  WARNING: could not find <ul class=\"map-list\"> in root index.html; skipping link insert")


def main():
    parser = argparse.ArgumentParser(description="Generate combined STR comp set map")
    parser.add_argument("--deploy", action="store_true")
    args = parser.parse_args()

    comp_sets = build_payload()
    if not comp_sets:
        print("No comp sets parsed — nothing to render.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html = render_html(comp_sets)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nGlobal map saved: {OUTPUT_PATH}")

    update_root_index_link()

    if args.deploy:
        os.chdir(REPO_DIR)
        os.system('git add . && git commit -m "Add global combined comp set map" && git push origin main')
        print("\nLive at: https://acarras92.github.io/str-comp-maps/global/")


if __name__ == "__main__":
    main()
