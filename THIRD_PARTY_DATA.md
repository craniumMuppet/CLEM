# Third-Party Data and Attribution

CLEM uses and, in some cases, distributes processed or derived data from third-party scientific datasets.

The **MIT License included with CLEM applies only to the CLEM source code and other original CLEM material**. It does not replace, override, or relicense third-party datasets.

Third-party data remain subject to the terms, licences, citation requirements, and attribution requirements of their respective providers.

---

## HadCRUT5

**Dataset:** HadCRUT5 global surface temperature dataset  
**Version used by CLEM:** 5.1.0.0  
**Provider:** Met Office Hadley Centre / Climatic Research Unit  
**Use in CLEM:** Historical global-mean surface-temperature evaluation and retrospective hindcast diagnostics  
**Licence:** Open Government Licence v3.0  
**Copyright:** British Crown Copyright, Met Office

CLEM includes the HadCRUT5 global annual analysis summary series:

```text
data/validation/temperature/HadCRUT.5.1.0.0.analysis.summary_series.global.annual.csv
```

HadCRUT5 is provided under the UK Open Government Licence v3.0 and requires attribution.

### Citation

Morice, C. P., Kennedy, J. J., Rayner, N. A., Winn, J. P., Hogan, E., Killick, R. E., Dunn, R. J. H., Osborn, T. J., Jones, P. D., & Simpson, I. R. (2021). *An updated assessment of near-surface temperature change from 1850: The HadCRUT5 data set*. Journal of Geophysical Research: Atmospheres, 126, e2019JD032361.

DOI: **10.1029/2019JD032361**

### Required acknowledgement

HadCRUT5 data are © British Crown Copyright, Met Office, and are provided under the Open Government Licence v3.0.

HadCRUT5 data are not covered by the CLEM MIT License.

---

## NOAA/NSIDC Sea Ice Index

**Dataset:** Sea Ice Index  
**Product ID:** G02135  
**Version used by CLEM:** Version 4  
**Provider:** National Snow and Ice Data Center (NSIDC)  
**Use in CLEM:** Historical Arctic sea-ice area and extent evaluation

CLEM includes processed March and September Northern Hemisphere time series derived from the Sea Ice Index:

```text
data/validation/nsidc/N_03_extent_v4.0.csv
data/validation/nsidc/N_09_extent_v4.0.csv
```

NSIDC requires citation of datasets used in scientific work and other media.

### Citation

Fetterer, F., Knowles, K., Meier, W. N., Savoie, M., Windnagel, A. K., & Stafford, T. (2025). *Sea Ice Index* (G02135, Version 4). National Snow and Ice Data Center.

DOI: **10.7265/a98x-0f50**

The Sea Ice Index source record used by CLEM includes changes in its underlying satellite products over time. CLEM records this transition in:

```text
data/validation/nsidc/METADATA.json
```

The metadata identifies NSIDC-0051 for much of the historical record and NSIDC-0803 for the more recent record.

These data are not covered by the CLEM MIT License.

---

## EUMETSAT OSI SAF Sea Ice Concentration

**Dataset:** Sea Ice Concentration Climate Data Record Release 3.1  
**Product:** OSI-450-a1  
**Provider:** EUMETSAT Ocean and Sea Ice Satellite Application Facility (OSI SAF)  
**Use in CLEM:** Independent fixed-mask Arctic sea-ice area cross-check  
**Licence:** Creative Commons Attribution 4.0 International (**CC BY 4.0**)

CLEM contains processed OSI-450-a1 diagnostics and a model-observation operator under:

```text
data/validation/sea_ice_crosscheck/osi_saf_osi450a1/
```

### Citation

OSI SAF (2025). *Sea Ice Concentration Climate Data Record Release 3.1 - Multimission*. EUMETSAT SAF on Ocean and Sea Ice.

DOI: **10.15770/EUM_SAF_OSI_0023**

OSI-450-a1 is distributed as free and unrestricted data under CC BY 4.0. Redistribution and adaptation are permitted provided appropriate attribution is given.

The OSI SAF data remain copyright/licensed material of their respective provider and are not relicensed under CLEM's MIT License.

---

## PIOMAS

**Dataset:** Pan-Arctic Ice Ocean Modeling and Assimilation System (PIOMAS)  
**Version used by CLEM:** 2.1  
**Provider:** Polar Science Center, Applied Physics Laboratory, University of Washington  
**Use in CLEM:** Long-record Arctic sea-ice volume and thickness constraint

CLEM contains processed PIOMAS-derived products under:

```text
data/validation/sea_ice_physical/
```

including:

```text
PIOMAS.monthly.Current.v2.1.csv
piomas_volume_monthly.csv
piomas_common_domain_operator.npz
piomas_v2_1_metadata.json
```

