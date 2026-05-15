# Flight Search Tool (Python)

This repository contains a Python automation script that searches flights with **flexible dates** and (for round-trips) **flexible trip duration** using the **Duffel Flight Offers API**.

## Features

- Route-based search (example: `MIL` → `LIM`)
- Flexible departure window around a target date (e.g., ±30 days)
- Round-trip duration range (e.g., 5 to 21 days) or one-way mode
- Best price summary for each departure date
- Airline, airport route, flight code, layover, and total duration details for each best offer
- CSV output and console summary
- API authentication (Duffel bearer token)
- Error handling for:
  - Invalid input arguments
  - API rate limits (`429`) with retries
  - Temporary server errors (`5xx`) with retries

## Requirements

- Python 3.10+
- `requests`

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install requests
```

Set your Duffel access token as an environment variable:

```bash
export DUFFEL_ACCESS_TOKEN="..."
```

You can also pass the token explicitly via CLI flag:

- `--duffel-access-token`

## Usage

### Round-trip flexible search

```bash
python3 flight_search.py \
  --origin MIL \
  --destination LIM \
  --target-date 2026-08-10 \
  --date-flex-days 4 \
  --min-duration 13 \
  --max-duration 17
```

### One-way flexible search

```bash
python flight_search.py \
  --origin MIL \
  --destination LIM \
  --target-date 2026-07-15 \
  --date-flex-days 30 \
  --one-way \
  --output-csv mil_lim_oneway.csv
```

## Output

The script prints a summary by departure date and optionally writes CSV output.

Round-trip CSV columns:

- `origin`
- `destination`
- `departure_date`
- `best_return_date`
- `best_price`
- `currency`
- `airlines`
- `airports`
- `flight_codes`
- `flight_segments`
- `layovers`
- `total_duration`
- `mode`
- `best_offer_id`

One-way CSV columns:

- `origin`
- `destination`
- `departure_date`
- `best_price`
- `currency`
- `airlines`
- `airports`
- `flight_codes`
- `flight_segments`
- `layovers`
- `total_duration`
- `mode`
- `best_offer_id`

## Notes

- The script uses Duffel API v2 and creates offer requests with `return_offers=true`.
- Duffel test tokens start with `duffel_test_`; test mode can return unrealistic schedules, prices, and flight numbers.
- Duffel returns offer prices in your organisation's billing currency unless your account setup supports airline-provided currencies.
- City codes like `MIL` may work depending on API support; airport-specific codes (e.g., `MXP`) can be used if needed.
- Use `--min-connections-per-slice 1` to exclude direct-looking offers for routes where direct flights should not exist.
- The script defaults to `--max-connections-per-slice 2`, excluding offers with more than two layovers in any outbound or return slice.
- If you hit rate limits, the script retries according to `Retry-After` or Duffel's `ratelimit-reset` header when provided.
