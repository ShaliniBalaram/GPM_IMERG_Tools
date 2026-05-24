#!/usr/bin/env python3
"""
subset_gpm_data.py

This script spatially subsets (clips) GPM IMERG data using a shapefile.
It processes HDF5 files to extract precipitation data for a specific region
and saves the results as NetCDF files.

Date: March 21, 2025
"""

import os
import glob
import argparse
import xarray as xr
import rioxarray
import geopandas as gpd
from datetime import datetime
import time
import logging

def setup_logging(log_dir="logs"):
    """Configure logging to both console and file"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"gpm_subset_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_shapefile(shapefile_path, logger):
    """Load and validate a shapefile to use for subsetting"""
    logger.info(f"Reading shapefile: {shapefile_path}")
    try:
        gdf = gpd.read_file(shapefile_path)
        
        # Ensure the shapefile is in WGS84 (EPSG:4326) coordinate system
        if gdf.crs is None or gdf.crs.to_string() != "EPSG:4326":
            logger.info("Converting shapefile to WGS84 (EPSG:4326) coordinate system")
            gdf = gdf.to_crs("EPSG:4326")
        
        logger.info(f"Shapefile loaded. Bounding box: {gdf.total_bounds}")
        return gdf
    except Exception as e:
        logger.error(f"Error loading shapefile: {e}")
        raise

def list_hdf5_files(input_dir, pattern="*.HDF5", logger=None):
    """Find all HDF5 files in the input directory matching the pattern"""
    file_pattern = os.path.join(input_dir, pattern)
    hdf5_files = glob.glob(file_pattern)
    
    if logger:
        logger.info(f"Found {len(hdf5_files)} HDF5 files matching pattern '{pattern}' in {input_dir}")
    
    return hdf5_files

def find_existing_subsets(output_dir, logger=None):
    """Find all existing NetCDF subset files to avoid duplicate processing"""
    nc_files = glob.glob(os.path.join(output_dir, "*.nc"))
    
    # Create a set of original filenames (convert from subset filename back to original)
    existing_subsets = set(os.path.basename(f).replace("_subset.nc", ".HDF5") 
                          for f in nc_files)
    
    if logger:
        logger.info(f"Found {len(existing_subsets)} existing subset files in {output_dir}")
    
    return existing_subsets

def subset_file(file_path, shapefile_gdf, output_dir, logger):
    """
    Process a single HDF5 file:
    1. Open it with xarray
    2. Set spatial dimensions
    3. Clip using the shapefile geometry
    4. Save the clipped data as NetCDF
    """
    file_name = os.path.basename(file_path)
    subset_file_name = file_name.replace(".HDF5", "_subset.nc")
    subset_path = os.path.join(output_dir, subset_file_name)
    
    logger.info(f"Processing {file_name} ...")
    
    try:
        # Open the HDF5 file with xarray, specifying the group path
        # GPM IMERG files have data in the 'Grid' group
        ds = xr.open_dataset(file_path, group="Grid", engine="h5netcdf", decode_times=False)
        
        # Log dataset information
        logger.debug(f"Dataset dimensions: {ds.dims}")
        logger.debug(f"Dataset coordinates: {list(ds.coords)}")
        logger.debug(f"Dataset data variables: {list(ds.data_vars)}")
        
        # Make sure the dataset has spatial coordinates
        if 'lon' in ds.coords and 'lat' in ds.coords:
            # Set the spatial dimensions explicitly
            ds = ds.rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=False)
            
            # Write CRS if not already defined; GPM IMERG data is in WGS84 (EPSG:4326)
            ds = ds.rio.write_crs("EPSG:4326", inplace=False)
            
            logger.debug(f"Set spatial dimensions: x=lon, y=lat for {file_name}")
        else:
            # If coordinates are not found, log what's available
            logger.error(f"Could not identify lon and lat coordinates in {file_name}")
            logger.error(f"Available dimensions: {list(ds.dims)}")
            logger.error(f"Available coordinates: {list(ds.coords)}")
            ds.close()
            return False
        
        # Spatially subset (clip) the data using the shapefile geometry
        try:
            # Focus on key precipitation variables for subsetting
            if 'precipitation' in ds.data_vars:
                # Subset only the precipitation variable to reduce processing time
                ds_precip = ds[['precipitation']].rio.clip(
                    shapefile_gdf.geometry, shapefile_gdf.crs, drop=True, invert=False
                )
                logger.debug(f"Successfully clipped precipitation data for {file_name}")
                
                # Use the clipped precipitation as our subset dataset
                ds_subset = ds_precip
            else:
                logger.warning(f"'precipitation' variable not found in {file_name}.")
                logger.warning(f"Available variables: {list(ds.data_vars)}")
                # Try to clip the entire dataset if precipitation variable is not found
                ds_subset = ds.rio.clip(
                    shapefile_gdf.geometry, shapefile_gdf.crs, drop=True, invert=False
                )
        except Exception as e:
            logger.error(f"Error clipping {file_name}: {e}")
            ds.close()
            return False
        
        # Save the subset (clipped) data to a new NetCDF file
        ds_subset.to_netcdf(subset_path)
        logger.info(f"Saved subset file: {subset_file_name}")
        
        # Close the dataset
        ds.close()
        return True
        
    except Exception as e:
        logger.error(f"Error processing {file_name}: {e}")
        return False

def process_files(file_list, existing_subsets, shapefile_gdf, output_dir, logger, max_files=None):
    """Process multiple HDF5 files, skipping those that already have subsets"""
    # Limit the number of files to process if specified
    if max_files and max_files > 0:
        file_list = file_list[:max_files]
        logger.info(f"Processing limited to first {max_files} files")
    
    # Track progress and timing
    processed_count = 0
    success_count = 0
    failure_count = 0
    start_time = time.time()
    total_files = len(file_list)
    
    for i, file_path in enumerate(file_list):
        file_name = os.path.basename(file_path)
        
        # Skip if subset already exists
        if file_name in existing_subsets:
            logger.info(f"Skipping {file_name} - subset already exists.")
            continue
        
        # Process the file
        success = subset_file(file_path, shapefile_gdf, output_dir, logger)
        processed_count += 1
        
        if success:
            success_count += 1
        else:
            failure_count += 1
        
        # Print progress every 10 files or at the end
        if (i+1) % 10 == 0 or i+1 == total_files:
            elapsed = time.time() - start_time
            files_per_min = processed_count / (elapsed / 60) if elapsed > 0 else 0
            
            # Estimate remaining time
            if processed_count > 0 and i+1 < total_files:
                remaining_files = total_files - (i+1)
                est_remaining = (elapsed / processed_count) * remaining_files / 60  # minutes
                time_msg = f", Est. remaining time: {est_remaining:.1f} minutes"
            else:
                time_msg = ""
            
            logger.info(f"Progress: {i+1}/{total_files} files ({processed_count} processed). "
                       f"Speed: {files_per_min:.1f} files/min{time_msg}")
    
    # Final summary
    elapsed_total = (time.time() - start_time) / 60  # minutes
    logger.info(f"Processing complete. Processed {processed_count} files in {elapsed_total:.1f} minutes.")
    logger.info(f"Success: {success_count}, Failed: {failure_count}")
    
    return processed_count, success_count, failure_count

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Subset GPM IMERG data using a shapefile")
    parser.add_argument("--input-dir", required=True, help="Directory containing HDF5 files")
    parser.add_argument("--output-dir", required=True, help="Directory to save subset NetCDF files")
    parser.add_argument("--shapefile", required=True, help="Path to shapefile for subsetting")
    parser.add_argument("--pattern", default="*.HDF5", help="File pattern to match (default: *.HDF5)")
    parser.add_argument("--max-files", type=int, help="Maximum number of files to process (for testing)")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    try:
        # Validate input directory
        if not os.path.isdir(args.input_dir):
            logger.error(f"Input directory does not exist: {args.input_dir}")
            return 1
        
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Load the shapefile
        shapefile_gdf = load_shapefile(args.shapefile, logger)
        
        # Find HDF5 files to process
        hdf5_files = list_hdf5_files(args.input_dir, args.pattern, logger)
        
        if not hdf5_files:
            logger.warning(f"No files found matching pattern '{args.pattern}' in {args.input_dir}")
            return 0
        
        # Find existing subsets to avoid duplicate processing
        existing_subsets = find_existing_subsets(args.output_dir, logger)
        
        # Process the files
        processed, success, failed = process_files(
            hdf5_files, existing_subsets, shapefile_gdf, 
            args.output_dir, logger, args.max_files
        )
        
        # Final summary
        logger.info("Subsetting Summary:")
        logger.info(f"  Input Directory: {args.input_dir}")
        logger.info(f"  Output Directory: {args.output_dir}")
        logger.info(f"  Shapefile: {args.shapefile}")
        logger.info(f"  Total Files Found: {len(hdf5_files)}")
        logger.info(f"  Files Already Processed: {len(existing_subsets)}")
        logger.info(f"  Files Processed This Run: {processed}")
        logger.info(f"  Successfully Processed: {success}")
        logger.info(f"  Failed to Process: {failed}")
    
    except Exception as e:
        logger.error(f"Error in main execution: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
