"""
Shared constants for WompBot.

Centralises lookup tables and configuration lists that are used by multiple modules
(tool_executor, conversations, etc.) so they can be maintained in one place.
"""

# ---------------------------------------------------------------------------
# Timezone aliases  (used by _get_time in tool_executor.py)
# Keys are lower-cased user input; values are IANA tz database names.
# ---------------------------------------------------------------------------
TIMEZONE_ALIASES = {
    'est': 'America/New_York', 'edt': 'America/New_York',
    'cst': 'America/Chicago', 'cdt': 'America/Chicago',
    'mst': 'America/Denver', 'mdt': 'America/Denver',
    'pst': 'America/Los_Angeles', 'pdt': 'America/Los_Angeles',
    'gmt': 'Europe/London', 'bst': 'Europe/London',
    'utc': 'UTC',
    'tokyo': 'Asia/Tokyo', 'japan': 'Asia/Tokyo',
    'london': 'Europe/London', 'uk': 'Europe/London',
    'paris': 'Europe/Paris', 'france': 'Europe/Paris',
    'berlin': 'Europe/Berlin', 'germany': 'Europe/Berlin',
    'sydney': 'Australia/Sydney', 'australia': 'Australia/Sydney',
    'new york': 'America/New_York', 'nyc': 'America/New_York',
    'los angeles': 'America/Los_Angeles', 'la': 'America/Los_Angeles',
    'chicago': 'America/Chicago',
    'denver': 'America/Denver',
    'phoenix': 'America/Phoenix',
    'seattle': 'America/Los_Angeles',
    'miami': 'America/New_York',
    'dallas': 'America/Chicago',
    'houston': 'America/Chicago',
    'toronto': 'America/Toronto', 'canada': 'America/Toronto',
    'vancouver': 'America/Vancouver',
    'moscow': 'Europe/Moscow', 'russia': 'Europe/Moscow',
    'beijing': 'Asia/Shanghai', 'china': 'Asia/Shanghai', 'shanghai': 'Asia/Shanghai',
    'hong kong': 'Asia/Hong_Kong',
    'singapore': 'Asia/Singapore',
    'dubai': 'Asia/Dubai',
    'india': 'Asia/Kolkata', 'mumbai': 'Asia/Kolkata', 'delhi': 'Asia/Kolkata',
    'seoul': 'Asia/Seoul', 'korea': 'Asia/Seoul',
}

# ---------------------------------------------------------------------------
# Language codes  (used by _translate in tool_executor.py)
# Keys are lower-cased language names; values are ISO 639-1 codes.
# ---------------------------------------------------------------------------
LANGUAGE_CODES = {
    'spanish': 'es', 'french': 'fr', 'german': 'de', 'italian': 'it',
    'portuguese': 'pt', 'russian': 'ru', 'japanese': 'ja', 'chinese': 'zh',
    'korean': 'ko', 'arabic': 'ar', 'hindi': 'hi', 'dutch': 'nl',
    'swedish': 'sv', 'norwegian': 'no', 'danish': 'da', 'finnish': 'fi',
    'polish': 'pl', 'turkish': 'tr', 'greek': 'el', 'hebrew': 'he',
    'thai': 'th', 'vietnamese': 'vi', 'indonesian': 'id', 'malay': 'ms',
    'english': 'en', 'czech': 'cs', 'romanian': 'ro', 'hungarian': 'hu',
    'ukrainian': 'uk', 'tagalog': 'tl', 'filipino': 'tl', 'swahili': 'sw',
    'persian': 'fa', 'farsi': 'fa', 'catalan': 'ca', 'croatian': 'hr',
    'serbian': 'sr', 'slovak': 'sk', 'slovenian': 'sl', 'bulgarian': 'bg',
    'latvian': 'lv', 'lithuanian': 'lt', 'estonian': 'et', 'icelandic': 'is',
    'welsh': 'cy', 'irish': 'ga', 'maltese': 'mt', 'basque': 'eu',
    'galician': 'gl', 'afrikaans': 'af', 'albanian': 'sq', 'macedonian': 'mk',
    'bosnian': 'bs', 'belarusian': 'be', 'georgian': 'ka', 'armenian': 'hy',
    'urdu': 'ur', 'bengali': 'bn', 'tamil': 'ta', 'telugu': 'te',
    'marathi': 'mr', 'gujarati': 'gu', 'kannada': 'kn', 'malayalam': 'ml',
    'punjabi': 'pa', 'nepali': 'ne', 'sinhala': 'si',
    'mandarin': 'zh', 'simplified chinese': 'zh', 'traditional chinese': 'zh-TW',
}

