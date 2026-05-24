#!/usr/bin/env python3
"""
analyze_gpm_data.py

This script analyzes and visualizes GPM IMERG data that has been subset to a specific region.
It creates visualizations of precipitation data and saves results in timestamped folders.

Date: March 21, 2025
"""

import os
import glob
import argparse
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import re
from datetime import datetime
import time
import logging

def setup_logging(log_dir="logs"):
    """Configure logging to both console and file"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"gpm_analysis_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def create_results_folder(base_dir="analysis_results"):
    """Create a timestamped folder structure for analysis results"""
    # Create base results directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # Create a timestamp-based folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(base_dir, f"gpm_analysis_{timestamp}")
    
    # Create subfolders for different plot types
    single_event_dir = os.path.join(results_dir, "single_events")
    comparison_dir = os.path.join(results_dir, "comparisons")
    
    os.makedirs(results_dir)
    os.makedirs(single_event_dir)
    os.makedirs(comparison_dir)
    
    return {
        'main': results_dir,
        'single_events': single_event_dir,
        'comparisons': comparison_dir
    }

def extract_date_from_filename(filename):
    """Extract date from IMERG filename format"""
    # Half-hourly file format: 3B-HHR.MS.MRG.3IMERG.20230101-S000000-E002959.0000.V07B_subset.nc
    match = re.search(r'\.(\d{8})-S(\d{6})', filename)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        return datetime.strptime(f"{date_str} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}", 
                               "%Y%m%d %H:%M:%S")
    
    # Monthly file format: 3B-MO.MS.MRG.3IMERG.20230101-S000000-E235959.01.V07B_subset.nc
    match = re.search(r'\.(\d{8})-S000000-E235959\.(\d{2})\.', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, "%Y%m%d")
    
    return None

def find_files_with_precipitation(directory, num_samples=50, threshold=0.1, logger=None):
    """Find files that contain precipitation above threshold"""
    all_files = glob.glob(os.path.join(directory, "*.nc"))
    
    if logger:
        logger.info(f"Found {len(all_files)} NetCDF files in {directory}")
    
    # If there are too many files, take a sample
    if len(all_files) > num_samples:
        sample_indices = np.linspace(0, len(all_files) - 1, num_samples, dtype=int)
        sample_files = [all_files[i] for i in sample_indices]
    else:
        sample_files = all_files
    
    if logger:
        logger.info(f"Scanning {len(sample_files)} files for precipitation data...")
    
    files_with_precip = []
    
    for i, file_path in enumerate(sample_files):
        if i % 10 == 0 and logger:
            logger.info(f"  Progress: {i}/{len(sample_files)}")
        
        try:
            ds = xr.open_dataset(file_path)
            if 'precipitation' in ds:
                max_precip = float(ds['precipitation'].max())
                if max_precip > threshold:
                    files_with_precip.append((file_path, max_precip))
            ds.close()
        except Exception as e:
            if logger:
                logger.error(f"Error reading {os.path.basename(file_path)}: {e}")
    
    # Sort by precipitation amount (highest first)
    files_with_precip.sort(key=lambda x: x[1], reverse=True)
    
    if logger:
        logger.info(f"Found {len(files_with_precip)} files with precipitation > {threshold} mm/hr")
    
    return files_with_precip

def analyze_file(file_path, logger=None):
    """Analyze a single NetCDF file and return dataset"""
    filename = os.path.basename(file_path)
    
    if logger:
        logger.info(f"Analyzing file: {filename}")
    
    # Extract date from filename
    date_time = extract_date_from_filename(filename)
    if date_time and logger:
        logger.info(f"Timestamp: {date_time}")
    
    # Open the NetCDF file using xarray
    ds = xr.open_dataset(file_path)
    
    # Basic statistics for the precipitation variable
    if 'precipitation' in ds:
        precip = ds['precipitation']
        
        if logger:
            logger.info("\nPrecipitation Statistics:")
            logger.info(f"  Min: {float(precip.min().values):.4f} mm/hr")
            logger.info(f"  Max: {float(precip.max().values):.4f} mm/hr")
            logger.info(f"  Mean: {float(precip.mean().values):.4f} mm/hr")
            
            if np.any(precip.values > 0):
                non_zero_median = float(np.median(precip.values[precip.values > 0]))
                logger.info(f"  Median of non-zero values: {non_zero_median:.4f} mm/hr")
            else:
                logger.info("  Median of non-zero values: N/A")
            
            non_zero_count = np.sum(precip.values > 0)
            non_zero_pct = non_zero_count/precip.size*100
            logger.info(f"  Non-zero cells: {non_zero_count}/{precip.size} ({non_zero_pct:.1f}%)")
    
    return ds

def visualize_precipitation(ds, file_path, save_dir, logger=None):
    """Create visualizations for precipitation data"""
    filename = os.path.basename(file_path)
    
    if 'precipitation' not in ds:
        if logger:
            logger.warning("No precipitation variable found in dataset.")
        return None
    
    precip = ds['precipitation']
    
    # Get the first time slice (since time dimension is 1)
    precip_data = precip.isel(time=0)
    
    # Create a plot
    plt.figure(figsize=(12, 8))
    
    # Plot the precipitation data as a heatmap
    im = plt.pcolormesh(precip_data.lon, precip_data.lat, precip_data.T, 
                       cmap='Blues', shading='auto', vmin=0)
    cbar = plt.colorbar(im, label='Precipitation (mm/hr)')
    
    # Extract timestamp from filename for title
    date_time = extract_date_from_filename(filename)
    if date_time:
        plt.title(f"GPM IMERG Precipitation - {date_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        plt.title(f"GPM IMERG Precipitation - {filename}")
    
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Save the figure
    output_filename = f"precip_{os.path.splitext(filename)[0]}.png"
    output_path = os.path.join(save_dir, output_filename)
    plt.savefig(output_path)
    
    if logger:
        logger.info(f"Plot saved as '{output_path}'")
    
    plt.close()
    
    # Also create a high-resolution version
    plt.figure(figsize=(16, 12), dpi=300)
    im = plt.pcolormesh(precip_data.lon, precip_data.lat, precip_data.T, 
                       cmap='Blues', shading='auto', vmin=0)
    cbar = plt.colorbar(im, label='Precipitation (mm/hr)')
    
    if date_time:
        plt.title(f"GPM IMERG Precipitation - {date_time.strftime('%Y-%m-%d %H:%M:%S')} UTC (High Resolution)")
    else:
        plt.title(f"GPM IMERG Precipitation - {filename} (High Resolution)")
    
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.grid(True, linestyle='--', alpha=0.6)
    
    output_filename = f"precip_{os.path.splitext(filename)[0]}_hires.png"
    output_path = os.path.join(save_dir, output_filename)
    plt.savefig(output_path)
    
    if logger:
        logger.info(f"High-resolution plot saved as '{output_path}'")
    
    plt.close()
    
    return output_path

def compare_multiple_files(files_list, save_dir, max_files=3, logger=None):
    """Compare multiple precipitation files"""
    # Limit to max_files
    files_to_compare = files_list[:min(max_files, len(files_list))]
    
    if logger:
        logger.info(f"Comparing {len(files_to_compare)} files with highest precipitation:")
    
    # Create a multi-panel figure
    fig, axes = plt.subplots(1, len(files_to_compare), figsize=(6*len(files_to_compare), 6))
    if len(files_to_compare) == 1:
        axes = [axes]
    
    max_precip = 0.0
    
    # First pass to find the maximum precipitation value across all files
    for file_info in files_to_compare:
        file_path, _ = file_info
        ds = xr.open_dataset(file_path)
        if 'precipitation' in ds:
            precip = ds['precipitation'].isel(time=0)
            file_max = float(precip.max())
            max_precip = max(max_precip, file_max)
        ds.close()
    
    # Second pass to create the plots
    for i, (file_path, _) in enumerate(files_to_compare):
        filename = os.path.basename(file_path)
        date_time = extract_date_from_filename(filename)
        
        ds = xr.open_dataset(file_path)
        precip = ds['precipitation'].isel(time=0)
        
        # Plot on the corresponding axis
        im = axes[i].pcolormesh(precip.lon, precip.lat, precip.T, 
                              cmap='Blues', shading='auto', vmin=0, vmax=max_precip)
        
        if date_time:
            axes[i].set_title(f"{date_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            axes[i].set_title(f"{filename}")
        
        axes[i].set_xlabel('Longitude')
        if i == 0:
            axes[i].set_ylabel('Latitude')
        
        axes[i].grid(True, linestyle='--', alpha=0.6)
        ds.close()
    
    # Add a colorbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(im, cax=cbar_ax, label='Precipitation (mm/hr)')
    
    # Set an overall title
    fig.suptitle("GPM IMERG Precipitation Comparison", fontsize=16, y=0.98)
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 0.9, 0.95])
    
    # Save the figure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"precipitation_comparison_{timestamp}.png"
    output_path = os.path.join(save_dir, output_filename)
    plt.savefig(output_path)
    
    if logger:
        logger.info(f"Comparison plot saved as '{output_path}'")
    
    plt.close()
    
    # Also create a high-resolution version
    fig, axes = plt.subplots(1, len(files_to_compare), figsize=(6*len(files_to_compare), 6), dpi=300)
    if len(files_to_compare) == 1:
        axes = [axes]
    
    for i, (file_path, _) in enumerate(files_to_compare):
        filename = os.path.basename(file_path)
        date_time = extract_date_from_filename(filename)
        
        ds = xr.open_dataset(file_path)
        precip = ds['precipitation'].isel(time=0)
        
        im = axes[i].pcolormesh(precip.lon, precip.lat, precip.T, 
                              cmap='Blues', shading='auto', vmin=0, vmax=max_precip)
        
        if date_time:
            axes[i].set_title(f"{date_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            axes[i].set_title(f"{filename}")
        
        axes[i].set_xlabel('Longitude')
        if i == 0:
            axes[i].set_ylabel('Latitude')
        
        axes[i].grid(True, linestyle='--', alpha=0.6)
        ds.close()
    
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(im, cax=cbar_ax, label='Precipitation (mm/hr)')
    fig.suptitle("GPM IMERG Precipitation Comparison (High Resolution)", fontsize=16, y=0.98)
    plt.tight_layout(rect=[0, 0, 0.9, 0.95])
    
    output_filename = f"precipitation_comparison_{timestamp}_hires.png"
    output_path = os.path.join(save_dir, output_filename)
    plt.savefig(output_path)
    
    if logger:
        logger.info(f"High-resolution comparison plot saved as '{output_path}'")
    
    plt.close()
    
    return output_path

def create_summary_file(files_with_precip, results_dir, logger=None):
    """Create a summary text file of the analysis results"""
    summary_file = os.path.join(results_dir, "analysis_summary.txt")
    
    with open(summary_file, "w") as f:
        f.write("GPM IMERG Precipitation Analysis Summary\n")
        f.write("=======================================\n\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Files Analyzed: {len(files_with_precip)}\n\n")
        
        f.write("Top Precipitation Events:\n")
        f.write("------------------------\n")
        
        for i, (file_path, max_precip) in enumerate(files_with_precip[:10]):
            filename = os.path.basename(file_path)
            date_time = extract_date_from_filename(filename)
            
            if date_time:
                date_str = date_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                date_str = "Unknown"
            
            f.write(f"{i+1}. {date_str}: {max_precip:.4f} mm/hr ({filename})\n")
    
    if logger:
        logger.info(f"Summary file created: {summary_file}")
    
    return summary_file

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Analyze and visualize GPM IMERG subset data")
    parser.add_argument("--input-dir", required=True, help="Directory containing subset NetCDF files")
    parser.add_argument("--results-dir", default="analysis_results", help="Base directory for results")
    parser.add_argument("--num-samples", type=int, default=100, help="Number of files to sample (default: 100)")
    parser.add_argument("--threshold", type=float, default=0.1, help="Min precipitation threshold (mm/hr) (default: 0.1)")
    parser.add_argument("--top-events", type=int, default=5, help="Number of top precipitation events to analyze (default: 5)")
    parser.add_argument("--comparison-count", type=int, default=3, help="Number of events to include in comparison plots (default: 3)")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    try:
        # Validate input directory
        if not os.path.isdir(args.input_dir):
            logger.error(f"Input directory does not exist: {args.input_dir}")
            return 1
        
        logger.info(f"Starting GPM IMERG data analysis from {args.input_dir}")
        
        # Create results folders (timestamped)
        results_folders = create_results_folder(args.results_dir)
        logger.info(f"Created results folders at: {results_folders['main']}")
        
        # Find files with precipitation above threshold
        files_with_precip = find_files_with_precipitation(
            args.input_dir, 
            num_samples=args.num_samples,
            threshold=args.threshold,
            logger=logger
        )
        
        if not files_with_precip:
            logger.warning(f"No files found with precipitation above {args.threshold} mm/hr")
            return 0
        
        # Analyze and visualize top precipitation events
        top_events = files_with_precip[:args.top_events]
        logger.info(f"Analyzing top {len(top_events)} precipitation events")
        
        for file_path, max_precip in top_events:
            # Analyze file and get dataset
            ds = analyze_file(file_path, logger)
            
            # Create visualizations
            visualize_precipitation(ds, file_path, results_folders['single_events'], logger)
            
            # Close dataset
            ds.close()
        
        # Create comparison plot of top events
        compare_multiple_files(
            files_with_precip, 
            results_folders['comparisons'],
            max_files=args.comparison_count,
            logger=logger
        )
        
        # Create a summary file
        create_summary_file(files_with_precip, results_folders['main'], logger)
        
        # Final summary
        logger.info("\nAnalysis Complete:")
        logger.info(f"  Files Analyzed: {len(files_with_precip)} (from {args.num_samples} sampled)")
        logger.info(f"  Top Events Visualized: {len(top_events)}")
        logger.info(f"  Results Directory: {results_folders['main']}")
    
    except Exception as e:
        logger.error(f"Error in main execution: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
