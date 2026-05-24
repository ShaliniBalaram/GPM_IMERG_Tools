# GPM IMERG Tools

A collection of Python tools for downloading, subsetting, and analyzing GPM IMERG precipitation data.

## Overview

This repository contains tools to:

1. **Download GPM IMERG data** from NASA servers for a specific date range
2. **Subset the data** using a shapefile to focus on a specific geographical area
3. **Analyze and visualize** the precipitation data, with results organized in timestamped folders

## Requirements

- Python 3.7 or higher
- NASA Earthdata login credentials ([Register here](https://urs.earthdata.nasa.gov/))
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/ShaliniBalaram/GPM_IMERG_Tools.git
   cd GPM_IMERG_Tools
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

The workflow consists of three main steps:

### 1. Download GPM IMERG Data

Use `download_gpm_data.py` to download GPM IMERG data for a specified date range from NASA servers.

```bash
python download_gpm_data.py \
  --start-date 2023-01-01 \
  --end-date 2023-01-31 \
  --username "$NASA_EARTHDATA_USERNAME" \
  --password "$NASA_EARTHDATA_PASSWORD" \
  --download-dir "GPM_IMERG_Data" \
  --include-monthly
```

**Required arguments:**
- `--start-date`: Start date (YYYY-MM-DD)
- `--end-date`: End date (YYYY-MM-DD)
- `--username`: NASA Earthdata username, preferably supplied from an environment variable
- `--password`: NASA Earthdata password, preferably supplied from an environment variable

**Optional arguments:**
- `--download-dir`: Directory to store downloaded files (default: "GPM_IMERG_Data")
- `--url-file`: File to save generated URLs (default: "gpm_urls.txt")
- `--include-monthly`: Include monthly files in addition to half-hourly files

### 2. Subset GPM IMERG Data

Use `subset_gpm_data.py` to spatially subset the downloaded data using a shapefile.

```bash
python subset_gpm_data.py \
  --input-dir "GPM_IMERG_Data" \
  --output-dir "GPM_IMERG_Subset" \
  --shapefile "path/to/your/shapefile.shp"
```

**Required arguments:**
- `--input-dir`: Directory containing downloaded HDF5 files
- `--output-dir`: Directory to save subset NetCDF files
- `--shapefile`: Path to shapefile for subsetting

**Optional arguments:**
- `--pattern`: File pattern to match (default: "*.HDF5")
- `--max-files`: Maximum number of files to process (for testing)

### 3. Analyze GPM IMERG Data

Use `analyze_gpm_data.py` to analyze and visualize the subset data.

```bash
python analyze_gpm_data.py \
  --input-dir "GPM_IMERG_Subset" \
  --results-dir "Analysis_Results" \
  --num-samples 100 \
  --threshold 0.5 \
  --top-events 5
```

**Required arguments:**
- `--input-dir`: Directory containing subset NetCDF files

**Optional arguments:**
- `--results-dir`: Base directory for results (default: "analysis_results")
- `--num-samples`: Number of files to sample (default: 100)
- `--threshold`: Minimum precipitation threshold in mm/hr (default: 0.1)
- `--top-events`: Number of top precipitation events to analyze (default: 5)
- `--comparison-count`: Number of events to include in comparison plots (default: 3)

## Results Organization

The analysis results are organized in timestamped folders with the following structure:

```
analysis_results/
└── gpm_analysis_YYYYMMDD_HHMMSS/
    ├── analysis_summary.txt
    ├── single_events/
    │   ├── precip_3B-HHR.MS.MRG.3IMERG.YYYYMMDD-SHHMMSS-EHHMMSS.XXXX.V07B_subset.png
    │   └── precip_3B-HHR.MS.MRG.3IMERG.YYYYMMDD-SHHMMSS-EHHMMSS.XXXX.V07B_subset_hires.png
    └── comparisons/
        ├── precipitation_comparison_YYYYMMDD_HHMMSS.png
        └── precipitation_comparison_YYYYMMDD_HHMMSS_hires.png
```

This organized structure helps keep track of different analysis runs and their outputs.

## Data Format

### Input Data

- **GPM IMERG HDF5 Files**: The original data downloaded from NASA servers
  - Format: `3B-HHR.MS.MRG.3IMERG.YYYYMMDD-SHHMMSS-EHHMMSS.XXXX.V07B.HDF5`
  - Available at: [NASA GES DISC](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary)

### Output Data

- **Subset NetCDF Files**: Spatially clipped precipitation data for the specific region
  - Format: `3B-HHR.MS.MRG.3IMERG.YYYYMMDD-SHHMMSS-EHHMMSS.XXXX.V07B_subset.nc`

### Visualization Outputs

- Standard and high-resolution precipitation maps
- Comparison plots of top precipitation events
- Summary text file with key statistics

## Example Shapefile

To use these tools, you'll need a shapefile defining your area of interest. The shapefile should:

- Be in WGS84 (EPSG:4326) coordinate system, or the script will attempt to convert it
- Define the boundary of the area you want to extract precipitation data for
- Include all required shapefile components (.shp, .shx, .dbf, etc.)

## Logging

All scripts include detailed logging that is saved to a timestamped log file in the `logs` directory.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [NASA GES DISC](https://disc.gsfc.nasa.gov/) for providing the GPM IMERG data
- The [GPM mission](https://gpm.nasa.gov/) for producing high-quality precipitation measurements