PIOMAS is a model/assimilation product rather than a direct satellite observation.

### Citations

For PIOMAS sea-ice volume:

Schweiger, A., Lindsay, R., Zhang, J., Steele, M., Stern, H., & Kwok, R. (2011). *Uncertainty in modeled Arctic sea ice volume*. Journal of Geophysical Research: Oceans.

DOI: **10.1029/2011JC007084**

For the underlying sea-ice model:

Zhang, J. L., & Rothrock, D. A. (2003). *Modeling global sea ice with a thickness and enthalpy distribution model in generalized curvilinear coordinates*. Monthly Weather Review, 131, 845-861.

### Licence note

The Polar Science Center PIOMAS data page specifies the requested scientific citations but does not clearly identify a standard open-source or Creative Commons licence for the PIOMAS data.

CLEM therefore **does not claim ownership of or relicense PIOMAS data**.

Users wishing to redistribute original PIOMAS source products should consult the Polar Science Center's current terms. Derived PIOMAS products included with CLEM retain this attribution and provenance information.

---

## CryoSat-2 Sea Ice Thickness

**Dataset:** CryoSat-2 Level-4 Sea Ice Elevation, Freeboard, and Thickness  
**Product ID:** RDEFT4  
**Version used by CLEM:** Version 1  
**Provider:** NASA National Snow and Ice Data Center Distributed Active Archive Center  
**Satellite:** ESA CryoSat-2  
**Use in CLEM:** Satellite-derived Arctic sea-ice thickness constraint

CLEM contains processed monthly values and an observation operator:

```text
data/validation/sea_ice_physical/cryosat2_rdeft4_monthly.csv
data/validation/sea_ice_physical/cryosat2_rdeft4_operator.npz
data/validation/sea_ice_physical/cryosat2_rdeft4_v1_metadata.json
```

### Citation

Kurtz, N., & Harbeck, J. (2017). *CryoSat-2 Level-4 Sea Ice Elevation, Freeboard, and Thickness* (RDEFT4, Version 1). NASA National Snow and Ice Data Center Distributed Active Archive Center.

DOI: **10.5067/96JO0KIFDAS8**

NSIDC requires citation of the dataset when it is used.

The source dataset is not relicensed under the CLEM MIT License.

---

## ICESat-2 Sea Ice Thickness

**Dataset:** ICESat-2 L4 Monthly Gridded Sea Ice Thickness  
**Product ID:** IS2SITMOGR4  
**Version used by CLEM:** Version 4  
**Provider:** NASA National Snow and Ice Data Center Distributed Active Archive Center  
**Use in CLEM:** Satellite-derived Arctic sea-ice thickness constraint

CLEM contains processed monthly values and an observation operator:

```text
data/validation/sea_ice_physical/icesat2_is2sitmogr4_monthly.csv
data/validation/sea_ice_physical/icesat2_is2sitmogr4_operator.npz
data/validation/sea_ice_physical/icesat2_is2sitmogr4_v4_metadata.json
```

### Citation

Petty, A. A., Kurtz, N. T., Kwok, R., Markus, T., Neumann, T. A., Keeney, N., & Cabaj, A. (2025). *ICESat-2 L4 Monthly Gridded Sea Ice Thickness* (IS2SITMOGR4, Version 4). NASA National Snow and Ice Data Center Distributed Active Archive Center.

DOI: **10.5067/TXDHDJ1JT0CG**

NASA/NSIDC DAAC data are openly available for scientific use, with dataset citation requested/required according to the product documentation.

The source dataset is not relicensed under the CLEM MIT License.

---

## NSIDC EASE-Grid Sea Ice Age

**Dataset:** EASE-Grid Sea Ice Age  
**Product ID:** NSIDC-0611  
**Version used by CLEM:** Version 4 (annual source files revision v4.1)  
**Provider:** NASA National Snow and Ice Data Center Distributed Active Archive Center  
**Subset used by CLEM:** Northern Hemisphere, 1984-2024  
**Use in CLEM:** Structural diagnostic of multiyear Arctic sea ice  
**Licence metadata:** U.S. Government Works (as listed by the NASA Open Data Portal)

CLEM redistributes processed March and September multiyear-sea-ice fractions and provenance metadata, not the original NSIDC NetCDF archive:

```text
data/validation/sea_ice_structural/nsidc_0611_v4/multiyear_ice_annual.csv
data/validation/sea_ice_structural/nsidc_0611_v4/METADATA.json
data/validation/sea_ice_structural/nsidc_0611_v4/README.md
```

