#!/usr/bin/env python3
"""
Data Preprocessing Module for Online Learning
===============================================

Designed for Adaptive Random Forest Regressor with ADWIN drift detection.
Handles streaming data preparation for time-series forecasting.

Features:
- Lag feature engineering (past values)
- Rolling window statistics
- Time-based features
- Categorical encoding
- Data normalization/standardization
- Missing value handling
- Outlier detection and treatment

Author: Bipul Kumar Dahal
Date: December 14, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class StreamingPreprocessor:
    """
    Preprocessor for online/streaming machine learning models.
    Designed for Adaptive Random Forest with incremental learning.
    """
    
    def __init__(
        self,
        target_column: str = 'aqi',
        lag_features: List[int] = [1, 2, 3, 6, 12, 24],
        rolling_windows: List[int] = [3, 6, 12, 24],
        categorical_columns: List[str] = ['day_name', 'time_of_day'],
        numerical_columns: List[str] = ['pm25', 'pm1', 'temperature', 'relativehumidity', 'um003'],
        normalize: bool = True,
        handle_outliers: bool = True
    ):
        """
        Initialize the streaming preprocessor.
        
        Parameters:
        -----------
        target_column : str
            The column to predict (e.g., 'aqi')
        lag_features : list
            Number of time steps to look back for lag features
            [1, 2, 3] means t-1, t-2, t-3 hours
        rolling_windows : list
            Window sizes for rolling statistics
            [3, 6, 12] means 3-hour, 6-hour, 12-hour averages
        categorical_columns : list
            Columns to encode as categories
        numerical_columns : list
            Columns to use as features
        normalize : bool
            Whether to normalize numerical features
        handle_outliers : bool
            Whether to cap outliers
        """
        self.target_column = target_column
        self.lag_features = lag_features
        self.rolling_windows = rolling_windows
        self.categorical_columns = categorical_columns
        self.numerical_columns = numerical_columns
        self.normalize = normalize
        self.should_handle_outliers = handle_outliers
        
        # Statistics for normalization (updated incrementally)
        self.feature_stats = {}
        self.is_fitted = False
        
    def create_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create lag features for time series forecasting.
        
        For each lag value, creates columns like:
        - aqi_lag_1 (value 1 hour ago)
        - aqi_lag_3 (value 3 hours ago)
        - aqi_lag_24 (value 24 hours ago)
        
        Example:
        If current row is 10:00 AM with AQI=120:
        - aqi_lag_1 = AQI at 09:00 AM
        - aqi_lag_24 = AQI at 10:00 AM yesterday
        """
        df = df.copy()
        
        # Sort by location and datetime
        df = df.sort_values(['location_id', 'datetime']).reset_index(drop=True)
        
        # Create lag features for target variable
        for lag in self.lag_features:
            df[f'{self.target_column}_lag_{lag}'] = df.groupby('location_id')[self.target_column].shift(lag)
        
        # Create lag features for other numerical columns
        for col in self.numerical_columns:
            for lag in [1, 3, 6]:  # Keep fewer lags for other features
                df[f'{col}_lag_{lag}'] = df.groupby('location_id')[col].shift(lag)
        
        return df
    
    def create_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create rolling window statistics.
        
        For each window size, creates:
        - mean (average over window)
        - std (volatility over window)
        - min/max (range over window)
        
        Example for window=6:
        - aqi_rolling_mean_6 = average AQI over last 6 hours
        - aqi_rolling_std_6 = standard deviation over last 6 hours
        """
        df = df.copy()
        
        for window in self.rolling_windows:
            # Rolling statistics for target
            df[f'{self.target_column}_rolling_mean_{window}'] = (
                df.groupby('location_id')[self.target_column]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )
            
            df[f'{self.target_column}_rolling_std_{window}'] = (
                df.groupby('location_id')[self.target_column]
                .transform(lambda x: x.rolling(window, min_periods=1).std())
            )
            
            df[f'{self.target_column}_rolling_min_{window}'] = (
                df.groupby('location_id')[self.target_column]
                .transform(lambda x: x.rolling(window, min_periods=1).min())
            )
            
            df[f'{self.target_column}_rolling_max_{window}'] = (
                df.groupby('location_id')[self.target_column]
                .transform(lambda x: x.rolling(window, min_periods=1).max())
            )
        
        return df
    
    def create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create cyclical time features.
        
        Converts time into sine/cosine to capture cyclical patterns:
        - hour_sin, hour_cos (24-hour cycle)
        - day_sin, day_cos (7-day weekly cycle)
        - month_sin, month_cos (12-month yearly cycle)
        
        Why sine/cosine? Because 23:00 and 00:00 are close in time!
        """
        df = df.copy()
        
        # Hour of day (0-23) as cyclical feature
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        # Day of week (0-6) as cyclical feature
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Month (1-12) as cyclical feature
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        return df
    
    def create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create interaction features between parameters.
        
        These capture relationships like:
        - PM2.5 × humidity (particles stick to moisture)
        - PM2.5 × temperature (temperature inversions trap pollution)
        """
        df = df.copy()
        
        # PM2.5 and humidity interaction
        df['pm25_humidity_interaction'] = df['pm25'] * df['relativehumidity']
        
        # PM2.5 and temperature interaction
        df['pm25_temp_interaction'] = df['pm25'] * df['temperature']
        
        # PM ratio (PM2.5 / PM1)
        df['pm_ratio'] = df['pm25'] / (df['pm1'] + 1e-5)  # Avoid division by zero
        
        return df
    
    def create_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create rate of change features.
        
        Captures how fast values are changing:
        - aqi_change_1h = change in last hour
        - aqi_change_rate = acceleration
        """
        df = df.copy()
        
        # First-order changes (velocity)
        df[f'{self.target_column}_change_1h'] = (
            df.groupby('location_id')[self.target_column].diff(1)
        )
        
        df[f'{self.target_column}_change_3h'] = (
            df.groupby('location_id')[self.target_column].diff(3)
        )
        
        # Second-order changes (acceleration)
        df[f'{self.target_column}_change_rate'] = (
            df.groupby('location_id')[f'{self.target_column}_change_1h'].diff(1)
        )
        
        return df
    
    def encode_categorical(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Encode categorical variables.
        
        Uses one-hot encoding for:
        - day_name (Monday, Tuesday, etc.)
        - time_of_day (Morning, Afternoon, etc.)
        - is_weekend (0 or 1)
        """
        df = df.copy()
        
        # One-hot encode categorical columns
        for col in self.categorical_columns:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
                df = pd.concat([df, dummies], axis=1)
                df = df.drop(columns=[col])
        
        return df
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values intelligently.
        
        Strategy:
        - Forward fill for time series (use last known value)
        - Backward fill for start of series
        - Fill remaining with median
        """
        df = df.copy()
        
        # For each location, forward fill then backward fill
        for location in df['location_id'].unique():
            mask = df['location_id'] == location
            df.loc[mask] = df.loc[mask].fillna(method='ffill').fillna(method='bfill')
        
        # Fill any remaining NaN with median
        numerical_cols = df.select_dtypes(include=[np.number]).columns
        for col in numerical_cols:
            if df[col].isna().any():
                df[col].fillna(df[col].median(), inplace=True)
        
        return df
    
    def handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cap outliers using IQR method.
        
        Values beyond 1.5 × IQR are capped to reduce extreme influence.
        """
        if not self.should_handle_outliers:
            return df
        
        df = df.copy()
        
        for col in self.numerical_columns:
            if col in df.columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                df[col] = df[col].clip(lower=lower_bound, upper=upper_bound)
        
        return df
    
    def normalize_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """
        Normalize numerical features using min-max scaling.
        
        For online learning:
        - fit=True: Calculate statistics from this batch
        - fit=False: Use previously calculated statistics
        """
        if not self.normalize:
            return df
        
        df = df.copy()
        
        numerical_cols = df.select_dtypes(include=[np.number]).columns
        numerical_cols = [col for col in numerical_cols if col not in ['location_id', self.target_column]]
        
        for col in numerical_cols:
            if fit:
                # Calculate and store statistics
                self.feature_stats[col] = {
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'mean': df[col].mean(),
                    'std': df[col].std()
                }
            
            if col in self.feature_stats:
                # Normalize using stored statistics
                col_min = self.feature_stats[col]['min']
                col_max = self.feature_stats[col]['max']
                
                if col_max - col_min > 0:
                    df[col] = (df[col] - col_min) / (col_max - col_min)
                else:
                    df[col] = 0
        
        return df
    
    def prepare_for_streaming(
        self, 
        df: pd.DataFrame, 
        fit: bool = False
    ) -> pd.DataFrame:
        """
        Complete preprocessing pipeline for streaming data.
        
        This is the main function you'll call!
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe with aligned data
        fit : bool
            Whether to fit normalization statistics (True for first batch)
        
        Returns:
        --------
        pd.DataFrame
            Preprocessed dataframe ready for online learning
        """
        print("🔄 Starting preprocessing pipeline...")
        
        # Ensure datetime is parsed
        if 'datetime' in df.columns and df['datetime'].dtype == 'object':
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Sort by location and time
        df = df.sort_values(['location_id', 'datetime']).reset_index(drop=True)
        
        print("  ✓ Creating lag features...")
        df = self.create_lag_features(df)
        
        print("  ✓ Creating rolling features...")
        df = self.create_rolling_features(df)
        
        print("  ✓ Creating time features...")
        df = self.create_time_features(df)
        
        print("  ✓ Creating interaction features...")
        df = self.create_interaction_features(df)
        
        print("  ✓ Creating change features...")
        df = self.create_change_features(df)
        
        print("  ✓ Handling outliers...")
        df = self.handle_outliers(df)
        
        print("  ✓ Encoding categorical variables...")
        df = self.encode_categorical(df)
        
        print("  ✓ Handling missing values...")
        df = self.handle_missing_values(df)
        
        print("  ✓ Normalizing features...")
        df = self.normalize_features(df, fit=fit)
        
        # Remove rows with NaN in target (can't train on these)
        initial_rows = len(df)
        df = df.dropna(subset=[self.target_column])
        dropped_rows = initial_rows - len(df)
        
        if dropped_rows > 0:
            print(f"  ⚠ Dropped {dropped_rows} rows with missing target values")
        
        self.is_fitted = True
        print(f"\n✅ Preprocessing complete! Shape: {df.shape}")
        
        return df
    
    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of feature columns (everything except target and metadata).
        
        Returns:
        --------
        list
            Column names to use as features in the model
        """
        exclude_cols = [
            'location_id', 
            'datetime', 
            self.target_column,
            'day', 'month', 'day_of_week', 'day_name', 'time_of_day', 'is_weekend'
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        return feature_cols
    
    def save_statistics(self, filepath: str):
        """Save normalization statistics for later use."""
        import json
        
        # Convert numpy types to native Python types
        feature_stats_serializable = {}
        for key, stats in self.feature_stats.items():
            feature_stats_serializable[key] = {
                k: float(v) if hasattr(v, 'item') else v
                for k, v in stats.items()
            }
        
        stats_to_save = {
            'feature_stats': feature_stats_serializable,
            'is_fitted': self.is_fitted,
            'target_column': self.target_column
        }
        
        with open(filepath, 'w') as f:
            json.dump(stats_to_save, f, indent=2)
        
        print(f"✅ Statistics saved to {filepath}")
    
    def load_statistics(self, filepath: str):
        """Load normalization statistics from file."""
        import json
        
        with open(filepath, 'r') as f:
            stats = json.load(f)
        
        self.feature_stats = stats['feature_stats']
        self.is_fitted = stats['is_fitted']
        self.target_column = stats['target_column']
        
        print(f"✅ Statistics loaded from {filepath}")


def create_train_test_split(
    df: pd.DataFrame, 
    test_size: float = 0.2,
    by_time: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create train/test split for time series.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Preprocessed dataframe
    test_size : float
        Proportion of data for testing (0.2 = 20%)
    by_time : bool
        If True, split chronologically (last 20% as test)
        If False, random split (not recommended for time series!)
    
    Returns:
    --------
    train_df, test_df : tuple
        Training and testing dataframes
    """
    df = df.sort_values(['location_id', 'datetime']).reset_index(drop=True)
    
    if by_time:
        # Chronological split (recommended for time series)
        split_idx = int(len(df) * (1 - test_size))
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        
        print(f"📊 Chronological split:")
        print(f"  Training: {len(train_df)} rows ({train_df['datetime'].min()} to {train_df['datetime'].max()})")
        print(f"  Testing: {len(test_df)} rows ({test_df['datetime'].min()} to {test_df['datetime'].max()})")
    else:
        # Random split
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(df, test_size=test_size, random_state=42)
        print(f"📊 Random split: {len(train_df)} train, {len(test_df)} test")
    
    return train_df, test_df


# Example usage and testing
if __name__ == "__main__":
    print("="*70)
    print("STREAMING DATA PREPROCESSOR - TEST RUN")
    print("="*70)
    
    # Load the aligned data
    input_file = Path(__file__).parent / "aligned_all_locations.csv"
    
    if not input_file.exists():
        print(f"❌ Error: {input_file} not found!")
        print("Please run the alignment script first.")
        exit(1)
    
    print(f"\n📂 Loading data from: {input_file}")
    df = pd.read_csv(input_file)
    print(f"✅ Loaded {len(df):,} records with {len(df.columns)} columns")
    
    # Initialize preprocessor
    print("\n🔧 Initializing preprocessor...")
    preprocessor = StreamingPreprocessor(
        target_column='aqi',
        lag_features=[1, 2, 3, 6, 12, 24],  # 1h, 2h, 3h, 6h, 12h, 24h lags
        rolling_windows=[3, 6, 12, 24],      # 3h, 6h, 12h, 24h windows
        normalize=True,
        handle_outliers=True
    )
    
    # Preprocess the data
    print("\n" + "="*70)
    df_processed = preprocessor.prepare_for_streaming(df, fit=True)
    
    # Get feature columns
    feature_cols = preprocessor.get_feature_columns(df_processed)
    
    print("\n" + "="*70)
    print("📊 PREPROCESSING SUMMARY")
    print("="*70)
    print(f"Original shape: {df.shape}")
    print(f"Processed shape: {df_processed.shape}")
    print(f"Number of features created: {len(feature_cols)}")
    print(f"\nFeature categories:")
    
    lag_features = [c for c in feature_cols if 'lag' in c]
    rolling_features = [c for c in feature_cols if 'rolling' in c]
    time_features = [c for c in feature_cols if any(x in c for x in ['sin', 'cos', 'hour'])]
    interaction_features = [c for c in feature_cols if 'interaction' in c or 'ratio' in c]
    change_features = [c for c in feature_cols if 'change' in c]
    
    print(f"  - Lag features: {len(lag_features)}")
    print(f"  - Rolling features: {len(rolling_features)}")
    print(f"  - Time features: {len(time_features)}")
    print(f"  - Interaction features: {len(interaction_features)}")
    print(f"  - Change features: {len(change_features)}")
    
    # Save preprocessed data
    output_file = Path(__file__).parent / "processed_for_streaming.csv"
    df_processed.to_csv(output_file, index=False)
    print(f"\n✅ Preprocessed data saved to: {output_file}")
    
    # Save statistics
    stats_file = Path(__file__).parent / "preprocessor_stats.json"
    preprocessor.save_statistics(str(stats_file))
    
    # Create train/test split
    print("\n" + "="*70)
    train_df, test_df = create_train_test_split(df_processed, test_size=0.2, by_time=True)
    
    # Save splits
    train_file = Path(__file__).parent / "train_data.csv"
    test_file = Path(__file__).parent / "test_data.csv"
    
    train_df.to_csv(train_file, index=False)
    test_df.to_csv(test_file, index=False)
    
    print(f"\n✅ Train data saved to: {train_file}")
    print(f"✅ Test data saved to: {test_file}")
    
    print("\n" + "="*70)
    print("🎉 PREPROCESSING COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Use 'processed_for_streaming.csv' for full dataset")
    print("2. Use 'train_data.csv' and 'test_data.csv' for model training/evaluation")
    print("3. Feature columns are ready for Adaptive Random Forest")
    print("4. Data is normalized and ready for online learning")
