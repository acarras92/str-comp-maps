#!/usr/bin/env python3
"""
Holiday Inn Manhattan Chelsea — STR Comp Set Map (one-off).

Source data is a HospitalityDataGrid + Participation export (not the standard
Response/Glance STR report), so there is NO subject-vs-comp split and no
MPI/ARI/RGI. The only performance figure available is a blended R12 composite
for the entire tracked panel (subject + comps), shown here labeled as such.

Comp order is fixed per the request; subject is starred as #1.

Usage:
    python generate_chelsea_map.py            # generate only
    python generate_chelsea_map.py --deploy   # generate + push to GitHub Pages
"""

import argparse
import os

import generate_str_map as base

REPORT_PERIOD = "Apr 2026"  # R12 ending
SLUG = "holiday-inn-manhattan-chelsea"  # clean URL slug

# Tracked-panel composite R12 (subject + 7 comps blended) from HospitalityDataGrid
PANEL = {"occ": "91.7%", "adr": "$278", "revpar": "$255"}

# Hotels in the requested display order. Subject first (starred #1), comps 2-8.
HOTELS = [
    {"name": "Holiday Inn Manhattan 6th Ave - Chelsea", "subject": True,
     "address": "125 W 26th St", "city_state": "New York, NY", "zip": "10001",
     "rooms": 226, "str_id": ""},
    {"name": "Hilton Garden Inn New York Times Square South", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10018",
     "rooms": 250, "str_id": "9571683"},
    {"name": "Fairfield by Marriott Inn & Suites New York Midtown Manhattan/Penn Station",
     "subject": False, "address": "", "city_state": "New York, NY", "zip": "10001",
     "rooms": 239, "str_id": "9208355"},
    {"name": "Hilton Garden Inn New York Times Square Central", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10036",
     "rooms": 282, "str_id": "6529472"},
    {"name": "Holiday Inn New York City Times Square", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10018",
     "rooms": 271, "str_id": "9569480"},
    {"name": "Delta Hotels New York Times Square", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10018",
     "rooms": 310, "str_id": "8229453"},
    {"name": "Courtyard New York Manhattan/Times Square West", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10018",
     "rooms": 224, "str_id": "5000125"},
    {"name": "voco Times Square South", "subject": False,
     "address": "", "city_state": "New York, NY", "zip": "10018",
     "rooms": 224, "str_id": "6209181"},
]


