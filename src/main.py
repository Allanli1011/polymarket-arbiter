#!/usr/bin/env python3
"""
Polymarket Arbitrage Monitor - Main Entry Point

Production-grade arbitrage detection system for Polymarket prediction markets.

Usage:
    python -m src.main
    
Environment variables:
    TELEGRAM_BOT_TOKEN  - Bot token for alerts
    TELEGRAM_CHAT_ID    - Chat ID to receive alerts
    LOG_LEVEL          - DEBUG, INFO, WARNING, ERROR
"""
import asyncio
import signal
import sys
from datetime import datetime
from typing import Set
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

from .config import config
from .api_client import PolymarketClient
from .arbitrage_detector import ArbitrageDetector
from .notifier import get_notifier, TelegramNotifier, ConsoleNotifier
from .models import ArbitrageOpportunity

logger = structlog.get_logger()


class ArbitrageMonitor:
    """Main arbitrage monitoring application"""
    
    def __init__(self):
        self.client = PolymarketClient()
        self.detector = ArbitrageDetector(self.client)
        self.notifier = get_notifier()
        
        self._running = False
        self._seen_opportunity_ids: Set[str] = set()
        self._last_full_scan = None
        
        # Statistics
        self.stats = {
            "scans": 0,
            "opportunities": 0,
            "notifications": 0,
            "errors": 0,
        }
    
    async def start(self):
        """Start the monitoring loop"""
        logger.info("starting_arbiter", config={
            "min_volume": config.MIN_VOLUME,
            "prob_threshold": config.PROB_SUM_THRESHOLD,
            "spread_threshold": config.SPREAD_THRESHOLD,
        })
        
        self._running = True
        
        # Handle shutdown signals
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop)
        
        async with self.client:
            async with self.notifier:
                await self._monitor_loop()
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # Full scan every MARKET_SCAN_INTERVAL
                await self._full_scan_cycle()
                
                # Brief pause between cycles
                await asyncio.sleep(config.MARKET_SCAN_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitor_error", error=str(e))
                self.stats["errors"] += 1
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _full_scan_cycle(self):
        """Run a full arbitrage detection cycle"""
        logger.info("starting_full_scan_cycle")
        self.stats["scans"] += 1
        
        # Fetch all active markets
        markets = await self.client.scan_all_markets()
        
        if not markets:
            logger.warning("no_markets_fetched")
            return
        
        # Run detection
        opportunities = await self.detector.full_scan(markets)
        
        # Filter to new opportunities
        new_opps = [o for o in opportunities if o.id not in self._seen_opportunity_ids]
        
        if new_opps:
            for opp in new_opps:
                self._seen_opportunity_ids.add(opp.id)
            
            self.stats["opportunities"] += len(new_opps)
            
            # Send notifications
            notified = await self.notifier.notify_opportunities(new_opps)
            self.stats["notifications"] += notified
            
            logger.info(
                "new_opportunities", 
                count=len(new_opps),
                notified=notified,
            )
        
        self._last_full_scan = datetime.now()
        
        # Log stats periodically
        if self.stats["scans"] % 10 == 0:
            logger.info("stats", **self.stats)
    
    def stop(self):
        """Stop the monitor"""
        logger.info("stopping_arbiter", stats=self.stats)
        self._running = False


async def main():
    """Entry point"""
    # Check for Telegram config
    notifier = get_notifier()
    if isinstance(notifier, ConsoleNotifier):
        logger.warning("running_without_telegram")
    
    # Create and start monitor
    monitor = ArbitrageMonitor()
    
    try:
        await monitor.start()
    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
