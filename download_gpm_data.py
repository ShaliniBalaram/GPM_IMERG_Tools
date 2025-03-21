#!/usr/bin/env python3
"""
download_gpm_data.py

This script downloads GPM IMERG data from NASA's servers for a specified date range.
It generates URLs for the specified timeframe and downloads the corresponding HDF5 files.

Author: Cascade
Date: March 21, 2025
"""

import os
import requests
import argparse
from datetime import datetime, timedelta
import time
import logging

def setup_logging(log_dir="logs"):
    """Configure logging to both console and file"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"gpm_download_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def generate_dates(start_date, end_date):
    """Generate list of dates between start and end date (inclusive)"""
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    return dates

def generate_half_hourly_urls(date):
    """Generate URLs for half-hourly GPM IMERG data for a given date"""
    base_url = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGHH.07"
    urls = []
    
    year = date.strftime("%Y")
    month = date.strftime("%m")
    day = date.strftime("%d")
    
    # Half-hourly files are produced every 30 minutes
    # File naming convention: 3B-HHR.MS.MRG.3IMERG.YYYYMMDD-S000000-E002959.0000.V07B.HDF5
    for hour in range(24):
        for half_hour in range(0, 60, 30):
            start_hour = hour
            start_min = half_hour
            end_hour = hour
            end_min = half_hour + 29
            
            # Handle end minute/hour overlap
            if end_min >= 60:
                end_min -= 60
                end_hour += 1
            
            # Handle day overlap (rare case for the last file of the day)
            if end_hour >= 24:
                end_hour -= 24
            
            # For the index part of the filename (based on half-hour count)
            index = (hour * 2) + (1 if half_hour == 30 else 0)
            index_str = f"{index:04d}"
            
            # Construct the filename
            filename = (f"3B-HHR.MS.MRG.3IMERG.{year}{month}{day}-"
                      f"S{start_hour:02d}{start_min:02d}00-"
                      f"E{end_hour:02d}{end_min:02d}59.{index_str}.V07B.HDF5")
            
            # Construct the URL
            url = f"{base_url}/{year}/{month}/{day}/{filename}"
            urls.append(url)
    
    return urls

def generate_monthly_urls(start_date, end_date):
    """Generate URLs for monthly GPM IMERG data between start and end dates"""
    base_url = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGM.07"
    urls = []
    
    # Start from the first day of the start_date's month
    current_month = datetime(start_date.year, start_date.month, 1)
    
    # Loop until we reach the month after end_date
    while current_month <= end_date:
        year = current_month.strftime("%Y")
        month = current_month.strftime("%m")
        
        # File naming convention: 3B-MO.MS.MRG.3IMERG.YYYYMMDD-S000000-E235959.MM.V07B.HDF5
        filename = f"3B-MO.MS.MRG.3IMERG.{year}{month}01-S000000-E235959.{month}.V07B.HDF5"
        
        # Construct the URL
        url = f"{base_url}/{year}/{month}/{filename}"
        urls.append(url)
        
        # Move to the next month
        if current_month.month == 12:
            current_month = datetime(current_month.year + 1, 1, 1)
        else:
            current_month = datetime(current_month.year, current_month.month + 1, 1)
    
    return urls

def write_urls_to_file(urls, output_file):
    """Write list of URLs to a text file"""
    with open(output_file, 'w') as f:
        for url in urls:
            f.write(f"{url}\n")
    return output_file

def download_file(url, download_dir, username, password, logger, max_retries=3):
    """Download a file from a URL with credentials and retry logic"""
    file_name = os.path.basename(url)
    download_path = os.path.join(download_dir, file_name)
    
    # Check if file already exists
    if os.path.exists(download_path):
        logger.info(f"{file_name} already exists; skipping download.")
        return True, download_path
    
    # Try to download with retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {file_name} (Attempt {attempt+1}/{max_retries})...")
            response = requests.get(url, auth=(username, password), timeout=300)
            
            if response.status_code == 200:
                with open(download_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Successfully downloaded {file_name}")
                return True, download_path
            else:
                logger.warning(f"Failed to download {file_name}. Status code: {response.status_code}")
                time.sleep(5)  # Wait before retrying
        except Exception as e:
            logger.error(f"Error downloading {file_name}: {e}")
            time.sleep(5)  # Wait before retrying
    
    logger.error(f"All attempts to download {file_name} failed.")
    return False, None

def download_from_url_list(url_file, download_dir, username, password, logger):
    """Download all files specified in a URL list file"""
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)
    
    # Read the URL list
    with open(url_file, "r") as file:
        urls = [line.strip() for line in file if line.strip()]
    
    logger.info(f"Found {len(urls)} URLs to process in {url_file}")
    
    # Keep track of successful and failed downloads
    successful = 0
    failed = 0
    failed_urls = []
    
    # Download each file
    start_time = time.time()
    for i, url in enumerate(urls):
        success, _ = download_file(url, download_dir, username, password, logger)
        
        if success:
            successful += 1
        else:
            failed += 1
            failed_urls.append(url)
        
        # Print progress every 10 files or at the end
        if (i+1) % 10 == 0 or i+1 == len(urls):
            elapsed = time.time() - start_time
            files_per_min = (i+1) / (elapsed / 60) if elapsed > 0 else 0
            logger.info(f"Progress: {i+1}/{len(urls)} files processed. "
                       f"Speed: {files_per_min:.1f} files/min. "
                       f"Success: {successful}, Failed: {failed}")
    
    # Write failed URLs to a file for later retry
    if failed_urls:
        failed_file = os.path.join(os.path.dirname(url_file), f"failed_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(failed_file, "w") as f:
            for url in failed_urls:
                f.write(f"{url}\n")
        logger.info(f"Wrote {len(failed_urls)} failed URLs to {failed_file}")
    
    # Final summary
    elapsed_total = (time.time() - start_time) / 60  # minutes
    logger.info(f"Download complete. Downloaded {successful}/{len(urls)} files in {elapsed_total:.1f} minutes.")
    
    return successful, failed

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Download GPM IMERG data for a specified date range")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--username", required=True, help="NASA Earthdata username")
    parser.add_argument("--password", required=True, help="NASA Earthdata password")
    parser.add_argument("--download-dir", default="GPM_IMERG_Data", help="Directory to store downloaded files")
    parser.add_argument("--url-file", default="gpm_urls.txt", help="File to save generated URLs")
    parser.add_argument("--include-monthly", action="store_true", help="Include monthly files")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    try:
        # Parse dates
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
        
        logger.info(f"Generating URLs for date range: {start_date.date()} to {end_date.date()}")
        
        # Generate list of dates
        dates = generate_dates(start_date, end_date)
        
        # Generate URLs for each date
        all_urls = []
        for date in dates:
            urls = generate_half_hourly_urls(date)
            all_urls.extend(urls)
            logger.info(f"Generated {len(urls)} URLs for {date.date()}")
        
        # Add monthly files if requested
        if args.include_monthly:
            monthly_urls = generate_monthly_urls(start_date, end_date)
            all_urls.extend(monthly_urls)
            logger.info(f"Added {len(monthly_urls)} monthly URLs")
        
        logger.info(f"Total URLs generated: {len(all_urls)}")
        
        # Write URLs to file
        url_file = write_urls_to_file(all_urls, args.url_file)
        logger.info(f"Wrote URLs to {url_file}")
        
        # Download files
        successful, failed = download_from_url_list(url_file, args.download_dir, args.username, args.password, logger)
        
        # Summary
        logger.info("Download Summary:")
        logger.info(f"  Date Range: {start_date.date()} to {end_date.date()}")
        logger.info(f"  Total Files: {len(all_urls)}")
        logger.info(f"  Successfully Downloaded: {successful}")
        logger.info(f"  Failed Downloads: {failed}")
        logger.info(f"  Download Directory: {os.path.abspath(args.download_dir)}")
    
    except Exception as e:
        logger.error(f"Error in main execution: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
