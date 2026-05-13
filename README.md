# Flight Search Tool (Python + Duffel)

This script searches **live flight inventory** through the **Duffel API** across a flexible departure-date window and flexible trip durations.

## Requirements
- Python 3.10+
- `requests`

```bash
pip install requests
```

## Duffel credentials
Create an account and API token at:
- https://duffel.com/
- https://duffel.com/docs/api

Set token:

```bash
export DUFFEL_API_TOKEN="your_duffel_token"
```

## Usage

```bash
python flight_search.py \
  --origin MXP \
  --destination LIM \
  --target-date 2026-07-15 \
  --date-flex-days 30 \
  --min-duration 7 \
  --max-duration 18 \
  --adults 1 \
  --currency EUR \
  --cabin-class economy \
  --output-csv mxp_lim_summary.csv
```

One-way mode:

```bash
python flight_search.py --origin MXP --destination LIM --target-date 2026-07-15 --date-flex-days 30 --one-way
```

## Output
Per departure date, the script prints the lowest fare found and writes optional CSV with:
- `origin`, `destination`, `departure_date`
- `best_return_date` (round-trip mode)
- `best_price`, `best_offer_id`

## Notes
- Uses Duffel `POST /air/offer_requests`.
- Includes retry handling for rate limits (`429`) and transient server errors (`5xx`).
