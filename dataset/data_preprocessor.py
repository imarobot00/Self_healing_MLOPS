#!/usr/bin/env python3
"""
Data Preprocessing Module for Air Quality Analysis

Aligns multiple parameters by timestamp and creates a unified dataset
with format: Time | AQI | PM2.5 | PM1 | Humidity | Temperature | um003

Author: Bipul Kumar Dahal
Date: December 14, 2025
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from analytics import AirQualityAnalytics
except ImportError:
    print("Warning: analytics.py not found. AQI calculation will be skipped.")
    AirQualityAnalytics = None


class AirQualityPreprocessor:
    """
    Preprocesses air quality data by aligning all parameters to common timestamps.
    Creates a unified dataset suitable for multi-parameter analysis and ML models.
    """
    
    def __init__(self, data_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        """
        Initialize the preprocessor.
        
        Args:
            data_dir: Directory containing location JSON files
            output_dir: Directory to save processed files (default: data_dir/preprocessed/)
        """
        self.data_dir = data_dir or Path(__file__).parent
        self.output_dir = output_dir or (self.data_dir / "preprocessed")
        self.output_dir.mkdir(exist_ok=True)
        
        # Location names mapping
        self.location_names = {
            5506835: "US Embassy",
            5509787: "Ratna Park",
            6093549: "Golfutar",
            6093550: "Bouddha",
            6093551: "Kirtipur",
            6133623: "Thamel",
            6142022: "Patan",
            6142174: "Ranibari",
            6142175: "Bhaktapur"
        }
    
    def load_location_data(self, location_id: int) -> pd.DataFrame:
        """
        Load data for a specific location and parse into DataFrame.
        
        Args:
            location_id: Location identifier
            
        Returns:
            DataFrame with columns: location_id, datetime_local, parameter, value
        """
        file_path = self.data_dir / f"location_{location_id}.json"
        
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            return pd.DataFrame()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract relevant fields
            records = []
            for record in data:
                records.append({
                    'location_id': location_id,
                    'location_name': self.location_names.get(location_id, f"Location {location_id}"),
                    'datetime_local': record['period']['datetimeFrom']['local'],
                    'datetime_utc': record['period']['datetimeFrom']['utc'],
                    'parameter': record['parameter']['name'],
                    'value': record['value'],
                    'units': record['parameter']['units']
                })
            
            df = pd.DataFrame(records)
            
            # Convert datetime strings to datetime objects
            df['datetime_local'] = pd.to_datetime(df['datetime_local'])
            df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return pd.DataFrame()
    
    def align_by_timestamp(self, df: pd.DataFrame, freq: str = 'H') -> pd.DataFrame:
        """
        Align all parameters by common timestamps (hourly by default).
        
        Args:
            df: DataFrame with datetime_local, parameter, value columns
            freq: Frequency for alignment ('H' for hourly, '15T' for 15-min, etc.)
            
        Returns:
            DataFrame with columns: datetime, pm25, pm1, temperature, relativehumidity, um003
        """
        if df.empty:
            return pd.DataFrame()
        
        # Round timestamps to nearest hour (or specified frequency)
        df['time_rounded'] = df['datetime_local'].dt.floor(freq)
        
        # Pivot to get parameters as columns
        pivot_df = df.pivot_table(
            index='time_rounded',
            columns='parameter',
            values='value',
            aggfunc='mean'  # Average if multiple readings in same hour
        ).reset_index()
        
        # Rename for clarity
        pivot_df = pivot_df.rename(columns={'time_rounded': 'datetime'})
        
        # Ensure all expected columns exist (fill with NaN if missing)
        expected_params = ['pm25', 'pm1', 'temperature', 'relativehumidity', 'um003', 'o3']
        for param in expected_params:
            if param not in pivot_df.columns:
                pivot_df[param] = np.nan
        
        # Reorder columns
        available_cols = ['datetime'] + [col for col in expected_params if col in pivot_df.columns]
        pivot_df = pivot_df[available_cols]
        
        # Sort by datetime
        pivot_df = pivot_df.sort_values('datetime').reset_index(drop=True)
        
        return pivot_df
    
    def calculate_aqi_for_aligned_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate AQI values for the aligned dataset.
        
        Args:
            df: DataFrame with aligned parameters
            
        Returns:
            DataFrame with added AQI column
        """
        if df.empty or AirQualityAnalytics is None:
            df['aqi'] = np.nan
            return df
        
        # Import AQI calculation functions from analytics
        try:
            from analytics import calculate_aqi_pm25, calculate_aqi_o3
            
            aqi_values = []
            for _, row in df.iterrows():
                # Calculate AQI for each pollutant
                aqi_pm25 = calculate_aqi_pm25(row.get('pm25', np.nan)) if pd.notna(row.get('pm25')) else np.nan
                aqi_o3 = calculate_aqi_o3(row.get('o3', np.nan)) if pd.notna(row.get('o3')) else np.nan
                
                # Overall AQI is the maximum
                valid_aqis = [x for x in [aqi_pm25, aqi_o3] if pd.notna(x)]
                overall_aqi = max(valid_aqis) if valid_aqis else np.nan
                
                aqi_values.append(overall_aqi)
            
            df.insert(1, 'aqi', aqi_values)  # Insert AQI as second column
            
        except Exception as e:
            print(f"⚠️  Could not calculate AQI: {e}")
            df['aqi'] = np.nan
        
        return df
    
    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add useful time-based features for analysis.
        
        Args:
            df: DataFrame with datetime column
            
        Returns:
            DataFrame with added time features
        """
        if df.empty or 'datetime' not in df.columns:
            return df
        
        df['hour'] = df['datetime'].dt.hour
        df['day'] = df['datetime'].dt.day
        df['month'] = df['datetime'].dt.month
        df['day_of_week'] = df['datetime'].dt.dayofweek
        df['day_name'] = df['datetime'].dt.day_name()
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Categorize time of day
        def categorize_hour(hour):
            if 6 <= hour < 12:
                return 'Morning'
            elif 12 <= hour < 18:
                return 'Afternoon'
            elif 18 <= hour < 22:
                return 'Evening'
            else:
                return 'Night'
        
        df['time_of_day'] = df['hour'].apply(categorize_hour)
        
        return df
    
    def process_location(self, location_id: int, include_aqi: bool = True, 
                        include_time_features: bool = True) -> pd.DataFrame:
        """
        Complete preprocessing pipeline for a single location.
        
        Args:
            location_id: Location identifier
            include_aqi: Whether to calculate AQI values
            include_time_features: Whether to add time-based features
            
        Returns:
            Preprocessed DataFrame
        """
        print(f"\n{'='*70}")
        print(f"Processing Location {location_id}: {self.location_names.get(location_id, 'Unknown')}")
        print(f"{'='*70}")
        
        # Load raw data
        df = self.load_location_data(location_id)
        if df.empty:
            print("❌ No data found")
            return pd.DataFrame()
        
        print(f"✓ Loaded {len(df)} raw records")
        
        # Align by timestamp
        aligned_df = self.align_by_timestamp(df, freq='H')
        print(f"✓ Aligned to {len(aligned_df)} hourly records")
        
        # Calculate AQI
        if include_aqi:
            aligned_df = self.calculate_aqi_for_aligned_data(aligned_df)
            aqi_count = aligned_df['aqi'].notna().sum()
            print(f"✓ Calculated AQI for {aqi_count} records")
        
        # Add time features
        if include_time_features:
            aligned_df = self.add_time_features(aligned_df)
            print(f"✓ Added time-based features")
        
        # Add location info
        aligned_df.insert(0, 'location_id', location_id)
        aligned_df.insert(1, 'location_name', self.location_names.get(location_id, f"Location {location_id}"))
        
        # Show data quality
        total_cells = len(aligned_df) * len(aligned_df.columns)
        missing_cells = aligned_df.isna().sum().sum()
        completeness = ((total_cells - missing_cells) / total_cells) * 100
        print(f"✓ Data completeness: {completeness:.1f}%")
        
        return aligned_df
    
    def process_all_locations(self, location_ids: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Process all locations and combine into a single dataset.
        
        Args:
            location_ids: List of location IDs to process (default: all known locations)
            
        Returns:
            Combined DataFrame for all locations
        """
        if location_ids is None:
            location_ids = list(self.location_names.keys())
        
        all_data = []
        
        for location_id in location_ids:
            df = self.process_location(location_id)
            if not df.empty:
                all_data.append(df)
        
        if not all_data:
            print("\n❌ No data processed")
            return pd.DataFrame()
        
        # Combine all locations
        combined_df = pd.concat(all_data, ignore_index=True)
        
        print(f"\n{'='*70}")
        print(f"COMBINED DATASET SUMMARY")
        print(f"{'='*70}")
        print(f"Total Records: {len(combined_df):,}")
        print(f"Locations: {combined_df['location_id'].nunique()}")
        print(f"Date Range: {combined_df['datetime'].min()} to {combined_df['datetime'].max()}")
        print(f"Parameters: {', '.join([col for col in combined_df.columns if col not in ['location_id', 'location_name', 'datetime', 'hour', 'day', 'month', 'day_of_week', 'day_name', 'is_weekend', 'time_of_day']])}")
        
        return combined_df
    
    def save_to_csv(self, df: pd.DataFrame, filename: str = "aligned_data.csv"):
        """
        Save processed data to CSV file.
        
        Args:
            df: DataFrame to save
            filename: Output filename
        """
        if df.empty:
            print("⚠️  No data to save")
            return
        
        output_path = self.output_dir / filename
        df.to_csv(output_path, index=False)
        print(f"\n✓ Saved to: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    def save_to_excel(self, df: pd.DataFrame, filename: str = "aligned_data.xlsx"):
        """
        Save processed data to Excel file with multiple sheets.
        
        Args:
            df: DataFrame to save
            filename: Output filename
        """
        if df.empty:
            print("⚠️  No data to save")
            return
        
        output_path = self.output_dir / filename
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # All data
            df.to_excel(writer, sheet_name='All Data', index=False)
            
            # Summary by location
            if 'location_name' in df.columns:
                summary = df.groupby('location_name').agg({
                    'aqi': ['mean', 'min', 'max'],
                    'pm25': ['mean', 'min', 'max'],
                    'pm1': ['mean', 'min', 'max'],
                    'temperature': ['mean', 'min', 'max'],
                    'relativehumidity': ['mean', 'min', 'max']
                }).round(2)
                summary.to_excel(writer, sheet_name='Summary by Location')
            
            # Hourly averages
            if 'hour' in df.columns:
                hourly_avg = df.groupby('hour')[['aqi', 'pm25', 'pm1', 'temperature', 'relativehumidity']].mean().round(2)
                hourly_avg.to_excel(writer, sheet_name='Hourly Averages')
        
        print(f"\n✓ Saved to: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    def get_sample_data(self, df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        """
        Get a sample of the processed data for inspection.
        
        Args:
            df: DataFrame to sample from
            n: Number of rows to return
            
        Returns:
            Sample DataFrame
        """
        if df.empty:
            return df
        
        # Get evenly spaced samples
        indices = np.linspace(0, len(df) - 1, n, dtype=int)
        return df.iloc[indices]


def main():
    """Main execution function with example usage."""
    
    print("="*70)
    print("AIR QUALITY DATA PREPROCESSOR")
    print("Aligning parameters by timestamp for multi-parameter analysis")
    print("="*70)
    
    # Initialize preprocessor
    preprocessor = AirQualityPreprocessor()
    
    # Process all locations
    combined_df = preprocessor.process_all_locations()
    
    if not combined_df.empty:
        # Display sample
        print("\n" + "="*70)
        print("SAMPLE DATA (First 10 records)")
        print("="*70)
        sample = combined_df.head(10)
        
        # Select key columns for display
        display_cols = ['datetime', 'location_name', 'aqi', 'pm25', 'pm1', 'temperature', 'relativehumidity', 'um003']
        display_cols = [col for col in display_cols if col in sample.columns]
        
        print(sample[display_cols].to_string(index=False))
        
        # Save outputs
        preprocessor.save_to_csv(combined_df, "aligned_all_locations.csv")
        preprocessor.save_to_excel(combined_df, "aligned_all_locations.xlsx")
        
        # Process individual locations
        print("\n" + "="*70)
        print("SAVING INDIVIDUAL LOCATION FILES")
        print("="*70)
        
        for location_id in combined_df['location_id'].unique():
            location_df = combined_df[combined_df['location_id'] == location_id].copy()
            location_name = preprocessor.location_names.get(location_id, f"location_{location_id}")
            filename = f"aligned_{location_name.lower().replace(' ', '_')}.csv"
            preprocessor.save_to_csv(location_df, filename)
        
        print("\n" + "="*70)
        print("✅ PREPROCESSING COMPLETE!")
        print("="*70)
        print(f"Output directory: {preprocessor.output_dir}")
        print(f"Files generated: {len(list(preprocessor.output_dir.glob('*')))}")


if __name__ == "__main__":
    main()
