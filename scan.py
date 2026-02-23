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
        # Fetch all active markets (paginated)
        all_markets = []
        offset = 0
        
        while len(all_markets) < 200:  # Max 200 markets
            markets = await client.get_markets(
                limit=100, 
                offset=offset, 
                closed=False,
                volume_min=10000
            )
            if not markets:
                break
            all_markets.extend(markets)
            offset += 100
            
            # If we got less than 100, no more data
            if len(markets) < 100:
                break
        
        if not all_markets:
            print("❌ 无法获取 Polymarket 市场数据")
            return
        
        # Run detection
        opportunities = await detector.full_scan(all_markets)
        
        # Always show market summary
        print("📊 *Polymarket 市场速览*\n")
        print(f"扫描范围: {len(all_markets)} 个活跃市场 (成交量 > $10k)\n")
        print("─" * 35)
        
        # Show top markets by volume
        sorted_markets = sorted(all_markets, key=lambda m: m.volume, reverse=True)
        
        print("\n🔥 *热门事件 TOP 10:*\n")
        
        for i, m in enumerate(sorted_markets[:10], 1):
            # Format volume
            if m.volume >= 1_000_000:
                vol_str = f"${m.volume/1_000_000:.1f}M"
            else:
                vol_str = f"${m.volume/1000:.0f}K"
            
            # Format outcomes
            outcomes_str = " | ".join([f"{o.name}: {o.price:.1%}" for o in m.outcomes])
            
            print(f"{i}. *{m.question}*")
            print(f"   📈 {vol_str} | {outcomes_str}\n")
        
        # Show arbitrage opportunities if any
        print("─" * 35)
        
        if not opportunities:
            print(f"\n✅ 套利扫描: 暂无明显机会")
            return
        
        # Found opportunities
        print(f"\n🔍 *发现 {len(opportunities)} 个套利机会:*\n")
        
        for i, opp in enumerate(opportunities[:5], 1):
            emoji = {"prob_sum": "📊", "cross_market": "🔄", "spread": "📈", "liquidity_arb": "💧"}.get(opp.type.value, "🎯")
            
            print(f"{i}. {emoji} *{opp.type.value}*")
            print(f"   预估收益: *{opp.profit_estimate:.2%}*")
            print(f"   {opp.markets[0].question[:60]}...")
            
            # Show outcome prices
            for o in opp.markets[0].outcomes[:3]:
                print(f"   • {o.name}: {o.price:.2%}")
            print()
        
        if len(opportunities) > 5:
            print(f"... 还有 {len(opportunities) - 5} 个机会")


if __name__ == "__main__":
    asyncio.run(scan_once())
