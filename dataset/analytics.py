#!/usr/bin/env python3
"""
Air Quality Data Analytics
Analyzes parameter values across different Kathmandu locations using:
- Histograms (distribution of values)
- Scatter plots (relationships between parameters)
- Line graphs (time series trends)
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import numpy as np
from typing import List, Dict
import warnings
warnings.filterwarnings('ignore')

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (15, 10)
plt.rcParams['font.size'] = 10


def calculate_aqi_pm25(pm25):
    """Calculate AQI from PM2.5 concentration (µg/m³) using EPA standard"""
    if pd.isna(pm25) or pm25 < 0:
        return np.nan
    
    # EPA AQI breakpoints for PM2.5 (24-hour)
    breakpoints = [
        (0.0, 12.0, 0, 50),      # Good
        (12.1, 35.4, 51, 100),   # Moderate
        (35.5, 55.4, 101, 150),  # Unhealthy for Sensitive Groups
        (55.5, 150.4, 151, 200), # Unhealthy
        (150.5, 250.4, 201, 300),# Very Unhealthy
        (250.5, 500.4, 301, 500) # Hazardous
    ]
    
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= pm25 <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
            return round(aqi)
    
    # If above 500.4
    if pm25 > 500.4:
        return 500
    
    return np.nan


def calculate_aqi_pm10(pm10):
    """Calculate AQI from PM10 concentration (µg/m³) using EPA standard"""
    if pd.isna(pm10) or pm10 < 0:
        return np.nan
    
    # EPA AQI breakpoints for PM10 (24-hour)
    breakpoints = [
        (0, 54, 0, 50),          # Good
        (55, 154, 51, 100),      # Moderate
        (155, 254, 101, 150),    # Unhealthy for Sensitive Groups
        (255, 354, 151, 200),    # Unhealthy
        (355, 424, 201, 300),    # Very Unhealthy
        (425, 604, 301, 500)     # Hazardous
    ]
    
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= pm10 <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm10 - c_low) + i_low
            return round(aqi)
    
    if pm10 > 604:
        return 500
    
    return np.nan


def calculate_aqi_o3(o3_ppm):
    """Calculate AQI from O3 concentration (ppm) using EPA standard"""
    if pd.isna(o3_ppm) or o3_ppm < 0:
        return np.nan
    
    # EPA AQI breakpoints for O3 (8-hour, ppm)
    breakpoints = [
        (0.000, 0.054, 0, 50),     # Good
        (0.055, 0.070, 51, 100),   # Moderate
        (0.071, 0.085, 101, 150),  # Unhealthy for Sensitive Groups
        (0.086, 0.105, 151, 200),  # Unhealthy
        (0.106, 0.200, 201, 300)   # Very Unhealthy
    ]
    
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= o3_ppm <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (o3_ppm - c_low) + i_low
            return round(aqi)
    
    if o3_ppm > 0.200:
        return 300
    
    return np.nan


def get_aqi_category(aqi):
    """Get AQI category and color"""
    if pd.isna(aqi):
        return 'Unknown', 'gray'
    elif aqi <= 50:
        return 'Good', 'green'
    elif aqi <= 100:
        return 'Moderate', 'yellow'
    elif aqi <= 150:
        return 'Unhealthy for Sensitive Groups', 'orange'
    elif aqi <= 200:
        return 'Unhealthy', 'red'
    elif aqi <= 300:
        return 'Very Unhealthy', 'purple'
    else:
        return 'Hazardous', 'maroon'


class AirQualityAnalytics:
    """Analyzes air quality data from multiple locations"""
    
    def __init__(self, data_dir: Path = None):
        """Initialize analytics with data directory"""
        self.data_dir = data_dir or Path(__file__).parent
        self.location_files = list(self.data_dir.glob("location_*.json"))
        self.df = None
        
        # Create analytics output folder
        self.output_dir = self.data_dir / "analytics_output"
        self.output_dir.mkdir(exist_ok=True)
        
        self.location_names = {
            6142174: "Ranibari (SC-43 GD Labs)",
            6093549: "Golfutar",
            6093550: "Location 6093550",
            6093551: "Location 6093551",
            6142022: "Location 6142022",
            6142175: "Location 6142175",
            6133623: "Location 6133623",
            5506835: "Location 5506835",
            5509787: "Location 5509787",
            3459: "Location 3459"
        }
        
    def load_data(self) -> pd.DataFrame:
        """Load all location JSON files into a single DataFrame"""
        print("📊 Loading data from all location files...")
        all_data = []
        
        for file_path in self.location_files:
            location_id = int(file_path.stem.split('_')[1])
            
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                print(f"  ✓ Loaded {len(data):,} records from {file_path.name}")
                
                for record in data:
                    all_data.append({
                        'location_id': location_id,
                        'location_name': self.location_names.get(location_id, f"Location {location_id}"),
                        'parameter': record['parameter']['name'],
                        'value': record['value'],
                        'units': record['parameter']['units'],
                        'datetime_utc': record['period']['datetimeFrom']['utc'],
                        'datetime_local': record['period']['datetimeFrom']['local']
                    })
                    
            except Exception as e:
                print(f"  ✗ Error loading {file_path.name}: {e}")
                
        self.df = pd.DataFrame(all_data)
        
        # Filter out location 3459
        records_before = len(self.df)
        self.df = self.df[self.df['location_id'] != 3459]
        records_after = len(self.df)
        print(f"\n🚫 Filtered out location 3459: {records_before - records_after:,} records removed")
        
        # Convert datetime strings to datetime objects
        self.df['datetime_utc'] = pd.to_datetime(self.df['datetime_utc'])
        self.df['datetime_local'] = pd.to_datetime(self.df['datetime_local'])
        
        # Add time-based features
        self.df['date'] = self.df['datetime_local'].dt.date
        self.df['hour'] = self.df['datetime_local'].dt.hour
        self.df['day_of_week'] = self.df['datetime_local'].dt.day_name()
        
        print(f"\n✅ Total records loaded: {len(self.df):,}")
        print(f"📍 Locations: {self.df['location_id'].nunique()}")
        print(f"📏 Parameters: {', '.join(self.df['parameter'].unique())}")
        print(f"📅 Date range: {self.df['datetime_local'].min()} to {self.df['datetime_local'].max()}")
        
        # Calculate AQI values
        print("\n🔢 Calculating AQI values...")
        self._calculate_aqi()
        
        return self.df
    
    def _calculate_aqi(self):
        """Calculate AQI values from available parameters"""
        # Create pivot to get parameters as columns
        pivot_df = self.df.pivot_table(
            index=['location_id', 'datetime_utc', 'datetime_local'],
            columns='parameter',
            values='value',
            aggfunc='first'
        ).reset_index()
        
        # Calculate AQI for each pollutant
        if 'pm25' in pivot_df.columns:
            pivot_df['aqi_pm25'] = pivot_df['pm25'].apply(calculate_aqi_pm25)
        
        if 'o3' in pivot_df.columns:
            pivot_df['aqi_o3'] = pivot_df['o3'].apply(calculate_aqi_o3)
        
        # Calculate overall AQI (maximum of all pollutant AQIs)
        aqi_cols = [col for col in pivot_df.columns if col.startswith('aqi_')]
        if aqi_cols:
            pivot_df['aqi_overall'] = pivot_df[aqi_cols].max(axis=1)
            pivot_df['aqi_category'] = pivot_df['aqi_overall'].apply(lambda x: get_aqi_category(x)[0])
            pivot_df['aqi_color'] = pivot_df['aqi_overall'].apply(lambda x: get_aqi_category(x)[1])
        
        # Store AQI data
        self.aqi_df = pivot_df
        
        aqi_count = pivot_df['aqi_overall'].notna().sum() if 'aqi_overall' in pivot_df.columns else 0
        print(f"  ✓ Calculated {aqi_count:,} AQI values")
        
        if 'aqi_overall' in pivot_df.columns:
            avg_aqi = pivot_df['aqi_overall'].mean()
            max_aqi = pivot_df['aqi_overall'].max()
            print(f"  📊 Average AQI: {avg_aqi:.1f}")
            print(f"  ⚠️  Maximum AQI: {max_aqi:.0f}")
    
    def generate_histograms(self):
        """Generate separate histogram for each parameter"""
        print("\n📊 Generating histograms (separate files)...")
        
        parameters = self.df['parameter'].unique()
        
        for param in parameters:
            param_data = self.df[self.df['parameter'] == param]
            units = param_data['units'].iloc[0]
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            ax.hist(param_data['value'], bins=50, color='steelblue', alpha=0.7, edgecolor='black')
            ax.set_xlabel(f'{param} ({units})', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title(f'Distribution of {param.upper()} Values', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Add statistics text box
            stats_text = f'Count: {len(param_data):,}\nMean: {param_data["value"].mean():.2f}\nMedian: {param_data["value"].median():.2f}\nStd: {param_data["value"].std():.2f}'
            ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
                   verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            plt.tight_layout()
            filename = f"histogram_{param}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
        
    def generate_scatter_plots(self):
        """Generate separate scatter plot for each parameter pair"""
        print("\n📊 Generating scatter plots (separate files)...")
        
        # Create pivot table with parameters as columns
        pivot_df = self.df.pivot_table(
            index=['location_id', 'datetime_utc'],
            columns='parameter',
            values='value',
            aggfunc='mean'
        ).reset_index()
        
        # Common parameter pairs to compare
        param_pairs = [
            ('pm25', 'pm1'),
            ('pm25', 'temperature'),
            ('relativehumidity', 'temperature'),
            ('pm25', 'relativehumidity'),
            ('pm1', 'temperature'),
            ('pm1', 'relativehumidity')
        ]
        
        # Filter pairs that exist in data
        valid_pairs = [(p1, p2) for p1, p2 in param_pairs 
                       if p1 in pivot_df.columns and p2 in pivot_df.columns]
        
        if not valid_pairs:
            print("  ⚠ Not enough parameters for scatter plots")
            return
        
        for param1, param2 in valid_pairs:
            # Remove NaN values
            plot_data = pivot_df[[param1, param2]].dropna()
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            ax.scatter(plot_data[param1], plot_data[param2], 
                      alpha=0.5, c='steelblue', s=30)
            ax.set_xlabel(param1.upper(), fontsize=12)
            ax.set_ylabel(param2.upper(), fontsize=12)
            ax.set_title(f'{param1.upper()} vs {param2.upper()}', 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Add correlation coefficient
            corr = plot_data[param1].corr(plot_data[param2])
            ax.text(0.05, 0.95, f'Correlation: {corr:.3f}\nSamples: {len(plot_data):,}',
                   transform=ax.transAxes,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.3))
            
            plt.tight_layout()
            filename = f"scatter_{param1}_vs_{param2}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
        
    def generate_timeseries_by_parameter(self):
        """Generate separate time series for each parameter across all locations"""
        print("\n📊 Generating time series by parameter (separate files)...")
        
        parameters = self.df['parameter'].unique()
        
        for param in parameters:
            param_data = self.df[self.df['parameter'] == param].copy()
            units = param_data['units'].iloc[0]
            
            fig, ax = plt.subplots(figsize=(16, 8))
            
            for location_id in sorted(param_data['location_id'].unique()):
                loc_data = param_data[param_data['location_id'] == location_id].sort_values('datetime_local')
                location_name = self.location_names.get(location_id, f"Loc {location_id}")
                
                ax.plot(loc_data['datetime_local'], loc_data['value'], 
                       label=location_name, linewidth=1.5, alpha=0.7)
            
            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel(f'{param.upper()} ({units})', fontsize=12)
            ax.set_title(f'{param.upper()} Over Time - All Locations', 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.tick_params(axis='x', rotation=45)
            
            # Add WHO guideline for PM2.5
            if param == 'pm25':
                ax.axhline(y=15, color='red', linestyle='--', linewidth=2, 
                          label='WHO 24h Guideline (15 µg/m³)', alpha=0.7)
            
            plt.tight_layout()
            filename = f"timeseries_{param}_all_locations.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
    
    def generate_timeseries_by_location(self):
        """Generate separate time series for each location showing all parameters"""
        print("\n📊 Generating time series by location (separate files)...")
        
        locations = sorted(self.df['location_id'].unique())
        
        for location_id in locations:
            location_name = self.location_names.get(location_id, f"Location {location_id}")
            loc_data = self.df[self.df['location_id'] == location_id]
            
            parameters = loc_data['parameter'].unique()
            n_params = len(parameters)
            
            fig, axes = plt.subplots(n_params, 1, figsize=(16, 4 * n_params))
            if n_params == 1:
                axes = [axes]
            
            for idx, param in enumerate(parameters):
                param_data = loc_data[loc_data['parameter'] == param].sort_values('datetime_local')
                units = param_data['units'].iloc[0]
                
                axes[idx].plot(param_data['datetime_local'], param_data['value'],
                             color='steelblue', linewidth=1.5, alpha=0.7)
                axes[idx].set_ylabel(f'{param.upper()} ({units})', fontsize=11)
                axes[idx].set_title(f'{param.upper()} Time Series', fontsize=12, fontweight='bold')
                axes[idx].grid(True, alpha=0.3)
                axes[idx].tick_params(axis='x', rotation=45)
                
                # Add WHO guideline for PM2.5
                if param == 'pm25':
                    axes[idx].axhline(y=15, color='red', linestyle='--', linewidth=1.5, 
                                    label='WHO 24h Guideline', alpha=0.7)
                    axes[idx].legend(loc='upper right')
            
            fig.suptitle(f'{location_name} - All Parameters', fontsize=16, fontweight='bold', y=0.995)
            plt.tight_layout()
            
            filename = f"timeseries_location_{location_id}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
            
    def generate_parameter_change_over_time(self):
        """Generate daily/hourly average trends for each parameter"""
        print("\n📊 Generating parameter change over time (daily averages)...")
        
        parameters = self.df['parameter'].unique()
        
        for param in parameters:
            param_data = self.df[self.df['parameter'] == param].copy()
            units = param_data['units'].iloc[0]
            
            # Calculate daily averages
            param_data['date'] = param_data['datetime_local'].dt.date
            daily_avg = param_data.groupby(['location_id', 'date'])['value'].mean().reset_index()
            daily_avg['date'] = pd.to_datetime(daily_avg['date'])
            
            fig, ax = plt.subplots(figsize=(16, 8))
            
            for location_id in sorted(daily_avg['location_id'].unique()):
                loc_data = daily_avg[daily_avg['location_id'] == location_id].sort_values('date')
                location_name = self.location_names.get(location_id, f"Loc {location_id}")
                
                ax.plot(loc_data['date'], loc_data['value'], 
                       label=location_name, linewidth=2, alpha=0.8, marker='o', markersize=3)
            
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel(f'{param.upper()} Daily Average ({units})', fontsize=12)
            ax.set_title(f'{param.upper()} - Daily Average Trend', 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            filename = f"trend_daily_{param}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
    
    def generate_distribution_over_time(self):
        """Generate box plots showing distribution of parameter values over time periods"""
        print("\n📊 Generating distribution over time (box plots)...")
        
        parameters = self.df['parameter'].unique()
        
        for param in parameters:
            param_data = self.df[self.df['parameter'] == param].copy()
            units = param_data['units'].iloc[0]
            
            # Create time periods (weekly or monthly based on data range)
            date_range = (param_data['datetime_local'].max() - param_data['datetime_local'].min()).days
            
            if date_range > 365:
                # Use monthly periods for longer time ranges
                param_data['time_period'] = param_data['datetime_local'].dt.to_period('M').astype(str)
                period_label = "Month"
            elif date_range > 60:
                # Use weekly periods for medium time ranges
                param_data['time_period'] = param_data['datetime_local'].dt.to_period('W').astype(str)
                period_label = "Week"
            else:
                # Use daily periods for short time ranges
                param_data['time_period'] = param_data['datetime_local'].dt.date.astype(str)
                period_label = "Day"
            
            # Get unique time periods and limit to avoid overcrowding
            unique_periods = sorted(param_data['time_period'].unique())
            
            # If too many periods, sample them
            if len(unique_periods) > 30:
                step = len(unique_periods) // 30
                selected_periods = unique_periods[::step]
                param_data = param_data[param_data['time_period'].isin(selected_periods)]
                unique_periods = selected_periods
            
            fig, ax = plt.subplots(figsize=(18, 8))
            
            # Create box plot
            box_data = [param_data[param_data['time_period'] == period]['value'].values 
                       for period in unique_periods]
            
            bp = ax.boxplot(box_data, labels=unique_periods, patch_artist=True,
                           showfliers=True, widths=0.6)
            
            # Customize box plot colors
            for patch in bp['boxes']:
                patch.set_facecolor('lightblue')
                patch.set_alpha(0.7)
            
            for whisker in bp['whiskers']:
                whisker.set(color='#8B8B8B', linewidth=1.5)
            
            for cap in bp['caps']:
                cap.set(color='#8B8B8B', linewidth=1.5)
            
            for median in bp['medians']:
                median.set(color='red', linewidth=2)
            
            ax.set_xlabel(period_label, fontsize=12)
            ax.set_ylabel(f'{param.upper()} ({units})', fontsize=12)
            ax.set_title(f'{param.upper()} - Distribution Over Time', 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            ax.tick_params(axis='x', rotation=45)
            
            # Add WHO guideline for PM2.5
            if param == 'pm25':
                ax.axhline(y=15, color='red', linestyle='--', linewidth=2, 
                          label='WHO 24h Guideline (15 µg/m³)', alpha=0.5)
                ax.legend(loc='upper right')
            
            plt.tight_layout()
            filename = f"distribution_over_time_{param}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
    
    def generate_violin_distribution_over_time(self):
        """Generate violin plots showing distribution of parameter values over time"""
        print("\n📊 Generating violin distribution over time...")
        
        parameters = self.df['parameter'].unique()
        
        for param in parameters:
            param_data = self.df[self.df['parameter'] == param].copy()
            units = param_data['units'].iloc[0]
            
            # Create time periods
            date_range = (param_data['datetime_local'].max() - param_data['datetime_local'].min()).days
            
            if date_range > 365:
                param_data['time_period'] = param_data['datetime_local'].dt.to_period('M').astype(str)
                period_label = "Month"
            elif date_range > 60:
                param_data['time_period'] = param_data['datetime_local'].dt.to_period('W').astype(str)
                period_label = "Week"
            else:
                param_data['time_period'] = param_data['datetime_local'].dt.date.astype(str)
                period_label = "Day"
            
            # Limit periods for visualization
            unique_periods = sorted(param_data['time_period'].unique())
            if len(unique_periods) > 20:
                step = len(unique_periods) // 20
                selected_periods = unique_periods[::step]
                param_data = param_data[param_data['time_period'].isin(selected_periods)]
            
            fig, ax = plt.subplots(figsize=(18, 8))
            
            # Create violin plot
            sns.violinplot(data=param_data, x='time_period', y='value', 
                          ax=ax, color='lightblue', inner='quartile')
            
            ax.set_xlabel(period_label, fontsize=12)
            ax.set_ylabel(f'{param.upper()} ({units})', fontsize=12)
            ax.set_title(f'{param.upper()} - Violin Distribution Over Time', 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            ax.tick_params(axis='x', rotation=45)
            
            # Add WHO guideline for PM2.5
            if param == 'pm25':
                ax.axhline(y=15, color='red', linestyle='--', linewidth=2, 
                          label='WHO 24h Guideline (15 µg/m³)', alpha=0.5)
                ax.legend(loc='upper right')
            
            plt.tight_layout()
            filename = f"violin_distribution_{param}.png"
            plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {filename}")
            plt.close()
    
    def generate_aqi_visualizations(self):
        """Generate comprehensive AQI visualizations"""
        if not hasattr(self, 'aqi_df') or 'aqi_overall' not in self.aqi_df.columns:
            print("\n⚠️  No AQI data available. Skipping AQI visualizations.")
            return
        
        print("\n📊 Generating AQI visualizations...")
        
        # 1. AQI Time Series by Location
        fig, ax = plt.subplots(figsize=(18, 8))
        
        for location_id in sorted(self.aqi_df['location_id'].unique()):
            loc_data = self.aqi_df[self.aqi_df['location_id'] == location_id].sort_values('datetime_local')
            location_name = self.location_names.get(location_id, f"Loc {location_id}")
            
            ax.plot(loc_data['datetime_local'], loc_data['aqi_overall'], 
                   label=location_name, linewidth=1.5, alpha=0.7)
        
        # Add AQI category reference lines
        ax.axhline(y=50, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Good')
        ax.axhline(y=100, color='yellow', linestyle='--', linewidth=1, alpha=0.5, label='Moderate')
        ax.axhline(y=150, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Unhealthy (Sensitive)')
        ax.axhline(y=200, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Unhealthy')
        ax.axhline(y=300, color='purple', linestyle='--', linewidth=1, alpha=0.5, label='Very Unhealthy')
        
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('AQI (Air Quality Index)', fontsize=12)
        ax.set_title('Air Quality Index Over Time - All Locations', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_timeseries_all_locations.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_timeseries_all_locations.png")
        plt.close()
        
        # 2. AQI Distribution by Location (Bar Chart)
        fig, ax = plt.subplots(figsize=(14, 8))
        
        location_aqi = []
        location_labels = []
        
        for location_id in sorted(self.aqi_df['location_id'].unique()):
            loc_data = self.aqi_df[self.aqi_df['location_id'] == location_id]
            avg_aqi = loc_data['aqi_overall'].mean()
            location_aqi.append(avg_aqi)
            location_name = self.location_names.get(location_id, f"Loc {location_id}")
            location_labels.append(location_name)
        
        # Color bars by AQI category
        colors = [get_aqi_category(aqi)[1] for aqi in location_aqi]
        
        bars = ax.bar(range(len(location_labels)), location_aqi, color=colors, alpha=0.7, edgecolor='black')
        ax.set_xticks(range(len(location_labels)))
        ax.set_xticklabels(location_labels, rotation=45, ha='right')
        ax.set_ylabel('Average AQI', fontsize=12)
        ax.set_title('Average Air Quality Index by Location', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for i, (bar, aqi) in enumerate(zip(bars, location_aqi)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{aqi:.0f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_average_by_location.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_average_by_location.png")
        plt.close()
        
        # 3. AQI Category Distribution (Pie Chart)
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))
        
        # Overall distribution
        category_counts = self.aqi_df['aqi_category'].value_counts()
        category_colors = [get_aqi_category(50 if cat == 'Good' else 
                                           75 if cat == 'Moderate' else 
                                           125 if cat == 'Unhealthy for Sensitive Groups' else 
                                           175 if cat == 'Unhealthy' else 
                                           250 if cat == 'Very Unhealthy' else 400)[1] 
                          for cat in category_counts.index]
        
        axes[0].pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%',
                   colors=category_colors, startangle=90)
        axes[0].set_title('Overall AQI Category Distribution', fontsize=12, fontweight='bold')
        
        # Daily average distribution
        daily_aqi = self.aqi_df.groupby(self.aqi_df['datetime_local'].dt.date)['aqi_overall'].mean()
        daily_categories = daily_aqi.apply(lambda x: get_aqi_category(x)[0])
        daily_counts = daily_categories.value_counts()
        daily_colors = [get_aqi_category(50 if cat == 'Good' else 
                                         75 if cat == 'Moderate' else 
                                         125 if cat == 'Unhealthy for Sensitive Groups' else 
                                         175 if cat == 'Unhealthy' else 
                                         250 if cat == 'Very Unhealthy' else 400)[1] 
                       for cat in daily_counts.index]
        
        axes[1].pie(daily_counts.values, labels=daily_counts.index, autopct='%1.1f%%',
                   colors=daily_colors, startangle=90)
        axes[1].set_title('Daily Average AQI Category Distribution', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_category_distribution.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_category_distribution.png")
        plt.close()
        
        # 4. AQI Heatmap by Location and Time
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Create daily average AQI pivot
        self.aqi_df['date'] = pd.to_datetime(self.aqi_df['datetime_local'].dt.date)
        aqi_pivot = self.aqi_df.pivot_table(
            index='location_id',
            columns='date',
            values='aqi_overall',
            aggfunc='mean'
        )
        
        # Use location names
        aqi_pivot.index = [self.location_names.get(idx, f"Loc {idx}") for idx in aqi_pivot.index]
        
        # Limit columns if too many dates
        if len(aqi_pivot.columns) > 60:
            step = len(aqi_pivot.columns) // 60
            aqi_pivot = aqi_pivot.iloc[:, ::step]
        
        sns.heatmap(aqi_pivot, cmap='RdYlGn_r', center=100, vmin=0, vmax=300,
                   cbar_kws={'label': 'AQI'}, linewidths=0.5, ax=ax)
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Location', fontsize=12)
        ax.set_title('Air Quality Index Heatmap Over Time', fontsize=14, fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_heatmap_over_time.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_heatmap_over_time.png")
        plt.close()
        
        # 5. AQI Daily Trend
        fig, ax = plt.subplots(figsize=(16, 8))
        
        daily_aqi_by_location = self.aqi_df.groupby(['location_id', 
                                                      self.aqi_df['datetime_local'].dt.date])['aqi_overall'].mean().reset_index()
        daily_aqi_by_location.columns = ['location_id', 'date', 'aqi']
        daily_aqi_by_location['date'] = pd.to_datetime(daily_aqi_by_location['date'])
        
        for location_id in sorted(daily_aqi_by_location['location_id'].unique()):
            loc_data = daily_aqi_by_location[daily_aqi_by_location['location_id'] == location_id].sort_values('date')
            location_name = self.location_names.get(location_id, f"Loc {location_id}")
            
            ax.plot(loc_data['date'], loc_data['aqi'], 
                   label=location_name, linewidth=2, alpha=0.8, marker='o', markersize=3)
        
        # Add AQI category bands
        ax.axhspan(0, 50, alpha=0.1, color='green', label='Good')
        ax.axhspan(50, 100, alpha=0.1, color='yellow', label='Moderate')
        ax.axhspan(100, 150, alpha=0.1, color='orange', label='Unhealthy (Sensitive)')
        ax.axhspan(150, 200, alpha=0.1, color='red', label='Unhealthy')
        ax.axhspan(200, 300, alpha=0.1, color='purple', label='Very Unhealthy')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Daily Average AQI', fontsize=12)
        ax.set_title('Daily Average Air Quality Index Trend', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_daily_trend.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_daily_trend.png")
        plt.close()
        
        # 6. Hourly Average AQI (Daily Basis)
        print("\n📊 Generating hourly AQI averages...")
        fig, ax = plt.subplots(figsize=(18, 8))
        
        # Calculate hourly averages
        self.aqi_df['hour'] = self.aqi_df['datetime_local'].dt.hour
        hourly_aqi = self.aqi_df.groupby(['location_id', 'hour'])['aqi_overall'].mean().reset_index()
        
        for location_id in sorted(hourly_aqi['location_id'].unique()):
            loc_data = hourly_aqi[hourly_aqi['location_id'] == location_id].sort_values('hour')
            location_name = self.location_names.get(location_id, f"Loc {location_id}")
            
            ax.plot(loc_data['hour'], loc_data['aqi_overall'], 
                   label=location_name, linewidth=2.5, alpha=0.8, marker='o', markersize=5)
        
        # Add AQI category reference lines
        ax.axhline(y=50, color='green', linestyle='--', linewidth=1, alpha=0.4, label='Good (50)')
        ax.axhline(y=100, color='yellow', linestyle='--', linewidth=1, alpha=0.4, label='Moderate (100)')
        ax.axhline(y=150, color='orange', linestyle='--', linewidth=1, alpha=0.4, label='Unhealthy Sensitive (150)')
        ax.axhline(y=200, color='red', linestyle='--', linewidth=1, alpha=0.4, label='Unhealthy (200)')
        
        ax.set_xlabel('Hour of Day (Local Time: Nepal Time, UTC+5:45)', fontsize=13)
        ax.set_ylabel('Average AQI', fontsize=13)
        ax.set_title('Average AQI by Hour of Day (All Locations)', fontsize=15, fontweight='bold')
        ax.set_xticks(range(0, 24))
        ax.set_xticklabels([f'{h:02d}:00' for h in range(24)], rotation=45, ha='right')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_hourly_average.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_hourly_average.png")
        plt.close()
        
        # 7. 15-Day Period Averages (Monthly Basis)
        print("\n📊 Generating 15-day period AQI averages...")
        fig, ax = plt.subplots(figsize=(18, 8))
        
        # Create 15-day periods
        self.aqi_df['date'] = pd.to_datetime(self.aqi_df['datetime_local'].dt.date)
        min_date = self.aqi_df['date'].min()
        max_date = self.aqi_df['date'].max()
        
        # Create 15-day period labels
        def get_15day_period(date):
            days_since_start = (date - min_date).days
            period_num = days_since_start // 15
            period_start = min_date + pd.Timedelta(days=period_num * 15)
            period_end = period_start + pd.Timedelta(days=14)
            return f"{period_start.strftime('%m/%d')}-{period_end.strftime('%m/%d')}"
        
        self.aqi_df['period_15day'] = self.aqi_df['date'].apply(get_15day_period)
        
        # Calculate 15-day period averages
        period_aqi = self.aqi_df.groupby(['location_id', 'period_15day'])['aqi_overall'].mean().reset_index()
        
        # Get unique periods in chronological order
        period_order = sorted(self.aqi_df.groupby('period_15day')['date'].min().items(), 
                            key=lambda x: x[1])
        ordered_periods = [p[0] for p in period_order]
        
        # Plot each location
        for location_id in sorted(period_aqi['location_id'].unique()):
            loc_data = period_aqi[period_aqi['location_id'] == location_id]
            # Reindex to maintain period order
            loc_data['period_order'] = loc_data['period_15day'].map({p: i for i, p in enumerate(ordered_periods)})
            loc_data = loc_data.sort_values('period_order')
            
            location_name = self.location_names.get(location_id, f"Loc {location_id}")
            
            ax.plot(loc_data['period_order'], loc_data['aqi_overall'], 
                   label=location_name, linewidth=2.5, alpha=0.8, marker='o', markersize=4)
        
        # Add AQI category bands
        ax.axhspan(0, 50, alpha=0.08, color='green')
        ax.axhspan(50, 100, alpha=0.08, color='yellow')
        ax.axhspan(100, 150, alpha=0.08, color='orange')
        ax.axhspan(150, 200, alpha=0.08, color='red')
        ax.axhspan(200, 300, alpha=0.08, color='purple')
        
        # Add reference lines
        ax.axhline(y=50, color='green', linestyle='--', linewidth=1, alpha=0.4)
        ax.axhline(y=100, color='yellow', linestyle='--', linewidth=1, alpha=0.4)
        ax.axhline(y=150, color='orange', linestyle='--', linewidth=1, alpha=0.4)
        ax.axhline(y=200, color='red', linestyle='--', linewidth=1, alpha=0.4)
        
        ax.set_xlabel('15-Day Period', fontsize=13)
        ax.set_ylabel('Average AQI', fontsize=13)
        ax.set_title('Average AQI per 15-Day Period (All Locations)', fontsize=15, fontweight='bold')
        
        # Set x-axis labels (show every nth period to avoid crowding)
        step = max(1, len(ordered_periods) // 20)
        ax.set_xticks([i for i in range(0, len(ordered_periods), step)])
        ax.set_xticklabels([ordered_periods[i] for i in range(0, len(ordered_periods), step)], 
                          rotation=45, ha='right', fontsize=9)
        
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "aqi_15day_average.png", dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: aqi_15day_average.png")
        plt.close()
        
    def generate_heatmap(self):
        """Generate heatmap showing average values by location and parameter"""
        print("\n📊 Generating heatmap...")
        
        # Create pivot table
        heatmap_data = self.df.pivot_table(
            index='location_name',
            columns='parameter',
            values='value',
            aggfunc='mean'
        )
        
        fig = plt.figure(figsize=(14, 10))
        sns.heatmap(heatmap_data, annot=True, fmt='.2f', cmap='YlOrRd', 
                    cbar_kws={'label': 'Average Value'}, linewidths=0.5)
        plt.title('Average Parameter Values by Location', fontsize=14, fontweight='bold')
        plt.xlabel('Parameter', fontsize=12)
        plt.ylabel('Location', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        filename = "heatmap_parameters_by_location.png"
        plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {filename}")
        plt.close()
        
    def generate_summary_statistics(self):
        """Generate detailed summary statistics"""
        print("\n📊 Generating summary statistics...")
        
        output = []
        output.append("=" * 80)
        output.append("AIR QUALITY DATA ANALYTICS SUMMARY")
        output.append("=" * 80)
        output.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"Total Records: {len(self.df):,}")
        output.append(f"Date Range: {self.df['datetime_local'].min()} to {self.df['datetime_local'].max()}")
        output.append(f"Output Directory: {self.output_dir}")
        output.append(f"\n{'=' * 80}\n")
        
        # Statistics by parameter
        output.append("PARAMETER STATISTICS")
        output.append("-" * 80)
        
        for param in sorted(self.df['parameter'].unique()):
            param_data = self.df[self.df['parameter'] == param]
            units = param_data['units'].iloc[0]
            
            output.append(f"\n{param.upper()} ({units}):")
            output.append(f"  Count:   {len(param_data):,}")
            output.append(f"  Mean:    {param_data['value'].mean():.2f}")
            output.append(f"  Median:  {param_data['value'].median():.2f}")
            output.append(f"  Min:     {param_data['value'].min():.2f}")
            output.append(f"  Max:     {param_data['value'].max():.2f}")
            output.append(f"  Std Dev: {param_data['value'].std():.2f}")
            
        output.append(f"\n{'=' * 80}\n")
        
        # Statistics by location
        output.append("LOCATION STATISTICS")
        output.append("-" * 80)
        
        for location_id in sorted(self.df['location_id'].unique()):
            loc_data = self.df[self.df['location_id'] == location_id]
            location_name = self.location_names.get(location_id, f"Location {location_id}")
            
            output.append(f"\n{location_name} (ID: {location_id}):")
            output.append(f"  Total Records: {len(loc_data):,}")
            output.append(f"  Parameters: {', '.join(loc_data['parameter'].unique())}")
            output.append(f"  Date Range: {loc_data['datetime_local'].min()} to {loc_data['datetime_local'].max()}")
            
            # PM2.5 specific stats if available
            pm25_loc = loc_data[loc_data['parameter'] == 'pm25']
            if not pm25_loc.empty:
                output.append(f"  PM2.5 Mean: {pm25_loc['value'].mean():.2f} µg/m³")
                output.append(f"  PM2.5 Max:  {pm25_loc['value'].max():.2f} µg/m³")
                
        output.append(f"\n{'=' * 80}\n")
        
        # Save to file
        summary_text = "\n".join(output)
        filename = "summary_statistics.txt"
        with open(self.output_dir / filename, 'w') as f:
            f.write(summary_text)
            
        print(f"  ✓ Saved: {filename}")
        
        # Also print to console
        print("\n" + summary_text)
        
    def run_complete_analysis(self):
        """Run all analytics and generate all visualizations"""
        print("\n" + "=" * 80)
        print("🚀 STARTING COMPLETE AIR QUALITY DATA ANALYSIS")
        print("=" * 80)
        print(f"📁 Output directory: {self.output_dir}")
        
        # Load data
        self.load_data()
        
        if self.df is None or self.df.empty:
            print("\n❌ No data loaded. Exiting.")
            return
            
        # Generate all visualizations
        self.generate_summary_statistics()
        self.generate_histograms()
        self.generate_scatter_plots()
        self.generate_timeseries_by_parameter()
        self.generate_timeseries_by_location()
        self.generate_parameter_change_over_time()
        self.generate_distribution_over_time()
        self.generate_violin_distribution_over_time()
        self.generate_aqi_visualizations()
        self.generate_heatmap()
        
        print("\n" + "=" * 80)
        print("\nGenerated file types:")
        print("  • summary_statistics.txt - Detailed statistics")
        print("  • histogram_<parameter>.png - Distribution for each parameter")
        print("  • scatter_<param1>_vs_<param2>.png - Parameter relationships")
        print("  • timeseries_<parameter>_all_locations.png - Time series for each parameter")
        print("  • timeseries_location_<id>.png - All parameters for each location")
        print("  • trend_daily_<parameter>.png - Daily average trends")
        print("  • distribution_over_time_<parameter>.png - Box plot distribution over time")
        print("  • violin_distribution_<parameter>.png - Violin plot distribution over time")
        print("  • aqi_*.png - Air Quality Index visualizations (7 files)")
        print("  • heatmap_parameters_by_location.png - Average values heatmap")
        
        # Count files
        files_generated = list(self.output_dir.glob("*.png")) + list(self.output_dir.glob("*.txt"))
        print(f"\n📊 Total files generated: {len(files_generated)}")
        print("\n")


def main():
    """Main execution function"""
    analytics = AirQualityAnalytics()
    analytics.run_complete_analysis()


if __name__ == "__main__":
    main()
