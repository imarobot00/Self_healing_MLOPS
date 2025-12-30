#!/usr/bin/env python3
"""
Test script for Air Quality Prediction API
"""
import requests
import json
from datetime import datetime

API_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("="*60)
    print("🏥 Health Check")
    print("="*60)
    response = requests.get(f"{API_URL}/health")
    print(json.dumps(response.json(), indent=2))
    print()

def test_prediction():
    """Test prediction endpoint"""
    print("="*60)
    print("🔮 Making Prediction")
    print("="*60)
    
    # Sample air quality data
    data = {
        "pm25": 45.2,
        "pm1": 32.1,
        "temperature": 18.5,
        "relativehumidity": 65.3,
        "um003": 1250.0
    }
    
    print(f"Input Data:")
    print(json.dumps(data, indent=2))
    print()
    
    response = requests.post(f"{API_URL}/predict", json=data)
    result = response.json()
    
    print(f"Prediction Result:")
    print(json.dumps(result, indent=2))
    print()
    
    # Interpret the result
    aqi = result['predicted_aqi']
    category = result['aqi_category']
    
    print("="*60)
    print(f"📊 RESULT: AQI = {aqi:.2f} ({category})")
    print("="*60)
    
    # Explain what this means
    if aqi <= 50:
        print("✅ Air quality is satisfactory, and air pollution poses little or no risk.")
    elif aqi <= 100:
        print("⚠️  Air quality is acceptable. However, there may be a risk for some people.")
    elif aqi <= 150:
        print("🚨 Members of sensitive groups may experience health effects.")
    elif aqi <= 200:
        print("🚨 Everyone may begin to experience health effects.")
    elif aqi <= 300:
        print("☠️  Health alert: everyone may experience more serious health effects.")
    else:
        print("☠️  Health warnings of emergency conditions. The entire population is likely to be affected.")
    print()

def test_multiple_scenarios():
    """Test different air quality scenarios"""
    print("="*60)
    print("🧪 Testing Multiple Scenarios")
    print("="*60)
    
    scenarios = [
        {
            "name": "Good Air Quality",
            "data": {"pm25": 10.0, "pm1": 5.0, "temperature": 20.0, "relativehumidity": 50.0, "um003": 500.0}
        },
        {
            "name": "Moderate Air Quality",
            "data": {"pm25": 35.0, "pm1": 25.0, "temperature": 25.0, "relativehumidity": 60.0, "um003": 1000.0}
        },
        {
            "name": "Unhealthy Air Quality",
            "data": {"pm25": 100.0, "pm1": 75.0, "temperature": 30.0, "relativehumidity": 70.0, "um003": 2500.0}
        },
        {
            "name": "Very Unhealthy Air",
            "data": {"pm25": 250.0, "pm1": 200.0, "temperature": 35.0, "relativehumidity": 40.0, "um003": 5000.0}
        }
    ]
    
    results = []
    for scenario in scenarios:
        response = requests.post(f"{API_URL}/predict", json=scenario['data'])
        result = response.json()
        results.append({
            'scenario': scenario['name'],
            'pm25': scenario['data']['pm25'],
            'aqi': result['predicted_aqi'],
            'category': result['aqi_category']
        })
    
    print(f"\n{'Scenario':<25} {'PM2.5':<10} {'Predicted AQI':<15} {'Category':<30}")
    print("-" * 80)
    for r in results:
        print(f"{r['scenario']:<25} {r['pm25']:<10} {r['aqi']:<15.2f} {r['category']:<30}")
    print()

def test_model_info():
    """Get model information"""
    print("="*60)
    print("📦 Model Information")
    print("="*60)
    response = requests.get(f"{API_URL}/model/info")
    print(json.dumps(response.json(), indent=2))
    print()

def main():
    """Run all tests"""
    print("\n" + "🚀 " + "="*58)
    print("   AIR QUALITY PREDICTION API - TEST SUITE")
    print("="*60 + "\n")
    
    try:
        test_health()
        test_model_info()
        test_prediction()
        test_multiple_scenarios()
        
        print("="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        print(f"\n📚 API Documentation: {API_URL}/docs")
        print(f"📊 Metrics: {API_URL}/metrics")
        print()
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API.")
        print(f"   Make sure the API is running on {API_URL}")
        print("\n   Start it with: python api/main.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
