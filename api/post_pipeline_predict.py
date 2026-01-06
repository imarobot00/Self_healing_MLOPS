"""
Post-Pipeline Prediction Script

This script runs after the data pipeline updates location data.
It performs two critical tasks:
1. Makes new predictions for the next 5 hours based on latest data
2. Matches old predictions with newly arrived actual values

This enables automatic model performance tracking without manual intervention.

Usage:
    # Run after data pipeline
    python api/post_pipeline_predict.py
    
    # Run for specific locations only
    python api/post_pipeline_predict.py --locations 5509787 6093549
    
    # Skip prediction matching
    python api/post_pipeline_predict.py --no-match
"""

import sys
import requests
import json
import logging
from pathlib import Path
from datetime import datetime
import argparse
from typing import List

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from prediction_matcher import PredictionMatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PostPipelinePredictor:
    """Make predictions and match actuals after data pipeline runs"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        data_dir: str = "dataset",
        hours_ahead: int = 5
    ):
        self.api_url = api_url
        self.data_dir = Path(data_dir)
        self.hours_ahead = hours_ahead
        
        # Ensure data_dir is absolute
        if not self.data_dir.is_absolute():
            self.data_dir = self.data_dir.resolve()
        
        self.matcher = PredictionMatcher(
            predictions_dir="api/logs/predictions",
            data_dir=str(self.data_dir)
        )
    
    def get_available_locations(self) -> List[int]:
        """Get list of all available location IDs from data files"""
        location_files = list(self.data_dir.glob("location_*.json"))
        
        locations = []
        for f in location_files:
            try:
                location_id = int(f.stem.split('_')[1])
                locations.append(location_id)
            except (ValueError, IndexError):
                continue
        
        return sorted(locations)
    
    def check_api_health(self) -> bool:
        """Check if API is running"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def make_predictions_for_location(self, location_id: int) -> dict:
        """
        Make predictions for a specific location
        
        Returns dict with success status and details
        """
        try:
            logger.info(f"Making predictions for location {location_id}...")
            
            response = requests.get(
                f"{self.api_url}/forecast",
                params={
                    'location_id': location_id,
                    'hours': self.hours_ahead
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # API returns 'forecasts' not 'predictions'
                num_predictions = len(data.get('forecasts', []))
                
                logger.info(f"✅ Location {location_id}: {num_predictions} predictions made")
                
                return {
                    'success': True,
                    'location_id': location_id,
                    'num_predictions': num_predictions,
                    'forecasts': data.get('forecasts', [])
                }
            else:
                logger.warning(f"❌ Location {location_id}: API returned {response.status_code}")
                return {
                    'success': False,
                    'location_id': location_id,
                    'error': f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            logger.error(f"❌ Location {location_id}: {e}")
            return {
                'success': False,
                'location_id': location_id,
                'error': str(e)
            }
    
    def make_all_predictions(self, location_ids: List[int] = None) -> dict:
        """
        Make predictions for all (or specified) locations
        
        Args:
            location_ids: Specific locations to predict for, or None for all
        
        Returns:
            Summary dictionary with results
        """
        logger.info("\n" + "="*70)
        logger.info("MAKING PREDICTIONS AFTER DATA PIPELINE UPDATE")
        logger.info("="*70 + "\n")
        
        # Get locations to process
        if location_ids:
            locations = location_ids
            logger.info(f"Processing {len(locations)} specified locations")
        else:
            locations = self.get_available_locations()
            logger.info(f"Processing all {len(locations)} available locations")
        
        if not locations:
            logger.warning("No locations found!")
            return {'error': 'No locations available'}
        
        # Check API health
        if not self.check_api_health():
            logger.error("API is not running! Start with: uvicorn api.main:app")
            return {'error': 'API not available'}
        
        logger.info(f"API is healthy at {self.api_url}")
        logger.info(f"Predicting {self.hours_ahead} hours ahead for each location\n")
        
        # Make predictions for each location
        results = {
            'total_locations': len(locations),
            'successful': 0,
            'failed': 0,
            'total_predictions': 0,
            'details': []
        }
        
        for location_id in locations:
            result = self.make_predictions_for_location(location_id)
            results['details'].append(result)
            
            if result['success']:
                results['successful'] += 1
                results['total_predictions'] += result['num_predictions']
            else:
                results['failed'] += 1
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("PREDICTION SUMMARY")
        logger.info("="*70)
        logger.info(f"Locations processed: {results['total_locations']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Total predictions made: {results['total_predictions']}")
        logger.info("="*70 + "\n")
        
        return results
    
    def match_actuals(self, location_ids: List[int] = None):
        """
        Match predictions with actual values
        
        Args:
            location_ids: Specific locations to match, or None for all
        """
        logger.info("\n" + "="*70)
        logger.info("MATCHING PREDICTIONS WITH ACTUAL VALUES")
        logger.info("="*70 + "\n")
        
        if location_ids:
            # Match specific locations
            for location_id in location_ids:
                self.matcher.match_predictions_with_actuals(location_id)
        else:
            # Match all locations
            self.matcher.match_all_locations()
    
    def run_full_cycle(self, location_ids: List[int] = None, skip_matching: bool = False):
        """
        Complete post-pipeline cycle:
        1. Match old predictions with new actuals
        2. Make new predictions for next N hours
        
        Args:
            location_ids: Specific locations, or None for all
            skip_matching: If True, skip prediction matching step
        """
        logger.info("\n" + "="*70)
        logger.info("POST-PIPELINE PREDICTION CYCLE")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("="*70 + "\n")
        
        # Step 1: Match old predictions with newly arrived data
        if not skip_matching:
            logger.info("STEP 1: Matching old predictions with new actual values")
            self.match_actuals(location_ids)
        else:
            logger.info("STEP 1: Skipped (--no-match flag)")
        
        # Step 2: Make new predictions
        logger.info("\nSTEP 2: Making new predictions based on latest data")
        prediction_results = self.make_all_predictions(location_ids)
        
        # Final summary
        logger.info("\n" + "="*70)
        logger.info("POST-PIPELINE CYCLE COMPLETE")
        logger.info("="*70)
        logger.info(f"✅ New predictions: {prediction_results.get('total_predictions', 0)}")
        if not skip_matching:
            logger.info("✅ Old predictions matched with actuals")
        logger.info("="*70 + "\n")
        
        return prediction_results


def main():
    """Main function for standalone execution"""
    parser = argparse.ArgumentParser(
        description='Make predictions and match actuals after data pipeline runs'
    )
    parser.add_argument(
        '--locations',
        type=int,
        nargs='+',
        help='Specific location IDs to process (default: all)'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=5,
        help='Hours ahead to predict (default: 5)'
    )
    parser.add_argument(
        '--api-url',
        default='http://localhost:8000',
        help='API URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--data-dir',
        default='dataset',
        help='Data directory (default: dataset)'
    )
    parser.add_argument(
        '--no-match',
        action='store_true',
        help='Skip prediction matching step'
    )
    parser.add_argument(
        '--predict-only',
        action='store_true',
        help='Only make predictions (no matching)'
    )
    parser.add_argument(
        '--match-only',
        action='store_true',
        help='Only match predictions (no new predictions)'
    )
    
    args = parser.parse_args()
    
    predictor = PostPipelinePredictor(
        api_url=args.api_url,
        data_dir=args.data_dir,
        hours_ahead=args.hours
    )
    
    try:
        if args.match_only:
            # Only match actuals
            predictor.match_actuals(args.locations)
        elif args.predict_only:
            # Only make predictions
            predictor.make_all_predictions(args.locations)
        else:
            # Full cycle (match + predict)
            predictor.run_full_cycle(args.locations, skip_matching=args.no_match)
    
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
