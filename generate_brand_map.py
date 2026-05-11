#!/usr/bin/env python3
"""
Brand Portfolio Map Generator
Reads brands/<slug>.json (or all brand JSONs), geocodes the hotel list, and
renders a standalone Google Maps page showing every property in the brand.

Brand maps are not STR comp sets — there is no subject, no R12 performance.
They are reference maps for understanding a brand's footprint.

Usage:
    python generate_brand_map.py                    # generate every brand in brands/
    python generate_brand_map.py capella            # one brand by slug (matches brands/capella.json)
    python generate_brand_map.py capella --deploy   # generate + push + verify
"""

import argparse
import glob
import json
import os
import sys

from generate_str_map import (
    REPO_DIR,
    API_KEY,
    PAGES_BASE_URL,
    geocode,
    _commit_and_push,
    verify_deploy,
)

BRANDS_DIR = os.path.join(REPO_DIR, "brands")


def load_brand(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_brand_files(slugs=None):
    files = sorted(glob.glob(os.path.join(BRANDS_DIR, "*.json")))
    if not slugs:
        return files
    wanted = set(slugs)
    matched = [p for p in files if os.path.splitext(os.path.basename(p))[0] in wanted]
    missing = wanted - {os.path.splitext(os.path.basename(p))[0] for p in matched}
    if missing:
        raise FileNotFoundError(f"No brand JSON for: {', '.join(sorted(missing))}")
    return matched


def geocode_brand(brand):
    """Geocode each hotel; mutate in place. Returns count of successes."""
    print(f"\nGeocoding {brand['brand']} ({len(brand['hotels'])} hotels)...")
    ok = 0
    for h in brand["hotels"]:
        addr = h.get("address", "") or ""
        city = h.get("city", "") or ""
        country = h.get("country", "") or ""
        # Reuse the existing cached geocoder. zip_code slot carries country so
        # the query string ends up "<name>, <addr>, <city> <country>".
        loc = geocode(h["name"], addr, city, country)
        if loc:
            h["lat"] = loc["lat"]
            h["lng"] = loc["lng"]
            ok += 1
        else:
            h["lat"] = 0.0
            h["lng"] = 0.0
    print(f"  Geocoded {ok}/{len(brand['hotels'])} hotels")
    return ok


def render_html(brand):
    hotels = [h for h in brand["hotels"] if h.get("lat")]
    if not hotels:
        raise RuntimeError("No hotels could be geocoded for this brand")

    color = brand.get("color", "#7c2d12")
    marker_stroke = brand.get("marker_stroke", "#ffffff")
    label_color = brand.get("label_color") or ("#000000" if marker_stroke == "#000000" else "#ffffff")
    avg_lat = sum(h["lat"] for h in hotels) / len(hotels)
    avg_lng = sum(h["lng"] for h in hotels) / len(hotels)

    # Optional rich fields (status, keys, opening_year, sub_brand, owner, operator,
    # notes, source, verified, region). Brands without these render exactly as before.
    hotels_js = json.dumps([
        {
            "name": h["name"],
            "address": h.get("address") or "",
            "city": h.get("city") or "",
            "country": h.get("country") or "",
            "region": h.get("region") or "",
            "lat": h["lat"],
            "lng": h["lng"],
            "sub_brand": h.get("sub_brand", ""),
            "status": h.get("status", ""),
            "opening_year": h.get("opening_year"),
            "keys": h.get("keys"),
            "owner": h.get("owner", ""),
            "operator": h.get("operator", ""),
            "notes": h.get("notes", ""),
            "source": h.get("source", ""),
            "verified": h.get("verified", True),
        }
        for h in hotels
    ], indent=2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{brand['brand']} &mdash; Brand Portfolio Map</title>
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
      border-bottom: 3px solid {color};
      padding: 14px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }}
    .header-left h1 {{ font-size: 18px; font-weight: 700; color: #fff; }}
    .header-left p {{ font-size: 11px; color: #8fa8d8; margin-top: 3px; }}
    .header-right {{ font-size: 11px; color: #8fa8d8; }}
    .header-right a {{ color: #8fa8d8; text-decoration: none; }}
    .header-right a:hover {{ color: #fff; }}
    .main {{ display: flex; flex: 1; overflow: hidden; }}
    .sidebar {{
      width: 320px;
      background: #fff;
      border-right: 1px solid #dde3ed;
      overflow-y: auto;
      flex-shrink: 0;
      box-shadow: 2px 0 8px rgba(0,0,0,0.06);
    }}
    .sb-section {{ padding: 14px; border-bottom: 1px solid #eaecf0; }}
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
      margin-bottom: 6px; font-size: 12px; color: #334;
    }}
    .leg-dot {{
      width: 14px; height: 14px;
      transform: rotate(45deg);
      border: 2px solid rgba(0,0,0,0.15);
      flex-shrink: 0;
    }}
    .hotel-item {{
      display: flex;
      align-items: flex-start;
      gap: 9px;
      padding: 9px 6px;
      cursor: pointer;
      border-bottom: 1px solid #f0f2f5;
    }}
    .hotel-item:hover {{ background: #f0f5ff; }}
    .h-pin {{
      width: 22px; height: 22px;
      transform: rotate(45deg);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }}
    .h-pin-num {{
      transform: rotate(-45deg);
      color: #fff;
      font-weight: 700;
      font-size: 10px;
    }}
    .h-info h4 {{ font-size: 12px; font-weight: 600; color: #1a2744; line-height: 1.3; }}
    .h-info .h-meta {{ font-size: 10px; color: #7080a0; margin-top: 2px; }}
    .sidebar-footer {{
      padding: 10px 14px;
      font-size: 10px;
      color: #aabbd0;
      border-top: 1px solid #eaecf0;
    }}
    #map {{ flex: 1; }}
    .gm-iw {{ font-family: 'Segoe UI', Arial, sans-serif; min-width: 240px; max-width: 290px; }}
    .gm-iw-title {{ font-size: 14px; font-weight: 700; color: #1a2744; line-height: 1.3; }}
    .gm-iw-brand {{ font-size: 10px; color: #1a2744; background: {color}; display: inline-block; padding: 2px 6px; border: 1px solid rgba(0,0,0,0.15); border-radius: 3px; text-transform: uppercase; letter-spacing: 0.6px; margin: 4px 0 8px; font-weight: 700; }}
    .gm-iw-meta {{ font-size: 11px; color: #556; margin-bottom: 3px; }}
    .gm-iw-stats {{ display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; font-size: 11px; margin: 8px 0 4px; padding-top: 8px; border-top: 1px solid #eee; }}
    .gm-iw-stats dt {{ color: #7080a0; font-weight: 600; }}
    .gm-iw-stats dd {{ color: #1a2744; }}
    .gm-iw-status {{ display: inline-block; font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }}
    .gm-iw-status.operating {{ background: #d1fae5; color: #047857; }}
    .gm-iw-status.under-construction {{ background: #fef3c7; color: #92400e; }}
    .gm-iw-status.announced {{ background: #e0e7ff; color: #3730a3; }}
    .gm-iw-notes {{ font-size: 10px; color: #556; margin-top: 6px; line-height: 1.4; font-style: italic; }}
    .gm-iw-source {{ font-size: 10px; margin-top: 6px; }}
    .gm-iw-source a {{ color: #2563eb; text-decoration: none; }}
    .gm-iw-source a:hover {{ text-decoration: underline; }}
    .gm-iw-unverified {{ font-size: 9px; color: #92400e; background: #fef3c7; padding: 1px 5px; border-radius: 3px; margin-left: 4px; font-weight: 600; letter-spacing: 0.3px; }}
    .h-status-badge {{ font-size: 8px; padding: 1px 4px; border-radius: 2px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; margin-left: 4px; vertical-align: middle; }}
    .h-status-badge.operating {{ background: #d1fae5; color: #047857; }}
    .h-status-badge.under-construction {{ background: #fef3c7; color: #92400e; }}
    .h-status-badge.announced {{ background: #e0e7ff; color: #3730a3; }}
    .breakdown-table {{ width: 100%; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }}
    .breakdown-table th, .breakdown-table td {{ padding: 0; text-align: right; line-height: 1.2; }}
    .breakdown-table th:first-child, .breakdown-table td:first-child {{ text-align: left; }}
    .breakdown-table thead th {{ font-size: 9.5px; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; padding: 5px 6px; }}
    .breakdown-table thead th.s-region   {{ background: #1a2744; border-top-left-radius: 4px; }}
    .breakdown-table thead th.s-operating          {{ background: #047857; }}
    .breakdown-table thead th.s-under-construction {{ background: #b45309; }}
    .breakdown-table thead th.s-announced          {{ background: #3730a3; }}
    .breakdown-table thead th.s-total              {{ background: #1a2744; border-top-right-radius: 4px; }}
    .breakdown-table tbody tr.r-hotels td {{ font-size: 13px; font-weight: 600; color: #1a2744; padding: 7px 6px 2px; }}
    .breakdown-table tbody tr.r-keys td {{ font-size: 10.5px; font-weight: 400; color: #7080a0; padding: 0 6px 7px; border-bottom: 1px solid #eef0f3; }}
    .breakdown-table tbody tr.r-keys td:first-child {{ font-style: italic; color: #a0aabe; padding-left: 18px; }}
    .breakdown-table tfoot tr.r-hotels td {{ font-size: 13px; font-weight: 800; color: #1a2744; padding: 9px 6px 2px; border-top: 2px solid #1a2744; }}
    .breakdown-table tfoot tr.r-keys td {{ font-size: 10.5px; font-weight: 600; color: #1a2744; padding: 0 6px 6px; }}
    .breakdown-table tfoot tr.r-keys td:first-child {{ font-style: italic; color: #556; font-weight: 500; padding-left: 18px; }}
    .breakdown-table td.dash {{ color: #d1d5db; font-weight: 400; }}
    .breakdown-note {{ font-size: 10px; color: #8090b0; margin-top: 10px; line-height: 1.45; font-style: italic; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>{brand['brand']} &mdash; Brand Portfolio</h1>
    <p>{brand.get('tagline', '')} &nbsp;&middot;&nbsp; {len(hotels)} properties mapped</p>
  </div>
  <div class="header-right">
    <a href="../">&larr; All Maps</a> &nbsp;&middot;&nbsp; <a href="../global/">Global Map</a>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sb-section">
      <h3>Legend</h3>
      <div class="legend-row"><div class="leg-dot" style="background:{color};"></div> {brand['brand']} Property</div>
    </div>
    <div class="sb-section" id="breakdown-section" style="display:none;">
      <h3>Footprint &mdash; Region &times; Status</h3>
      <div id="breakdown"></div>
    </div>
    <div class="sb-section" style="border-bottom:none;">
      <h3>Properties &mdash; Click to Navigate</h3>
      <div id="hotel-list"></div>
    </div>
    <div class="sidebar-footer">
      Reference map &middot; Brand portfolio only &middot; No STR performance data
    </div>
  </div>
  <div id="map"></div>
</div>

<script>
  const HOTELS = {hotels_js};
  const COLOR = "{color}";
  const STROKE = "{marker_stroke}";
  const LABEL_COLOR = "{label_color}";
  const BRAND = "{brand['brand']}";
  let map, infoWindow;
  const markers = [];

  function statusClass(status) {{
    return (status || '').toLowerCase().replace(/\\s+/g, '-');
  }}

  function buildInfoWindow(h) {{
    const fullAddr = [h.address, h.city, h.country].filter(Boolean).join(', ');
    const statusBadge = h.status
      ? `<span class="gm-iw-status ${{statusClass(h.status)}}">${{h.status}}</span>` : '';
    const unverified = (h.verified === false)
      ? '<span class="gm-iw-unverified">UNVERIFIED</span>' : '';
    const rows = [];
    if (h.sub_brand)    rows.push(`<dt>Sub-brand</dt><dd>${{h.sub_brand}}</dd>`);
    if (h.keys)         rows.push(`<dt>Keys</dt><dd>${{h.keys}}</dd>`);
    if (h.opening_year) rows.push(`<dt>Opened</dt><dd>${{h.opening_year}}</dd>`);
    if (h.region)       rows.push(`<dt>Region</dt><dd>${{h.region}}${{h.country ? ' · ' + h.country : ''}}</dd>`);
    if (h.owner)        rows.push(`<dt>Owner</dt><dd>${{h.owner}}</dd>`);
    if (h.operator)     rows.push(`<dt>Operator</dt><dd>${{h.operator}}</dd>`);
    const statsBlock = rows.length ? `<dl class="gm-iw-stats">${{rows.join('')}}</dl>` : '';
    const notesBlock = h.notes ? `<div class="gm-iw-notes">${{h.notes}}</div>` : '';
    const sourceBlock = h.source
      ? `<div class="gm-iw-source"><a href="${{h.source}}" target="_blank" rel="noopener">Source &rarr;</a></div>` : '';
    return `
      <div class="gm-iw">
        <div class="gm-iw-title">${{h.name}}${{unverified}}</div>
        <span class="gm-iw-brand">${{BRAND}}</span>
        ${{statusBadge}}
        <div class="gm-iw-meta">${{fullAddr}}</div>
        ${{statsBlock}}
        ${{notesBlock}}
        ${{sourceBlock}}
      </div>`;
  }}

  // Region × Status × (hotels, keys) breakdown — only renders if at least
  // one hotel has both region and status. Counts are computed from HOTELS
  // so future brands with the same schema get a table for free.
  function buildBreakdown() {{
    const STATUSES = ['operating', 'under construction', 'announced'];
    const STATUS_LABELS = {{
      'operating': 'Operating',
      'under construction': 'UC',
      'announced': 'Announced',
    }};
    const fmt = n => n ? n.toLocaleString() : '';

    const haveData = HOTELS.some(h => h.region && h.status);
    if (!haveData) return;

    // Preserve insertion order from the source data so brand authors can
    // sort regions however they want (here: Americas, EMEA, APAC, MEA).
    const regions = [];
    const grid = {{}};                 // region → status → {{ hotels, keys }}
    HOTELS.forEach(h => {{
      const r = h.region || '—';
      if (!grid[r]) {{
        grid[r] = {{}};
        regions.push(r);
      }}
      const s = (h.status || '').toLowerCase();
      const cell = grid[r][s] = grid[r][s] || {{ hotels: 0, keys: 0 }};
      cell.hotels += 1;
      cell.keys += Number(h.keys || 0);
    }});

    const colTotal = {{}};               // status → {{ hotels, keys }}
    const rowTotal = {{}};               // region → {{ hotels, keys }}
    let grand = {{ hotels: 0, keys: 0 }};
    STATUSES.forEach(s => colTotal[s] = {{ hotels: 0, keys: 0 }});
    regions.forEach(r => {{
      rowTotal[r] = {{ hotels: 0, keys: 0 }};
      STATUSES.forEach(s => {{
        const c = grid[r][s];
        if (!c) return;
        rowTotal[r].hotels += c.hotels;
        rowTotal[r].keys += c.keys;
        colTotal[s].hotels += c.hotels;
        colTotal[s].keys += c.keys;
        grand.hotels += c.hotels;
        grand.keys += c.keys;
      }});
    }});

    const hCell = c => c ? `${{c.hotels}}` : '<span class="dash">—</span>';
    const kCell = c => (c && c.keys) ? fmt(c.keys) : '<span class="dash">—</span>';

    const head = `<tr>
      <th class="s-region">Region</th>
      ${{STATUSES.map(s => `<th class="s-${{statusClass(s)}}">${{STATUS_LABELS[s]}}</th>`).join('')}}
      <th class="s-total">Total</th>
    </tr>`;

    // Two rows per region: hotels (primary) on top, keys (subordinate) below.
    const body = regions.map(r => {{
      const hotelsRow = `<tr class="r-hotels">
        <td>${{r}}</td>
        ${{STATUSES.map(s => `<td>${{hCell(grid[r][s])}}</td>`).join('')}}
        <td>${{hCell(rowTotal[r])}}</td>
      </tr>`;
      const keysRow = `<tr class="r-keys">
        <td>keys</td>
        ${{STATUSES.map(s => `<td>${{kCell(grid[r][s])}}</td>`).join('')}}
        <td>${{kCell(rowTotal[r])}}</td>
      </tr>`;
      return hotelsRow + keysRow;
    }}).join('');

    const foot = `<tr class="r-hotels">
        <td>Total</td>
        ${{STATUSES.map(s => `<td>${{hCell(colTotal[s])}}</td>`).join('')}}
        <td>${{hCell(grand)}}</td>
      </tr>
      <tr class="r-keys">
        <td>keys</td>
        ${{STATUSES.map(s => `<td>${{kCell(colTotal[s])}}</td>`).join('')}}
        <td>${{kCell(grand)}}</td>
      </tr>`;

    document.getElementById('breakdown').innerHTML = `
      <table class="breakdown-table">
        <thead>${{head}}</thead>
        <tbody>${{body}}</tbody>
        <tfoot>${{foot}}</tfoot>
      </table>
      <div class="breakdown-note">Top row of each region = number of hotels; bottom row = key count. A dash means none in that cell, or the property's key count hasn't been publicly disclosed yet.</div>`;
    document.getElementById('breakdown-section').style.display = '';
  }}

  function initMap() {{
    map = new google.maps.Map(document.getElementById('map'), {{
      center: {{ lat: {avg_lat}, lng: {avg_lng} }},
      zoom: 3,
      mapTypeControl: true,
      streetViewControl: false,
      fullscreenControl: true,
    }});
    infoWindow = new google.maps.InfoWindow({{ maxWidth: 310 }});

    const listEl = document.getElementById('hotel-list');
    const bounds = new google.maps.LatLngBounds();

    HOTELS.forEach((h, i) => {{
      const label = String(i + 1);
      const svgIcon = {{
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 34 34">
            <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="1.5" flood-opacity="0.35"/></filter>
            <rect x="6" y="6" width="22" height="22" transform="rotate(45 17 17)"
                  fill="${{COLOR}}" stroke="${{STROKE}}" stroke-width="2" filter="url(#s)"/>
            <text x="17" y="20" text-anchor="middle" font-family="Arial,sans-serif"
                  font-size="11" font-weight="bold" fill="${{LABEL_COLOR}}">${{label}}</text>
          </svg>`),
        scaledSize: new google.maps.Size(34, 34),
        anchor: new google.maps.Point(17, 17),
      }};

      const marker = new google.maps.Marker({{
        position: {{ lat: h.lat, lng: h.lng }},
        map,
        icon: svgIcon,
        title: h.name,
      }});
      markers.push(marker);
      bounds.extend({{ lat: h.lat, lng: h.lng }});

      const iwContent = buildInfoWindow(h);
      marker.addListener('click', () => {{
        infoWindow.setContent(iwContent);
        infoWindow.open(map, marker);
      }});

      const statusBadge = h.status
        ? `<span class="h-status-badge ${{statusClass(h.status)}}">${{h.status}}</span>` : '';
      const item = document.createElement('div');
      item.className = 'hotel-item';
      item.innerHTML = `
        <div class="h-pin" style="background:${{COLOR}}; border:1.5px solid ${{STROKE}};"><span class="h-pin-num" style="color:${{LABEL_COLOR}}">${{label}}</span></div>
        <div class="h-info">
          <h4>${{h.name}}${{statusBadge}}</h4>
          <div class="h-meta">${{[h.city, h.country].filter(Boolean).join(', ')}}</div>
        </div>`;
      item.addEventListener('click', () => {{
        map.panTo({{ lat: h.lat, lng: h.lng }});
        map.setZoom(14);
        infoWindow.setContent(iwContent);
        infoWindow.open(map, marker);
      }});
      listEl.appendChild(item);
    }});

    map.fitBounds(bounds, {{ top: 60, right: 60, bottom: 60, left: 60 }});
  }}

  buildBreakdown();
</script>
<script src="https://maps.googleapis.com/maps/api/js?key={API_KEY}&callback=initMap" async defer></script>

</body>
</html>"""


def update_root_index(brand, hotel_count):
    """Add a brand entry to root index.html if not already present."""
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    href = f'./{brand["slug"]}/'
    if f'href="{href}"' in content:
        print(f"  {brand['brand']} already in root index.html")
        return

    new_entry = f"""      <li>
        <a href="{href}">
          {brand['brand']} &mdash; Brand Portfolio
          <div class="meta">Reference map &middot; {hotel_count} properties &middot; Brand footprint only</div>
        </a>
      </li>"""

    if "<!-- MAPS_END -->" not in content:
        print("  WARNING: <!-- MAPS_END --> marker missing from index.html; skipping insert")
        return

    content = content.replace("      <!-- MAPS_END -->", f"{new_entry}\n      <!-- MAPS_END -->")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Added {brand['brand']} to root index.html")


def process_brand(json_path):
    brand = load_brand(json_path)
    print(f"\n{'=' * 60}")
    print(f"Processing brand: {brand['brand']} ({brand['slug']})")
    print('=' * 60)

    geocode_brand(brand)
    html = render_html(brand)

    output_dir = os.path.join(REPO_DIR, brand["slug"])
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {output_path}")

    geocoded = sum(1 for h in brand["hotels"] if h.get("lat"))
    update_root_index(brand, geocoded)
    return brand


def regenerate_global_map():
    import generate_global_map as ggm
    print(f"\n{'=' * 60}")
    print("Regenerating global combined map (with brands)...")
    print('=' * 60)
    comp_sets = ggm.build_payload()
    if not comp_sets:
        print("  WARNING: no comp sets parsed for global map")
        return
    os.makedirs(ggm.OUTPUT_DIR, exist_ok=True)
    html = ggm.render_html(comp_sets)
    with open(ggm.OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Global map saved: {ggm.OUTPUT_PATH}")
    ggm.update_root_index_link()


def main():
    parser = argparse.ArgumentParser(description="Generate brand portfolio maps")
    parser.add_argument("brands", nargs="*",
                        help="Brand slug(s) — e.g. 'capella'. Defaults to all brands in brands/.")
    parser.add_argument("--deploy", action="store_true",
                        help="Push to GitHub Pages and verify after generating")
    parser.add_argument("--no-global", action="store_true",
                        help="Skip regenerating the global combined map")
    args = parser.parse_args()

    files = list_brand_files(args.brands or None)
    if not files:
        print(f"No brand JSON files found in {BRANDS_DIR}")
        sys.exit(1)

    processed = [process_brand(p) for p in files]

    if not args.no_global:
        regenerate_global_map()

    print(f"\n{'=' * 60}")
    print(f"Generated {len(processed)} brand map(s):")
    for b in processed:
        print(f"  - {b['brand']} -> /{b['slug']}/")
    if not args.no_global:
        print(f"  - Global combined map -> /global/")
    print('=' * 60)

    if not args.deploy:
        print("\nTo deploy, re-run with --deploy")
        for b in processed:
            print(f"  Will be live at: {PAGES_BASE_URL}/{b['slug']}/")
        return

    print("\nDeploying to GitHub Pages...")
    names = ", ".join(b["brand"] for b in processed)
    commit_msg = f"Add brand portfolio map(s): {names}"
    _commit_and_push(commit_msg)

    urls = [f"{PAGES_BASE_URL}/{b['slug']}/" for b in processed]
    if not args.no_global:
        urls.append(f"{PAGES_BASE_URL}/global/")
    ok = verify_deploy(urls)

    print(f"\n{'=' * 60}")
    print("DEPLOY VERIFIED [OK]" if ok else "DEPLOY INCOMPLETE — see warnings above")
    for u in urls:
        print(f"  {u}")
    print('=' * 60)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
