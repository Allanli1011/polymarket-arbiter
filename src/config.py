"""
Configuration for Polymarket Arbitrage Monitor
"""
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class Config:
    # API Endpoints
    GAMMA_API: str = "https://gamma-api.polymarket.com"
    CLOB_API: str = "https://clob.polymarket.com"
    DATA_API: str = "https://data-api.polymarket.com"
    
    # Polling intervals (seconds)
    MARKET_SCAN_INTERVAL: int = 30      # Full market scan
    PRICE_CHECK_INTERVAL: int = 5        # Price check for flagged markets
    ORDERBOOK_CHECK_INTERVAL: int = 2    # Orderbook deep dive
    
    # Arbitrage thresholds
    PROB_SUM_THRESHOLD: float = 0.03     # Prob sum deviation >3% = potential arb
    SPREAD_THRESHOLD: float = 0.02      # Bid-ask spread >2% = opportunity
    MIN_LIQUIDITY: float = 1000          # Min liquidity to consider
    
    # Filters
    MIN_VOLUME: float = 10000            # Min 24h volume
    MAX_MARKETS: int = 500               # Max markets to scan
    
    # Notification
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "arbiter.log"
    
    # Performance
    MAX_CONCURRENT_REQUESTS: int = 20
    REQUEST_TIMEOUT: int = 10
    
    @classmethod
    def from_env(cls):
        """Load config from environment variables"""
        return cls(
            TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN"),
            TELEGRAM_CHAT_ID=os.getenv("TELEGRAM_CHAT_ID"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global config instance
config = Config.from_env()
