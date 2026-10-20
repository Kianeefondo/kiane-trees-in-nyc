"""Add ACS 5-year demographic and housing layers to the NYC ZIP-code map.

Paste your Census API key into ``CENSUS_API_KEY`` below, then run:

    python economic_census_data_in_nyc.py

The first run downloads 2024 ACS 5-year ZCTA estimates and caches them under
``datasets``. Later runs reuse the cache; pass ``--refresh-acs`` to update it.
"""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from heat_vulnerability_in_nyc import (
    BOUNDARIES,
    HVI_DATASET,
    OUTPUT,
    ROOT,
    TREE_DATASET,
    load_boundaries,
    read_hvi_ranks,
    read_tree_counts,
)


def load_census_api_key(env_path: Path = ROOT / ".env") -> str:
    """Load the Census key from the environment or a local, ignored .env file."""
    if env_path.is_file():
        with env_path.open("r", encoding="utf-8") as env_file:
            for line in env_file:
                entry = line.strip()
                if not entry or entry.startswith("#"):
                    continue
                if entry.startswith("export "):
                    entry = entry[len("export "):].lstrip()
                name, separator, value = entry.partition("=")
                if separator and name.strip() == "CENSUS_API_KEY":
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    os.environ.setdefault("CENSUS_API_KEY", value)
                    break
    return os.environ.get("CENSUS_API_KEY", "")


CENSUS_API_KEY = load_census_api_key()

ACS_YEAR = 2024
ACS_ENDPOINT = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
ACS_CACHE = ROOT / "datasets" / f"acs_{ACS_YEAR}_nyc_zcta.json"

# ACS detailed-table estimate variables used by these map layers.
ACS_VARIABLES = {
    "B19013_001E": "median household income",
    "B17001_001E": "population with poverty status determined",
    "B17001_002E": "population below poverty level",
    "B03002_001E": "total population",
    "B03002_003E": "non-Hispanic White alone",
    "B03002_004E": "non-Hispanic Black alone",
    "B03002_005E": "non-Hispanic American Indian and Alaska Native alone",
    "B03002_006E": "non-Hispanic Asian alone",
    "B03002_007E": "non-Hispanic Native Hawaiian and Other Pacific Islander alone",
    "B03002_008E": "non-Hispanic some other race alone",
    "B03002_009E": "non-Hispanic two or more races",
    "B03002_012E": "Hispanic or Latino, any race",
    "B25077_001E": "median owner-occupied home value",
    "B25064_001E": "median gross rent",
    "B25001_001E": "total housing units",
    "B25002_001E": "total occupancy status",
    "B25002_002E": "occupied housing units",
    "B25002_003E": "vacant housing units",
    "B25003_001E": "total tenure",
    "B25003_002E": "owner-occupied housing units",
    "B25003_003E": "renter-occupied housing units",
    "B25070_001E": "renter-occupied units with gross rent",
    "B25070_008E": "gross rent 35 to 39.9 percent of household income",
    "B25070_009E": "gross rent 40 to 49.9 percent of household income",
    "B25070_010E": "gross rent 50 percent or more of household income",
}

RACE_VARIABLES = {
    "White, non-Hispanic": "B03002_003E",
    "Black, non-Hispanic": "B03002_004E",
    "American Indian / Alaska Native, non-Hispanic": "B03002_005E",
    "Asian, non-Hispanic": "B03002_006E",
    "Native Hawaiian / Pacific Islander, non-Hispanic": "B03002_007E",
    "Some other race, non-Hispanic": "B03002_008E",
    "Two or more races, non-Hispanic": "B03002_009E",
    "Hispanic or Latino, any race": "B03002_012E",
}

