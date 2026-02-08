"""
Shared Watchlists
Shared price watchlists with 5%+ move alerts.
Admin only. 1-minute alert checking, daily summary.
Uses Finnhub (stocks) and CoinGecko (crypto) APIs.
"""

import os
import asyncio
import requests
from datetime import datetime
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

from constants import STOCK_TICKERS, CRYPTO_TICKERS

logger = logging.getLogger(__name__)


class WatchlistManager:
    """Manage shared price watchlists."""

    def __init__(self, db, cache=None):
        self.db = db
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'WompBot-Discord'})

    async def add_symbols(self, guild_id: int, channel_id: int,
                           symbols: List[str], added_by: int,
                           alert_threshold: float = 5.0) -> Dict:
        """
        Add symbols to the watchlist.

        Args:
            guild_id: Discord guild ID
            channel_id: Channel for alerts
            symbols: List of ticker symbols
            added_by: Admin user ID
            alert_threshold: Percent move to trigger alert

        Returns:
            Dict with added symbols or errors
        """
        alert_threshold = min(max(alert_threshold, 1.0), 50.0)
        added = []
        errors = []

        for symbol in symbols:
            sym = symbol.upper().strip()
            if not sym:
                continue

            # Determine if stock or crypto
            if sym in CRYPTO_TICKERS:
                sym_type = 'crypto'
            elif sym in STOCK_TICKERS or len(sym) <= 5:
                sym_type = 'stock'
            else:
                sym_type = 'stock'  # Default to stock

            # Fetch current price to validate
            price_data = await self._fetch_price(sym, sym_type)
            if not price_data or price_data.get('error'):
                errors.append(f"{sym}: {price_data.get('error', 'Not found')}")
                continue

            # Save to database
            try:
                result = await asyncio.to_thread(
                    self._add_symbol_sync, guild_id, channel_id, sym,
                    sym_type, added_by, alert_threshold, price_data['price']
                )
                if result.get('error'):
                    errors.append(f"{sym}: {result['error']}")
                else:
                    added.append({
                        'symbol': sym,
                        'type': sym_type,
                        'price': price_data['price']
                    })
            except Exception as e:
                errors.append(f"{sym}: {str(e)}")

        return {
            'added': added,
            'errors': errors
        }

    def _add_symbol_sync(self, guild_id: int, channel_id: int,
                          symbol: str, sym_type: str, added_by: int,
                          alert_threshold: float, current_price: float) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, is_active FROM watchlists
                    WHERE guild_id = %s AND symbol = %s
                """, (guild_id, symbol))
                existing = cur.fetchone()

                if existing:
                    if existing[1]:  # is_active
                        return {'error': 'Already on watchlist'}
                    else:
                        cur.execute("""
                            UPDATE watchlists SET is_active = TRUE, channel_id = %s,
                                last_price = %s, alert_threshold = %s
                            WHERE id = %s
                        """, (channel_id, current_price, alert_threshold, existing[0]))
                        conn.commit()
                        return {'reactivated': True}

                cur.execute("""
                    INSERT INTO watchlists (guild_id, channel_id, symbol, symbol_type,
                                            added_by, alert_threshold, last_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (guild_id, channel_id, symbol, sym_type,
                      added_by, alert_threshold, current_price))
                conn.commit()
                return {'added': True}

    async def remove_symbol(self, guild_id: int, symbol: str) -> Dict:
        """Remove a symbol from the watchlist."""
        try:
            return await asyncio.to_thread(
                self._remove_symbol_sync, guild_id, symbol.upper()
            )
        except Exception as e:
            logger.error("Error removing watchlist symbol: %s", e)
            return {'error': str(e)}

    def _remove_symbol_sync(self, guild_id: int, symbol: str) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE watchlists SET is_active = FALSE
                    WHERE guild_id = %s AND symbol = %s AND is_active = TRUE
                    RETURNING symbol
                """, (guild_id, symbol))
                row = cur.fetchone()
                conn.commit()

                if not row:
                    return {'error': f'{symbol} not found on watchlist.'}
                return {'removed': True, 'symbol': symbol}

    async def get_watchlist(self, guild_id: int) -> List[Dict]:
        """Get active watchlist for a guild."""
        try:
            return await asyncio.to_thread(self._get_watchlist_sync, guild_id)
        except Exception as e:
            logger.error("Error getting watchlist: %s", e)
            return []

    def _get_watchlist_sync(self, guild_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, channel_id, symbol, symbol_type, alert_threshold,
                           last_price, last_alert_at, created_at
                    FROM watchlists
                    WHERE guild_id = %s AND is_active = TRUE
                    ORDER BY symbol ASC
                """, (guild_id,))
                return cur.fetchall()

    async def check_price_alerts(self) -> List[Dict]:
        """
        Check all watched symbols for significant price moves.

        Returns:
            List of alert dicts with channel_id, symbol, old_price, new_price, change_pct
        """
        try:
            watchlist = await asyncio.to_thread(self._get_all_active_symbols)
        except Exception as e:
            logger.error("Error fetching watchlist symbols: %s", e)
            return []

        if not watchlist:
            return []

        alerts = []

        for item in watchlist:
            try:
                # Skip if recently alerted (within 30 min)
                if item.get('last_alert_at'):
                    time_since = (datetime.now() - item['last_alert_at']).total_seconds()
                    if time_since < 1800:  # 30 minutes
                        continue

                price_data = await self._fetch_price(item['symbol'], item['symbol_type'])
                if not price_data or price_data.get('error'):
                    continue

                new_price = price_data['price']
                old_price = item.get('last_price', 0)

                if old_price and old_price > 0:
                    change_pct = ((new_price - old_price) / old_price) * 100

                    if abs(change_pct) >= item.get('alert_threshold', 5.0):
                        alerts.append({
                            'channel_id': item['channel_id'],
                            'symbol': item['symbol'],
                            'symbol_type': item['symbol_type'],
                            'old_price': old_price,
                            'new_price': new_price,
                            'change_pct': change_pct,
                            'threshold': item['alert_threshold']
                        })

                        # Update last_alert_at
                        await asyncio.to_thread(
                            self._update_alert_time, item['id'], new_price
                        )
                    else:
                        # Update price without alert timestamp
                        await asyncio.to_thread(
                            self._update_price, item['id'], new_price
                        )

            except Exception as e:
                logger.error("Error checking price for %s: %s", item.get('symbol', '?'), e)
                continue

        return alerts

    async def generate_daily_summary(self, guild_id: int) -> Optional[Dict]:
        """Generate a daily summary of all watched symbols."""
        watchlist = await self.get_watchlist(guild_id)
        if not watchlist:
            return None

        summary_items = []
        channel_id = None

        for item in watchlist:
            channel_id = item['channel_id']  # Use the last seen channel
            price_data = await self._fetch_price(item['symbol'], item['symbol_type'])
            if not price_data or price_data.get('error'):
                continue

            new_price = price_data['price']
            old_price = item.get('last_price', 0)
            change_pct = 0
            if old_price and old_price > 0:
                change_pct = ((new_price - old_price) / old_price) * 100

            summary_items.append({
                'symbol': item['symbol'],
                'type': item['symbol_type'],
                'price': new_price,
                'change_pct': change_pct
            })

            # Update stored price
            await asyncio.to_thread(self._update_price, item['id'], new_price)

        if not summary_items:
            return None

        return {
            'channel_id': channel_id,
            'items': summary_items,
            'guild_id': guild_id
        }

    async def _fetch_price(self, symbol: str, sym_type: str) -> Optional[Dict]:
        """Fetch current price for a symbol."""
        try:
            if sym_type == 'crypto':
                coingecko_id = CRYPTO_TICKERS.get(symbol)
                if not coingecko_id:
                    return {'error': f'Unknown crypto: {symbol}'}
                return await self._fetch_crypto(coingecko_id, symbol)
            else:
                return await self._fetch_stock(symbol)
        except Exception as e:
            return {'error': str(e)}

    async def _fetch_stock(self, symbol: str) -> Optional[Dict]:
        """Fetch stock price from Finnhub."""
        finnhub_key = os.getenv('FINNHUB_API_KEY')
        if not finnhub_key:
            return {'error': 'FINNHUB_API_KEY not configured'}

        mapped_symbol = STOCK_TICKERS.get(symbol, symbol)

        def fetch():
            url = f"https://finnhub.io/api/v1/quote?symbol={mapped_symbol}&token={finnhub_key}"
            resp = self.session.get(url, timeout=10)
            return resp.json()

        try:
            data = await asyncio.to_thread(fetch)
            if not data or data.get('c', 0) == 0:
                return {'error': f'No price data for {symbol}'}

            return {
                'price': data['c'],
                'change': data.get('d', 0),
                'change_pct': data.get('dp', 0)
            }
        except Exception as e:
            return {'error': str(e)}

    async def _fetch_crypto(self, coingecko_id: str, display: str) -> Optional[Dict]:
        """Fetch crypto price from CoinGecko."""
        def fetch():
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd&include_24hr_change=true"
            resp = self.session.get(url, timeout=10)
            return resp.json()

        try:
            data = await asyncio.to_thread(fetch)
            if not data or coingecko_id not in data:
                return {'error': f'No price data for {display}'}

            crypto_data = data[coingecko_id]
            return {
                'price': crypto_data['usd'],
                'change_pct': crypto_data.get('usd_24h_change', 0) or 0
            }
        except Exception as e:
            return {'error': str(e)}

    def _get_all_active_symbols(self) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, guild_id, channel_id, symbol, symbol_type,
                           alert_threshold, last_price, last_alert_at
                    FROM watchlists
                    WHERE is_active = TRUE
                """)
                return cur.fetchall()

    def _update_alert_time(self, watchlist_id: int, new_price: float):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE watchlists SET last_price = %s, last_alert_at = NOW()
                    WHERE id = %s
                """, (new_price, watchlist_id))
                conn.commit()

    def _update_price(self, watchlist_id: int, new_price: float):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE watchlists SET last_price = %s WHERE id = %s
                """, (new_price, watchlist_id))
                conn.commit()
