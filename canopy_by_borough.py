"""Build an interactive borough-level map of NYC tree canopy coverage.

Run ``python canopy_by_borough.py`` to create ``canopy_by_borough.html``.
The dashboard uses the canopy jurisdiction CSV's 2010 and 2017 acreage data;
it does not represent current canopy coverage.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).parent
DATASET = ROOT / "datasets" / "canopy_jurisdiction_landuse_borough.csv"
BOUNDARIES = ROOT / "datasets" / "nyc_borough_boundaries.geojson"
OUTPUT = ROOT / "canopy_by_borough.html"
BOUNDARIES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "Census2020/State_County/MapServer/1/query"
)
BOROUGH_BY_COUNTY = {
    "005": "Bronx",
    "047": "Brooklyn",
    "061": "Manhattan",
    "081": "Queens",
    "085": "Staten Island",
}
REQUIRED_COLUMNS = {
    "boroname",
    "natural_developed",
    "acreage",
    "canopy_loss_acres",
    "canopy_gain_acres",
    "canopy2010_acres",
    "canopy2017_acres",
}


def _download_boundaries(path: Path) -> dict:
    params = urlencode(
        {
            "where": "STATE='36' AND COUNTY IN ('005','047','061','081','085')",
            "outFields": "NAME,STATE,COUNTY",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    request = Request(
        f"{BOUNDARIES_URL}?{params}",
        headers={"User-Agent": "NYC borough canopy dashboard"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            boundaries = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Census boundary service returned HTTP {error.code}."
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not connect to the Census boundary service: {error.reason}"
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Census boundary service did not return valid GeoJSON.") from error

    if boundaries.get("type") != "FeatureCollection":
        raise ValueError("Census boundary service did not return a GeoJSON FeatureCollection.")

    for feature in boundaries.get("features", []):
        properties = feature.get("properties", {})
        county_code = properties.get("COUNTY")
        borough = BOROUGH_BY_COUNTY.get(county_code)
        if borough is None or not feature.get("geometry"):
            raise ValueError(f"Unexpected borough boundary feature: {properties!r}")
        properties["borough"] = borough

    boroughs = {
        feature["properties"]["borough"] for feature in boundaries.get("features", [])
    }
    if boroughs != set(BOROUGH_BY_COUNTY.values()):
        raise ValueError("Census boundary response did not include all five boroughs.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(boundaries, separators=(",", ":")), encoding="utf-8")
    return boundaries


def load_boundaries(path: Path) -> dict:
    if not path.exists():
        return _download_boundaries(path)

    with path.open("r", encoding="utf-8") as boundary_file:
        boundaries = json.load(boundary_file)
    if boundaries.get("type") != "FeatureCollection":
        raise ValueError(f"Borough boundaries are not a GeoJSON FeatureCollection: {path}")

    for feature in boundaries.get("features", []):
        properties = feature.get("properties", {})
        county_code = properties.get("COUNTY")
        if "borough" not in properties:
            properties["borough"] = BOROUGH_BY_COUNTY.get(county_code)

    boroughs = {
        feature.get("properties", {}).get("borough")
        for feature in boundaries.get("features", [])
        if feature.get("geometry")
    }
    if boroughs != set(BOROUGH_BY_COUNTY.values()):
        raise ValueError(f"Borough boundary file must contain all five NYC boroughs: {path}")
    return boundaries


def read_canopy_data(path: Path) -> dict:
    boroughs = defaultdict(
        lambda: defaultdict(
            lambda: {
                "acreage": 0.0,
                "canopy2010_acres": 0.0,
                "canopy2017_acres": 0.0,
                "canopy_loss_acres": 0.0,
                "canopy_gain_acres": 0.0,
            }
        )
    )

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "Canopy dataset is missing columns: " + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            borough = row["boroname"].strip()
            land_type = row["natural_developed"].strip()
            if borough not in BOROUGH_BY_COUNTY.values():
                raise ValueError(
                    f"Unknown borough {borough!r} in canopy dataset at line {line_number}."
                )
            if land_type not in {"Developed", "Natural", "NA"}:
                raise ValueError(
                    f"Unknown land classification {land_type!r} at line {line_number}."
                )

            try:
                values = {
                    column: float(row[column])
                    for column in (
                        "acreage",
                        "canopy2010_acres",
                        "canopy2017_acres",
                        "canopy_loss_acres",
                        "canopy_gain_acres",
                    )
                }
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid acreage value in canopy dataset at line {line_number}."
                ) from error

            totals = boroughs[borough][land_type]
            for column, value in values.items():
                totals[column] += value

    result = {}
    for borough, land_types in boroughs.items():
        result[borough] = {
            land_type: {
                **values,
                "canopy2010_percent": (
                    100 * values["canopy2010_acres"] / values["acreage"]
                    if values["acreage"]
                    else None
                ),
                "canopy2017_percent": (
                    100 * values["canopy2017_acres"] / values["acreage"]
                    if values["acreage"]
                    else None
                ),
            }
            for land_type, values in land_types.items()
        }
        combined = {}
        for land_type in ("Developed", "Natural", "NA"):
            for column, value in result[borough].get(land_type, {}).items():
                if isinstance(value, (float, int)):
                    combined[column] = combined.get(column, 0.0) + value

        acreage = combined.get("acreage", 0.0)
        combined["canopy2010_percent"] = (
            100 * combined.get("canopy2010_acres", 0.0) / acreage if acreage else None
        )
        combined["canopy2017_percent"] = (
            100 * combined.get("canopy2017_acres", 0.0) / acreage if acreage else None
        )
        result[borough]["All"] = combined

    return result


def create_dashboard(dataset: Path, boundaries_path: Path, output: Path) -> None:
    payload = json.dumps(
        {
            "canopy": read_canopy_data(dataset),
            "boundaries": load_boundaries(boundaries_path),
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
  <title>NYC Canopy by Borough</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ font: 14px/1.5 system-ui, sans-serif; color: #25352f; }}
    .panel {{ position: absolute; z-index: 1000; top: 20px; left: 64px;
      width: min(330px, calc(100vw - 104px)); max-height: calc(100vh - 72px);
      overflow-y: auto; padding: 20px; background: #fffdf8; border-radius: 8px;
      box-shadow: 0 3px 18px #25352f24; }}
    .eyebrow {{ margin: 0 0 4px; color: #52745e; font-size: 11px;
      font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ font-family: Georgia, "Times New Roman", serif; font-size: 26px;
      font-weight: 500; letter-spacing: -.03em; line-height: 1.1;
      margin: 0 0 8px; }}
    .intro, #note {{ color: #64736b; }}
    .intro {{ margin: 0 0 16px; }}
    label {{ display: block; margin-top: 12px; font-size: 12px; font-weight: 700; }}
    select {{ box-sizing: border-box; width: 100%; margin-top: 5px; padding: 8px;
      border: 1px solid #d6ddd5; border-radius: 5px; background: white;
      color: inherit; font: inherit; }}
    #summary {{ color: #52745e; font-size: 12px; margin: 12px 0 0; }}
    .legend {{ display: flex; justify-content: space-between; margin-top: 14px;
      color: #64736b; font-size: 11px; }}
    .swatches {{ display: flex; gap: 5px; margin-top: 6px; }}
    .swatches span {{ flex: 1; height: 8px; border-radius: 4px; }}
    #note {{ font-size: 11px; margin: 10px 0 0; }}
    .leaflet-container {{ background: #e8eee9; }}
    @media (max-width: 520px) {{
      .panel {{ top: 12px; left: 54px; width: min(280px, calc(100vw - 82px));
        padding: 14px; }}
      h1 {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <div id="map" role="application" aria-label="Tree canopy percentage by NYC borough"></div>
  <section class="panel">
    <p class="eyebrow">NYC, Block by Block</p>
    <h1>Tree Canopy by Borough</h1>
    <p class="intro">A borough-level look at estimated canopy cover and how it changed over time.</p>
    <label for="year">Canopy year</label>
    <select id="year">
      <option value="2010">2010</option>
      <option value="2017" selected>2017</option>
    </select>
    <label for="landType">Land type</label>
    <select id="landType">
      <option value="All">All land types</option>
      <option value="Developed">Developed</option>
      <option value="Natural">Natural</option>
    </select>
    <p id="summary"></p>
    <div class="legend"><span>Lower canopy</span><span>Higher canopy</span></div>
    <div class="swatches" aria-hidden="true">
      <span style="background:#f1f7e8"></span>
      <span style="background:#cfe5bd"></span>
      <span style="background:#91c68a"></span>
      <span style="background:#4b9b62"></span>
      <span style="background:#17633c"></span>
    </div>
    <p id="note">Hover over a borough to see canopy area, borough area, and canopy change.</p>
  </section>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const data = {data};
    const map = L.map("map", {{ preferCanvas: true }});
    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }}).addTo(map);

    const colors = ["#f1f7e8", "#cfe5bd", "#91c68a", "#4b9b62", "#17633c"];
    const breaks = [10, 15, 20, 25];
    const yearSelect = document.getElementById("year");
    const landTypeSelect = document.getElementById("landType");

    function boroughData(borough) {{
      return data.canopy[borough]?.[landTypeSelect.value];
    }}

    function canopyPercent(borough) {{
      const record = boroughData(borough);
      return record?.[`canopy${{yearSelect.value}}_percent`];
    }}

    function colorFor(value) {{
      if (value === undefined || value === null) return "#d9dfdc";
      const index = breaks.findIndex(limit => value < limit);
      return colors[index < 0 ? colors.length - 1 : index];
    }}

    function style(feature) {{
      return {{
        color: "#ffffff",
        weight: 2,
        fillColor: colorFor(canopyPercent(feature.properties.borough)),
        fillOpacity: 0.86
      }};
    }}

    function tooltip(borough) {{
      const record = boroughData(borough);
      if (!record) return `<strong>${{borough}}</strong><br>No data for this land type`;
      const year = yearSelect.value;
      const canopyArea = record[`canopy${{year}}_acres`];
      const percent = record[`canopy${{year}}_percent`];
      const netChange = record.canopy2017_acres - record.canopy2010_acres;
      const percentagePointChange =
        record.canopy2017_percent - record.canopy2010_percent;
      return `<strong>${{borough}}</strong><br>` +
        `${{year}} canopy: ${{percent.toFixed(1)}}% ` +
        `(${{canopyArea.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} acres)` +
        `<br>Land area: ${{record.acreage.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} acres` +
        `<br>2010–2017 net change: ${{netChange >= 0 ? "+" : ""}}` +
        `${{netChange.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} canopy acres` +
        `<br>Change: ${{percentagePointChange >= 0 ? "+" : ""}}` +
        `${{percentagePointChange.toFixed(1)}} percentage points`;
    }}

    function updateMap() {{
      const year = yearSelect.value;
      const landType = landTypeSelect.value;
      const values = Object.keys(data.canopy)
        .map(borough => canopyPercent(borough))
        .filter(value => value !== undefined && value !== null);
      const average = values.reduce((sum, value) => sum + value, 0) / values.length;
      const rank = [...Object.entries(data.canopy)]
        .sort((left, right) => right[1][landType][`canopy${{year}}_percent`]
          - left[1][landType][`canopy${{year}}_percent`])[0];

      document.getElementById("summary").textContent =
        `${{year}} · ${{landType === "All" ? "all land types" : landType.toLowerCase()}} · ` +
        `${{average.toFixed(1)}}% average across five boroughs · ` +
        `${{rank[0]}} highest at ${{rank[1][landType][`canopy${{year}}_percent`].toFixed(1)}}%`;

      boroughLayer.setStyle(style);
      boroughLayer.eachLayer(layer => {{
        const borough = layer.feature.properties.borough;
        layer.setTooltipContent(tooltip(borough));
      }});
    }}

    const boroughLayer = L.geoJSON(data.boundaries, {{
      style,
      onEachFeature: (feature, layer) => {{
        layer.bindTooltip(tooltip(feature.properties.borough));
        layer.on({{
          mouseover: () => layer.setStyle({{ color: "#25352f", weight: 3 }}),
          mouseout: () => layer.setStyle(style(feature))
        }});
      }}
    }}).addTo(map);

    yearSelect.addEventListener("change", updateMap);
    landTypeSelect.addEventListener("change", updateMap);
    map.fitBounds(boroughLayer.getBounds(), {{ padding: [24, 24] }});
    updateMap();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an NYC tree canopy dashboard divided by borough."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET,
        help="Path to the canopy jurisdiction CSV.",
    )
    parser.add_argument(
        "--boundaries",
        type=Path,
        default=BOUNDARIES,
        help="GeoJSON borough boundaries; downloaded from Census TIGERweb if absent.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Path for the generated HTML dashboard.",
    )
    args = parser.parse_args()

    if not args.dataset.is_file():
        parser.error(f"Canopy dataset does not exist: {args.dataset}")
    try:
        create_dashboard(args.dataset, args.boundaries, args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Created {args.output}.")


if __name__ == "__main__":
    main()
