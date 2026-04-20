# STR Comp Set Map Generator

## Quick usage
Drop any STR Excel file into: C:\Users\acarr\OneDrive\Documents\STR Drops\

Then run:
    python generate_str_map.py            # generate only
    python generate_str_map.py --deploy   # generate + push to GitHub Pages

## How it works
1. Auto-detects newest .xlsx in C:\Users\acarr\OneDrive\Documents\STR Drops\
2. Reads "Response" sheet → extracts subject + comp hotel list
3. Reads "Glance" sheet → pulls R12 Occ/ADR/RevPAR/MPI/ARI/RGI
4. Geocodes all addresses via Google Maps Geocoding API (cached in geocache.json)
5. Generates Google Maps HTML with custom pins, sidebar, info windows
6. Optionally deploys to https://acarras92.github.io/str-comp-maps/{hotel-slug}/

## Drop folder
C:\Users\acarr\OneDrive\Documents\STR Drops\

## Live maps index
https://acarras92.github.io/str-comp-maps/

## API Key
AIzaSyCTAmcCrmL2Z-SerlTKHoG3xPQaGcvmKcU
Restrict to https://acarras92.github.io/* in Google Cloud Console.

## Dependencies
pip install pandas openpyxl requests

## Skills location (Claude Code)
C:\Users\acarr\OneDrive\Documents\Claude\skills\
