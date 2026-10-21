"""Build an NYC map of street trees, heat vulnerability, and ACS data.

Set your Census API key in the local ``.env`` file, then run:

    python economic_census_data_in_nyc.py

The first run downloads 2024 ACS 5-year ZCTA estimates and caches them under
``datasets``. Later runs reuse the cache; pass ``--refresh-acs`` to update it.
Edit the map title and introduction in ``_html`` to personalize the project.
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
from canopy_by_borough import (
    BOUNDARIES as BOROUGH_BOUNDARIES,
    DATASET as CANOPY_DATASET,
    load_boundaries as load_borough_boundaries,
    read_canopy_data,
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
RACE_GROUP_COLORS = {
    "White, non-Hispanic": "#1b9e77",
    "Black, non-Hispanic": "#d95f02",
    "American Indian / Alaska Native, non-Hispanic": "#7570b3",
    "Asian, non-Hispanic": "#e7298a",
    "Native Hawaiian / Pacific Islander, non-Hispanic": "#66a61e",
    "Some other race, non-Hispanic": "#e6ab02",
    "Two or more races, non-Hispanic": "#a6761d",
    "Hispanic or Latino, any race": "#1f78b4",
}


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
            "race_counts": {
                group: raw[variable]
                for group, variable in RACE_VARIABLES.items()
            },
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
        data = cached.get("data")
        if (
            cached.get("year") == ACS_YEAR
            and isinstance(data, dict)
            and all("race_counts" in estimate for estimate in data.values())
        ):
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
    canopy_dataset: Path,
    borough_boundaries_path: Path,
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
    canopy_data = read_canopy_data(canopy_dataset)
    borough_boundaries = load_borough_boundaries(borough_boundaries_path)

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
        "canopyBoundaries": borough_boundaries,
        "canopyData": canopy_data,
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
    canopy_dataset: Path,
    borough_boundaries_path: Path,
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
            canopy_dataset,
            borough_boundaries_path,
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
  <title>NYC, Block by Block</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ font: 14px/1.5 system-ui, sans-serif; color: #25352f; }}
    .panel {{ position: absolute; z-index: 1000; top: 20px; left: 64px;
      width: min(310px, calc(100vw - 104px)); max-height: calc(100vh - 72px);
      overflow-y: auto; padding: 20px; background: #fffdf8; border-radius: 8px;
      box-shadow: 0 3px 18px #25352f24; }}
    .eyebrow {{ margin: 0 0 4px; color: #52745e; font-size: 11px;
      font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ font-family: Georgia, "Times New Roman", serif; font-size: 26px;
      font-weight: 500; letter-spacing: -.03em; line-height: 1.1;
      margin: 0 0 8px; }}
    .intro {{ color: #64736b; margin: 0 0 16px; }}
    label {{ display: block; margin-top: 12px; font-size: 12px;
      font-weight: 700; }}
    select {{ box-sizing: border-box; width: 100%; margin-top: 5px; padding: 8px;
      border: 1px solid #d6ddd5; border-radius: 5px; background: white;
      color: inherit; font: inherit; }}
    #summary {{ color: #52745e; font-size: 12px; margin: 12px 0 0; }}
    .legend {{ display: flex; justify-content: space-between; margin-top: 14px;
      color: #64736b; font-size: 11px; gap: 8px; }}
    .swatches {{ display: flex; gap: 5px; margin-top: 6px; }}
    .swatches span {{ flex: 1; height: 8px; border-radius: 4px; }}
    .category-legend {{ display: grid; grid-template-columns: 1fr 1fr;
      gap: 5px 9px; margin-top: 8px; color: #53645a; font-size: 10px; }}
    .category-legend span {{ display: flex; align-items: flex-start; gap: 5px; }}
    .category-legend i {{ flex: 0 0 9px; height: 9px; margin-top: 2px;
      border-radius: 50%; }}
    #note {{ color: #78847d; font-size: 11px; margin: 9px 0 0; }}
    .leaflet-container {{ background: #e8eee9; }}
    @media (max-width: 520px) {{
      .panel {{ top: 12px; left: 54px; width: min(280px, calc(100vw - 82px));
        padding: 14px; }}
      h1 {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <div id="map" role="application" aria-label="NYC community data by ZIP code"></div>
  <section class="panel">
    <p class="eyebrow">A New York City data project</p>
    <h1>NYC, Block by Block</h1>
    <p class="intro">Explore street trees, heat, and neighborhood patterns across the five boroughs.</p>
    <label for="metric">Explore a map layer</label>
    <select id="metric">
      <option value="trees">Street tree count</option>
      <option value="hvi">Heat Vulnerability Index</option>
      <option value="canopy">Tree canopy by borough</option>
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
      <label for="raceMode">Race / ethnicity view</label>
      <select id="raceMode">
        <option value="city_share">Share of group's NYC-wide population</option>
        <option value="dominant">Largest group in each ZIP</option>
      </select>
      <label for="raceGroup">Race / ethnicity group</label>
      <select id="raceGroup">{race_options}</select>
    </div>
    <div id="canopyControl" hidden>
      <label for="canopyYear">Canopy year</label>
      <select id="canopyYear">
        <option value="2010">2010</option>
        <option value="2017" selected>2017</option>
      </select>
      <label for="canopyLandType">Land type</label>
      <select id="canopyLandType">
        <option value="All">All land types</option>
        <option value="Developed">Developed</option>
        <option value="Natural">Natural</option>
      </select>
    </div>
    <p id="summary"></p>
    <div class="legend"><span id="legendLow"></span><span id="legendHigh"></span></div>
    <div class="swatches" id="swatches" aria-hidden="true"></div>
    <div class="category-legend" id="categoryLegend" hidden></div>
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
    const raceGroupColors = {json.dumps(RACE_GROUP_COLORS, separators=(",", ":"))};
    const canopyColors = ["#f1f7e8", "#cfe5bd", "#91c68a", "#4b9b62", "#17633c"];
    const metricSelect = document.getElementById("metric");
    const raceModeSelect = document.getElementById("raceMode");
    const raceGroupSelect = document.getElementById("raceGroup");
    const canopyYearSelect = document.getElementById("canopyYear");
    const canopyLandTypeSelect = document.getElementById("canopyLandType");
    const treeValues = Object.values(data.treeCounts).sort((a, b) => a - b);
    const treeBreaks = [0.2, 0.4, 0.6, 0.8].map(percentile =>
      treeValues[Math.floor((treeValues.length - 1) * percentile)] || 0
    );
    const cityRaceTotals = Object.fromEntries(
      Object.keys(raceGroupColors).map(group => [
        group,
        Object.values(data.acsMetrics).reduce(
          (total, estimate) => total + (estimate.race_counts[group] || 0),
          0
        )
      ])
    );

    function raceShare(zipCode, group) {{
      const estimate = data.acsMetrics[zipCode];
      const total = cityRaceTotals[group];
      const count = estimate && estimate.race_counts[group];
      return count === undefined || count === null || !total
        ? undefined
        : 100 * count / total;
    }}

    function dominantRace(zipCode) {{
      const estimate = data.acsMetrics[zipCode];
      if (!estimate) return undefined;
      const entries = Object.entries(estimate.race_counts)
        .filter(([, count]) => count !== undefined && count !== null);
      if (!entries.length) return undefined;
      return entries.reduce((largest, current) =>
        current[1] > largest[1] ? current : largest
      )[0];
    }}

    function metricValue(zipCode) {{
      const metric = metricSelect.value;
      if (metric === "trees") return data.treeCounts[zipCode];
      if (metric === "hvi") return data.hviRanks[zipCode];
      const estimate = data.acsMetrics[zipCode];
      if (!estimate) return undefined;
      if (metric === "race") {{
        return raceModeSelect.value === "dominant"
          ? dominantRace(zipCode)
          : raceShare(zipCode, raceGroupSelect.value);
      }}
      return estimate[metric];
    }}

    function colorIndex(value) {{
      if (value === undefined || value === null) return -1;
      if (metricSelect.value === "hvi") return value - 1;
      if (metricSelect.value === "race" && raceModeSelect.value === "dominant") {{
        return Object.keys(raceGroupColors).indexOf(value);
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
      if (metricSelect.value === "canopy") return canopyColors;
      if (metricSelect.value === "race" && raceModeSelect.value === "dominant") {{
        return Object.values(raceGroupColors);
      }}
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
        fillOpacity: 0.82
      }};
    }}

    function canopyRecord(borough) {{
      return data.canopyData[borough]?.[canopyLandTypeSelect.value];
    }}

    function canopyPercent(borough) {{
      const record = canopyRecord(borough);
      return record?.[`canopy${{canopyYearSelect.value}}_percent`];
    }}

    function canopyStyle(feature) {{
      const percent = canopyPercent(feature.properties.borough);
      const breaks = [10, 15, 20, 25];
      const index = percent === undefined || percent === null
        ? -1
        : breaks.findIndex(limit => percent < limit);
      return {{
        color: "#ffffff",
        weight: 2,
        fillColor: index < 0
          ? (percent === undefined || percent === null
            ? "#d9dfdc"
            : canopyColors[canopyColors.length - 1])
          : canopyColors[index],
        fillOpacity: 0.86
      }};
    }}

    function canopyTooltip(borough) {{
      const record = canopyRecord(borough);
      if (!record) return `<strong>${{borough}}</strong><br>No canopy data`;
      const year = canopyYearSelect.value;
      const area = record[`canopy${{year}}_acres`];
      const percent = record[`canopy${{year}}_percent`];
      const netChange = record.canopy2017_acres - record.canopy2010_acres;
      const percentagePointChange =
        record.canopy2017_percent - record.canopy2010_percent;
      return `<strong>${{borough}}</strong><br>` +
        `${{year}} canopy: ${{percent.toFixed(1)}}% ` +
        `(${{area.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} acres)` +
        `<br>Land area: ${{record.acreage.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} acres` +
        `<br>2010–2017 net change: ${{netChange >= 0 ? "+" : ""}}` +
        `${{netChange.toLocaleString(undefined, {{maximumFractionDigits: 0}})}} canopy acres` +
        `<br>Change: ${{percentagePointChange >= 0 ? "+" : ""}}` +
        `${{percentagePointChange.toFixed(1)}} percentage points`;
    }}

    function formatValue(zipCode, value) {{
      if (value === undefined || value === null) return "No estimate available";
      const metric = metricSelect.value;
      if (metric === "trees") {{
        const status = data.status === "All" ? "" : data.status.toLowerCase() + " ";
        return `${{Number(value).toLocaleString()}} ${{status}}trees`;
      }}
      if (metric === "hvi") return `HVI rank: ${{value}} of 5`;
      const unit = metricConfig[metric].unit;
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
            ? raceModeSelect.value === "dominant"
              ? "Largest group"
              : raceGroupSelect.value
            : metricConfig[metric].label;
      if (metric === "race") {{
        const estimate = data.acsMetrics[zipCode];
        if (raceModeSelect.value === "dominant") {{
          const group = metricValue(zipCode);
          const count = group && estimate.race_counts[group];
          return `<strong>ZIP ${{zipCode}}</strong><br>Largest group: ` +
            (group ? `${{group}} (${{count.toLocaleString()}} people)` : "No estimate available");
        }}
        const group = raceGroupSelect.value;
        const count = estimate && estimate.race_counts[group];
        const share = metricValue(zipCode);
        return `<strong>ZIP ${{zipCode}}</strong><br>${{group}}: ` +
          (share === undefined
            ? "No estimate available"
            : `${{share.toFixed(2)}}% of NYC-wide group population ` +
              `(${{count.toLocaleString()}} of ${{cityRaceTotals[group].toLocaleString()}} people)`);
      }}
      return `<strong>ZIP ${{zipCode}}</strong><br>${{label}}: ` +
        formatValue(zipCode, metricValue(zipCode));
    }}

    function updateMap() {{
      const metric = metricSelect.value;
      const colors = palette();
      const isDominantRace = metric === "race" && raceModeSelect.value === "dominant";
      const isCanopy = metric === "canopy";
      if (isCanopy && map.hasLayer(zipLayer)) {{
        map.removeLayer(zipLayer);
        boroughLayer.addTo(map);
        map.fitBounds(boroughLayer.getBounds(), {{ padding: [20, 20] }});
      }} else if (!isCanopy && map.hasLayer(boroughLayer)) {{
        map.removeLayer(boroughLayer);
        zipLayer.addTo(map);
        map.fitBounds(zipLayer.getBounds(), {{ padding: [20, 20] }});
      }}
      document.getElementById("raceControl").hidden = metric !== "race";
      document.getElementById("canopyControl").hidden = !isCanopy;
      document.getElementById("raceGroup").hidden =
        isDominantRace;
      document.getElementById("swatches").hidden = isDominantRace;
      document.getElementById("categoryLegend").hidden = !isDominantRace;
      document.getElementById("categoryLegend").innerHTML = isDominantRace
        ? Object.entries(raceGroupColors).map(([group, color]) =>
            `<span><i style="background:${{color}}"></i>${{group}}</span>`
          ).join("")
        : "";
      document.getElementById("swatches").innerHTML = colors
        .map(color => `<span style="background:${{color}}"></span>`).join("");

      if (isCanopy) {{
        const percentages = data.canopyBoundaries.features
          .map(feature => canopyPercent(feature.properties.borough))
          .filter(value => value !== undefined && value !== null);
        const average = percentages.length
          ? percentages.reduce((sum, value) => sum + value, 0) / percentages.length
          : 0;
        document.getElementById("legendLow").textContent = "0% canopy";
        document.getElementById("legendHigh").textContent = "25%+ canopy";
        document.getElementById("summary").textContent =
          `${{percentages.length}} boroughs · ${{average.toFixed(1)}}% average canopy in ${{canopyYearSelect.value}}`;
        document.getElementById("note").textContent =
          `${{canopyLandTypeSelect.value === "All" ? "All land types" : canopyLandTypeSelect.value}} · Historical canopy estimates from 2010 and 2017. Hover a borough for acreage and change since 2010.`;
        document.getElementById("swatches").innerHTML =
          canopyColors.map(color => `<span style="background:${{color}}"></span>`).join("");
      }} else if (metric === "race" && raceModeSelect.value === "dominant") {{
        document.getElementById("legendLow").textContent = "Largest group in each ZIP";
        document.getElementById("legendHigh").textContent = "";
        document.getElementById("summary").textContent =
          "ZIP codes are colored by their largest race / ethnicity group.";
        document.getElementById("note").textContent =
          "Shows the largest group (not necessarily a majority) using mutually exclusive ACS categories.";
      }} else if (metric === "race") {{
        document.getElementById("legendLow").textContent = "Smaller share of NYC group";
        document.getElementById("legendHigh").textContent = "Larger share of NYC group";
        document.getElementById("summary").textContent =
          `${{data.acsMappedZipCodes}} ZIP areas · share of selected group's NYC-wide population`;
        document.getElementById("note").textContent =
          `${{raceGroupSelect.value}} residents in each ZIP as a share of all matching residents across the mapped NYC ZIP areas. Hover for counts.`;
      }} else if (metric === "trees") {{
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
        const selectedMetric = metricConfig[metric];
        document.getElementById("legendLow").textContent = selectedMetric.low;
        document.getElementById("legendHigh").textContent = selectedMetric.high;
        const label = selectedMetric.label;
        document.getElementById("summary").textContent =
          `${{data.acsMappedZipCodes}} ZIP areas with ACS estimates · ${{data.acsYear}} ACS 5-year`;
        document.getElementById("note").textContent =
          `${{label}}. ACS rates are calculated from published count estimates; gray areas have no estimate.`;
      }}

      if (isCanopy) {{
        boroughLayer.setStyle(canopyStyle);
        boroughLayer.eachLayer(layer =>
          layer.setTooltipContent(canopyTooltip(layer.feature.properties.borough))
        );
      }} else {{
        zipLayer.setStyle(polygonStyle);
        zipLayer.eachLayer(layer =>
          layer.setTooltipContent(tooltip(layer.feature.properties.ZCTA5))
        );
      }}
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

    const boroughLayer = L.geoJSON(data.canopyBoundaries, {{
      style: canopyStyle,
      onEachFeature: (feature, layer) => {{
        layer.bindTooltip(canopyTooltip(feature.properties.borough));
        layer.on({{
          mouseover: () => layer.setStyle({{ color: "#183128", weight: 3 }}),
          mouseout: () => layer.setStyle(canopyStyle(feature))
        }});
      }}
    }});

    metricSelect.addEventListener("change", updateMap);
    raceModeSelect.addEventListener("change", updateMap);
    raceGroupSelect.addEventListener("change", updateMap);
    canopyYearSelect.addEventListener("change", updateMap);
    canopyLandTypeSelect.addEventListener("change", updateMap);
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
        "--canopy-dataset", type=Path, default=CANOPY_DATASET,
        help="Path to the canopy jurisdiction CSV.",
    )
    parser.add_argument(
        "--borough-boundaries", type=Path, default=BOROUGH_BOUNDARIES,
        help="Path to cached Census borough boundaries (downloaded if missing).",
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

    for path in (
        args.tree_dataset,
        args.hvi_dataset,
        args.boundaries,
        args.canopy_dataset,
    ):
        if not path.is_file():
            parser.error(f"Required data file does not exist: {path}")

    try:
        create_map(
            args.tree_dataset,
            args.hvi_dataset,
            args.boundaries,
            args.canopy_dataset,
            args.borough_boundaries,
            args.acs_cache,
            args.output,
            args.status,
            CENSUS_API_KEY,
            args.refresh_acs,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Created {args.output} with ACS {ACS_YEAR} data and borough canopy layers.")


if __name__ == "__main__":
    main()