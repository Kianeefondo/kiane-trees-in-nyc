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

When we look at the trees in NYC, we can definitely see that trees come in clusters, but do we ever stop to think why the trees are there. We have a bunch of different trees in NYC, and sometimes I wish we had more trees or at least more greenery. As we know it, NYC has developed itself to be very much a salad bowl with its defined cultural enclaves. NYC has very notable neighborhoods like Chinatown, Harlem, and new enclaves are popping up, like Little Manila. 

## Are neighborhoods with higher poverty rates associated with lower tree coverage?

When we look closer into these neighborhoods, we can focus on a few neighborhoods for reference.

- Brownsville - 11212
- Williamsburg - 11211
- Hunts Point/Longwood - 10474/10459
- Corona - 11368
- Forest Hills - 11375
- Sunnyside - 11104

These neighborhoods is a good assortment of high income, medium income and low income neighborhoods that we can cross reference to each other.

### Median Household Income / Population below poverty level vs. Trees in NYC

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/9123b5ba-069f-4cc3-be2c-a9cae8ac3590" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/3c51a12b-5707-4147-9f33-1d17ce7d3827" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

| Neighborhood | ZIP Code(s) | Median Household Income | Poverty Rate | Tree Count |
|---|---|---:|---:|---:|
| Brownsville | 11212 | $41,355 | 33.6% | 4,007 |
| Williamsburg | 11211 | $107,506 | 20.3% | 3,966 |
| Hunts Point/Longwood | 10474 / 10459 | $41,586 / $38,006 | 29.3% / 33.7% | 2,462 / 2,910 |
| Corona | 11368 | $72,270 | 19.4% | 4,124 |
| Forest Hills | 11375 | $105,904 | 8.7% | 6,742 |
| Sunnyside | 11104 | $80,709 | 10.6% | 1,615 |

### Heat Vulnerability Index vs. Trees in NYC

* HVI is is used to masure which communities ar emore vulnerable to health impacts of extreme heat
* 1/5 means less heat-related health impacts
* 5/5 means most vulnerable to heat-related health impacts
* HVI also considers surface temperature, green scape, access to home AC, income and racial disparities.

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/4ad27c4b-bcd8-499c-a06d-7001c8a4f15d" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

| Neighborhood | ZIP Code(s) | Heat Vulnerability Index | Tree Count |
|---|---|---:|---:|
| Brownsville | 11212 | 5/5 | 4,007 |
| Williamsburg | 11211 | 3/5 | 3,966 |
| Hunts Point/Longwood | 10474 / 10459 | 5/5 | 2,462 / 2,910 |
| Corona | 11368 | 4/5 | 4,124 |
| Forest Hills | 11375 | 2/5 | 6,742 |
| Sunnyside | 11104 | 3/5 | 1,615 |

### Race / Ethnic Population vs. Trees in NYC

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/2a686953-70d8-4b2b-b6f3-769b5e553107" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/759a6e1e-fc2a-42df-a5a3-59f5e9b4174e" width="100%" /></td>
  </tr>
</table>

| Neighborhood | ZIP Code(s) | Heat Vulnerability Index | Tree Count |
|---|---|---:|---:|
| Brownsville | 11212 | Black, non-Hispanic | 4,007 |
| Williamsburg | 11211 | White | 3,966 |
| Hunts Point/Longwood | 10474 / 10459 | Hispanic | 2,462 / 2,910 |
| Corona | 11368 | White | 4,124 |
| Forest Hills | 11375 | White | 6,742 |
| Sunnyside | 11104 | White | 1,615 |

## Are lower income neighborhoods more vulnerable to extreme heat?

### Heat Vulnerability Index vs Median household income

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/9123b5ba-069f-4cc3-be2c-a9cae8ac3590" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/4ad27c4b-bcd8-499c-a06d-7001c8a4f15d" width="100%" /></td>
  </tr>
</table>

| Neighborhood | ZIP Code(s) | Median Household Income | Heat Vulnerability Index |
|---|---|---:|---:|
| Brownsville | 11212 | $41,355 | 5/5 |
| Williamsburg | 11211 | $107,506 | 3/5 |
| Hunts Point/Longwood | 10474 / 10459 | $41,586 / $38,006 | 5/5 |
| Corona | 11368 | $72,270 | 4/5 |
| Forest Hills | 11375 | $105,904 | 2/5 |
| Sunnyside | 11104 | $80,709 | 3/5 |

### Race / Ethnic population vs Heat Vulnerability Index

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/2a686953-70d8-4b2b-b6f3-769b5e553107" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/4ad27c4b-bcd8-499c-a06d-7001c8a4f15d" width="100%" /></td>
  </tr>
</table>

| Neighborhood | ZIP Code(s) | Race/Ethnicity | Heat Vulnerability Index |
|---|---|---|---:|
| Brownsville | 11212 | Black, non-Hispanic | 5/5 |
| Williamsburg | 11211 | White | 3/5 |
| Hunts Point/Longwood | 10474 / 10459 | Hispanic | 5/5 |
| Corona | 11368 | White | 4/5 |
| Forest Hills | 11375 | White | 2/5 |
| Sunnyside | 11104 | White | 3/5 |

## Some important notes about this subset

| Neighborhood | ZIP Code(s) | Median Household Income | Poverty Rate | Heat Vulnerability Index | Largest Racial/Ethnic Group (as provided) | Tree Count |
|---|---|---:|---:|---:|---|---:|
| Brownsville | 11212 | $41,355 | 33.6% | 5/5 | Black, non-Hispanic | 4,007 |
| Williamsburg | 11211 | $107,506 | 20.3% | 3/5 | White | 3,966 |
| Hunts Point/Longwood | 10474 / 10459 | $41,586 / $38,006 | 29.3% / 33.7% | 5/5* | Hispanic | 2,462 / 2,910 |
| Corona | 11368 | $72,270 | 19.4% | 4/5 | White | 4,124 |
| Forest Hills | 11375 | $105,904 | 8.7% | 2/5 | White | 6,742 |
| Sunnyside | 11104 | $80,709 | 10.6% | 3/5 | White | 1,615 |

Going through the data, we deduce that a higher tree count does not necessarily mean lower heat vulnerability, but we can deduce some interesting comparisons.

### Brownsville vs Forest Hills
These two neighborhoods have opposing logistics, such that Forest hills has a low poverty rate, high house median household income with a lower relative HVI, while Brownsville is the opposite.

### Corona is a very important middle case
Corona has very intermediate numbers, where each number is not high but also not low.



## So how does NYC actually think about trees getting planted in NYC?

Looking into more of how trees are prioritized throughout NYC, the NYC Parks department does factor in heavily the HVI score to survey which streets need more trees and identify feasible planting locations. This approach not only targets at risk neighborhoods, but also communities that are most vulnerable to extreme heat while accounting for the physical constraints of the urban environment.

We can see that these comparisons in economic disadvantages and heat vulnerability may overlap in some neighborhoods. However, without proper tree canopy coverage in NYC, there is not enough information to work with to understand number of feasible planting locations, tree distribution, and neighborhood sizes. Since recorded trees do not give enough information on environmental equity, this analysis would factor in canopy coverage and tree density to strengthen information on areas needed for additional planting.

## Some things to note
- NYC's HVI factors in green space and socioeconomic factors.
- Street Tree count does not factor in for tree canopy coverage.
- Dataset years do differ by a few years, which may have mismatching conditions.
- Poverty rate + Median household income measure different things.