METRICS = {
    "median_income": {
        "label": "Median household income",
        "unit": "currency",
        "low": "Lower income",
        "high": "Higher income",
        "colors": ["#fff7bc", "#fec44f", "#fe9929", "#ec7014", "#993404"],
    },
    "poverty_rate": {
        "label": "Population below poverty level",
        "unit": "percent",
        "low": "Lower poverty rate",
        "high": "Higher poverty rate",
        "colors": ["#fff7bc", "#fec44f", "#fe9929", "#ec7014", "#b30000"],
    },
    "median_home_value": {
        "label": "Median owner-occupied home value",
        "unit": "currency",
        "low": "Lower value",
        "high": "Higher value",
        "colors": ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
    },
    "median_gross_rent": {
        "label": "Median gross rent",
        "unit": "currency",
        "low": "Lower rent",
        "high": "Higher rent",
        "colors": ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
    },
    "renter_share": {
        "label": "Renter-occupied housing units",
        "unit": "percent",
        "low": "Lower renter share",
        "high": "Higher renter share",
        "colors": ["#edf8fb", "#b3cde3", "#8c96c6", "#8856a7", "#810f7c"],
    },
    "vacancy_rate": {
        "label": "Vacant housing units",
        "unit": "percent",
        "low": "Lower vacancy rate",
        "high": "Higher vacancy rate",
        "colors": ["#edf8fb", "#b3cde3", "#8c96c6", "#8856a7", "#810f7c"],
    },
    "severe_rent_burden": {
        "label": "Renters paying at least 35% of income on rent",
        "unit": "percent",
        "low": "Lower rent burden",
        "high": "Higher rent burden",
        "colors": ["#fff7bc", "#fec44f", "#fe9929", "#ec7014", "#b30000"],
    },
}

TREE_COLORS = ["#edf8d5", "#c7e9b4", "#7fcdbb", "#41ab5d", "#006837"]
HVI_COLORS = ["#fff7bc", "#fec44f", "#fe9929", "#ec7014", "#cc4c02"]
RACE_COLORS = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"]


def _estimate(value: str) -> int | None:
    """Return a nonnegative ACS estimate, treating Census sentinels as missing."""
    try:
        estimate = int(value)
    except (TypeError, ValueError):
        return None
    return estimate if estimate >= 0 else None


def _percent(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(100 * numerator / denominator, 2)


def fetch_acs_data(api_key: str, nyc_zip_codes: set[str]) -> dict:
    if not api_key or api_key == "PASTE_YOUR_CENSUS_API_KEY_HERE":
        raise ValueError(
            "Add your Census API key to CENSUS_API_KEY near the top of "
            "economic_census_data_in_nyc.py, then run the script again."
        )

    params = {
        "get": ",".join(["NAME", *ACS_VARIABLES]),
        "for": "zip code tabulation area:*",
        "key": api_key,
    }
    request = Request(
        f"{ACS_ENDPOINT}?{urlencode(params)}",
        headers={"User-Agent": "NYC ACS ZIP-code map"},
    )
    try:
        with urlopen(request, timeout=90) as response:
            response_data = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Census ACS API returned HTTP {error.code}. Check the API key "
            "and retry."
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to the Census ACS API: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The Census ACS API response was not valid JSON. Check the API key "
            "and try again."
        ) from error

    if not isinstance(response_data, list) or len(response_data) < 2:
        raise RuntimeError(f"Unexpected Census ACS API response: {response_data!r}")

    headers = response_data[0]
    required_headers = {"zip code tabulation area", *ACS_VARIABLES}
    missing_headers = required_headers.difference(headers)
    if missing_headers:
        raise RuntimeError(
            "Census ACS API response is missing expected columns: "
            + ", ".join(sorted(missing_headers))
        )

    columns = {name: headers.index(name) for name in required_headers}
    estimates = {}
    for row in response_data[1:]:
        zip_code = row[columns["zip code tabulation area"]]
        if zip_code not in nyc_zip_codes:
            continue
        raw = {variable: _estimate(row[columns[variable]]) for variable in ACS_VARIABLES}
        population = raw["B03002_001E"]
        poverty_denominator = raw["B17001_001E"]
        housing_units = raw["B25001_001E"]
        total_occupancy = raw["B25002_001E"]
        occupied_units = raw["B25003_001E"]
        gross_rent_units = raw["B25070_001E"]
        rent_burden_counts = [
            raw[variable]
            for variable in ("B25070_008E", "B25070_009E", "B25070_010E")
        ]
        severe_rent_burden = (
            sum(rent_burden_counts)
            if all(count is not None for count in rent_burden_counts)
            else None
        )

        estimates[zip_code] = {
            "median_income": raw["B19013_001E"],
            "poverty_rate": _percent(raw["B17001_002E"], poverty_denominator),
            "race_shares": {
                group: _percent(raw[variable], population)
                for group, variable in RACE_VARIABLES.items()
            },
            "median_home_value": raw["B25077_001E"],
            "median_gross_rent": raw["B25064_001E"],
            "renter_share": _percent(raw["B25003_003E"], occupied_units),
            "vacancy_rate": _percent(raw["B25002_003E"], total_occupancy),
            "severe_rent_burden": _percent(severe_rent_burden, gross_rent_units),
            "population": population,
            "housing_units": housing_units,
        }

    if not estimates:
        raise RuntimeError(
            "The Census ACS API returned no records for the ZIP areas in the "
            "cached NYC boundaries."
        )

    return {"year": ACS_YEAR, "survey": "ACS 5-Year Estimates", "data": estimates}


