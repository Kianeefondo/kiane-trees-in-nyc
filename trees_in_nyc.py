"""Create an interactive ZIP-code map from NYC's 2015 Street Tree Census.

Run ``python trees_in_nyc.py`` to create ``nyc_tree_map.html`` in this folder.
The first run downloads ZIP Code Tabulation Area boundaries from the U.S.
Census Bureau and saves them under ``datasets`` for later runs. Use
``--status All`` to include trees that are not alive, or ``--help`` for
other options.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DATASET = (
    Path(__file__).parent
    / "datasets"
    / "2015_Street_Tree_Census_-_Tree_Data_20261020.csv"
)
BOUNDARIES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "Census2020/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/2/query"
)


def load_boundaries(path: Path, zip_codes: set[str]) -> dict:
    if not zip_codes:
        return {"type": "FeatureCollection", "features": []}

    if not path.exists():
        where_clause = "ZCTA5 IN (" + ",".join(
            f"'{zip_code}'" for zip_code in sorted(zip_codes)
        ) + ")"
        params = urlencode(
            {
                "where": where_clause,
                "outFields": "ZCTA5",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            }
        )
        request = Request(
            f"{BOUNDARIES_URL}?{params}",
            headers={"User-Agent": "NYC street tree map"},
        )
        with urlopen(request, timeout=90) as response:
            boundaries = json.load(response)
        if boundaries.get("type") != "FeatureCollection":
            raise ValueError("Census boundary service did not return GeoJSON.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(boundaries, separators=(",", ":")), encoding="utf-8"
        )

    with path.open("r", encoding="utf-8") as boundary_file:
        boundaries = json.load(boundary_file)
    if boundaries.get("type") != "FeatureCollection":
        raise ValueError(f"ZIP boundaries are not a GeoJSON FeatureCollection: {path}")
    return boundaries


def create_map(dataset: Path, output: Path, boundaries_path: Path, status: str) -> None:
    zip_counts = Counter()
    total = 0
    invalid_zip_trees = 0

    with dataset.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"postcode", "status"}
        missing_columns = required_columns.difference(reader.fieldnames or ())
        if missing_columns:
            names = ", ".join(sorted(missing_columns))
            raise ValueError(f"Dataset is missing required columns: {names}")

        for row in reader:
            if status != "All" and row["status"] != status:
                continue
            total += 1
            zip_code = row["postcode"].strip()
            if zip_code.isdigit() and len(zip_code) == 5:
                zip_counts[zip_code] += 1
            else:
                invalid_zip_trees += 1

    boundaries = load_boundaries(boundaries_path, set(zip_counts))
    boundary_zip_codes = {
        feature.get("properties", {}).get("ZCTA5")
        for feature in boundaries.get("features", [])
    }
    unmatched_zip_trees = sum(
        count for zip_code, count in zip_counts.items() if zip_code not in boundary_zip_codes
    )
    mapped_total = total - invalid_zip_trees - unmatched_zip_trees
    payload = json.dumps(
        {
            "boundaries": boundaries,
            "zipCounts": zip_counts,
            "total": total,
            "mappedTotal": mapped_total,
            "unmappedTotal": invalid_zip_trees + unmatched_zip_trees,
            "mappedZipCodes": len(set(zip_counts) & boundary_zip_codes),
            "status": status,
        },
        separators=(",", ":"),
    ).replace("</", "<\\/")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_html(payload), encoding="utf-8")


def _html(data: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NYC Street Trees by ZIP Code</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ font: 14px/1.4 system-ui, sans-serif; color: #183128; }}
    .panel {{ position: absolute; z-index: 1000; top: 16px; left: 56px;
      width: min(310px, calc(100vw - 88px)); padding: 16px;
      background: #fff; border-radius: 10px;
      box-shadow: 0 2px 14px #18312833; }}
    h1 {{ font-size: 18px; margin: 0 0 5px; }}
    #summary {{ color: #466257; margin: 0 0 12px; }}
    #note {{ color: #60746c; font-size: 12px; margin: 8px 0 0; }}
    label {{ display: block; margin-top: 9px; font-weight: 600; }}
    input {{ width: 100%; margin-top: 5px; }}
    .legend {{ display: flex; justify-content: space-between; margin-top: 12px;
      color: #466257; font-size: 12px; }}
    .swatches {{ display: flex; gap: 7px; margin-top: 6px; }}
    .swatches span {{ flex: 1; height: 9px; border-radius: 5px; }}
    .leaflet-container {{ background: #e9f0ed; }}
  </style>
</head>
<body>
  <div id="map" role="application" aria-label="NYC street tree counts by ZIP code"></div>
  <section class="panel">
    <h1>NYC Street Trees by ZIP Code</h1>
    <p id="summary"></p>
    <label for="opacity">Map opacity</label>
    <input id="opacity" type="range" min="20" max="100" value="75">
    <div class="legend">
      <span>Fewer trees</span>
      <span>More</span>
    </div>
    <div class="swatches" aria-hidden="true">
      <span style="background:#d9f0a3"></span>
      <span style="background:#addd8e"></span>
      <span style="background:#78c679"></span>
      <span style="background:#31a354"></span>
      <span style="background:#006837"></span>
    </div>
    <p id="note"></p>
  </section>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const data = {data};
    const map = L.map("map", {{ preferCanvas: true }}).setView([40.7128, -74.0060], 10);
    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }}).addTo(map);

    const colors = ["#d9f0a3", "#addd8e", "#78c679", "#31a354", "#006837"];
    const opacityControl = document.getElementById("opacity");
    const counts = Object.values(data.zipCounts).sort((a, b) => a - b);
    const breaks = [0.2, 0.4, 0.6, 0.8].map(percentile =>
      counts[Math.floor((counts.length - 1) * percentile)] || 0
    );

    function polygonStyle(feature) {{
      const zipCode = feature.properties.ZCTA5;
      const count = data.zipCounts[zipCode] || 0;
      const colorIndex = breaks.findIndex(limit => count <= limit);
      return {{
        color: "#ffffff",
        weight: 1,
        fillColor: colors[colorIndex < 0 ? colors.length - 1 : colorIndex],
        fillOpacity: Number(opacityControl.value) / 100
      }};
    }}

    const zipLayer = L.geoJSON(data.boundaries, {{
      style: polygonStyle,
      onEachFeature: (feature, layer) => {{
        const zipCode = feature.properties.ZCTA5;
        const count = data.zipCounts[zipCode] || 0;
        layer.bindTooltip(
          `<strong>ZIP ${{zipCode}}</strong><br>${{count.toLocaleString()}} ${{data.status.toLowerCase()}} trees`
        );
        layer.on({{
          mouseover: () => layer.setStyle({{ color: "#183128", weight: 2 }}),
          mouseout: () => layer.setStyle(polygonStyle(feature))
        }});
      }}
    }}).addTo(map);

    opacityControl.addEventListener("input", () => zipLayer.setStyle(polygonStyle));
    if (zipLayer.getLayers().length) {{
      map.fitBounds(zipLayer.getBounds(), {{ padding: [20, 20] }});
    }}

    document.getElementById("summary").textContent =
      `${{data.mappedTotal.toLocaleString()}} ${{data.status === "All" ? "" : data.status.toLowerCase() + " "}}trees` +
      ` across ${{data.mappedZipCodes}} ZIP codes`;
    document.getElementById("note").textContent = data.unmappedTotal
      ? `${{data.unmappedTotal.toLocaleString()}} trees could not be mapped to a ZIP boundary. Areas use approximate 2020 Census ZIP Code Tabulation Areas (U.S. Census Bureau).`
      : "Areas use approximate 2020 Census ZIP Code Tabulation Areas (U.S. Census Bureau).";
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an interactive density map from NYC's tree census."
    )
    parser.add_argument(
        "--dataset", type=Path, default=DATASET, help="Path to the tree census CSV."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "nyc_tree_map.html",
        help="Path for the generated HTML map.",
    )
    parser.add_argument(
        "--boundaries",
        type=Path,
        default=Path(__file__).parent / "datasets" / "nyc_zcta_boundaries.geojson",
        help="GeoJSON ZIP-area boundaries; downloaded from the Census Bureau if absent.",
    )
    parser.add_argument(
        "--status",
        default="Alive",
        help='Tree status to map (default: "Alive"); use "All" for every status.',
    )
    args = parser.parse_args()

    if not args.dataset.is_file():
        parser.error(f"Dataset does not exist: {args.dataset}")
    create_map(args.dataset, args.output, args.boundaries, args.status)
    print(f"Created {args.output} with status={args.status}.")


if __name__ == "__main__":
    main()