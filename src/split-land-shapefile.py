import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import os

"""
This script splits the original coastline dataset into a 2 degree grid. This helps to
improve rendering speed as it splits the enormous mainland polygon into many smaller
polygons. This allows the rendering to quickly exclude polygons that are not within
view. The downside is that rendering with a stroke will result in the land be covered
in a grid pattern. To compensate for this we also create a line feature that corresponds
to the coastline, then we cut the line into 2 deg segments. A full render can be made
by rendering the polygons as fill and the split lines as the stroke.

This script also generates a simplified version of the coastline for use in applications
where the full dataset causes a problem, such as Google Earth Engine.
"""

# Paths to input and output shapefiles
VERSION = 'V1-1'
BASE_PATH = f'../data/Aus-Coastline-50k_2024/{VERSION}'
input_shapefile = f'{BASE_PATH}/Full/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_{VERSION}.shp'
out_polygon_shapefile = f'{BASE_PATH}/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_{VERSION}_split.shp'
out_line_shapefile = f'{BASE_PATH}/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_{VERSION}_split_lines.shp'
out_simp_shapefile = f'{BASE_PATH}/Simp/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_{VERSION}_simp.shp'

def ensure_directory_exists(filepath):
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

# Define a function to create a grid over the bounding box of the large polygon
def create_grid(bounds, cell_size):
    min_x, min_y, max_x, max_y = bounds
    x_coords = np.arange(min_x, max_x, cell_size)
    y_coords = np.arange(min_y, max_y, cell_size)

    grid_polygons = []
    for x in x_coords:
        for y in y_coords:
            grid_polygons.append(Polygon([(x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)]))

    return gpd.GeoDataFrame(geometry=grid_polygons, crs=gdf.crs)
    
print("Loading coastline shapefile")
gdf = gpd.read_file(input_shapefile)

# Set the grid size (units of the projection which in this case is degrees)
cell_size = 2  

# Create the grid over the extent of the large polygons
print("Creating grid")
grid = create_grid(gdf.total_bounds, cell_size)


# Perform the intersection between the grid and your large polygons
print("Performing polygon intersection")
split_polygons = gpd.overlay(gdf, grid, how="intersection")

ensure_directory_exists(out_polygon_shapefile)

# Save the split polygons to a new shapefile or GeoJSON
print("Saving split polygon shapefile")
split_polygons.to_file(out_polygon_shapefile)


# Convert polygons to lines
print("Converting polygons to lines")
gdf_lines = gdf.copy()
gdf_lines['geometry'] = gdf_lines.boundary

# Perform the intersection between the grid and the line features
print("Performing line intersection")
split_lines = gpd.overlay(gdf_lines, grid, how="intersection")

ensure_directory_exists(out_line_shapefile)

# Save the split lines to a new shapefile
print("Saving split line shapefile")
split_lines.to_file(out_line_shapefile)


# Simplify the polygons
print("Simplifying polygons")
simplified_gdf = gdf.copy()
simplification_tolerance = 0.00007  # Simplification tolerance in degrees
simplified_gdf['geometry'] = simplified_gdf['geometry'].simplify(tolerance=simplification_tolerance, preserve_topology=True)

ensure_directory_exists(out_simp_shapefile)

# Save the simplified polygons to a new shapefile
print("Saving simplified polygon shapefile")
simplified_gdf.to_file(out_simp_shapefile)

print("Process completed!")