def load_acs_data(
    cache_path: Path, nyc_zip_codes: set[str], api_key: str, refresh: bool
) -> dict:
    if cache_path.exists() and not refresh:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            cached = json.load(cache_file)
        if cached.get("year") == ACS_YEAR and isinstance(cached.get("data"), dict):
            return cached

    fetched = fetch_acs_data(api_key, nyc_zip_codes)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(fetched, separators=(",", ":")), encoding="utf-8"
    )
    return fetched


def _map_data(
    tree_dataset: Path,
    hvi_dataset: Path,
    boundaries_path: Path,
    acs_cache: Path,
    status: str,
    api_key: str,
    refresh_acs: bool,
) -> dict:
    tree_counts, tree_total, invalid_zip_trees = read_tree_counts(tree_dataset, status)
    hvi_ranks = read_hvi_ranks(hvi_dataset)
    boundaries = load_boundaries(boundaries_path)
    boundary_zip_codes = {
        feature.get("properties", {}).get("ZCTA5")
        for feature in boundaries.get("features", [])
        if feature.get("geometry")
    }
    acs = load_acs_data(acs_cache, boundary_zip_codes, api_key, refresh_acs)
    acs_data = acs["data"]

    matched_tree_codes = set(tree_counts) & boundary_zip_codes
    matched_hvi_codes = set(hvi_ranks) & boundary_zip_codes
    matched_acs_codes = set(acs_data) & boundary_zip_codes
    unmatched_tree_count = invalid_zip_trees + sum(
        count
        for zip_code, count in tree_counts.items()
        if zip_code not in boundary_zip_codes
    )
    return {
        "boundaries": boundaries,
        "treeCounts": tree_counts,
        "treeTotal": tree_total,
        "treeMappedTotal": sum(
            tree_counts[zip_code] for zip_code in matched_tree_codes
        ),
        "treeUnmappedTotal": unmatched_tree_count,
        "treeMappedZipCodes": len(matched_tree_codes),
        "hviRanks": hvi_ranks,
        "hviMappedZipCodes": len(matched_hvi_codes),
        "hviUnmappedZipCodes": len(hvi_ranks) - len(matched_hvi_codes),
        "acsYear": acs["year"],
        "acsSurvey": acs["survey"],
        "acsMetrics": acs_data,
        "acsMappedZipCodes": len(matched_acs_codes),
        "status": status,
    }