The diagnostic uses NSIDC sea-ice-age categories to estimate the fraction of valid sea-ice cells classified as multiyear ice. The comparison is structural rather than a direct model-observation RMSE target.

### Citation

Tschudi, M., Meier, W. N., Stewart, J. S., Fowler, C., & Maslanik, J. (2019). *EASE-Grid Sea Ice Age* (NSIDC-0611, Version 4). NASA National Snow and Ice Data Center Distributed Active Archive Center.

DOI: **10.5067/UTAV7490FEPB**

NSIDC states that citation of this dataset is required when the data are used. The NASA Open Data Portal lists NSIDC-0611 as public and identifies its licence field as **U.S. Government Works**.

The original NSIDC-0611 NetCDF files are not included in the CLEM release package. The processed CLEM-derived products retain dataset identification, temporal coverage, processing details, and SHA-256 provenance for all 41 annual source files in `METADATA.json`.

NSIDC-0611 data and derived products are not relicensed under the CLEM MIT License.

---

## NOAA Optimum Interpolation Sea Surface Temperature

**Dataset:** NOAA 0.25-degree Daily Optimum Interpolation Sea Surface Temperature  
**Version:** 2.1  
**Provider:** NOAA National Centers for Environmental Information (NCEI)  
**Use in CLEM:** Arctic open-water / sea-surface-temperature validation benchmarks

CLEM does **not redistribute the original OISST NetCDF source files**.

The repository contains processed benchmarks and provenance information generated from the official NOAA source data:

```text
data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json
data/validation/open_water/OISST_SOURCE_ACQUISITION.md
```

### Dataset citation

Huang, B., Liu, C., Banzon, V. F., Freeman, E., Graham, G., Hankins, W., Smith, T. M., & Zhang, H.-M. (2020). *NOAA 0.25-degree Daily Optimum Interpolation Sea Surface Temperature (OISST), Version 2.1*. NOAA National Centers for Environmental Information.

DOI: **10.25921/RE9P-PT57**

NOAA/NCEI requests citation of the dataset when it is used.

The NOAA source data are not relicensed under CLEM's MIT License.

---

## RCMIP Scenario Data

**Dataset:** Reduced Complexity Model Intercomparison Project (RCMIP) protocol input data  
**Version used by CLEM:** 5.1.0  
**Use in CLEM:** SSP emissions, concentrations and/or radiative-forcing scenario pathways

CLEM contains a processed scenario pathway file:

```text
data/ssp_pathways_rcmip_v5_1_0.csv
```

The original RCMIP v5.1.0 protocol includes annual emissions, concentrations, and radiative-forcing pathways.

### Citations

Nicholls, Z. R. J., Meinshausen, M., Lewis, J., et al. (2020). *Reduced Complexity Model Intercomparison Project Phase 1: introduction and evaluation of global-mean temperature response*. Geoscientific Model Development, 13, 5175-5190.

DOI: **10.5194/gmd-13-5175-2020**

RCMIP protocol archive:

Nicholls, Z., & Lewis, J. *Reduced Complexity Model Intercomparison Project (RCMIP) protocol*, version 5.1.0.

DOI: **10.5281/zenodo.4589756**

RCMIP Phase 1 input and output data are distributed under the **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** licence.

Material derived from those data therefore remains subject to the applicable RCMIP attribution and share-alike terms and is not relicensed solely under CLEM's MIT License.

---

## Processed and Derived Data

Several files distributed with CLEM are not verbatim copies of upstream datasets. They may contain:

- temporal averages;
- spatial subsets;
- fixed-mask area calculations;
- model-observation operators;
- derived volume or thickness diagnostics;
- interpolated values;
- reduced benchmark tables;
- metadata and cryptographic source hashes.

Processing third-party data does not remove the original provider's rights or attribution requirements.

Where a CLEM-generated file is derived substantially from a third-party dataset, users should retain the corresponding attribution when redistributing that file.

---

## CLEM Licence Boundary

The repository's `LICENSE` file applies to:

- CLEM model source code;
- CLEM-specific scripts;
- CLEM documentation written for the project;
- original CLEM model configuration and analysis code.

It does **not automatically apply** to:

- HadCRUT5;
- NSIDC datasets;
- NASA Earthdata products;
- EUMETSAT OSI SAF products;
- PIOMAS;
- NOAA OISST;
- RCMIP data;
- other externally sourced scientific datasets.

Each third-party dataset remains subject to its own terms.

---

## Attribution and Corrections

Every effort has been made to preserve dataset provenance and the citation requirements supplied by the original providers.

If an attribution, dataset version, citation, or licence statement in this file is incomplete or incorrect, please open an issue so that it can be corrected.

This file documents CLEM's use of third-party scientific data; it does not grant additional rights to those datasets.