# ---------------------------------------------------------------------------
# Stock tickers  (used by _stock_price and _stock_history in tool_executor.py)
# Keys are upper-cased company names; values are ticker symbols.
# Merged from both _stock_price (full list) and _stock_history (subset) -- deduplicated.
# ---------------------------------------------------------------------------
STOCK_TICKERS = {
    'MICROSOFT': 'MSFT', 'APPLE': 'AAPL', 'GOOGLE': 'GOOGL', 'ALPHABET': 'GOOGL',
    'AMAZON': 'AMZN', 'META': 'META', 'FACEBOOK': 'META', 'NETFLIX': 'NFLX',
    'NVIDIA': 'NVDA', 'TESLA': 'TSLA', 'AMD': 'AMD', 'INTEL': 'INTC',
    'IBM': 'IBM', 'ORACLE': 'ORCL', 'CISCO': 'CSCO', 'ADOBE': 'ADBE',
    'SALESFORCE': 'CRM', 'PAYPAL': 'PYPL', 'SQUARE': 'SQ', 'BLOCK': 'SQ',
    'SHOPIFY': 'SHOP', 'SPOTIFY': 'SPOT', 'UBER': 'UBER', 'LYFT': 'LYFT',
    'AIRBNB': 'ABNB', 'TWITTER': 'X', 'SNAP': 'SNAP', 'SNAPCHAT': 'SNAP',
    'PALANTIR': 'PLTR', 'SNOWFLAKE': 'SNOW', 'DATADOG': 'DDOG',
    'CROWDSTRIKE': 'CRWD', 'CLOUDFLARE': 'NET',
    'JPMORGAN': 'JPM', 'JP MORGAN': 'JPM', 'CHASE': 'JPM',
    'BANK OF AMERICA': 'BAC', 'BOFA': 'BAC', 'WELLS FARGO': 'WFC',
    'GOLDMAN': 'GS', 'GOLDMAN SACHS': 'GS', 'MORGAN STANLEY': 'MS',
    'VISA': 'V', 'MASTERCARD': 'MA', 'AMEX': 'AXP',
    'BERKSHIRE': 'BRK.A', 'BERKSHIRE HATHAWAY': 'BRK.A',
    'WALMART': 'WMT', 'TARGET': 'TGT', 'COSTCO': 'COST', 'HOME DEPOT': 'HD',
    'NIKE': 'NKE', 'STARBUCKS': 'SBUX', 'MCDONALDS': 'MCD', 'DISNEY': 'DIS',
    'PFIZER': 'PFE', 'MODERNA': 'MRNA', 'MERCK': 'MRK',
    'EXXON': 'XOM', 'EXXONMOBIL': 'XOM', 'CHEVRON': 'CVX',
}

# ---------------------------------------------------------------------------
# Crypto tickers  (used by _stock_price in tool_executor.py)
# Keys are upper-cased crypto names/symbols; values are CoinGecko IDs.
# ---------------------------------------------------------------------------
CRYPTO_TICKERS = {
    'BITCOIN': 'bitcoin', 'BTC': 'bitcoin', 'BTC-USD': 'bitcoin',
    'ETHEREUM': 'ethereum', 'ETH': 'ethereum', 'ETH-USD': 'ethereum',
    'DOGECOIN': 'dogecoin', 'DOGE': 'dogecoin', 'DOGE-USD': 'dogecoin',
    'SOLANA': 'solana', 'SOL': 'solana', 'SOL-USD': 'solana',
    'CARDANO': 'cardano', 'ADA': 'cardano', 'ADA-USD': 'cardano',
    'XRP': 'ripple', 'RIPPLE': 'ripple', 'XRP-USD': 'ripple',
    'LITECOIN': 'litecoin', 'LTC': 'litecoin', 'LTC-USD': 'litecoin',
    'POLKADOT': 'polkadot', 'DOT': 'polkadot', 'DOT-USD': 'polkadot',
    'AVALANCHE': 'avalanche-2', 'AVAX': 'avalanche-2', 'AVAX-USD': 'avalanche-2',
    'CHAINLINK': 'chainlink', 'LINK': 'chainlink', 'LINK-USD': 'chainlink',
    'SHIBA': 'shiba-inu', 'SHIB': 'shiba-inu', 'SHIB-USD': 'shiba-inu',
}

# ---------------------------------------------------------------------------
# Self-contained tools  (used by synthesis logic in conversations.py)
# Tool name substrings that produce user-ready output and do NOT need an
# additional LLM synthesis pass.
# ---------------------------------------------------------------------------
SELF_CONTAINED_TOOLS = [
    "get_weather", "get_weather_forecast", "wolfram_query",
    "wikipedia", "define_word", "movie_info", "stock_price",
    "sports_scores", "currency_convert", "translate", "get_time",
    "url_preview", "random_choice", "stock_history",
    "fetch_crypto_price", "create_reminder",
]
