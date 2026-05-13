#!/usr/bin/env python3
"""Flight search automation tool using the Duffel API (live inventory)."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import requests

DUFFEL_OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests"
DUFFEL_API_VERSION = "v2"


@dataclass(frozen=True)
class SearchConfig:
    origin: str
    destination: str
    target_date: date
    date_flex_days: int
    one_way: bool
    min_duration: Optional[int]
    max_duration: Optional[int]
    adults: int
    currency: str
    max_results_per_query: int
    output_csv: Optional[str]
    cabin_class: str


class ApiError(Exception):
    pass


class RateLimitError(ApiError):
    pass


class DuffelClient:
    def __init__(self, api_token: str, session: Optional[requests.Session] = None) -> None:
        self.api_token = api_token
        self.session = session or requests.Session()

    def search_offers(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date],
        adults: int,
        currency: str,
        max_results: int,
        cabin_class: str,
        retries: int = 3,
    ) -> List[dict]:
        slices = [{"origin": origin, "destination": destination, "departure_date": departure_date.isoformat()}]
        if return_date:
            slices.append(
                {
                    "origin": destination,
                    "destination": origin,
                    "departure_date": return_date.isoformat(),
                }
            )

        payload = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(adults)],
                "cabin_class": cabin_class,
                "max_connections": 1,
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": DUFFEL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for attempt in range(retries + 1):
            response = self.session.post(DUFFEL_OFFER_REQUESTS_URL, json=payload, headers=headers, timeout=45)

            if response.status_code in (200, 201):
                body = response.json().get("data", {})
                offers = body.get("offers", [])
                return offers[:max_results]

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2") or "2")
                if attempt < retries:
                    time.sleep(retry_after * (attempt + 1))
                    continue
                raise RateLimitError(f"Duffel rate limit reached: {response.text[:300]}")

            if 500 <= response.status_code < 600 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue

            raise ApiError(f"Duffel search failed ({response.status_code}): {response.text[:300]}")

        raise ApiError("Unexpected retry loop termination")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search for best flights over flexible dates.")
    parser.add_argument("--origin", required=True, help="IATA origin code (e.g., MXP)")
    parser.add_argument("--destination", required=True, help="IATA destination code (e.g., LIM)")
    parser.add_argument("--target-date", required=True, help="Target departure date (YYYY-MM-DD)")
    parser.add_argument("--date-flex-days", type=int, default=30)
    parser.add_argument("--one-way", action="store_true")
    parser.add_argument("--min-duration", type=int, default=5)
    parser.add_argument("--max-duration", type=int, default=21)
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--max-results-per-query", type=int, default=20)
    parser.add_argument("--cabin-class", default="economy", choices=["economy", "premium_economy", "business", "first"])
    parser.add_argument("--output-csv")
    parser.add_argument("--duffel-api-token", default=os.getenv("DUFFEL_API_TOKEN"))
    return parser.parse_args()


def date_range(center: date, flex_days: int) -> Iterable[date]:
    for offset in range(-flex_days, flex_days + 1):
        yield center + timedelta(days=offset)


def best_offer_summary(offers: List[dict], currency: str) -> Optional[Tuple[float, str]]:
    best_price: Optional[float] = None
    best_offer_id = ""

    for offer in offers:
        try:
            if offer.get("total_currency") and offer["total_currency"].upper() != currency.upper():
                continue
            price = float(offer["total_amount"])
            offer_id = offer.get("id", "N/A")
        except (KeyError, ValueError, TypeError):
            continue
        if best_price is None or price < best_price:
            best_price = price
            best_offer_id = offer_id

    if best_price is None:
        return None
    return best_price, best_offer_id


def validate_config(args: argparse.Namespace) -> SearchConfig:
    target = datetime.strptime(args.target_date, "%Y-%m-%d").date()
    if args.date_flex_days < 0 or args.adults < 1 or args.max_results_per_query < 1:
        raise ValueError("Invalid numeric argument values")

    min_duration = None if args.one_way else args.min_duration
    max_duration = None if args.one_way else args.max_duration
    if not args.one_way and (min_duration < 1 or max_duration < min_duration):
        raise ValueError("Invalid duration range")

    return SearchConfig(
        origin=args.origin.upper(),
        destination=args.destination.upper(),
        target_date=target,
        date_flex_days=args.date_flex_days,
        one_way=args.one_way,
        min_duration=min_duration,
        max_duration=max_duration,
        adults=args.adults,
        currency=args.currency.upper(),
        max_results_per_query=args.max_results_per_query,
        output_csv=args.output_csv,
        cabin_class=args.cabin_class,
    )


def run_search(client: DuffelClient, config: SearchConfig) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for dep_date in date_range(config.target_date, config.date_flex_days):
        return_dates = [None] if config.one_way else [dep_date + timedelta(days=d) for d in range(config.min_duration, config.max_duration + 1)]
        best_for_departure: Optional[Tuple[float, date, str]] = None
        for ret_date in return_dates:
            offers = client.search_offers(
                origin=config.origin,
                destination=config.destination,
                departure_date=dep_date,
                return_date=ret_date,
                adults=config.adults,
                currency=config.currency,
                max_results=config.max_results_per_query,
                cabin_class=config.cabin_class,
            )
            summary = best_offer_summary(offers, config.currency)
            if not summary:
                continue
            price, offer_id = summary
            if best_for_departure is None or price < best_for_departure[0]:
                best_for_departure = (price, ret_date if ret_date else dep_date, offer_id)

        row = {"origin": config.origin, "destination": config.destination, "departure_date": dep_date.isoformat()}
        if best_for_departure:
            row.update({"best_price": f"{best_for_departure[0]:.2f}", "best_offer_id": best_for_departure[2]})
            if not config.one_way:
                row["best_return_date"] = best_for_departure[1].isoformat()
        else:
            row.update({"best_price": "N/A", "best_offer_id": "N/A"})
            if not config.one_way:
                row["best_return_date"] = "N/A"
        rows.append(row)
    return rows


def print_summary(rows: List[Dict[str, str]], one_way: bool) -> None:
    print("\nBest flight prices by departure date")
    for row in rows:
        if one_way:
            print(f"{row['departure_date']} | {row['best_price']} | {row['best_offer_id']}")
        else:
            print(f"{row['departure_date']} | {row['best_return_date']} | {row['best_price']} | {row['best_offer_id']}")


def write_csv(rows: List[Dict[str, str]], csv_path: str, one_way: bool) -> None:
    fields = ["origin", "destination", "departure_date"] + ([] if one_way else ["best_return_date"]) + ["best_price", "best_offer_id"]
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    if not args.duffel_api_token:
        print("Missing Duffel API token. Set DUFFEL_API_TOKEN or --duffel-api-token.", file=sys.stderr)
        return 2
    try:
        config = validate_config(args)
        rows = run_search(DuffelClient(args.duffel_api_token), config)
    except ValueError as err:
        print(f"Invalid arguments: {err}", file=sys.stderr)
        return 2
    except RateLimitError as err:
        print(f"API rate limit reached: {err}", file=sys.stderr)
        return 3
    except (ApiError, requests.RequestException) as err:
        print(f"API/network error: {err}", file=sys.stderr)
        return 4

    print_summary(rows, config.one_way)
    if config.output_csv:
        write_csv(rows, config.output_csv, config.one_way)
        print(f"CSV summary written to: {config.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
