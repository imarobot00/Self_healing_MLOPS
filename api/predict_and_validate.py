#!/usr/bin/env python3
"""
Make a prediction for 2 hours from now and validate it later
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time

API_URL = "http://localhost:8000"
PREDICTIONS_FILE = Path("api/predictions_to_validate.json")

def get_latest_data(location_id=6142174):
    """Get the most recent data from location file"""
    location_file = Path(f"dataset/location_{location_id}.json")
    
    if not location_file.exists():
        raise FileNotFoundError(f"Location file not found: {location_file}")
    
    with open(location_file, 'r') as f:
        data = json.load(f)
    
    # Convert to DataFrame and sort by time
    df = pd.DataFrame(data)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    # Get the most recent record
    latest = df.iloc[-1]
    
    return {
        'datetime': latest['datetime'],
        'pm25': latest['pm25'],
        'pm1': latest['pm1'],
        'temperature': latest['temperature'],
        'relativehumidity': latest['relativehumidity'],
        'um003': latest['um003']
    }

def make_prediction(data):
    """Make prediction via API"""
    response = requests.post(
        f"{API_URL}/predict",
        json=data
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

def save_prediction(current_data, prediction_result):
    """Save prediction for later validation"""
    predictions = []
    
    # Load existing predictions if file exists
    if PREDICTIONS_FILE.exists():
        with open(PREDICTIONS_FILE, 'r') as f:
            predictions = json.load(f)
    
    # Add new prediction
    prediction_record = {
        'prediction_time': datetime.now().isoformat(),
        'target_time': (datetime.now() + timedelta(hours=2)).isoformat(),
        'current_data': current_data,
        'predicted_aqi': prediction_result['predicted_aqi'],
        'predicted_category': prediction_result['aqi_category'],
        'model_version': prediction_result['model_version'],
        'actual_aqi': None,  # Will be filled in after 2 hours
        'validated': False
    }
    
    predictions.append(prediction_record)
    
    # Save
    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(predictions, f, indent=2)
    
    return prediction_record

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

def validate_past_predictions():
    """Check if any past predictions can be validated now"""
    if not PREDICTIONS_FILE.exists():
        return []
    
    with open(PREDICTIONS_FILE, 'r') as f:
        predictions = json.load(f)
    
    validated = []
    now = datetime.now()
    
    for pred in predictions:
        if pred['validated']:
            continue
        
        target_time = pd.to_datetime(pred['target_time'])
        
        # If target time has passed, try to validate
        if now >= target_time:
            # Load actual data from location file
            try:
                location_id = 6142174
                location_file = Path(f"dataset/location_{location_id}.json")
                
                with open(location_file, 'r') as f:
                    data = json.load(f)
                
                df = pd.DataFrame(data)
                df['datetime'] = pd.to_datetime(df['datetime'])
                
                # Find data closest to target time (within 30 minutes)
                time_diff = abs(df['datetime'] - target_time)
                closest_idx = time_diff.idxmin()
                
                if time_diff[closest_idx] <= timedelta(minutes=30):
                    actual_row = df.iloc[closest_idx]
                    actual_aqi = calculate_aqi(actual_row['pm25'])
                    
                    # Calculate error
                    error = abs(pred['predicted_aqi'] - actual_aqi)
                    error_pct = (error / actual_aqi) * 100 if actual_aqi > 0 else 0
                    
                    pred['actual_aqi'] = float(actual_aqi)
                    pred['actual_pm25'] = float(actual_row['pm25'])
                    pred['actual_datetime'] = str(actual_row['datetime'])
                    pred['error'] = float(error)
                    pred['error_pct'] = float(error_pct)
                    pred['validated'] = True
                    
                    validated.append(pred)
                    
            except Exception as e:
                print(f"Could not validate prediction: {e}")
    
    # Save updated predictions
    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(predictions, f, indent=2)
    
    return validated

def main():
    print("\n" + "="*70)
    print("🔮 2-HOUR AQI PREDICTION & VALIDATION")
    print("="*70 + "\n")
    
    try:
        # First, check if any past predictions can be validated
        print("📊 Checking past predictions...")
        validated = validate_past_predictions()
        
        if validated:
            print(f"\n✅ Validated {len(validated)} past prediction(s):\n")
            for pred in validated:
                print(f"Prediction made: {pred['prediction_time']}")
                print(f"Target time: {pred['target_time']}")
                print(f"Predicted AQI: {pred['predicted_aqi']:.2f}")
                print(f"Actual AQI: {pred['actual_aqi']:.2f}")
                print(f"Error: {pred['error']:.2f} AQI points ({pred['error_pct']:.1f}%)")
                
                if pred['error'] <= 10:
                    print("✅ EXCELLENT prediction (error < 10)")
                elif pred['error'] <= 20:
                    print("✅ GOOD prediction (error < 20)")
                elif pred['error'] <= 30:
                    print("⚠️  ACCEPTABLE prediction (error < 30)")
                else:
                    print("❌ NEEDS IMPROVEMENT (error > 30)")
                print()
        else:
            print("No past predictions ready for validation yet.\n")
        
        # Get latest sensor data
        print("📡 Getting latest sensor data...")
        latest_data = get_latest_data()
        
        print(f"Latest data from: {latest_data['datetime']}")
        print(f"  PM2.5: {latest_data['pm25']:.2f} µg/m³")
        print(f"  PM1: {latest_data['pm1']:.2f} µg/m³")
        print(f"  Temperature: {latest_data['temperature']:.2f} °C")
        print(f"  Humidity: {latest_data['relativehumidity']:.2f} %")
        print(f"  Particle count: {latest_data['um003']:.2f}")
        print()
        
        # Make prediction for 2 hours from now
        print("🤖 Making prediction for 2 hours from now...")
        prediction_data = {
            'pm25': latest_data['pm25'],
            'pm1': latest_data['pm1'],
            'temperature': latest_data['temperature'],
            'relativehumidity': latest_data['relativehumidity'],
            'um003': latest_data['um003']
        }
        
        result = make_prediction(prediction_data)
        
        print(f"\n✨ PREDICTION RESULT:")
        print(f"  Predicted AQI: {result['predicted_aqi']:.2f}")
        print(f"  Category: {result['aqi_category']}")
        print(f"  Model: {result['model_version']}")
        print(f"  Target time: {(datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Save for validation
        saved = save_prediction(latest_data, result)
        print(f"💾 Prediction saved for validation")
        print(f"   Run this script again after {saved['target_time'][:19]} to validate!")
        print()
        
        print("="*70)
        print("✅ Done! Check back in 2 hours to validate the prediction.")
        print("="*70)
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API.")
        print(f"   Make sure the API is running on {API_URL}")
        print("\n   Start it with:")
        print("   python api/main.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
