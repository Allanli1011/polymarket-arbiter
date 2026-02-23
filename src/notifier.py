"""
Notification System - Telegram alerts for arbitrage opportunities
"""
import asyncio
from typing import List, Optional
import structlog

from .config import config
from .models import ArbitrageOpportunity

logger = structlog.get_logger()


class TelegramNotifier:
    """Send Telegram notifications for arbitrage opportunities"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self._session = None
    
    async def __aenter__(self):
        import aiohttp
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
    
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    async def send(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram"""
        if not self.is_configured:
            logger.warning("telegram_not_configured")
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.info("telegram_sent", chat_id=self.chat_id)
                    return True
                else:
                    error = await resp.text()
                    logger.error("telegram_failed", status=resp.status, error=error)
                    return False
                    
        except Exception as e:
            logger.error("telegram_error", error=str(e))
            return False
    
    async def notify_opportunities(
        self, 
        opportunities: List[ArbitrageOpportunity],
        since=None
    ) -> int:
        """Notify about new opportunities"""
        if not opportunities:
            return 0
        
        # Filter new opportunities
        new_opps = [o for o in opportunities if not o.notified]
        
        if not new_opps:
            return 0
        
        # Send each opportunity
        sent = 0
        for opp in new_opps:
            message = opp.to_message()
            if await self.send(message):
                sent += 1
                opp.notified = True
        
        # Send summary if multiple
        if len(new_opps) > 1:
            summary = f"\n📋 *共发现 {len(new_opps)} 个新机会*"
            await self.send(summary)
        
        logger.info("notifications_sent", count=sent)
        return sent


class ConsoleNotifier:
    """Console output for testing"""
    
    async def notify_opportunities(
        self, 
        opportunities: List[ArbitrageOpportunity],
        since=None
    ) -> int:
        for opp in opportunities:
            if not opp.notified:
                print("\n" + "="*50)
                print(opp.to_message())
                print("="*50 + "\n")
                opp.notified = True
        return len(opportunities)


def get_notifier() -> TelegramNotifier:
    """Get configured notifier"""
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        return TelegramNotifier()
    return ConsoleNotifier()
