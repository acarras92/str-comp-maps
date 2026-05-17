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

    # Owner-portfolio mode: same renderer, a few label swaps. A single Al-Bahar
    # owner-page spans Yotel, Fairmont, voco, etc., so the info-window chip
    # shows each property's own brand flag instead of the portfolio name.
    # Multi-brand mode: same chip behavior as owner, but the legend is
    # color-coded per sub_brand (one row per flag) instead of one ownership row.
    ptype = brand.get("portfolio_type", "brand")
    is_owner = ptype == "owner"
    is_multi = ptype == "multi-brand"
    chip_per_property = is_owner or is_multi
    header_suffix = (
        "Multi-Brand Portfolio" if is_multi
        else "Owner Portfolio" if is_owner
        else "Brand Portfolio"
    )
    legend_label = (
        f"Property in this portfolio" if is_multi
        else f"{brand['brand']}-owned property" if is_owner
        else f"{brand['brand']} Property"
    )
    footer_label = (
        "Reference map &middot; Multi-brand portfolio &middot; pins color-coded by sub-brand" if is_multi
        else "Reference map &middot; Ownership portfolio &middot; brand flag shown per property" if is_owner
        else "Reference map &middot; Brand portfolio only &middot; No STR performance data"
    )
    sub_brand_colors = brand.get("sub_brand_colors") or {}
    sub_brand_colors_js = json.dumps(sub_brand_colors, indent=2)
    scope_groups = brand.get("scope_groups") or []
    scope_groups_js = json.dumps(scope_groups, indent=2)

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
  <title>{brand['brand']} &mdash; {header_suffix} Map</title>
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
      margin-bottom: 2px; font-size: 12px; color: #334;
      padding: 4px 6px; margin-left: -6px; margin-right: -6px; border-radius: 4px;
    }}
    .legend-row.clickable {{ cursor: pointer; user-select: none; }}
    .legend-row.clickable:hover {{ background: #f0f5ff; }}
    .legend-row.off {{ opacity: 0.35; }}
    .legend-row.off .leg-dot {{ background: #cbd5e1 !important; border-color: #cbd5e1 !important; }}
    .leg-dot {{
      width: 14px; height: 14px;
      transform: rotate(45deg);
      border: 2px solid rgba(0,0,0,0.15);
      flex-shrink: 0;
    }}
    .filter-pills {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .filter-pill {{
      display: inline-flex; align-items: center; gap: 6px;
      padding: 3px 9px; border-radius: 12px;
      font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px;
      cursor: pointer; user-select: none;
      border: 1.5px solid; background: #fff;
    }}
    .filter-pill.off {{ opacity: 0.35; background: #f3f4f6; }}
    .filter-pill .pill-count {{
      font-weight: 400; opacity: 0.7;
      font-variant-numeric: tabular-nums; letter-spacing: 0;
    }}
    .filter-pill.s-operating          {{ color: #047857; border-color: #047857; }}
    .filter-pill.s-under-construction {{ color: #92400e; border-color: #92400e; }}
    .filter-pill.s-announced          {{ color: #3730a3; border-color: #3730a3; }}
    .filter-pill.s-uncertain          {{ color: #4b5563; border-color: #4b5563; }}
    .fit-btn {{
      width: 100%; margin-top: 10px; padding: 6px 10px;
      font-size: 11px; font-weight: 600; color: #1a2744;
      background: #f0f5ff; border: 1px solid #c8d4e8; border-radius: 4px;
      cursor: pointer;
    }}
    .fit-btn:hover {{ background: #e0eaff; }}
    .filter-note {{ font-size: 10px; color: #8090b0; margin-top: 8px; font-style: italic; line-height: 1.4; }}
    .hotel-item.off {{ display: none; }}
    .scope-tabs {{ display: flex; gap: 4px; flex-wrap: wrap; }}
    .scope-tab {{
      flex: 1 1 auto; min-width: 60px;
      padding: 7px 8px; text-align: center;
      font-size: 11px; font-weight: 700; color: #1a2744;
      background: #f0f5ff; border: 1.5px solid #c8d4e8; border-radius: 4px;
      cursor: pointer; user-select: none;
    }}
    .scope-tab:hover {{ background: #e0eaff; }}
    .scope-tab.active {{ background: #1a2744; color: #fff; border-color: #1a2744; }}
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
    .gm-iw-status.uncertain {{ background: #f3f4f6; color: #4b5563; }}
    .gm-iw-notes {{ font-size: 10px; color: #556; margin-top: 6px; line-height: 1.4; font-style: italic; }}
    .gm-iw-source {{ font-size: 10px; margin-top: 6px; }}
    .gm-iw-source a {{ color: #2563eb; text-decoration: none; }}
    .gm-iw-source a:hover {{ text-decoration: underline; }}
    .gm-iw-unverified {{ font-size: 9px; color: #92400e; background: #fef3c7; padding: 1px 5px; border-radius: 3px; margin-left: 4px; font-weight: 600; letter-spacing: 0.3px; }}
    .h-status-badge {{ font-size: 8px; padding: 1px 4px; border-radius: 2px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; margin-left: 4px; vertical-align: middle; }}
    .h-status-badge.operating {{ background: #d1fae5; color: #047857; }}
    .h-status-badge.under-construction {{ background: #fef3c7; color: #92400e; }}
    .h-status-badge.announced {{ background: #e0e7ff; color: #3730a3; }}
    .h-status-badge.uncertain {{ background: #f3f4f6; color: #4b5563; }}
    .breakdown-table {{ width: 100%; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }}
    .breakdown-table th, .breakdown-table td {{ padding: 0; text-align: right; line-height: 1.2; }}
    .breakdown-table th:first-child, .breakdown-table td:first-child {{ text-align: left; }}
    .breakdown-table tbody td + td, .breakdown-table tfoot td + td {{ border-left: 1px solid #eef0f3; }}
    .breakdown-table thead th + th {{ border-left: 1px solid rgba(255,255,255,0.25); }}
    .breakdown-table thead th {{ font-size: 9.5px; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; padding: 5px 6px; }}
    .breakdown-table thead th.s-region   {{ background: #1a2744; border-top-left-radius: 4px; }}
    .breakdown-table thead th.s-operating          {{ background: #047857; }}
    .breakdown-table thead th.s-under-construction {{ background: #b45309; }}
    .breakdown-table thead th.s-announced          {{ background: #3730a3; }}
    .breakdown-table thead th.s-uncertain          {{ background: #6b7280; }}
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
    <h1>{brand['brand']} &mdash; {header_suffix}</h1>
    <p>{brand.get('tagline', '')} &nbsp;&middot;&nbsp; {len(hotels)} properties mapped</p>
  </div>
  <div class="header-right">
    <a href="../">&larr; All Maps</a> &nbsp;&middot;&nbsp; <a href="../global/">Global Map</a>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sb-section" id="scope-section" style="display:none;">
      <h3>Scope</h3>
      <div class="scope-tabs" id="scope-tabs"></div>
    </div>
    <div class="sb-section">
      <h3>Legend <span id="legend-hint" style="display:none;font-size:9px;color:#8090b0;text-transform:none;letter-spacing:0;font-style:italic;">&middot; click to toggle</span></h3>
      <div id="legend"></div>
    </div>
    <div class="sb-section" id="filter-section" style="display:none;">
      <h3>Filter by status</h3>
      <div class="filter-pills" id="status-filters"></div>
      <button class="fit-btn" id="fit-btn">Fit map to visible</button>
      <div class="filter-note" id="filter-note"></div>
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
      {footer_label}
    </div>
  </div>
  <div id="map"></div>
</div>

<script>
  const HOTELS = {hotels_js};
  const COLOR = "{color}";
  const STROKE = "{marker_stroke}";
  const LABEL_COLOR = "{label_color}";
  const SUB_BRAND_COLORS = {sub_brand_colors_js};
  const SCOPE_GROUPS = {scope_groups_js};
  const BRAND = "{brand['brand']}";
  const PORTFOLIO_TYPE = "{ptype}";
  let map, infoWindow;
  const markers = [];
  const listItems = [];   // hotel-list <div>s, parallel to markers / HOTELS
  const filterState = {{
    subBrands: new Set(),  // populated on init from HOTELS — all on
    statuses:  new Set(),  // populated on init from HOTELS — all on
  }};

  function statusClass(status) {{
    return (status || '').toLowerCase().replace(/\\s+/g, '-');
  }}

  // Pin color resolver: per-sub_brand override (multi-brand portfolios) →
  // top-level brand color (single-brand or owner portfolios). A string-typed
  // sub_brand_colors value is treated as just the fill, with default stroke/label.
  // SVG marker icon, parameterized by pin colors and label number.
  // Pulled into a helper so applyFilters() can regenerate icons cheaply when
  // pins get renumbered to the currently-visible set.
  function iconFor(pin, label) {{
    return {{
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 34 34">
          <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="1.5" flood-opacity="0.35"/></filter>
          <rect x="6" y="6" width="22" height="22" transform="rotate(45 17 17)"
                fill="${{pin.fill}}" stroke="${{pin.stroke}}" stroke-width="2" filter="url(#s)"/>
          <text x="17" y="20" text-anchor="middle" font-family="Arial,sans-serif"
                font-size="11" font-weight="bold" fill="${{pin.label}}">${{label}}</text>
        </svg>`),
      scaledSize: new google.maps.Size(34, 34),
      anchor: new google.maps.Point(17, 17),
    }};
  }}

  function pinFor(h) {{
    const entry = SUB_BRAND_COLORS[h.sub_brand];
    if (!entry) return {{ fill: COLOR, stroke: STROKE, label: LABEL_COLOR }};
    if (typeof entry === 'string')
      return {{ fill: entry, stroke: STROKE, label: LABEL_COLOR }};
    return {{
      fill: entry.fill || COLOR,
      stroke: entry.stroke || STROKE,
      label: entry.label || LABEL_COLOR,
    }};
  }}

  function buildInfoWindow(h) {{
    const fullAddr = [h.address, h.city, h.country].filter(Boolean).join(', ');
    const statusBadge = h.status
      ? `<span class="gm-iw-status ${{statusClass(h.status)}}">${{h.status}}</span>` : '';
    const unverified = (h.verified === false)
      ? '<span class="gm-iw-unverified">UNVERIFIED</span>' : '';
    const rows = [];
    // In owner/multi-brand modes the chip already shows sub_brand (the flag), so skip the row.
    if (h.sub_brand && PORTFOLIO_TYPE !== "owner" && PORTFOLIO_TYPE !== "multi-brand")
      rows.push(`<dt>Sub-brand</dt><dd>${{h.sub_brand}}</dd>`);
    if (h.keys)         rows.push(`<dt>Keys</dt><dd>${{h.keys}}</dd>`);
    if (h.opening_year) rows.push(`<dt>Opened</dt><dd>${{h.opening_year}}</dd>`);
    if (h.region)       rows.push(`<dt>Region</dt><dd>${{h.region}}${{h.country ? ' · ' + h.country : ''}}</dd>`);
    if (h.owner)        rows.push(`<dt>${{PORTFOLIO_TYPE === "owner" ? "Vehicle" : "Owner"}}</dt><dd>${{h.owner}}</dd>`);
    if (h.operator)     rows.push(`<dt>Operator</dt><dd>${{h.operator}}</dd>`);
    const statsBlock = rows.length ? `<dl class="gm-iw-stats">${{rows.join('')}}</dl>` : '';
    const notesBlock = h.notes ? `<div class="gm-iw-notes">${{h.notes}}</div>` : '';
    const sourceBlock = h.source
      ? `<div class="gm-iw-source"><a href="${{h.source}}" target="_blank" rel="noopener">Source &rarr;</a></div>` : '';
    // Owner / multi-brand modes: chip shows each property's sub-brand flag.
    // Brand mode: chip shows the portfolio name (e.g. "Capella").
    // In multi-brand mode the chip also gets tinted to match the pin so the
    // legend/pin/chip color story stays consistent.
    const chipLabel = (PORTFOLIO_TYPE === "owner" || PORTFOLIO_TYPE === "multi-brand")
      ? (h.sub_brand || BRAND) : BRAND;
    const chipStyle = (PORTFOLIO_TYPE === "multi-brand")
      ? `background:${{pinFor(h).fill}};color:${{pinFor(h).label}};` : '';
    return `
      <div class="gm-iw">
        <div class="gm-iw-title">${{h.name}}${{unverified}}</div>
        <span class="gm-iw-brand" style="${{chipStyle}}">${{chipLabel}}</span>
        ${{statusBadge}}
        <div class="gm-iw-meta">${{fullAddr}}</div>
        ${{statsBlock}}
        ${{notesBlock}}
        ${{sourceBlock}}
      </div>`;
  }}

  // Region × Status × (hotels, keys) breakdown — only renders if at least
  // one hotel has both region and status. Counts are computed from currently
  // visible hotels (driven by filterState), so the table re-aggregates whenever
  // a scope tab, legend row, or status pill is toggled.
  function buildBreakdown() {{
    const ALL_STATUSES = ['operating', 'under construction', 'announced', 'uncertain'];
    const STATUS_LABELS = {{
      'operating': 'Operating',
      'under construction': 'UC',
      'announced': 'Announced',
      'uncertain': 'Uncertain',
    }};
    const fmt = n => n ? n.toLocaleString() : '';

    const haveData = HOTELS.some(h => h.region && h.status);
    if (!haveData) return;

    // Use the same visibility rule the markers use, so the footprint table
    // always reflects what's currently on the map.
    const visible = HOTELS.filter(h => {{
      const sbOn = filterState.subBrands.size === 0 || filterState.subBrands.has(h.sub_brand || '');
      const stOn = !h.status || filterState.statuses.size === 0 || filterState.statuses.has((h.status || '').toLowerCase());
      return sbOn && stOn;
    }});

    // Status columns: keep the set stable across re-renders by anchoring on the
    // statuses present in the FULL dataset, not just the visible subset (otherwise
    // toggling everything off would collapse the table to zero columns and
    // turning things back on would jump column widths around).
    const STATUSES = ALL_STATUSES.filter(
      s => HOTELS.some(h => (h.status || '').toLowerCase() === s)
    );

    // Region rows likewise — stable order, hide rows that the filter zeroes out.
    const regions = [];
    const grid = {{}};                 // region → status → {{ hotels, keys }}
    HOTELS.forEach(h => {{
      const r = h.region || '—';
      if (!regions.includes(r)) regions.push(r);
    }});
    visible.forEach(h => {{
      const r = h.region || '—';
      if (!grid[r]) grid[r] = {{}};
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
        const c = grid[r] && grid[r][s];
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
    const cellFor = (r, s) => (grid[r] || {{}})[s];

    const head = `<tr>
      <th class="s-region">Region</th>
      ${{STATUSES.map(s => `<th class="s-${{statusClass(s)}}">${{STATUS_LABELS[s]}}</th>`).join('')}}
      <th class="s-total">Total</th>
    </tr>`;

    // Two rows per region: hotels (primary) on top, keys (subordinate) below.
    // Skip regions that filter to zero so the table doesn't show empty rows.
    const body = regions.map(r => {{
      if (rowTotal[r].hotels === 0) return '';
      const hotelsRow = `<tr class="r-hotels">
        <td>${{r}}</td>
        ${{STATUSES.map(s => `<td>${{hCell(cellFor(r, s))}}</td>`).join('')}}
        <td>${{hCell(rowTotal[r])}}</td>
      </tr>`;
      const keysRow = `<tr class="r-keys">
        <td>keys</td>
        ${{STATUSES.map(s => `<td>${{kCell(cellFor(r, s))}}</td>`).join('')}}
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

  // Legend: per-sub_brand swatches in multi-brand mode (only flags actually
  // present in HOTELS, in the order they appear in SUB_BRAND_COLORS); single
  // brand swatch otherwise. Counts come from HOTELS so the legend doubles as
  // a footprint summary.
  function buildLegend() {{
    const el = document.getElementById('legend');
    const fallback = `<div class="legend-row"><div class="leg-dot" style="background:${{COLOR}}; border-color:${{STROKE}};"></div> {legend_label}</div>`;
    if (PORTFOLIO_TYPE !== "multi-brand" || !Object.keys(SUB_BRAND_COLORS).length) {{
      el.innerHTML = fallback;
      return;
    }}
    const counts = {{}};
    HOTELS.forEach(h => {{ counts[h.sub_brand] = (counts[h.sub_brand] || 0) + 1; }});
    const order = Object.keys(SUB_BRAND_COLORS).filter(sb => counts[sb]);
    Object.keys(counts).forEach(sb => {{ if (!order.includes(sb)) order.push(sb); }});
    el.innerHTML = order.map(sb => {{
      const p = pinFor({{ sub_brand: sb }});
      return `<div class="legend-row clickable" data-sub-brand="${{sb}}"><div class="leg-dot" style="background:${{p.fill}}; border-color:${{p.stroke}};"></div> ${{sb}} <span style="margin-left:auto;color:#8090b0;font-variant-numeric:tabular-nums;">${{counts[sb]}}</span></div>`;
    }}).join('');
    el.querySelectorAll('.legend-row.clickable').forEach(row => {{
      row.addEventListener('click', () => {{
        const sb = row.getAttribute('data-sub-brand');
        if (filterState.subBrands.has(sb)) filterState.subBrands.delete(sb);
        else filterState.subBrands.add(sb);
        row.classList.toggle('off', !filterState.subBrands.has(sb));
        applyFilters();
      }});
    }});
    document.getElementById('legend-hint').style.display = '';
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
      const pin = pinFor(h);
      const svgIcon = iconFor(pin, label);

      const marker = new google.maps.Marker({{
        position: {{ lat: h.lat, lng: h.lng }},
        map,
        icon: svgIcon,
        title: h.name,
      }});
      markers.push(marker);
      bounds.extend({{ lat: h.lat, lng: h.lng }});
      filterState.subBrands.add(h.sub_brand || '');
      if (h.status) filterState.statuses.add(h.status.toLowerCase());

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
        <div class="h-pin" style="background:${{pin.fill}}; border:1.5px solid ${{pin.stroke}};"><span class="h-pin-num" style="color:${{pin.label}}">${{label}}</span></div>
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
      listItems.push(item);
    }});

    map.fitBounds(bounds, {{ top: 60, right: 60, bottom: 60, left: 60 }});
    buildScopeTabs();
    buildLegend();
    buildStatusFilters();
    applyFilters();
  }}

  // Show/hide markers + list items based on filterState. Each hotel is
  // visible iff its sub_brand is on AND its status is on. Visible hotels are
  // renumbered 1..N in input order, so the labels always start at 1 regardless
  // of how many are filtered out. Hidden markers keep their stale numbers —
  // they're invisible, so it doesn't matter.
  function applyFilters() {{
    let visibleCount = 0;
    HOTELS.forEach((h, i) => {{
      const sbOn = filterState.subBrands.has(h.sub_brand || '');
      const stOn = !h.status || filterState.statuses.has((h.status || '').toLowerCase());
      const on = sbOn && stOn;
      markers[i].setVisible(on);
      listItems[i].classList.toggle('off', !on);
      if (on) {{
        visibleCount += 1;
        const label = String(visibleCount);
        markers[i].setIcon(iconFor(pinFor(h), label));
        const numEl = listItems[i].querySelector('.h-pin-num');
        if (numEl) numEl.textContent = label;
      }}
    }});
    const noteEl = document.getElementById('filter-note');
    if (noteEl) noteEl.textContent = `${{visibleCount}} of ${{HOTELS.length}} properties visible`;
    buildBreakdown();
    syncScopeTabs();
  }}

  // One-click scope tabs: each tab snaps filterState.subBrands to a preset
  // group (e.g. just Compass), All restores everything, and the active tab
  // gets highlighted when the current sub-brand filter matches a group exactly.
  // Status pills are intentionally NOT touched — scope vs. status are
  // orthogonal axes.
  function buildScopeTabs() {{
    if (!SCOPE_GROUPS.length || PORTFOLIO_TYPE !== "multi-brand") return;
    const allSubs = Object.keys(SUB_BRAND_COLORS).length
      ? Object.keys(SUB_BRAND_COLORS)
      : [...new Set(HOTELS.map(h => h.sub_brand || ''))];
    const tabs = [{{ label: 'All', sub_brands: allSubs }}, ...SCOPE_GROUPS];
    const wrap = document.getElementById('scope-tabs');
    wrap.innerHTML = tabs.map((g, i) =>
      `<span class="scope-tab" data-idx="${{i}}">${{g.label}}</span>`
    ).join('');
    wrap.querySelectorAll('.scope-tab').forEach(el => {{
      el.addEventListener('click', () => {{
        const g = tabs[Number(el.getAttribute('data-idx'))];
        filterState.subBrands = new Set(g.sub_brands);
        document.querySelectorAll('.legend-row.clickable').forEach(row => {{
          const sb = row.getAttribute('data-sub-brand');
          row.classList.toggle('off', !filterState.subBrands.has(sb));
        }});
        applyFilters();
        fitVisible();
      }});
    }});
    document.getElementById('scope-section').style.display = '';
    syncScopeTabs(tabs);
  }}

  // Highlight whichever tab matches the current sub-brand filter set
  // (or none, if the user has fine-tuned via individual legend rows).
  function syncScopeTabs(tabs) {{
    const wrap = document.getElementById('scope-tabs');
    if (!wrap || !wrap.children.length) return;
    const current = new Set(filterState.subBrands);
    const allSubs = Object.keys(SUB_BRAND_COLORS).length
      ? Object.keys(SUB_BRAND_COLORS)
      : [...new Set(HOTELS.map(h => h.sub_brand || ''))];
    const t = tabs || [{{ label: 'All', sub_brands: allSubs }}, ...SCOPE_GROUPS];
    [...wrap.children].forEach((el, i) => {{
      const g = t[i];
      const match = g.sub_brands.length === current.size
        && g.sub_brands.every(s => current.has(s));
      el.classList.toggle('active', match);
    }});
  }}

  function fitVisible() {{
    const b = new google.maps.LatLngBounds();
    let any = false;
    HOTELS.forEach((h, i) => {{
      if (markers[i].getVisible()) {{ b.extend({{ lat: h.lat, lng: h.lng }}); any = true; }}
    }});
    if (any) map.fitBounds(b, {{ top: 60, right: 60, bottom: 60, left: 60 }});
  }}

  // Status pills, one per status actually present in HOTELS. Each pill
  // toggles its status in filterState and re-applies filters. Order matches
  // the breakdown table (Operating → UC → Announced → Uncertain).
  function buildStatusFilters() {{
    const ALL_STATUSES = ['operating', 'under construction', 'announced', 'uncertain'];
    const STATUS_LABELS = {{
      'operating': 'Operating',
      'under construction': 'UC',
      'announced': 'Pipeline',
      'uncertain': 'Uncertain',
    }};
    const counts = {{}};
    HOTELS.forEach(h => {{
      const s = (h.status || '').toLowerCase();
      if (!s) return;
      counts[s] = (counts[s] || 0) + 1;
    }});
    const statuses = ALL_STATUSES.filter(s => counts[s]);
    if (!statuses.length) return;
    const wrap = document.getElementById('status-filters');
    wrap.innerHTML = statuses.map(s =>
      `<span class="filter-pill s-${{statusClass(s)}}" data-status="${{s}}">${{STATUS_LABELS[s]}} <span class="pill-count">${{counts[s]}}</span></span>`
    ).join('');
    wrap.querySelectorAll('.filter-pill').forEach(el => {{
      el.addEventListener('click', () => {{
        const s = el.getAttribute('data-status');
        if (filterState.statuses.has(s)) filterState.statuses.delete(s);
        else filterState.statuses.add(s);
        el.classList.toggle('off', !filterState.statuses.has(s));
        applyFilters();
      }});
    }});
    document.getElementById('fit-btn').addEventListener('click', fitVisible);
    document.getElementById('filter-section').style.display = '';
  }}
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

    is_owner = brand.get("portfolio_type") == "owner"
    title_suffix = "Owner Portfolio" if is_owner else "Brand Portfolio"
    meta_text = (
        f"Reference map &middot; {hotel_count} properties &middot; Ownership footprint (multi-brand)"
        if is_owner
        else f"Reference map &middot; {hotel_count} properties &middot; Brand footprint only"
    )
    new_entry = f"""      <li>
        <a href="{href}">
          {brand['brand']} &mdash; {title_suffix}
          <div class="meta">{meta_text}</div>
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