def create_map(
    tree_dataset: Path,
    hvi_dataset: Path,
    boundaries_path: Path,
    acs_cache: Path,
    output: Path,
    status: str,
    api_key: str,
    refresh_acs: bool = False,
) -> None:
    payload = json.dumps(
        _map_data(
            tree_dataset,
            hvi_dataset,
            boundaries_path,
            acs_cache,
            status,
            api_key,
            refresh_acs,
        ),
        separators=(",", ":"),
    ).replace("</", "<\\/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_html(payload), encoding="utf-8")


def _html(data: str) -> str:
    housing_options = "\n".join(
        f'<option value="{key}">{METRICS[key]["label"]}</option>'
        for key in (
            "median_home_value",
            "median_gross_rent",
            "renter_share",
            "vacancy_rate",
            "severe_rent_burden",
        )
    )
    race_options = "\n".join(
        f'<option value="{group}">{group}</option>' for group in RACE_VARIABLES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NYC Community Data by ZIP Code</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ font: 14px/1.4 system-ui, sans-serif; color: #183128; }}
    .panel {{ position: absolute; z-index: 1000; top: 16px; left: 56px;
      width: min(340px, calc(100vw - 88px)); max-height: calc(100vh - 64px);
      overflow-y: auto; padding: 16px; background: #fff; border-radius: 10px;
      box-shadow: 0 2px 14px #18312833; }}
    h1 {{ font-size: 18px; margin: 0 0 5px; }}
    #summary {{ color: #466257; margin: 0 0 12px; }}
    #note {{ color: #60746c; font-size: 12px; margin: 8px 0 0; }}
    label {{ display: block; margin-top: 9px; font-weight: 600; }}
    select, input {{ width: 100%; margin-top: 5px; }}
    .legend {{ display: flex; justify-content: space-between; margin-top: 12px;
      color: #466257; font-size: 12px; gap: 8px; }}
    .swatches {{ display: flex; gap: 7px; margin-top: 6px; }}
    .swatches span {{ flex: 1; height: 9px; border-radius: 5px; }}
    .leaflet-container {{ background: #e9f0ed; }}
  </style>
</head>
<body>
  <div id="map" role="application" aria-label="NYC community data by ZIP code"></div>
  <section class="panel">
    <h1>NYC Community Data by ZIP Code</h1>
    <label for="metric">Map layer</label>
    <select id="metric">
      <option value="trees">Street tree count</option>
      <option value="hvi">Heat Vulnerability Index</option>
      <optgroup label="Income and poverty">
        <option value="median_income">Median household income</option>
        <option value="poverty_rate">Population below poverty level</option>
      </optgroup>
      <optgroup label="Race and ethnicity">
        <option value="race">Race / ethnicity population share</option>
      </optgroup>
      <optgroup label="Housing">
        {housing_options}
      </optgroup>
    </select>
    <div id="raceControl" hidden>
      <label for="raceGroup">Race / ethnicity group</label>
      <select id="raceGroup">{race_options}</select>
    </div>
    <p id="summary"></p>
    <label for="opacity">Map opacity</label>
    <input id="opacity" type="range" min="20" max="100" value="75">
    <div class="legend"><span id="legendLow"></span><span id="legendHigh"></span></div>
    <div class="swatches" id="swatches" aria-hidden="true"></div>
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

    const metricConfig = {json.dumps(METRICS, separators=(",", ":"))};
    const treeColors = {json.dumps(TREE_COLORS)};
    const hviColors = {json.dumps(HVI_COLORS)};
    const raceColors = {json.dumps(RACE_COLORS)};
    const metricSelect = document.getElementById("metric");
    const raceGroupSelect = document.getElementById("raceGroup");
    const opacityControl = document.getElementById("opacity");
    const treeValues = Object.values(data.treeCounts).sort((a, b) => a - b);
    const treeBreaks = [0.2, 0.4, 0.6, 0.8].map(percentile =>
      treeValues[Math.floor((treeValues.length - 1) * percentile)] || 0
    );

    function metricValue(zipCode) {{
      const metric = metricSelect.value;
      if (metric === "trees") return data.treeCounts[zipCode];
      if (metric === "hvi") return data.hviRanks[zipCode];
      const estimate = data.acsMetrics[zipCode];
      if (!estimate) return undefined;
      if (metric === "race") return estimate.race_shares[raceGroupSelect.value];
      return estimate[metric];
    }}

    function colorIndex(value) {{
      if (value === undefined || value === null) return -1;
      if (metricSelect.value === "hvi") return value - 1;
      if (metricSelect.value === "race") {{
        return Math.min(4, Math.floor(value / 20));
      }}
      if (metricSelect.value === "trees") {{
        const index = treeBreaks.findIndex(limit => value <= limit);
        return index < 0 ? treeColors.length - 1 : index;
      }}
      const values = Object.keys(data.acsMetrics)
        .map(zipCode => metricValue(zipCode))
        .filter(value => value !== undefined && value !== null)
        .sort((a, b) => a - b);
      if (!values.length) return -1;
      const index = [0.2, 0.4, 0.6, 0.8].findIndex(percentile =>
        value <= values[Math.floor((values.length - 1) * percentile)]
      );
      return index < 0 ? 4 : index;
    }}

    function palette() {{
      if (metricSelect.value === "trees") return treeColors;
      if (metricSelect.value === "hvi") return hviColors;
      if (metricSelect.value === "race") return raceColors;
      return metricConfig[metricSelect.value].colors;
    }}

    function polygonStyle(feature) {{
      const value = metricValue(feature.properties.ZCTA5);
      const colors = palette();
      const index = colorIndex(value);
      return {{
        color: "#ffffff",
        weight: 1,
        fillColor: index < 0 ? "#d9dfdc" : colors[index],
        fillOpacity: Number(opacityControl.value) / 100
      }};
    }}

    function formatValue(zipCode, value) {{
      if (value === undefined || value === null) return "No estimate available";
      const metric = metricSelect.value;
      if (metric === "trees") {{
        const status = data.status === "All" ? "" : data.status.toLowerCase() + " ";
        return `${{Number(value).toLocaleString()}} ${{status}}trees`;
      }}
      if (metric === "hvi") return `HVI rank: ${{value}} of 5`;
      const unit = metric === "race"
        ? "percent of population"
        : metricConfig[metric].unit;
      if (unit === "currency") {{
        return `$${{Number(value).toLocaleString()}}`;
      }}
      return `${{Number(value).toFixed(1)}}% ${{unit === "percent" ? "" : unit}}`;
    }}

    function tooltip(zipCode) {{
      const metric = metricSelect.value;
      const label = metric === "trees"
        ? "Street trees"
        : metric === "hvi"
          ? "Heat Vulnerability Index"
          : metric === "race"
            ? raceGroupSelect.value
            : metricConfig[metric].label;
      return `<strong>ZIP ${{zipCode}}</strong><br>${{label}}: ` +
        formatValue(zipCode, metricValue(zipCode));
    }}

    function updateMap() {{
      const metric = metricSelect.value;
      const colors = palette();
      document.getElementById("raceControl").hidden = metric !== "race";
      document.getElementById("swatches").innerHTML = colors
        .map(color => `<span style="background:${{color}}"></span>`).join("");

      if (metric === "trees") {{
        document.getElementById("legendLow").textContent = "Fewer trees";
        document.getElementById("legendHigh").textContent = "More trees";
        document.getElementById("summary").textContent =
          `${{data.treeMappedTotal.toLocaleString()}} ${{data.status === "All" ? "" : data.status.toLowerCase() + " "}}trees across ${{data.treeMappedZipCodes}} ZIP codes`;
        document.getElementById("note").textContent =
          `${{data.treeUnmappedTotal.toLocaleString()}} trees could not be mapped to a ZIP boundary.`;
      }} else if (metric === "hvi") {{
        document.getElementById("legendLow").textContent = "1: Lower vulnerability";
        document.getElementById("legendHigh").textContent = "5: Higher vulnerability";
        document.getElementById("summary").textContent =
          `${{data.hviMappedZipCodes}} ZIP areas have an HVI ranking`;
        document.getElementById("note").textContent =
          `${{data.hviUnmappedZipCodes}} HVI ZIP codes have no matching boundary.`;
      }} else {{
        const selectedMetric = metric === "race" ? null : metricConfig[metric];
        document.getElementById("legendLow").textContent = metric === "race"
          ? "0% of population" : selectedMetric.low;
        document.getElementById("legendHigh").textContent = metric === "race"
          ? "100% of population" : selectedMetric.high;
        const label = metric === "race"
          ? raceGroupSelect.value + " population share"
          : selectedMetric.label;
        document.getElementById("summary").textContent =
          `${{data.acsMappedZipCodes}} ZIP areas with ACS estimates · ${{data.acsYear}} ACS 5-year`;
        document.getElementById("note").textContent =
          `${{label}}. ACS rates are calculated from published count estimates; gray areas have no estimate.`;
      }}

      zipLayer.setStyle(polygonStyle);
      zipLayer.eachLayer(layer =>
        layer.setTooltipContent(tooltip(layer.feature.properties.ZCTA5))
      );
    }}

    const zipLayer = L.geoJSON(data.boundaries, {{
      style: polygonStyle,
      onEachFeature: (feature, layer) => {{
        layer.bindTooltip(tooltip(feature.properties.ZCTA5));
        layer.on({{
          mouseover: () => layer.setStyle({{ color: "#183128", weight: 2 }}),
          mouseout: () => layer.setStyle(polygonStyle(feature))
        }});
      }}
    }}).addTo(map);

    metricSelect.addEventListener("change", updateMap);
    raceGroupSelect.addEventListener("change", updateMap);
    opacityControl.addEventListener("input", () => zipLayer.setStyle(polygonStyle));
    if (zipLayer.getLayers().length) {{
      map.fitBounds(zipLayer.getBounds(), {{ padding: [20, 20] }});
    }}
    updateMap();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add ACS 5-year demographic and housing layers to the NYC map."
    )
    parser.add_argument(
        "--tree-dataset", type=Path, default=TREE_DATASET,
        help="Path to the street tree census CSV.",
    )
    parser.add_argument(
        "--hvi-dataset", type=Path, default=HVI_DATASET,
        help="Path to the heat vulnerability rankings CSV.",
    )
    parser.add_argument(
        "--boundaries", type=Path, default=BOUNDARIES,
        help="Path to the cached Census ZIP Code Tabulation Area boundaries.",
    )
    parser.add_argument(
        "--acs-cache", type=Path, default=ACS_CACHE,
        help="Path to the cached ACS estimates.",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT,
        help="Path for the generated interactive map.",
    )
    parser.add_argument(
        "--status", default="Alive",
        help='Tree status to map (default: "Alive"); use "All" for every status.',
    )
    parser.add_argument(
        "--refresh-acs", action="store_true",
        help="Fetch ACS data again instead of using the local cache.",
    )
    args = parser.parse_args()

    for path in (args.tree_dataset, args.hvi_dataset, args.boundaries):
        if not path.is_file():
            parser.error(f"Required data file does not exist: {path}")

    try:
        create_map(
            args.tree_dataset,
            args.hvi_dataset,
            args.boundaries,
            args.acs_cache,
            args.output,
            args.status,
            CENSUS_API_KEY,
            args.refresh_acs,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Created {args.output} with ACS {ACS_YEAR} data.")


if __name__ == "__main__":
    main()