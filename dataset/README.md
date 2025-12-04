Fetch OpenAQ location measurements
=================================

Usage
-----

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Fetch and save measurements for location `6093549`:

```bash
python3 fetch_openaq_location.py --location 6093549 --output location_6093549.json
```

If you prefer, set the `OPENAQ_API_KEY` environment variable to override the built-in key:

```bash
export OPENAQ_API_KEY="your_key_here"
python3 fetch_openaq_location.py --location 6093549 --output location_6093549.json
```

If `--output` is omitted, JSON will be printed to stdout.
