#!/usr/bin/env python3
"""
Host 18 Pack — combined STR comp set map.

Reads the 18 hotels' R12-ending-March-2026 STR pulls from
    C:\\Users\\acarr\\OneDrive\\Documents\\STR Drops\\Host 18 Pack\\
(every "* - STR - 2026-03.xlsx" has a single, standard Response/Glance sheet —
the older periods in that folder use inconsistent _1/_4 multi-set layouts and
are intentionally ignored), parses subject + comps + R12 performance, geocodes,
and renders ONE combined national map with each comp set color-coded and
individually toggleable. Reuses the /global map renderer.

Usage:
    py -3 generate_host18_map.py            # generate only
    py -3 generate_host18_map.py --deploy   # + commit + push + verify
"""

import argparse
import glob
import os
import sys

from generate_global_map import load_cache, parse_comp_set, render_html, PALETTE
from generate_str_map import REPO_DIR, PAGES_BASE_URL, _commit_and_push, verify_deploy

PACK_DIR = r"C:\Users\acarr\OneDrive\Documents\STR Drops\Host 18 Pack"
PERIOD_GLOB = "* - STR - 2026-03.xlsx"
OUTPUT_SLUG = "host-18-pack"
OUTPUT_DIR = os.path.join(REPO_DIR, OUTPUT_SLUG)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "index.html")


def build_payload():
    cache = load_cache()
    files = sorted(glob.glob(os.path.join(PACK_DIR, PERIOD_GLOB)))
    comp_sets = []
    for path in files:
        print(f"Reading {os.path.basename(path)}")
        cs = parse_comp_set(path, cache)
        if cs is not None:
            comp_sets.append(cs)
    comp_sets.sort(key=lambda c: c["subject_name"].lower())
    for i, cs in enumerate(comp_sets):
        cs["color"] = PALETTE[i % len(PALETTE)]
    return comp_sets


def count_unique_hotels(comp_sets):
    keys = set()
    for cs in comp_sets:
        for h in cs["hotels"]:
            if h.get("lat"):
                keys.add(h["name"].strip().lower())
    return len(keys)


def update_root_index_link(n_sets, n_hotels):
    """Add a 'Host 18 Pack' portfolio banner to the root landing page if missing."""
    path = os.path.join(REPO_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if f'href="./{OUTPUT_SLUG}/"' in content:
        print("  Host 18 Pack link already present in root index.html")
        return
    banner = f"""    <a href="./{OUTPUT_SLUG}/" class="global-banner" style="display:block; margin:0 0 18px; padding:18px 22px; background:linear-gradient(135deg,#1f2937,#7c3aed); color:#fff; border-radius:10px; text-decoration:none;">
      <div style="font-size:18px; font-weight:600;">Host 18 Pack &mdash; Portfolio Comp Sets &rarr;</div>
      <div style="font-size:13px; opacity:0.9; margin-top:2px;">{n_sets} comp sets across the US on one map &middot; {n_hotels} unique hotels &middot; R12 ending Mar 2026.</div>
    </a>
"""
    marker = '<ul class="map-list">'
    if marker in content:
        content = content.replace(marker, banner + "    " + marker, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  Added Host 18 Pack banner to root index.html")
    else:
        print("  WARNING: could not find <ul class=\"map-list\"> in root index.html; skipping link insert")


def main():
    parser = argparse.ArgumentParser(description="Generate Host 18 Pack combined comp set map")
    parser.add_argument("--deploy", action="store_true")
    args = parser.parse_args()

    comp_sets = build_payload()
    if not comp_sets:
        print("No comp sets parsed — nothing to render.")
        sys.exit(1)

    n_sets = len(comp_sets)
    n_hotels = count_unique_hotels(comp_sets)
    subtitle = f"{n_sets} comp sets · {n_hotels} unique hotels · R12 ending Mar 2026"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html = render_html(
        comp_sets,
        title="Host 18 Pack — STR Comp Sets",
        heading="Host 18 Pack — Portfolio Comp Sets",
        subtitle=subtitle,
        link_subjects=False,
    )
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nHost 18 Pack map saved: {OUTPUT_PATH}")
    print(f"  {n_sets} comp sets, {n_hotels} unique hotels")

    update_root_index_link(n_sets, n_hotels)

    if not args.deploy:
        print(f"\nTo deploy, re-run with --deploy")
        print(f"  Will be live at: {PAGES_BASE_URL}/{OUTPUT_SLUG}/")
        return

    print("\nDeploying to GitHub Pages...")
    _commit_and_push("Add Host 18 Pack combined comp set map (R12 ending Mar 2026)")
    ok = verify_deploy([f"{PAGES_BASE_URL}/{OUTPUT_SLUG}/"])
    print(f"\n{'=' * 60}")
    print("DEPLOY VERIFIED [OK]" if ok else "DEPLOY INCOMPLETE — see warnings above")
    print(f"  {PAGES_BASE_URL}/{OUTPUT_SLUG}/")
    print('=' * 60)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
