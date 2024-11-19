This folder contains the data associated with this code. It is excluded from the Git repository because it is large. The data is available for download from the eAtlas nextcloud service. See [`split-land-shapefile.py`](../README.md#split-land-shapefile-py)

# Expected directory structure after restoring data

- data/
    - Aus-Coastline-50k_2024/ (Download from https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Australian-Coastline-50K-2024)
        - V1/
        - V1-1/
            - Full/
                - AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1.shp
            - Simp/
                - AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_simp.shp
            - Split/
                - AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp
                - AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split_lines.shp
    - geoTiffs/ (Download using src/download-aims-s2.py)
        - 15th_percentile/
            - NorthernAU/
            - GBR/
        - low_tide_infrared/
            - NorthernAU/
            - GBR/
        - low_tide_true_colour/
            - NorthernAU/
            - GBR/

