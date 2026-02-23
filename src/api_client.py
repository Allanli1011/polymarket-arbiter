"""
Polymarket API Client
"""
import asyncio
import aiohttp
import sys
from typing import List, Dict, Optional
import logging
import structlog

from .config import config
from .models import Market, OrderBook, MarketStatus

# Suppress noisy logs in scan mode
if not sys.stdout.isatty():
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

logger = structlog.get_logger()


class PolymarketClient:
    """Async client for Polymarket APIs"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._markets_cache: List[Market] = []
        self._cache_time: float = 0
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
        volume_min: Optional[float] = None,
    ) -> List[Market]:
        """Fetch markets from Gamma API"""
        params = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),  # API expects string
            "order": "volume",
            "ascending": "false",
        }
        
        if volume_min:
            params["volumeNumMin"] = volume_min
        
        url = f"{config.GAMMA_API}/markets"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning("api_error", status=resp.status, url=url)
                    return []
                
                data = await resp.json()
                markets = [Market.from_api_response(m) for m in data]
                
                # Filter to active markets with enough volume
                markets = [
                    m for m in markets 
                    if m.status == MarketStatus.ACTIVE 
                    and m.volume >= config.MIN_VOLUME
                ]
                
                logger.info("markets_fetched", count=len(markets))
                return markets
                
        except asyncio.TimeoutError:
            logger.error("request_timeout", url=url)
            return []
        except Exception as e:
            logger.error("request_failed", error=str(e), url=url)
            return []
    
    async def get_orderbook(self, token_id: str) -> Optional[OrderBook]:
        """Fetch orderbook from CLOB API"""
        url = f"{config.CLOB_API}/orderbook/{token_id}"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                
                return OrderBook(
                    token_id=token_id,
                    bids=data.get("bids", []),
                    asks=data.get("asks", []),
                )
                
        except Exception as e:
            logger.warning("orderbook_fetch_failed", token_id=token_id, error=str(e))
            return None
    
    async def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """Batch fetch current prices"""
        if not token_ids:
            return {}
        
        # Use query params (max 500)
        params = {"token_id": token_ids}
        url = f"{config.CLOB_API}/prices"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return {}
                
                data = await resp.json()
                return {item["token_id"]: float(item["price"]) for item in data}
                
        except Exception as e:
            logger.warning("prices_fetch_failed", error=str(e))
            return {}
    
    async def get_midpoints(self, token_ids: List[str]) -> Dict[str, float]:
        """Batch fetch midpoint prices"""
        if not token_ids:
            return {}
        
        params = {"token_id": token_ids}
        url = f"{config.CLOB_API}/midpoints"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return {}
                
                data = await resp.json()
                return {item["token_id"]: float(item["price"]) for item in data}
                
        except Exception as e:
            logger.warning("midpoints_fetch_failed", error=str(e))
            return {}
    
    async def get_spreads(self, token_ids: List[str]) -> Dict[str, float]:
        """Batch fetch bid-ask spreads"""
        if not token_ids:
            return {}
        
        params = {"token_id": token_ids}
        url = f"{config.CLOB_API}/spreads"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return {}
                
                data = await resp.json()
                return {item["token_id"]: float(item["spread"]) for item in data}
                
        except Exception as e:
            logger.warning("spreads_fetch_failed", error=str(e))
            return {}
    
    async def get_market_details(self, market_id: str) -> Optional[Dict]:
        """Get detailed market info including token IDs"""
        url = f"{config.GAMMA_API}/markets/{market_id}"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                return await resp.json()
                
        except Exception as e:
            logger.warning("market_details_failed", market_id=market_id, error=str(e))
            return None
    
    async def scan_all_markets(self) -> List[Market]:
        """Scan all active markets with volume"""
        markets = []
        offset = 0
        batch_size = 100
        
        while len(markets) < config.MAX_MARKETS:
            batch = await self.get_markets(
                limit=batch_size,
                offset=offset,
                closed=False,
                volume_min=config.MIN_VOLUME,
            )
            
            if not batch:
                break
                
            markets.extend(batch)
            offset += batch_size
            
            # Stop if we got less than batch_size (no more markets)
            if len(batch) < batch_size:
                break
        
        # Sort by volume descending
        markets.sort(key=lambda m: m.volume, reverse=True)
        
        self._markets_cache = markets[:config.MAX_MARKETS]
        return self._markets_cache
    
    async def get_token_ids_for_markets(self, markets: List[Market]) -> Dict[str, List[str]]:
        """Get token IDs for a list of markets (needed for price data)"""
        # This requires fetching market details
        # For now, we'll use a simplified approach
        
        result = {}
        
        # Batch fetch in groups of 20
        for i in range(0, len(markets), 20):
            batch = markets[i:i+20]
            tasks = [self.get_market_details(m.id) for m in batch]
            details = await asyncio.gather(*tasks, return_exceptions=True)
            
            for market, detail in zip(batch, details):
                if isinstance(detail, dict):
                    tokens = detail.get("clobTokenIds", [])
                    if tokens:
                        result[market.id] = tokens
        
        return result
