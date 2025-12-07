#!/usr/bin/env python3
"""
Incremental data loader for OpenAQ measurements.

This module fetches only new measurements since the last successful run,
deduplicates records, and appends them to existing location JSON files.
State is tracked in .state.json to enable incremental loading.
"""
import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set
import requests

# Default API key fallback
DEFAULT_API_KEY = "e0f9842b3c8da78aa32e1b2489176fe50eb4ebe98dbdf07dca6a10449b68b9ad"
API_BASE = "https://api.openaq.org/v3"

STATE_FILE = Path(__file__).parent / ".state.json"


class IncrementalLoader:
    """Handles incremental loading of OpenAQ measurements with state tracking."""

    def __init__(self, api_key: Optional[str] = None, data_dir: Optional[Path] = None):
        self.api_key = api_key or os.getenv("OPENAQ_API_KEY") or DEFAULT_API_KEY
        self.data_dir = data_dir or Path(__file__).parent
        self.headers = {"X-API-Key": self.api_key} if self.api_key else {}
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load the last fetch state from .state.json."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load state file: {e}")
                return {}
        return {}

    def _save_state(self):
        """Save the current fetch state to .state.json."""
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error: Could not save state file: {e}")

    def _get_last_fetch_time(self, location_id: int) -> Optional[str]:
        """Get the last successful fetch timestamp for a location (ISO format)."""
        location_key = str(location_id)
        return self.state.get("locations", {}).get(location_key, {}).get("last_fetch_time")

    def _update_fetch_time(self, location_id: int, fetch_time: str, records_count: int):
        """Update the last fetch timestamp and record count for a location."""
        location_key = str(location_id)
        if "locations" not in self.state:
            self.state["locations"] = {}
        
        self.state["locations"][location_key] = {
            "last_fetch_time": fetch_time,
            "last_records_count": records_count,
            "last_successful_run": datetime.utcnow().isoformat() + "Z"
        }
        self._save_state()

    def fetch_measurements_since(
        self, 
        location_id: int, 
        since: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch measurements for a location since a specific datetime.
        
        Args:
            location_id: OpenAQ location ID
            since: ISO format datetime string (e.g., "2025-12-05T10:00:00Z")
                   If None, fetches from last_fetch_time or all available data
            limit: Records per page
            
        Returns:
            List of measurement dictionaries
        """
        if since is None:
            since = self._get_last_fetch_time(location_id)
        
        page = 1
        all_results: List[Dict] = []
        
        print(f"Fetching measurements for location {location_id}" + 
              (f" since {since}" if since else " (all available data)"))

        # First, get the location to find its sensors
        try:
            loc_url = f"{API_BASE}/locations/{location_id}"
            loc_resp = requests.get(loc_url, headers=self.headers, timeout=15)
            loc_resp.raise_for_status()
            loc_data = loc_resp.json().get("results") or []
            
            if not loc_data:
                print(f"  Location {location_id} not found")
                return all_results
            
            location = loc_data[0]
            sensors = location.get("sensors") or []
            
            if not sensors:
                print(f"  No sensors found for location {location_id}")
                return all_results
            
            print(f"  Found {len(sensors)} sensors for location")
            
            # Fetch measurements from each sensor
            for sensor in sensors:
                sensor_id = sensor.get("id")
                if not sensor_id:
                    continue
                
                parameter_name = sensor.get("parameter", {}).get("name", "unknown")
                print(f"  Fetching {parameter_name} data from sensor {sensor_id}...")
                
                page = 1
                while True:
                    url = f"{API_BASE}/sensors/{sensor_id}/measurements"
                    params = {"limit": limit, "page": page}
                    
                    # Add date_from filter if we have a since timestamp
                    if since:
                        params["date_from"] = since
                    
                    try:
                        resp = requests.get(url, params=params, headers=self.headers, timeout=30)
                        resp.raise_for_status()
                        data = resp.json()
                        
                        results = data.get("results") or []
                        if not results:
                            break
                        
                        all_results.extend(results)
                        
                        # Check if there are more pages
                        if len(results) < limit:
                            break
                        
                        page += 1
                        time.sleep(0.2)  # Rate limiting
                        
                    except requests.HTTPError as e:
                        print(f"    HTTP error for sensor {sensor_id}: {e}")
                        break
                    except Exception as e:
                        print(f"    Error for sensor {sensor_id}: {e}")
                        break
            
            if all_results:
                print(f"  Total fetched: {len(all_results)} records from {len(sensors)} sensors")
            else:
                print(f"  No new measurements found")

        except requests.HTTPError as e:
            print(f"HTTP error while fetching location: {e}")
            return all_results
        except Exception as e:
            print(f"Error while fetching data: {e}")
            return all_results

        return all_results

    def _get_record_key(self, record: Dict) -> str:
        """Generate a unique key for a measurement record for deduplication."""
        # Use combination of datetime, location, parameter, and sensor
        period = record.get("period", {})
        datetime_from = period.get("datetimeFrom", {}).get("utc", "")
        datetime_to = period.get("datetimeTo", {}).get("utc", "")
        
        location_id = record.get("locationId", "")
        parameter = record.get("parameter", {}).get("id", "")
        sensor_id = record.get("sensors", [{}])[0].get("id", "") if record.get("sensors") else ""
        
        return f"{location_id}_{parameter}_{sensor_id}_{datetime_from}_{datetime_to}"

    def _deduplicate_records(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        """Remove duplicate records from new batch."""
        # Build set of existing record keys
        existing_keys: Set[str] = {self._get_record_key(r) for r in existing}
        
        # Filter out duplicates from new records
        deduplicated = []
        duplicates = 0
        
        for record in new:
            key = self._get_record_key(record)
            if key not in existing_keys:
                deduplicated.append(record)
                existing_keys.add(key)  # Prevent duplicates within new batch
            else:
                duplicates += 1
        
        if duplicates > 0:
            print(f"  Removed {duplicates} duplicate records")
        
        return deduplicated

    def load_existing_data(self, location_id: int) -> List[Dict]:
        """Load existing data from location JSON file."""
        json_file = self.data_dir / f"location_{location_id}.json"
        
        if not json_file.exists():
            print(f"  No existing data file found: {json_file}")
            return []
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    print(f"  Loaded {len(data)} existing records")
                    return data
                else:
                    print(f"  Warning: Unexpected data format in {json_file}")
                    return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Error loading existing data: {e}")
            return []

    def save_data(self, location_id: int, data: List[Dict]):
        """Save data to location JSON file."""
        json_file = self.data_dir / f"location_{location_id}.json"
        
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Saved {len(data)} total records to {json_file}")
        except IOError as e:
            print(f"  Error saving data: {e}")
            raise

    def process_location(self, location_id: int) -> Dict:
        """
        Process incremental loading for a single location.
        
        Returns:
            Dict with processing statistics
        """
        print(f"\n{'='*60}")
        print(f"Processing location {location_id}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Load existing data
        existing_data = self.load_existing_data(location_id)
        
        # Fetch new measurements
        new_measurements = self.fetch_measurements_since(location_id)
        
        if not new_measurements:
            print(f"  No new measurements found")
            elapsed = time.time() - start_time
            return {
                "location_id": location_id,
                "new_records": 0,
                "total_records": len(existing_data),
                "duplicates_removed": 0,
                "elapsed_time": elapsed,
                "status": "success"
            }
        
        # Deduplicate
        deduplicated = self._deduplicate_records(existing_data, new_measurements)
        
        # Merge and save
        merged_data = existing_data + deduplicated
        self.save_data(location_id, merged_data)
        
        # Update state with the latest measurement timestamp
        if merged_data:
            # Find the most recent datetime in the data
            latest_time = None
            for record in merged_data:
                datetime_str = record.get("period", {}).get("datetimeTo", {}).get("utc")
                if datetime_str and (latest_time is None or datetime_str > latest_time):
                    latest_time = datetime_str
            
            if latest_time:
                self._update_fetch_time(location_id, latest_time, len(deduplicated))
        
        elapsed = time.time() - start_time
        
        stats = {
            "location_id": location_id,
            "new_records": len(deduplicated),
            "total_records": len(merged_data),
            "duplicates_removed": len(new_measurements) - len(deduplicated),
            "elapsed_time": elapsed,
            "status": "success"
        }
        
        print(f"\n  ✓ Completed in {elapsed:.2f}s")
        print(f"    - New records: {stats['new_records']}")
        print(f"    - Total records: {stats['total_records']}")
        
        return stats

    def process_all_locations(self, location_ids: List[int]) -> Dict:
        """
        Process incremental loading for multiple locations.
        
        Returns:
            Dict with overall statistics
        """
        overall_start = time.time()
        all_stats = []
        
        print(f"\n{'#'*60}")
        print(f"# Starting incremental data loading for {len(location_ids)} locations")
        print(f"# {datetime.utcnow().isoformat()}Z")
        print(f"{'#'*60}")
        
        for location_id in location_ids:
            try:
                stats = self.process_location(location_id)
                all_stats.append(stats)
            except Exception as e:
                print(f"\n  ✗ Error processing location {location_id}: {e}")
                all_stats.append({
                    "location_id": location_id,
                    "status": "error",
                    "error": str(e)
                })
        
        overall_elapsed = time.time() - overall_start
        
        summary = {
            "start_time": datetime.utcnow().isoformat() + "Z",
            "total_locations": len(location_ids),
            "successful": sum(1 for s in all_stats if s.get("status") == "success"),
            "failed": sum(1 for s in all_stats if s.get("status") == "error"),
            "total_new_records": sum(s.get("new_records", 0) for s in all_stats),
            "total_elapsed_time": overall_elapsed,
            "location_stats": all_stats
        }
        
        print(f"\n{'#'*60}")
        print(f"# Pipeline completed in {overall_elapsed:.2f}s")
        print(f"# Successful: {summary['successful']}/{summary['total_locations']}")
        print(f"# Total new records: {summary['total_new_records']}")
        print(f"{'#'*60}\n")
        
        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally fetch OpenAQ measurements and update location JSON files."
    )
    parser.add_argument(
        "--locations", "-l",
        type=int,
        nargs="+",
        default=[3459],
        help="Location IDs to fetch (space-separated, default: 3459)"
    )
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=None,
        help="OpenAQ API key (overrides env and fallback)"
    )
    parser.add_argument(
        "--data-dir", "-d",
        type=str,
        default=None,
        help="Directory for data files (default: current directory)"
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset state and fetch all data (ignores last fetch time)"
    )
    
    args = parser.parse_args()
    
    # Reset state if requested
    if args.reset_state and STATE_FILE.exists():
        print("Resetting state...")
        STATE_FILE.unlink()
    
    # Initialize loader
    data_dir = Path(args.data_dir) if args.data_dir else None
    loader = IncrementalLoader(api_key=args.api_key, data_dir=data_dir)
    
    # Process all locations
    summary = loader.process_all_locations(args.locations)
    
    # Exit with appropriate code
    if summary["failed"] > 0:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()
