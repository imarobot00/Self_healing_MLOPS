#!/usr/bin/env python3
"""
Quick test script for the data pipeline components.

Run this to verify all components are working correctly.
"""
import sys
from pathlib import Path

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        import requests
        import yaml
        from apscheduler.schedulers.blocking import BlockingScheduler
        print("  ✓ All dependencies installed")
        return True
    except ImportError as e:
        print(f"  ✗ Missing dependency: {e}")
        return False

def test_config():
    """Test that config file exists and is valid."""
    print("\nTesting configuration...")
    config_path = Path(__file__).parent / "config.yaml"
    
    if not config_path.exists():
        print(f"  ✗ Config file not found: {config_path}")
        return False
    
    try:
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Check required keys
        if "locations" not in config:
            print("  ✗ 'locations' not found in config")
            return False
        
        if not config["locations"]:
            print("  ✗ No locations configured")
            return False
        
        print(f"  ✓ Config valid: {len(config['locations'])} locations configured")
        return True
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return False

def test_api_connection():
    """Test OpenAQ API connectivity."""
    print("\nTesting API connection...")
    try:
        import requests
        import os
        
        api_key = os.getenv("OPENAQ_API_KEY", "e0f9842b3c8da78aa32e1b2489176fe50eb4ebe98dbdf07dca6a10449b68b9ad")
        headers = {"X-API-Key": api_key} if api_key else {}
        
        response = requests.get(
            "https://api.openaq.org/v3/locations/3459",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        print(f"  ✓ API connection successful (status: {response.status_code})")
        return True
    except requests.RequestException as e:
        print(f"  ✗ API connection failed: {e}")
        return False

def test_modules():
    """Test that pipeline modules can be imported."""
    print("\nTesting pipeline modules...")
    try:
        from incremental_loader import IncrementalLoader
        print("  ✓ incremental_loader")
        
        from validator import DataValidator
        print("  ✓ validator")
        
        from monitor import create_pipeline_monitor
        print("  ✓ monitor")
        
        from scheduler import PipelineScheduler
        print("  ✓ scheduler")
        
        return True
    except ImportError as e:
        print(f"  ✗ Module import failed: {e}")
        return False

def test_state_management():
    """Test state file handling."""
    print("\nTesting state management...")
    try:
        from incremental_loader import IncrementalLoader
        
        loader = IncrementalLoader()
        state = loader.state
        
        print(f"  ✓ State loaded successfully")
        if state.get("locations"):
            print(f"    Tracked locations: {len(state['locations'])}")
        else:
            print(f"    No previous runs (fresh start)")
        
        return True
    except Exception as e:
        print(f"  ✗ State management failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Data Pipeline Component Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Dependencies", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("API Connection", test_api_connection()))
    results.append(("Pipeline Modules", test_modules()))
    results.append(("State Management", test_state_management()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} | {name}")
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! Pipeline is ready to use.")
        print("\nNext steps:")
        print("  1. Review config.yaml for your location IDs")
        print("  2. Run: python incremental_loader.py --locations 3459")
        print("  3. Start scheduler: python scheduler.py --mode interval --interval 2")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