def render_html(hotels, comp_rooms):
    subject = next(h for h in hotels if h["subject"])
    comps = [h for h in hotels if not h["subject"]]
    hotel_name = subject["name"]

    # Build JS array. Display index: subject -> star, comps -> 2..N (i+1).
    hotels_js = "const HOTELS = [\n"
    for i, h in enumerate(hotels):
        full_addr = f"{h.get('address', '')}, {h['city_state']} {h['zip']}".strip(", ")
        hotels_js += f"""    {{
      idx: {i + 1}, subject: {'true' if h['subject'] else 'false'},
      name: {h['name']!r}, address: {full_addr!r},
      city: {h['city_state']!r}, rooms: {h['rooms']}, strId: {h['str_id']!r},
      lat: {h['lat']}, lng: {h['lng']},
    }},\n"""
    hotels_js += "  ];"

    avg_lat = sum(h["lat"] for h in hotels) / len(hotels)
    avg_lng = sum(h["lng"] for h in hotels) / len(hotels)

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
    <p>{subject['city_state']} &nbsp;&middot;&nbsp; R12 ending {REPORT_PERIOD} &nbsp;&middot;&nbsp; 1 Subject + {len(comps)} Comps &nbsp;&middot;&nbsp; {comp_rooms:,} Comp Rooms</p>
  </div>
  <div class="header-right">
    <div class="kpi-card"><div class="k-label">Occupancy</div><div class="k-value">{PANEL['occ']}</div></div>
    <div class="kpi-sep"></div>
    <div class="kpi-card"><div class="k-label">ADR</div><div class="k-value">{PANEL['adr']}</div></div>
    <div class="kpi-sep"></div>
    <div class="kpi-card"><div class="k-label">RevPAR</div><div class="k-value">{PANEL['revpar']}</div></div>
    <div class="str-badge">Panel Composite &middot; R12 {REPORT_PERIOD}</div>
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
      <h3>Tracked Panel Composite &mdash; R12 ending {REPORT_PERIOD}</h3>
      <div class="perf-grid">
        <div class="perf-cell"><div class="p-metric">Occ</div><div class="p-value">{PANEL['occ']}</div></div>
        <div class="perf-cell"><div class="p-metric">ADR</div><div class="p-value">{PANEL['adr']}</div></div>
        <div class="perf-cell"><div class="p-metric">RevPAR</div><div class="p-value">{PANEL['revpar']}</div></div>
      </div>
      <div class="perf-note">Blended performance for the full tracked panel (subject + comps). Source export does not provide a subject-vs-comp split or MPI/ARI/RGI indices.</div>
    </div>

    <div class="sb-section" style="flex:1; border-bottom:none;">
      <h3>Properties &mdash; Click to Navigate</h3>
      <div id="hotel-list"></div>
    </div>

    <div class="sidebar-footer">
      Source: STR HospitalityDataGrid / Participation export &middot; R12 ending {REPORT_PERIOD}
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
      mapTypeControlOptions: {{ style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR, position: google.maps.ControlPosition.TOP_RIGHT }},
      streetViewControl: true,
      fullscreenControl: true,
      styles: [
        {{ featureType: "poi.business", stylers: [{{ visibility: "off" }}] }},
        {{ featureType: "transit", stylers: [{{ visibility: "simplified" }}] }}
      ]
    }});

    infoWindow = new google.maps.InfoWindow({{ maxWidth: 290 }});

    const listEl = document.getElementById('hotel-list');
    const bounds = new google.maps.LatLngBounds();

    HOTELS.forEach((h) => {{
      const label = h.subject ? '★' : String(h.idx);
      const color = h.subject ? '#c62828' : '#1565c0';

      const svgIcon = {{
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">
            <filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.35"/></filter>
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
        map, icon: svgIcon, title: h.name,
        zIndex: h.subject ? 100 : h.idx
      }});

      markers.push(marker);
      bounds.extend({{ lat: h.lat, lng: h.lng }});

      const iwContent = `
        <div class="gm-iw">
          <div class="gm-iw-title">${{h.idx}}. ${{h.name}}</div>
          <div>
            <span class="gm-iw-badge">${{h.rooms.toLocaleString()}} Keys</span>
            ${{h.subject ? '<span class="gm-iw-subject-badge">Subject Property</span>' : ''}}
          </div>
          <div class="gm-iw-meta" style="margin-top:6px;">${{h.address}}</div>
          ${{h.strId ? `<div class="gm-iw-str">STR ID: ${{h.strId}}</div>` : ''}}
          ${{h.subject
              ? '<div class="gm-iw-masked">Subject shown within tracked panel composite (no standalone STR figures in this export)</div>'
              : '<div class="gm-iw-masked">Individual comp performance not provided in this export</div>'}}
        </div>`;

      marker.addListener('click', () => {{ infoWindow.setContent(iwContent); infoWindow.open(map, marker); }});

      const item = document.createElement('div');
      item.className = `hotel-item${{h.subject ? ' is-subject' : ''}}`;
      item.innerHTML = `
        <div class="h-pin ${{h.subject ? 'pin-subject' : 'pin-comp'}}">${{label}}</div>
        <div class="h-info">
          <h4>${{h.idx}}. ${{h.name}}</h4>
          <div class="h-meta">${{h.address}}</div>
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

<script src="https://maps.googleapis.com/maps/api/js?key={base.API_KEY}&callback=initMap" async defer></script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate Holiday Inn Chelsea STR comp map")
    parser.add_argument("--deploy", action="store_true", help="Push to GitHub Pages after generating")
    args = parser.parse_args()

    hotels = [dict(h) for h in HOTELS]
    base.geocode_all(hotels)

    comp_rooms = sum(h["rooms"] for h in hotels if not h["subject"])
    subject = next(h for h in hotels if h["subject"])

    print("Generating HTML...")
    html = render_html(hotels, comp_rooms)

    slug = SLUG
    output_dir = os.path.join(base.REPO_DIR, slug)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {output_path}")

    base.update_root_index(slug, subject["name"], subject["city_state"],
                           f"R12 {REPORT_PERIOD}", len(hotels) - 1, comp_rooms)

    url = f"{base.PAGES_BASE_URL}/{slug}/"
    if not args.deploy:
        print(f"\nGenerated. To deploy: python generate_chelsea_map.py --deploy")
        print(f"  Will be live at: {url}")
        return

    print("\nDeploying to GitHub Pages...")
    base._commit_and_push(f"Add {subject['name']} comp set map - R12 {REPORT_PERIOD}")
    ok = base.verify_deploy([url])
    print("\nDEPLOY VERIFIED [OK]" if ok else "\nDEPLOY INCOMPLETE — see warnings above")
    print(f"  {url}")


if __name__ == "__main__":
    main()
