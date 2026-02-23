"""
System event handler for Polymarket scans
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_client import PolymarketClient
from src.arbitrage_detector import ArbitrageDetector


async def run_scan() -> str:
    """Run scan and return report"""
    client = PolymarketClient()
    detector = ArbitrageDetector(client)
    
    async with client:
        markets = await client.get_markets(limit=100, closed=False, volume_min=50000)
        
        if not markets:
            return "❌ 无法获取市场数据"
        
        opportunities = await detector.full_scan(markets)
        
        if not opportunities:
            return f"✅ 扫描完成: 检查了 {len(markets)} 个市场，未发现套利机会"
        
        # Format results
        report = f"🔍 *Polymarket 套利扫描*\n"
        report += f"扫描市场: {len(markets)}\n"
        report += f"发现机会: {len(opportunities)}\n\n"
        
        for i, opp in enumerate(opportunities[:5], 1):
            report += f"{i}. *{opp.type.value}*\n"
            report += f"   预估收益: {opp.prop_estimate:.2%}\n"
            report += f"   {opp.markets[0].question[:50]}...\n\n"
        
        return report


if __name__ == "__main__":
    result = asyncio.run(run_scan())
    print(result)
