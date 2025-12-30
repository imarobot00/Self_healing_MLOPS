#!/usr/bin/env python3
"""
Simple 2-Hour Prediction Test
Uses latest data from test_data.csv to make prediction
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path

API_URL = "http://localhost:8000"

def calculate_aqi(pm25):
    """Calculate AQI from PM2.5"""
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
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
            return aqi
    
    if pm25 > 500.4:
        return 500
    return 0

def main():
    print("\n" + "="*70)
    print("🔮 TESTING 2-HOUR AQI PREDICTION")
    print("="*70 + "\n")
    
    # Load test data
    test_file = Path("dataset/preprocessed/test_data.csv")
    df = pd.read_csv(test_file)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    print(f"📊 Loaded {len(df):,} test records")
    print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print()
    
    # Get a sample from the middle for testing
    test_idx = len(df) // 2
    current_row = df.iloc[test_idx]
    
    # The "actual" 2 hours later
    target_idx = min(test_idx + 2, len(df) - 1)  # 2 hours later
    target_row = df.iloc[target_idx]
    
    print(f"📍 Test Case:")
    print(f"   Current time: {current_row['datetime']}")
    print(f"   Target time: {target_row['datetime']} (2 hours later)")
    print()
    
    print(f"📡 Current Conditions:")
    print(f"   PM2.5: {current_row['pm25']:.2f} µg/m³")
    print(f"   PM1: {current_row['pm1']:.2f} µg/m³")
    print(f"   Temperature: {current_row['temperature']:.2f} °C")
    print(f"   Humidity: {current_row['relativehumidity']:.2f} %")
    print(f"   Particle count: {current_row['um003']:.2f}")
    print(f"   Current AQI: {current_row['aqi']:.2f}")
    print()
    
    # Make prediction
    prediction_data = {
        'pm25': float(current_row['pm25']),
        'pm1': float(current_row['pm1']),
        'temperature': float(current_row['temperature']),
        'relativehumidity': float(current_row['relativehumidity']),
        'um003': float(current_row['um003'])
    }
    
    print("🤖 Making prediction...")
    try:
        response = requests.post(f"{API_URL}/predict", json=prediction_data)
        if response.status_code == 200:
            result = response.json()
            
            predicted_aqi = result['predicted_aqi']
            actual_aqi = target_row['aqi']
            error = abs(predicted_aqi - actual_aqi)
            error_pct = (error / actual_aqi) * 100 if actual_aqi > 0 else 0
            
            print()
            print("="*70)
            print("📊 PREDICTION RESULTS")
            print("="*70)
            print(f"\n✨ Predicted AQI (2 hours ahead): {predicted_aqi:.2f}")
            print(f"   Category: {result['aqi_category']}")
            print(f"   Model: {result['model_version']}")
            print()
            print(f"🎯 Actual AQI (at target time): {actual_aqi:.2f}")
            print(f"   Actual PM2.5: {target_row['pm25']:.2f} µg/m³")
            print()
            print(f"📈 Prediction Error:")
            print(f"   Absolute Error: {error:.2f} AQI points")
            print(f"   Percentage Error: {error_pct:.1f}%")
            print()
            
            # Evaluate accuracy
            if error <= 10:
                print("✅ EXCELLENT prediction (error < 10 AQI points)")
                print("   This is production-ready accuracy!")
            elif error <= 20:
                print("✅ GOOD prediction (error < 20 AQI points)")
                print("   This is acceptable for most use cases.")
            elif error <= 30:
                print("⚠️  ACCEPTABLE prediction (error < 30 AQI points)")
                print("   May need improvement for critical applications.")
            else:
                print("❌ NEEDS IMPROVEMENT (error > 30 AQI points)")
                print("   Consider retraining or feature engineering.")
            
            print("\n" + "="*70)
            
            # Test a few more samples
            print("\n🧪 Testing 5 more random samples...\n")
            
            errors = []
            for i in range(5):
                idx = (test_idx + i * 100) % (len(df) - 2)
                curr = df.iloc[idx]
                target = df.iloc[idx + 2]
                
                pred_data = {
                    'pm25': float(curr['pm25']),
                    'pm1': float(curr['pm1']),
                    'temperature': float(curr['temperature']),
                    'relativehumidity': float(curr['relativehumidity']),
                    'um003': float(curr['um003'])
                }
                
                resp = requests.post(f"{API_URL}/predict", json=pred_data)
                if resp.status_code == 200:
                    pred_aqi = resp.json()['predicted_aqi']
                    actual = target['aqi']
                    err = abs(pred_aqi - actual)
                    errors.append(err)
                    
                    status = "✅" if err < 10 else "⚠️" if err < 20 else "❌"
                    print(f"{status} Sample {i+1}: Predicted {pred_aqi:.2f}, Actual {actual:.2f}, Error {err:.2f}")
            
            if errors:
                print(f"\n📊 Summary Statistics:")
                print(f"   Mean Error: {sum(errors)/len(errors):.2f} AQI points")
                print(f"   Min Error: {min(errors):.2f}")
                print(f"   Max Error: {max(errors):.2f}")
                print(f"   Accuracy (errors <10): {sum(1 for e in errors if e < 10)}/{len(errors)}")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API.")
        print(f"   Make sure the API is running on {API_URL}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
