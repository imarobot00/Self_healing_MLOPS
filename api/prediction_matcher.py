"""
Prediction Matcher - Automatically match predictions with actual values

This module reads the latest location data and matches it against logged predictions
to calculate model performance metrics in production.

Usage:
    python api/prediction_matcher.py
    python api/prediction_matcher.py --location 5509787
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictionMatcher:
    """Match predictions with actual values from data pipeline"""
    
    def __init__(
        self, 
        predictions_dir: str = "api/logs/predictions",
        data_dir: str = "dataset"
    ):
        self.predictions_dir = Path(predictions_dir)
        self.data_dir = Path(data_dir)
        
        if not self.predictions_dir.exists():
            self.predictions_dir.mkdir(parents=True, exist_ok=True)
    
    def load_location_data(self, location_id: int) -> pd.DataFrame:
        """Load location data and extract AQI values with timestamps"""
        location_file = self.data_dir / f"location_{location_id}.json"
        
        if not location_file.exists():
            logger.warning(f"Location file not found: {location_file}")
            return pd.DataFrame()
        
        with open(location_file, 'r') as f:
            raw_data = json.load(f)
        
        # Extract PM2.5 data (for AQI calculation)
        records = []
        for item in raw_data:
            try:
                if item.get('parameter', {}).get('name') == 'pm25':
                    timestamp = item['period']['datetimeFrom']['utc']
                    pm25 = item['value']
                    
                    # Calculate AQI from PM2.5
                    aqi = self._pm25_to_aqi(pm25)
                    
                    records.append({
                        'timestamp': pd.to_datetime(timestamp),
                        'pm25': pm25,
                        'aqi': aqi
                    })
            except (KeyError, TypeError) as e:
                continue
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df = df.sort_values('timestamp')
        return df
    
    def _pm25_to_aqi(self, pm25: float) -> float:
        """
        Convert PM2.5 to AQI using EPA formula
        Simplified version - full implementation should match feature_engineer.py
        """
        # EPA AQI breakpoints
        breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 500.4, 301, 500),
        ]
        
        for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
            if bp_lo <= pm25 <= bp_hi:
                aqi = ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + aqi_lo
                return round(aqi, 2)
        
        # Beyond scale
        if pm25 > 500.4:
            return 500.0
        return 0.0
    
    def load_predictions(self, days: int = 7) -> List[Dict]:
        """Load all predictions from log files"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        all_predictions = []
        for pred_file in sorted(self.predictions_dir.glob("predictions_*.jsonl")):
            try:
                with open(pred_file, 'r') as f:
                    for line in f:
                        try:
                            pred = json.loads(line)
                            pred_time = datetime.fromisoformat(pred['timestamp'].replace('Z', '+00:00'))
                            
                            # Only process recent predictions
                            if pred_time >= cutoff_date:
                                all_predictions.append(pred)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception as e:
                logger.warning(f"Error reading {pred_file}: {e}")
                continue
        
        return all_predictions
    
    def match_predictions_with_actuals(
        self, 
        location_id: int,
        time_tolerance_minutes: int = 60
    ) -> Tuple[int, int]:
        """
        Match predictions with actual values for a location
        
        Args:
            location_id: Location to match
            time_tolerance_minutes: How close timestamps need to be (default 60 min)
        
        Returns:
            (matched_count, total_predictions)
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Matching predictions for location {location_id}")
        logger.info(f"{'='*70}")
        
        # Load actual data
        actual_df = self.load_location_data(location_id)
        
        if actual_df.empty:
            logger.warning(f"No actual data found for location {location_id}")
            return 0, 0
        
        logger.info(f"Loaded {len(actual_df)} actual data points")
        logger.info(f"Date range: {actual_df['timestamp'].min()} to {actual_df['timestamp'].max()}")
        
        # Load predictions
        all_predictions = self.load_predictions(days=7)
        
        # Filter for this location
        location_preds = [
            p for p in all_predictions 
            if p.get('location_id') == location_id and p.get('actual_aqi') is None
        ]
        
        if not location_preds:
            logger.info(f"No unmatched predictions found for location {location_id}")
            return 0, 0
        
        logger.info(f"Found {len(location_preds)} unmatched predictions")
        
        # Match predictions with actuals
        matched_count = 0
        tolerance = pd.Timedelta(minutes=time_tolerance_minutes)
        
        for pred in location_preds:
            try:
                # Parse forecast timestamp
                forecast_ts = pd.to_datetime(pred['forecast_timestamp'])
                
                # Find closest actual value within tolerance
                time_diffs = (actual_df['timestamp'] - forecast_ts).abs()
                closest_idx = time_diffs.idxmin()
                min_diff = time_diffs[closest_idx]
                
                if min_diff <= tolerance:
                    actual_aqi = actual_df.loc[closest_idx, 'aqi']
                    actual_pm25 = actual_df.loc[closest_idx, 'pm25']
                    
                    # Update prediction with actual value
                    pred['actual_aqi'] = float(actual_aqi)
                    pred['actual_pm25'] = float(actual_pm25)
                    pred['matched_at'] = datetime.now().isoformat()
                    pred['time_difference_minutes'] = min_diff.total_seconds() / 60
                    
                    # Calculate error
                    pred['error'] = abs(pred['predicted_aqi'] - actual_aqi)
                    pred['error_pct'] = (pred['error'] / actual_aqi * 100) if actual_aqi > 0 else 0
                    
                    matched_count += 1
                    
                    logger.debug(f"✅ Matched: forecast={forecast_ts}, "
                               f"predicted={pred['predicted_aqi']:.1f}, "
                               f"actual={actual_aqi:.1f}, "
                               f"error={pred['error']:.1f}")
                
            except Exception as e:
                logger.warning(f"Error matching prediction: {e}")
                continue
        
        # Save updated predictions back to file
        if matched_count > 0:
            self._save_updated_predictions(all_predictions)
        
        logger.info(f"\n📊 Matching Results:")
        logger.info(f"   Total predictions: {len(location_preds)}")
        logger.info(f"   Successfully matched: {matched_count}")
        logger.info(f"   Match rate: {matched_count/len(location_preds)*100:.1f}%")
        logger.info(f"{'='*70}\n")
        
        return matched_count, len(location_preds)
    
    def _save_updated_predictions(self, predictions: List[Dict]):
        """Save updated predictions back to daily log files"""
        # Group predictions by date
        by_date = {}
        for pred in predictions:
            try:
                pred_date = datetime.fromisoformat(pred['timestamp'].replace('Z', '+00:00')).date()
                date_key = pred_date.strftime("%Y%m%d")
                
                if date_key not in by_date:
                    by_date[date_key] = []
                by_date[date_key].append(pred)
            except Exception:
                continue
        
        # Save each date's predictions
        for date_key, date_preds in by_date.items():
            pred_file = self.predictions_dir / f"predictions_{date_key}.jsonl"
            
            try:
                with open(pred_file, 'w') as f:
                    for pred in date_preds:
                        f.write(json.dumps(pred) + '\n')
                
                logger.debug(f"Updated {pred_file}")
            except Exception as e:
                logger.error(f"Error saving {pred_file}: {e}")
    
    def match_all_locations(self) -> Dict:
        """Match predictions for all available locations"""
        logger.info("\n" + "="*70)
        logger.info("MATCHING ALL LOCATIONS")
        logger.info("="*70 + "\n")
        
        # Find all location files
        location_files = list(self.data_dir.glob("location_*.json"))
        
        if not location_files:
            logger.warning("No location files found!")
            return {}
        
        results = {}
        total_matched = 0
        total_predictions = 0
        
        for location_file in location_files:
            try:
                # Extract location ID from filename
                location_id = int(location_file.stem.split('_')[1])
                
                matched, total = self.match_predictions_with_actuals(location_id)
                
                results[location_id] = {
                    'matched': matched,
                    'total': total,
                    'match_rate': (matched / total * 100) if total > 0 else 0
                }
                
                total_matched += matched
                total_predictions += total
                
            except Exception as e:
                logger.error(f"Error processing {location_file}: {e}")
                continue
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("OVERALL SUMMARY")
        logger.info("="*70)
        logger.info(f"Locations processed: {len(results)}")
        logger.info(f"Total predictions matched: {total_matched}")
        logger.info(f"Total predictions: {total_predictions}")
        logger.info(f"Overall match rate: {total_matched/total_predictions*100:.1f}%")
        logger.info("="*70 + "\n")
        
        return results


def main():
    """Main function for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Match predictions with actual values')
    parser.add_argument('--location', type=int, help='Specific location ID to match')
    parser.add_argument('--all', action='store_true', help='Match all locations')
    parser.add_argument('--predictions-dir', default='api/logs/predictions', help='Predictions directory')
    parser.add_argument('--data-dir', default='dataset', help='Data directory')
    
    args = parser.parse_args()
    
    matcher = PredictionMatcher(
        predictions_dir=args.predictions_dir,
        data_dir=args.data_dir
    )
    
    if args.location:
        # Match specific location
        matcher.match_predictions_with_actuals(args.location)
    elif args.all:
        # Match all locations
        matcher.match_all_locations()
    else:
        # Default: match all
        matcher.match_all_locations()


if __name__ == "__main__":
    main()
