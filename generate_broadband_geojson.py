"""
Generate colorado_broadband_access.geojson by joining:
  - NTAD Colorado census place polygons (geometry)
  - FCC BDC broadband coverage data (attributes)
"""

import csv
import json
import sys

GEOJSON_PATH = "NTAD_Places_-5495307668221019847.geojson"
CSV_PATH     = "bdc_08_fixed_broadband_summary_by_geography_place_J25_19mar2026.csv"
OUTPUT_PATH  = "colorado_broadband_access.geojson"

# Central City: NTAD shapefile uses older FIPS; FCC BDC uses current FIPS
FIPS_REMAP = {"0812900": "0812910"}

SPEED_COLS = [
    "speed_02_02",
    "speed_10_1",
    "speed_25_3",
    "speed_100_20",
    "speed_250_25",
    "speed_1000_100",
]


def to_float(s):
    try:
        return round(float(s), 4) if s not in ("", "N/A", "NULL") else None
    except (ValueError, TypeError):
        return None


# Step 1: Read and filter CSV into a lookup dict
broadband = {}

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if (row["area_data_type"] == "Total"
                and row["biz_res"] == "R"
                and row["technology"] == "Any Technology"):
            geo_id = row["geography_id"]
            broadband[geo_id] = {
                "bb_place_name":     row["geography_desc"],
                "bb_total_units":    int(row["total_units"]) if row["total_units"] else None,
                "bb_speed_02_02":    to_float(row["speed_02_02"]),
                "bb_speed_10_1":     to_float(row["speed_10_1"]),
                "bb_speed_25_3":     to_float(row["speed_25_3"]),
                "bb_speed_100_20":   to_float(row["speed_100_20"]),
                "bb_speed_250_25":   to_float(row["speed_250_25"]),
                "bb_speed_1000_100": to_float(row["speed_1000_100"]),
            }

print(f"Loaded {len(broadband)} broadband records from CSV")

# Step 2: Load the GeoJSON
with open(GEOJSON_PATH, encoding="utf-8") as f:
    geojson = json.load(f)

features = geojson["features"]
print(f"Loaded {len(features)} GeoJSON features")

# Step 3: Join broadband data onto each feature
matched   = 0
unmatched = []

NULL_BB = {
    "bb_place_name":     None,
    "bb_total_units":    None,
    "bb_speed_02_02":    None,
    "bb_speed_10_1":     None,
    "bb_speed_25_3":     None,
    "bb_speed_100_20":   None,
    "bb_speed_250_25":   None,
    "bb_speed_1000_100": None,
}

for feature in features:
    props = feature["properties"]
    geoid = props["GEOID"]
    lookup_id = FIPS_REMAP.get(geoid, geoid)

    bb = broadband.get(lookup_id)
    if bb:
        props.update(bb)
        matched += 1
    else:
        props.update(NULL_BB)
        unmatched.append((geoid, props.get("NAMELSAD")))

print(f"Matched: {matched} / {len(features)}")
if unmatched:
    print(f"WARNING: {len(unmatched)} place(s) had no broadband data (null fields added):")
    for geoid, name in unmatched:
        print(f"  GEOID={geoid}  Name={name}")

# Step 4: Write output
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False)

print(f"Written: {OUTPUT_PATH}")

# Step 5: Quick validation
with open(OUTPUT_PATH, encoding="utf-8") as f:
    out = json.load(f)

out_features = out["features"]
assert len(out_features) == len(features), f"Feature count mismatch: {len(out_features)}"

bb_keys = list(NULL_BB.keys())
for feat in out_features:
    p = feat["properties"]
    for key in bb_keys:
        assert key in p, f"Missing key {key} in feature {p.get('GEOID')}"
    for col in SPEED_COLS:
        v = p.get(f"bb_{col}")
        if v is not None:
            assert 0.0 <= v <= 1.0, f"Out-of-range {v} for bb_{col} in {p.get('GEOID')}"

null_count = sum(1 for f in out_features if f["properties"]["bb_speed_25_3"] is None)
print(f"Validation passed. Features with null bb_speed_25_3: {null_count}")
