#  Trees in NYC

This dashboard is made by Kiane Efondo, dedicated to analyzing and comparing data of trees in NYC to economic indexes of NYC.

I was influenced to make this to do an analytical study on the trees in NYC, and see if trees are maintained purposefully similar to how historically NYC's melting pot/salad bowl of ethnic backgrounds developed. Regardless of trees, this is a fun interactive dashboard to do a deep dive and see where trees are in NYC, economic indexes in NYC, and heat vulnerability in your neighborhoods. Enjoy!

## How to setup and use

1. Download datasets and access API below.
2. Once access to API has been secured, add this to your .env

CENSUS_API_KEY=[YOUR-API-KEY-HERE]

3. add datasets into a datasets folder

Make sure the datasets are in the `datasets` folder:

   - `2015_Street_Tree_Census_-_Tree_Data_20261020.csv`
   - `Heat_Vulnerability_Index_Rankings_20261020.csv`
   - `nyc_zcta_boundaries.geojson`
   - `canopy_jurisdiction_landuse_borough.csv`

4. Run these commands in the terminal to see dashboard

python economic_census_data_in_nyc.py
python open_map.py

## Data and map credits

- NYC 2015 Street Tree Census
- NYC Heat Vulnerability Index
- U.S. Census Bureau 2024 American Community Survey 5-Year Estimates
- U.S. Census Bureau 2020 ZIP Code Tabulation Area boundaries
- The Nature Conservancy
- Map tiles © OpenStreetMap contributors

## Datasets/APIs used

Heat Vulnerability Index Rankings
- https://data.cityofnewyork.us/Health/Heat-Vulnerability-Index-Rankings/4mhf-duep/about_data

American Community Survey 5-Year Data API
- [https://www.census.gov/data/developers/data-sets/acs-5year.html](https://www.census.gov/data/developers/data-sets/acs-5year.html)

2015 Street Tree Census Data
- https://data.nyc.gov/Environment/2015-Street-Tree-Census-Tree-Data/uvpi-gqnh/about_data

NYC Zip Code Boundaries data
- https://tigerweb.geo.census.gov/arcgis/rest/services/Census2020/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/2

Canopy Jurisdiction in each Borough
- https://zenodo.org/records/5210261?preview_file=canopy_jurisdiction_landuse_borough.zip

# Analysis on Dashboard

## Are neighborhoods with higher poverty rates associated with lower tree coverage?



### Median Household Income vs. Trees in NYC

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/9123b5ba-069f-4cc3-be2c-a9cae8ac3590" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

### Heat Vulnerability Index vs. Trees in NYC

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/4ad27c4b-bcd8-499c-a06d-7001c8a4f15d" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

### Race / Ethnic Population vs. Trees in NYC

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/2a686953-70d8-4b2b-b6f3-769b5e553107" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

## Are lower income neighborhoods more vulnerable to extreme heat?

### Heat Vulnerability Index vs Median household income



### Race / Ethnic population vs Heat Vulnerability Index



## So how does NYC prioritize how we plant trees in NYC?

### 
