#!/usr/bin/env python3
"""
Simple test script to verify the FastAPI prediction endpoint works.
"""

import requests
import json
from datetime import datetime

# API URL
API_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n" + "="*50)
    print("🏥 Testing Health Endpoint")
    print("="*50)
    
    response = requests.get(f"{API_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_prediction():
    """Test prediction endpoint with sample data"""
    print("\n" + "="*50)
    print("🔮 Testing Prediction Endpoint")
    print("="*50)
    
    # Sample input data (typical winter morning in Ranibari)
    sample_data = {
        "pm25": 65.3,
        "pm1": 48.2,
        "temperature": 12.5,
        "relativehumidity": 72.8,
        "um003": 2340.5
    }
    
    print(f"\n📊 Input Data:")
    print(json.dumps(sample_data, indent=2))
    
    response = requests.post(
        f"{API_URL}/predict",
        json=sample_data
    )
    
    print(f"\n✅ Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n🎯 Prediction Results:")
        print(f"  - Predicted AQI: {result['predicted_aqi']}")
        print(f"  - Category: {result['aqi_category']}")
        print(f"  - Model Version: {result['model_version']}")
        print(f"  - Timestamp: {result['timestamp']}")
        return True
    else:
        print(f"\n❌ Error: {response.text}")
        return False

def test_model_info():
    """Test model info endpoint"""
    print("\n" + "="*50)
    print("📊 Testing Model Info Endpoint")
    print("="*50)
    
    response = requests.get(f"{API_URL}/model/info")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_multiple_predictions():
    """Test multiple prediction scenarios"""
    print("\n" + "="*50)
    print("🧪 Testing Multiple Scenarios")
    print("="*50)
    
    scenarios = [
        {
            "name": "Good Air Quality (Morning)",
            "data": {
                "pm25": 25.0,
                "pm1": 18.0,
                "temperature": 18.0,
                "relativehumidity": 60.0,
                "um003": 1000.0
            }
        },
        {
            "name": "Moderate Pollution (Afternoon)",
            "data": {
                "pm25": 50.0,
                "pm1": 38.0,
                "temperature": 24.0,
                "relativehumidity": 55.0,
                "um003": 1800.0
            }
        },
        {
            "name": "Unhealthy (Evening)",
            "data": {
                "pm25": 120.0,
                "pm1": 95.0,
                "temperature": 15.0,
                "relativehumidity": 75.0,
                "um003": 4200.0
            }
        }
    ]
    
    results = []
    for scenario in scenarios:
        print(f"\n📍 Scenario: {scenario['name']}")
        response = requests.post(f"{API_URL}/predict", json=scenario['data'])
        
        if response.status_code == 200:
            result = response.json()
            print(f"   PM2.5: {scenario['data']['pm25']} → AQI: {result['predicted_aqi']} ({result['aqi_category']})")
            results.append(result)
        else:
            print(f"   ❌ Error: {response.status_code}")
    
    return len(results) == len(scenarios)

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🚀 FASTAPI PREDICTION API - TEST SUITE")
    print("="*70)
    print(f"⏰ Test Time: {datetime.now()}")
    print(f"🌐 API URL: {API_URL}")
    
    results = []
    
    try:
        # Run tests
        results.append(("Health Check", test_health()))
        results.append(("Prediction", test_prediction()))
        results.append(("Model Info", test_model_info()))
        results.append(("Multiple Scenarios", test_multiple_predictions()))
        
        # Summary
        print("\n" + "="*70)
        print("📋 TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status} - {test_name}")
        
        print("\n" + "="*70)
        print(f"🎯 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✨ All tests passed! Your API is working perfectly! 🎉")
        else:
            print("⚠️  Some tests failed. Check the logs above.")
        print("="*70)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API")
        print("💡 Make sure the FastAPI server is running:")
        print("   cd api && python3 main.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()
