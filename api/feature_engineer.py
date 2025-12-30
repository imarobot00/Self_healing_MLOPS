"""
Feature Engineering Pipeline for Real-Time Predictions
========================================================

This module creates all 65 features required by the trained model from:
- Current sensor readings (pm25, pm1, temperature, humidity, um003)
- Historical data (for lag and rolling features)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Generate all 65 features needed for prediction from raw sensor data.
    """
    
    def __init__(self, data_dir=None):
        if data_dir is None:
            # Try relative path first, then absolute
            data_dir = Path("../dataset")
            if not data_dir.exists():
                data_dir = Path(__file__).parent.parent / "dataset"
        
        self.data_dir = Path(data_dir)
        self.location_files = list(self.data_dir.glob("location_*.json"))
        logger.info(f"Initialized with {len(self.location_files)} location files")
    
    def load_recent_data(self, location_id, hours=48):
        """
        Load recent data from a location to compute lag features.
        
        Parameters:
        -----------
        location_id : int
            Location ID (e.g., 6142174)
        hours : int
            Number of hours of historical data to load
        
        Returns:
        --------
        pd.DataFrame : Recent historical data
        """
        location_file = self.data_dir / f"location_{location_id}.json"
        
        if not location_file.exists():
            raise FileNotFoundError(f"Location file not found: {location_file}")
        
        # Load JSON data
        with open(location_file, 'r') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Parse datetime
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Sort by time
        df = df.sort_values('datetime')
        
        # Filter to recent hours
        cutoff = datetime.now() - timedelta(hours=hours)
        df = df[df['datetime'] >= cutoff]
        
        return df
    
    def calculate_aqi(self, pm25):
        """
        Calculate AQI from PM2.5 concentration (simplified EPA formula).
        
        Parameters:
        -----------
        pm25 : float
            PM2.5 concentration in µg/m³
        
        Returns:
        --------
        float : Calculated AQI
        """
        # EPA AQI breakpoints for PM2.5
        breakpoints = [
            (0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 500.4, 301, 500)
        ]
        
        for c_low, c_high, i_low, i_high in breakpoints:
            if c_low <= pm25 <= c_high:
                # Linear interpolation
                aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
                return aqi
        
        # Beyond scale
        if pm25 > 500.4:
            return 500
        return 0
    
    def create_features(self, current_data, location_id=6142174):
        """
        Create all 65 features from current sensor readings and historical data.
        
        Parameters:
        -----------
        current_data : dict
            Current sensor readings:
            {
                'pm25': float,
                'pm1': float,
                'temperature': float,
                'relativehumidity': float,
                'um003': float,
                'datetime': datetime (optional, defaults to now)
            }
        location_id : int
            Location ID for loading historical data
        
        Returns:
        --------
        dict : All 65 features ready for model prediction
        """
        # Load historical data for lags and rolling features
        try:
            hist_df = self.load_recent_data(location_id, hours=48)
        except Exception as e:
            logger.warning(f"Could not load historical data: {e}. Using fallback values.")
            hist_df = pd.DataFrame()
        
        # Get current datetime
        current_dt = current_data.get('datetime', datetime.now())
        if isinstance(current_dt, str):
            current_dt = pd.to_datetime(current_dt)
        
        # Calculate current AQI
        current_aqi = self.calculate_aqi(current_data['pm25'])
        
        # Initialize features dict
        features = {}
        
        # 1. Basic features (5)
        features['pm25'] = current_data['pm25']
        features['pm1'] = current_data['pm1']
        features['temperature'] = current_data['temperature']
        features['relativehumidity'] = current_data['relativehumidity']
        features['um003'] = current_data['um003']
        
        # 2. Time features (1)
        features['hour'] = current_dt.hour
        features['is_weekend'] = 1 if current_dt.weekday() >= 5 else 0
        
        # 3. Lag features (24)
        # If we have historical data, compute real lags
        if len(hist_df) > 0:
            # Add current AQI to historical data
            hist_df['aqi'] = hist_df['pm25'].apply(self.calculate_aqi)
            
            # AQI lags
            features['aqi_lag_1'] = hist_df['aqi'].iloc[-1] if len(hist_df) >= 1 else current_aqi
            features['aqi_lag_2'] = hist_df['aqi'].iloc[-2] if len(hist_df) >= 2 else current_aqi
            features['aqi_lag_3'] = hist_df['aqi'].iloc[-3] if len(hist_df) >= 3 else current_aqi
            features['aqi_lag_6'] = hist_df['aqi'].iloc[-6] if len(hist_df) >= 6 else current_aqi
            features['aqi_lag_12'] = hist_df['aqi'].iloc[-12] if len(hist_df) >= 12 else current_aqi
            features['aqi_lag_24'] = hist_df['aqi'].iloc[-24] if len(hist_df) >= 24 else current_aqi
            
            # PM2.5 lags
            features['pm25_lag_1'] = hist_df['pm25'].iloc[-1] if len(hist_df) >= 1 else current_data['pm25']
            features['pm25_lag_3'] = hist_df['pm25'].iloc[-3] if len(hist_df) >= 3 else current_data['pm25']
            features['pm25_lag_6'] = hist_df['pm25'].iloc[-6] if len(hist_df) >= 6 else current_data['pm25']
            
            # PM1 lags
            features['pm1_lag_1'] = hist_df['pm1'].iloc[-1] if len(hist_df) >= 1 else current_data['pm1']
            features['pm1_lag_3'] = hist_df['pm1'].iloc[-3] if len(hist_df) >= 3 else current_data['pm1']
            features['pm1_lag_6'] = hist_df['pm1'].iloc[-6] if len(hist_df) >= 6 else current_data['pm1']
            
            # Temperature lags
            features['temperature_lag_1'] = hist_df['temperature'].iloc[-1] if len(hist_df) >= 1 else current_data['temperature']
            features['temperature_lag_3'] = hist_df['temperature'].iloc[-3] if len(hist_df) >= 3 else current_data['temperature']
            features['temperature_lag_6'] = hist_df['temperature'].iloc[-6] if len(hist_df) >= 6 else current_data['temperature']
            
            # Humidity lags
            features['relativehumidity_lag_1'] = hist_df['relativehumidity'].iloc[-1] if len(hist_df) >= 1 else current_data['relativehumidity']
            features['relativehumidity_lag_3'] = hist_df['relativehumidity'].iloc[-3] if len(hist_df) >= 3 else current_data['relativehumidity']
            features['relativehumidity_lag_6'] = hist_df['relativehumidity'].iloc[-6] if len(hist_df) >= 6 else current_data['relativehumidity']
            
            # um003 lags
            features['um003_lag_1'] = hist_df['um003'].iloc[-1] if len(hist_df) >= 1 else current_data['um003']
            features['um003_lag_3'] = hist_df['um003'].iloc[-3] if len(hist_df) >= 3 else current_data['um003']
            features['um003_lag_6'] = hist_df['um003'].iloc[-6] if len(hist_df) >= 6 else current_data['um003']
        else:
            # Fallback: use current values for all lags
            for col in ['aqi', 'pm25', 'pm1', 'temperature', 'relativehumidity', 'um003']:
                for lag in [1, 2, 3, 6, 12, 24]:
                    key = f'{col}_lag_{lag}'
                    if key in ['aqi_lag_1', 'aqi_lag_2', 'aqi_lag_3', 'aqi_lag_6', 'aqi_lag_12', 'aqi_lag_24']:
                        features[key] = current_aqi
                    elif 'pm25' in key:
                        features[key] = current_data['pm25']
                    elif 'pm1' in key:
                        features[key] = current_data['pm1']
                    elif 'temperature' in key:
                        features[key] = current_data['temperature']
                    elif 'relativehumidity' in key:
                        features[key] = current_data['relativehumidity']
                    elif 'um003' in key:
                        features[key] = current_data['um003']
        
        # 4. Rolling statistics (16 features)
        if len(hist_df) > 0:
            recent_aqi = hist_df['aqi'].tail(24).values
            
            # 3-hour rolling
            features['aqi_rolling_mean_3'] = np.mean(recent_aqi[-3:]) if len(recent_aqi) >= 3 else current_aqi
            features['aqi_rolling_std_3'] = np.std(recent_aqi[-3:]) if len(recent_aqi) >= 3 else 0
            features['aqi_rolling_min_3'] = np.min(recent_aqi[-3:]) if len(recent_aqi) >= 3 else current_aqi
            features['aqi_rolling_max_3'] = np.max(recent_aqi[-3:]) if len(recent_aqi) >= 3 else current_aqi
            
            # 6-hour rolling
            features['aqi_rolling_mean_6'] = np.mean(recent_aqi[-6:]) if len(recent_aqi) >= 6 else current_aqi
            features['aqi_rolling_std_6'] = np.std(recent_aqi[-6:]) if len(recent_aqi) >= 6 else 0
            features['aqi_rolling_min_6'] = np.min(recent_aqi[-6:]) if len(recent_aqi) >= 6 else current_aqi
            features['aqi_rolling_max_6'] = np.max(recent_aqi[-6:]) if len(recent_aqi) >= 6 else current_aqi
            
            # 12-hour rolling
            features['aqi_rolling_mean_12'] = np.mean(recent_aqi[-12:]) if len(recent_aqi) >= 12 else current_aqi
            features['aqi_rolling_std_12'] = np.std(recent_aqi[-12:]) if len(recent_aqi) >= 12 else 0
            features['aqi_rolling_min_12'] = np.min(recent_aqi[-12:]) if len(recent_aqi) >= 12 else current_aqi
            features['aqi_rolling_max_12'] = np.max(recent_aqi[-12:]) if len(recent_aqi) >= 12 else current_aqi
            
            # 24-hour rolling
            features['aqi_rolling_mean_24'] = np.mean(recent_aqi[-24:]) if len(recent_aqi) >= 24 else current_aqi
            features['aqi_rolling_std_24'] = np.std(recent_aqi[-24:]) if len(recent_aqi) >= 24 else 0
            features['aqi_rolling_min_24'] = np.min(recent_aqi[-24:]) if len(recent_aqi) >= 24 else current_aqi
            features['aqi_rolling_max_24'] = np.max(recent_aqi[-24:]) if len(recent_aqi) >= 24 else current_aqi
        else:
            # Fallback
            for window in [3, 6, 12, 24]:
                features[f'aqi_rolling_mean_{window}'] = current_aqi
                features[f'aqi_rolling_std_{window}'] = 0
                features[f'aqi_rolling_min_{window}'] = current_aqi
                features[f'aqi_rolling_max_{window}'] = current_aqi
        
        # 5. Cyclical time encodings (6 features)
        features['hour_sin'] = np.sin(2 * np.pi * current_dt.hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * current_dt.hour / 24)
        features['day_sin'] = np.sin(2 * np.pi * current_dt.day / 31)
        features['day_cos'] = np.cos(2 * np.pi * current_dt.day / 31)
        features['month_sin'] = np.sin(2 * np.pi * current_dt.month / 12)
        features['month_cos'] = np.cos(2 * np.pi * current_dt.month / 12)
        
        # 6. Interaction features (3)
        features['pm25_humidity_interaction'] = current_data['pm25'] * current_data['relativehumidity']
        features['pm25_temp_interaction'] = current_data['pm25'] * current_data['temperature']
        features['pm_ratio'] = current_data['pm25'] / max(current_data['pm1'], 0.1)
        
        # 7. Change features (3)
        if len(hist_df) > 0:
            features['aqi_change_1h'] = current_aqi - features['aqi_lag_1']
            features['aqi_change_3h'] = current_aqi - features['aqi_lag_3']
            features['aqi_change_rate'] = (current_aqi - features['aqi_lag_1']) / max(features['aqi_lag_1'], 1)
        else:
            features['aqi_change_1h'] = 0
            features['aqi_change_3h'] = 0
            features['aqi_change_rate'] = 0
        
        # 8. Day name one-hot encoding (6 features)
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Saturday', 'Sunday']
        current_day = current_dt.strftime('%A')
        for day in day_names:
            features[f'day_name_{day}'] = 1 if current_day == day else 0
        
        # 9. Time of day one-hot encoding (3 features)
        hour = current_dt.hour
        features['time_of_day_Morning'] = 1 if 6 <= hour < 12 else 0
        features['time_of_day_Evening'] = 1 if 18 <= hour < 22 else 0
        features['time_of_day_Night'] = 1 if hour >= 22 or hour < 6 else 0
        
        logger.info(f"Created {len(features)} features for prediction")
        return features
