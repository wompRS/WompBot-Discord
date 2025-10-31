"""
Warm iRacing caches for all active series in the current season.

Run inside the bot container:

    docker-compose exec bot python -m bot.scripts.warm_iracing_cache

Optional flags:
    --limit N   Only process the first N series (handy for testing)
    --sleep S   Delay S seconds between meta requests (default: 0.5)
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import List, Optional, Set

from credential_manager import CredentialManager
from database import Database
from features.iracing import iRacingIntegration
from features.iracing_meta import MetaAnalyzer


async def _ensure_meta_analyzer(integration: iRacingIntegration) -> MetaAnalyzer:
    """Return a MetaAnalyzer bound to the integration's authenticated client."""
    if integration._meta_analyzer is not None:  # type: ignore[attr-defined]
        return integration._meta_analyzer  # type: ignore[attr-defined]

    client = await integration._get_client()
    integration._meta_analyzer = MetaAnalyzer(client, database=integration.db)  # type: ignore[attr-defined]
    return integration._meta_analyzer  # type: ignore[attr-defined]


async def warm_series(
    integration: iRacingIntegration,
    meta_analyzer: MetaAnalyzer,
    series: dict,
    sleep_seconds: float = 0.5,
) -> dict:
    """
    Prefetch schedule and meta data for a single series.

    Returns a summary dict with counts for reporting.
    """
    series_id = series.get("series_id")
    season_id = series.get("season_id")
    series_name = series.get("series_name", f"Series {series_id}")

    summary = {
        "series_id": series_id,
        "season_id": season_id,
        "series_name": series_name,
        "weeks_processed": 0,
        "meta_hits": 0,
        "meta_misses": 0,
    }

    if not series_id or not season_id:
        print(f"⚠️  Skipping series with missing identifiers: {series}")
        return summary

    print(f"\n🏁 Warming cache for {series_name} (series_id={series_id}, season_id={season_id})")

    # Warm schedule cache (used by /iracing_schedule and /iracing_season_schedule)
    schedule = await integration.get_series_schedule(series_id, season_id)
    if not schedule:
        print(f"⚠️  No schedule data retrieved for {series_name}; skipping meta prefetch.")
        return summary

    week_numbers: Set[int] = set()
    for index, entry in enumerate(schedule):
        week_numbers.add(entry.get("race_week_num", index))

    sorted_weeks = sorted(week_numbers)
    if not sorted_weeks:
        print(f"⚠️  Could not determine week numbers for {series_name}")
        return summary

    print(f"📅  {series_name}: caching meta for weeks {sorted_weeks}")

    for week_num in sorted_weeks:
        summary["weeks_processed"] += 1
        try:
            result = await meta_analyzer.get_meta_for_series(
                series_id=series_id,
                season_id=season_id,
                week_num=week_num,
                max_results=300,
            )
            if result:
                summary["meta_hits"] += 1
                print(
                    f"   ✅ Week {week_num:02d}: {len(result.get('cars', []))} cars, "
                    f"{result.get('total_races_analyzed', 0)} sessions analyzed"
                )
            else:
                summary["meta_misses"] += 1
                print(f"   ⚠️ Week {week_num:02d}: no meta data available")
        except Exception as exc:
            summary["meta_misses"] += 1
            print(f"   ❌ Week {week_num:02d}: error fetching meta ({exc})")

        if sleep_seconds:
            await asyncio.sleep(sleep_seconds)

    return summary


async def warm_all_series(limit: Optional[int] = None, sleep_seconds: float = 0.5) -> List[dict]:
    """Warm caches for all active series in the current season."""
    db = Database()
    credential_manager = CredentialManager()
    credentials = credential_manager.get_iracing_credentials()

    if not credentials:
        raise RuntimeError("iRacing credentials are not configured. Run encrypt_credentials.py first.")

    email, password = credentials
    integration = iRacingIntegration(db, email, password)

    # Prime asset caches to avoid repeated fetches during the warmup
    await integration.get_all_cars()
    await integration.get_all_tracks()

    series_list = await integration.get_current_series()
    if not series_list:
        raise RuntimeError("The iRacing API did not return any active series.")

    if limit is not None:
        series_list = series_list[:limit]

    print(f"🚀 Warming caches for {len(series_list)} active series")

    meta_analyzer = await _ensure_meta_analyzer(integration)
    summaries: List[dict] = []
    started_at = datetime.utcnow()

    for idx, series in enumerate(series_list, start=1):
        print(f"\n=== ({idx}/{len(series_list)}) {series.get('series_name')} ===")
        summary = await warm_series(integration, meta_analyzer, series, sleep_seconds=sleep_seconds)
        summaries.append(summary)

    await integration.close()

    finished_at = datetime.utcnow()
    duration = finished_at - started_at
    total_weeks = sum(s["weeks_processed"] for s in summaries)
    total_hits = sum(s["meta_hits"] for s in summaries)
    total_misses = sum(s["meta_misses"] for s in summaries)

    print("\n✅ iRacing warmup complete")
    print(f"   Series processed : {len(summaries)}")
    print(f"   Weeks processed  : {total_weeks}")
    print(f"   Meta cache hits  : {total_hits}")
    print(f"   Meta cache misses: {total_misses}")
    print(f"   Duration         : {duration}")

    return summaries


async def main():
    parser = argparse.ArgumentParser(description="Warm iRacing caches for all active series.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of series to process (useful for testing).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Delay (seconds) between meta requests to avoid API rate limits.",
    )
    args = parser.parse_args()

    await warm_all_series(limit=args.limit, sleep_seconds=args.sleep)


if __name__ == "__main__":
    asyncio.run(main())
