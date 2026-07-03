"""Sanity/regression tests for the centralized constants (used by watchlists,
self-contained-tool routing, reminders, translation)."""
import constants


def test_self_contained_tools_is_frozenset_and_populated():
    assert isinstance(constants.SELF_CONTAINED_TOOLS, frozenset)
    assert len(constants.SELF_CONTAINED_TOOLS) > 0


def test_ticker_tables_populated_and_typed():
    assert len(constants.STOCK_TICKERS) > 0
    assert len(constants.CRYPTO_TICKERS) > 0


def test_stock_and_crypto_do_not_overlap():
    # watchlists auto-detect stock-vs-crypto from these; overlap would misroute a symbol.
    overlap = set(constants.STOCK_TICKERS) & set(constants.CRYPTO_TICKERS)
    assert not overlap, f"symbols classified as both stock and crypto: {overlap}"


def test_timezone_and_language_tables():
    assert isinstance(constants.TIMEZONE_ALIASES, dict) and constants.TIMEZONE_ALIASES
    assert isinstance(constants.LANGUAGE_CODES, dict) and constants.LANGUAGE_CODES
