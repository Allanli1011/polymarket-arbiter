#!/usr/bin/env python3
"""
Polymarket Arbitrage Scanner - 输出到 stdout 供 cron delivery 使用
"""
import asyncio
import sys
import os
import logging

# 禁用 logging 输出
logging.basicConfig(level=logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_client import PolymarketClient
from src.arbitrage_detector import ArbitrageDetector


async def scan_once():
    """Run scan and print results to stdout"""
    client = PolymarketClient()
    detector = ArbitrageDetector(client)
    
    async with client:
        # Fetch active markets with volume
        markets = await client.get_markets(limit=100, closed=False, volume_min=50000)
        
        if not markets:
            print("❌ 无法获取 Polymarket 市场数据")
            return
        
        # Run detection
        opportunities = await detector.full_scan(markets)
        
        # Output format for Telegram
        if not opportunities:
            print(f"✅ Polymarket 扫描完成: 检查了 {len(markets)} 个高流动性市场，暂无套利机会")
            return
        
        # Found opportunities - format for Telegram
        print(f"🔍 *Polymarket 套利扫描报告*\n")
        print(f"扫描市场: {len(markets)} 个 (成交量 > $50k)")
        print(f"发现机会: *{len(opportunities)} 个*\n")
        print("─" * 30)
        
        for i, opp in enumerate(opportunities[:5], 1):
            emoji = {"prob_sum": "📊", "cross_market": "🔄", "spread": "📈", "liquidity_arb": "💧"}.get(opp.type.value, "🎯")
            
            print(f"\n{i}. {emoji} *{opp.type.value}*")
            print(f"   预估收益: *{opp.profit_estimate:.2%}*")
            print(f"   {opp.markets[0].question[:60]}...")
            
            # Show outcome prices
            for o in opp.markets[0].outcomes[:3]:
                print(f"   • {o.name}: {o.price:.2%}")
        
        if len(opportunities) > 5:
            print(f"\n... 还有 {len(opportunities) - 5} 个机会")


if __name__ == "__main__":
    asyncio.run(scan_once())
