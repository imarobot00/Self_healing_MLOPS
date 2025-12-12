#!/usr/bin/env python3
"""
Merge data from GitHub and local Docker runs.
Deduplicates records and combines both sources.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set

def load_json_file(file_path: Path) -> List[Dict]:
    """Load JSON array from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []

def get_record_key(record: Dict) -> str:
    """Generate unique key for a record."""
    location = record.get('locationId', 0)
    period = record.get('period', {})
    datetime_from = period.get('datetimeFrom', {}).get('utc', '')
    parameter = record.get('parameter', {}).get('parameterId', 0)
    
    return f"{location}_{datetime_from}_{parameter}"

def merge_location_data(location_id: int, data_dir: Path) -> Dict:
    """Merge data for a single location from multiple sources."""
    file_path = data_dir / f"location_{location_id}.json"
    
    # Load existing data
    records = load_json_file(file_path)
    
    print(f"\nLocation {location_id}:")
    print(f"  Records before merge: {len(records)}")
    
    # Deduplicate using unique keys
    seen_keys: Set[str] = set()
    unique_records: List[Dict] = []
    duplicates = 0
    
    for record in records:
        key = get_record_key(record)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_records.append(record)
        else:
            duplicates += 1
    
    # Sort by datetime
    try:
        unique_records.sort(
            key=lambda x: x.get('period', {}).get('datetimeFrom', {}).get('utc', ''),
            reverse=False
        )
    except Exception as e:
        print(f"  Warning: Could not sort records: {e}")
    
    print(f"  Duplicates removed: {duplicates}")
    print(f"  Records after merge: {len(unique_records)}")
    
    # Get date range
    if unique_records:
        first_date = unique_records[0].get('period', {}).get('datetimeFrom', {}).get('local', 'Unknown')
        last_date = unique_records[-1].get('period', {}).get('datetimeFrom', {}).get('local', 'Unknown')
        print(f"  Date range: {first_date} to {last_date}")
    
    return {
        'location_id': location_id,
        'total_records': len(unique_records),
        'duplicates_removed': duplicates,
        'records': unique_records
    }

def save_merged_data(location_id: int, records: List[Dict], data_dir: Path, backup: bool = True):
    """Save merged data to file with optional backup."""
    file_path = data_dir / f"location_{location_id}.json"
    
    # Create backup
    if backup and file_path.exists():
        backup_path = data_dir / f"location_{location_id}.json.backup"
        file_path.rename(backup_path)
        print(f"  Backup created: {backup_path.name}")
    
    # Save merged data
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"  Saved: {file_path.name}")

def main():
    """Main merge process."""
    data_dir = Path(__file__).parent
    
    # Location IDs to merge
    location_ids = [3459, 5506835, 5509787, 6093549, 6093550, 6093551, 
                   6133623, 6142022, 6142174, 6142175]
    
    print("=" * 70)
    print("DATA MERGE TOOL")
    print("Merging GitHub Actions data with Local Docker data")
    print("=" * 70)
    
    total_records_before = 0
    total_records_after = 0
    total_duplicates = 0
    
    for location_id in location_ids:
        file_path = data_dir / f"location_{location_id}.json"
        
        if not file_path.exists():
            print(f"\nLocation {location_id}: File not found, skipping...")
            continue
        
        # Merge data
        result = merge_location_data(location_id, data_dir)
        
        # Save merged data
        save_merged_data(location_id, result['records'], data_dir, backup=True)
        
        # Update statistics
        total_records_before += result['total_records'] + result['duplicates_removed']
        total_records_after += result['total_records']
        total_duplicates += result['duplicates_removed']
    
    print("\n" + "=" * 70)
    print("MERGE SUMMARY")
    print("=" * 70)
    print(f"Total records before merge: {total_records_before:,}")
    print(f"Total duplicates removed:   {total_duplicates:,}")
    print(f"Total records after merge:  {total_records_after:,}")
    print(f"\nBackup files created with .backup extension")
    print("If everything looks good, you can delete the backups:")
    print("  rm dataset/location_*.json.backup")
    print("=" * 70)

if __name__ == "__main__":
    main()
