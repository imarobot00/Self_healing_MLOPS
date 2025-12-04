#!/usr/bin/env python3
"""
Fetch measurements for an OpenAQ location and save them as JSON.

Usage:
  python fetch_openaq_location.py --location 3459 --output location_3459.json

It will use the environment variable `OPENAQ_API_KEY` if set; otherwise it falls back
to a built-in API key found in the user's notebook.
"""
import argparse
import json
import os
import time
import requests
from typing import List, Dict

# Default API key fallback (taken from the notebook in this workspace)
DEFAULT_API_KEY = "e0f9842b3c8da78aa32e1b2489176fe50eb4ebe98dbdf07dca6a10449b68b9ad"

API_BASE = "https://api.openaq.org/v3"


def fetch_measurements_for_location(location_id: int, api_key: str, limit: int = 1000) -> List[Dict]:
    """Fetch all measurements for the given location id using the locations measurements endpoint.

    This will page through results until no more data is returned.
    """
    headers = {"X-API-Key": api_key} if api_key else {}
    page = 1
    all_results: List[Dict] = []

    # First try: measurements endpoint filtered by location_id
    try:
        while True:
            url = f"{API_BASE}/measurements"
            params = {"limit": limit, "page": page, "location_id": location_id}
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or []
            if not results:
                break

            all_results.extend(results)

            if len(results) < limit:
                break

            page += 1
            time.sleep(0.2)

        # If we found any results, return them
        if all_results:
            return all_results
    except requests.HTTPError:
        # fallthrough to sensors-based approach
        pass

    # Fallback: fetch the location resource and then fetch per-sensor measurements
    try:
        loc_url = f"{API_BASE}/locations/{location_id}"
        resp = requests.get(loc_url, headers=headers, timeout=15)
        resp.raise_for_status()
        loc_data = resp.json().get("results") or []
        if loc_data:
            location = loc_data[0]
        else:
            location = None
    except Exception:
        location = None

    if not location:
        return all_results

    sensors = location.get("sensors") or []
    for sensor in sensors:
        sensor_id = sensor.get("id")
        if not sensor_id:
            continue

        page = 1
        while True:
            url = f"{API_BASE}/sensors/{sensor_id}/measurements"
            params = {"limit": limit, "page": page}
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.HTTPError:
                break

            results = data.get("results") or []
            if not results:
                break

            all_results.extend(results)

            if len(results) < limit:
                break

            page += 1
            time.sleep(0.2)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Fetch OpenAQ location measurements and save as JSON.")
    parser.add_argument("--location", "-l", type=int, default=3459, help="OpenAQ location ID to fetch")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON filename (default: prints to stdout)")
    parser.add_argument("--api-key", "-k", type=str, default=None, help="OpenAQ API key (overrides env and fallback)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("OPENAQ_API_KEY") or DEFAULT_API_KEY

    print(f"Fetching measurements for location {args.location}...")
    try:
        results = fetch_measurements_for_location(args.location, api_key)
    except requests.HTTPError as e:
        print("HTTP error while fetching data:", e)
        return
    except Exception as e:
        print("Error while fetching data:", e)
        return

    print(f"Fetched {len(results)} measurement records.")

    if args.output:
        out_path = args.output
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Saved JSON to {out_path}")
    else:
        # Print JSON to stdout
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
