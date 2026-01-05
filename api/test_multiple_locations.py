#!/usr/bin/env python3
"""
Test script to create predictions for multiple locations at past timestamps
so we can immediately see metrics per location
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Locations with recent data up to 11:00 AM
locations = [5506835, 5509787, 6093549, 6093551, 6133623, 6142022]

print("🚀 Creating test predictions for multiple locations...\n")

# Create predictions for past hours (7 AM to 11 AM)
for hour in range(7, 12):
    timestamp = f"2026-01-05T{hour:02d}:00:00Z"
    print(f"⏰ Creating predictions for {timestamp}...")
    
    for loc_id in locations:
        # Simulate a forecast at this past time
        try:
            response = requests.post(
                f"{BASE_URL}/predict",
                json={
                    "location_id": loc_id,
                    "pm25": 50.0 + (hour - 7) * 10,  # Varying PM2.5
                    "temperature": 15.0 + hour,
                    "humidity": 65.0,
                    "wind_speed": 2.5,
                    "hour": hour,
                    "day_of_week": 0,
                    "pm25_lag_1h": 48.0,
                    "pm25_lag_2h": 46.0,
                    "pm25_rolling_3h": 48.0,
                    "pm25_rolling_6h": 47.0,
                    "pm25_rolling_12h": 46.0,
                    "temp_rolling_3h": 14.5,
                    "humidity_rolling_3h": 66.0,
                    "forecast_timestamp": timestamp
                }
            )
            if response.status_code == 200:
                print(f"  ✓ Location {loc_id}")
            else:
                print(f"  ✗ Location {loc_id}: {response.status_code}")
        except Exception as e:
            print(f"  ✗ Location {loc_id}: Error - {e}")

print("\n📥 Updating actuals from dataset...")
response = requests.post(f"{BASE_URL}/monitoring/update-actuals")
print(f"Response: {response.json()}")

# Wait for background task
import time
time.sleep(5)

print("\n📊 Location Metrics Summary:\n")
response = requests.get(f"{BASE_URL}/monitoring/locations")
location_metrics = response.json()['location_metrics']

if location_metrics:
    # Sort by MAE (highest error first)
    sorted_locations = sorted(
        location_metrics.items(), 
        key=lambda x: x[1]['mae'] if x[1]['mae'] is not None else -1,
        reverse=True
    )
    
    print(f"{'Location':<12} {'Count':<8} {'MAE':<10} {'RMSE':<10} {'R²':<10} {'Max Error':<12} {'Status'}")
    print("-" * 85)
    
    for loc_id, metrics in sorted_locations:
        mae = f"{metrics['mae']:.2f}" if metrics['mae'] is not None else "N/A"
        rmse = f"{metrics['rmse']:.2f}" if metrics['rmse'] is not None else "N/A"
        r2 = f"{metrics['r2']:.3f}" if metrics['r2'] is not None else "N/A"
        max_err = f"{metrics['max_error']:.1f}" if metrics['max_error'] is not None else "N/A"
        status = metrics['status']
        
        status_icon = "🔴" if status == "degraded" else "🟢" if status == "good" else "⚪"
        
        print(f"{loc_id:<12} {metrics['count']:<8} {mae:<10} {rmse:<10} {r2:<10} {max_err:<12} {status_icon} {status}")
else:
    print("No location metrics available yet")

print(f"\n✅ Done! Check the dashboard at {BASE_URL}/monitoring")
