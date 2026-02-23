"""
Arbitrage Detection Engine
"""
import asyncio
import logging
import sys

# Suppress noisy logs in scan mode
if not sys.stdout.isatty():
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
from typing import List, Dict, Set, Optional
from datetime import datetime
from collections import defaultdict
import structlog

from .config import config
from .models import (
    Market, 
    ArbitrageOpportunity, 
    OpportunityType,
    OrderBook,
)
from .api_client import PolymarketClient

logger = structlog.get_logger()


class ArbitrageDetector:
    """Detects arbitrage opportunities in Polymarket markets"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self._processed_conditions: Set[str] = set()
        self._flagged_markets: Dict[str, Market] = {}  # Markets needing deep check
        self._opportunity_history: List[ArbitrageOpportunity] = []
    
    async def full_scan(self, markets: List[Market]) -> List[ArbitrageOpportunity]:
        """Run full arbitrage detection scan"""
        opportunities = []
        
        logger.info("starting_full_scan", market_count=len(markets))
        
        # Stage 1: Probability sum anomalies
        prob_opps = await self._detect_prob_sum_anomalies(markets)
        opportunities.extend(prob_opps)
        
        # Stage 2: Cross-market opportunities (group by similar questions)
        cross_opps = await self._detect_cross_market_opportunities(markets)
        opportunities.extend(cross_opps)
        
        # Stage 3: Wide spread detection (requires orderbook)
        spread_opps = await self._detect_spread_opportunities(markets)
        opportunities.extend(spread_opps)
        
        # Deduplicate
        opportunities = self._deduplicate_opportunities(opportunities)
        
        logger.info("scan_complete", opportunities=len(opportunities))
        return opportunities
    
    async def _detect_prob_sum_anomalies(
        self, 
        markets: List[Market]
    ) -> List[ArbitrageOpportunity]:
        """
        Detect when outcome probabilities don't sum to 1.
        In efficient markets, sum should be ~1.0 (minus spread).
        Deviations indicate potential arbitrage.
        """
        opportunities = []
        
        for market in markets:
            if len(market.outcomes) < 2:
                continue
            
            prob_sum = market.prob_sum
            deviation = abs(prob_sum - 1.0)
            
            if deviation > config.PROB_SUM_THRESHOLD:
                # Calculate theoretical profit
                if prob_sum > 1.0:
                    # Sell overweight outcomes
                    profit_pct = (prob_sum - 1.0) / prob_sum
                    action = "卖出高概率结果"
                else:
                    # Buy underweight outcomes
                    profit_pct = (1.0 - prob_sum)
                    action = "买入低概率结果"
                
                opp = ArbitrageOpportunity(
                    id=f"prob_{market.condition_id}_{int(datetime.now().timestamp())}",
                    type=OpportunityType.PROB_SUM,
                    markets=[market],
                    profit_estimate=profit_pct,
                    details={
                        "prob_sum": prob_sum,
                        "deviation": deviation,
                        "action": action,
                        "condition_id": market.condition_id,
                    }
                )
                opportunities.append(opp)
                
                # Flag for deeper monitoring
                self._flagged_markets[market.id] = market
        
        if opportunities:
            logger.info("prob_sum_anomalies", count=len(opportunities))
        
        return opportunities
    
    async def _detect_cross_market_opportunities(
        self, 
        markets: List[Market]
    ) -> List[ArbitrageOpportunity]:
        """
        Detect same or related events across different markets.
        E.g., "Will X win?" vs "Will X not win?"
        """
        opportunities = []
        
        # Group markets by similar keywords/questions
        market_groups = self._group_similar_markets(markets)
        
        for group_key, group_markets in market_groups.items():
            if len(group_markets) < 2:
                continue
            
            # Look for complementary or competing markets
            for i, m1 in enumerate(group_markets):
                for m2 in group_markets[i+1:]:
                    # Check if they're on same event with opposing outcomes
                    cross_opp = self._check_cross_market(m1, m2)
                    if cross_opp:
                        opportunities.append(cross_opp)
        
        if opportunities:
            logger.info("cross_market_opportunities", count=len(opportunities))
        
        return opportunities
    
    def _group_similar_markets(self, markets: List[Market]) -> Dict[str, List[Market]]:
        """Group markets by similar keywords"""
        groups = defaultdict(list)
        
        # Normalize question for grouping
        for market in markets:
            # Simple grouping: use first few significant words
            q = market.question.lower()
            
            # Remove common words
            stop_words = {"will", "the", "a", "an", "be", "is", "are", "to", "of", "in", "on"}
            words = [w for w in q.split() if w not in stop_words]
            
            if words:
                # Use first 3 words as group key
                key = " ".join(words[:3])
                groups[key].append(market)
        
        # Only return groups with multiple markets
        return {k: v for k, v in groups.items() if len(v) >= 2}
    
    def _check_cross_market(
        self, 
        m1: Market, 
        m2: Market
    ) -> Optional[ArbitrageOpportunity]:
        """Check if two markets offer cross-market arbitrage"""
        
        # Skip if same condition ID (same market)
        if m1.condition_id == m2.condition_id:
            return None
        
        # Check if outcomes are complementary (Yes/No type)
        outcomes_1 = {o.name.lower() for o in m1.outcomes}
        outcomes_2 = {o.name.lower() for o in m2.outcomes}
        
        # Look for Yes/No pairs
        if "yes" in outcomes_1 and "no" in outcomes_1:
            yes_price = next(o.price for o in m1.outcomes if o.name.lower() == "yes")
            no_price = next(o.price for o in m1.outcomes if o.name.lower() == "no")
            
            # Check against other market
            if "yes" in outcomes_2:
                other_yes = next(o.price for o in m2.outcomes if o.name.lower() == "yes")
                
                diff = abs(yes_price - other_yes)
                if diff > config.SPREAD_THRESHOLD:
                    return ArbitrageOpportunity(
                        id=f"cross_{m1.condition_id}_{m2.condition_id}_{int(datetime.now().timestamp())}",
                        type=OpportunityType.CROSS_MARKET,
                        markets=[m1, m2],
                        profit_estimate=diff,
                        details={
                            "action": "跨市场对冲",
                            "m1_yes": yes_price,
                            "m2_yes": other_yes,
                            "diff": diff,
                        }
                    )
        
        return None
    
    async def _detect_spread_opportunities(
        self, 
        markets: List[Market]
    ) -> List[ArbitrageOpportunity]:
        """
        Detect wide bid-ask spreads that could be arbitraged.
        Requires orderbook data.
        """
        opportunities = []
        
        # Only check flagged markets to save API calls
        markets_to_check = list(self._flagged_markets.values())
        
        if not markets_to_check:
            return []
        
        # Get token IDs for these markets
        token_map = await self.client.get_token_ids_for_markets(markets_to_check)
        
        all_token_ids = []
        market_token_map = {}
        for market in markets_to_check:
            tokens = token_map.get(market.id, [])
            for token in tokens:
                all_token_ids.append(token)
                market_token_map[token] = market
        
        if not all_token_ids:
            return []
        
        # Batch fetch spreads
        spreads = await self.client.get_spreads(all_token_ids[:100])  # Limit batch
        
        for token_id, spread in spreads.items():
            if spread > config.SPREAD_THRESHOLD:
                market = market_token_map.get(token_id)
                if market:
                    # Midpoint might be exploitable
                    midpoints = await self.client.get_midpoints([token_id])
                    mid = midpoints.get(token_id, 0.5)
                    
                    opp = ArbitrageOpportunity(
                        id=f"spread_{token_id}_{int(datetime.now().timestamp())}",
                        type=OpportunityType.SPREAD,
                        markets=[market],
                        profit_estimate=spread,
                        details={
                            "spread": spread,
                            "mid_price": mid,
                            "token_id": token_id,
                            "action": "挂单套利",
                        }
                    )
                    opportunities.append(opp)
        
        if opportunities:
            logger.info("spread_opportunities", count=len(opportunities))
        
        return opportunities
    
    def _deduplicate_opportunities(
        self, 
        opportunities: List[ArbitrageOpportunity]
    ) -> List[ArbitrageOpportunity]:
        """Remove duplicate opportunities"""
        seen = set()
        unique = []
        
        for opp in opportunities:
            # Use market IDs as key
            market_keys = tuple(sorted(m.id for m in opp.markets))
            key = (opp.type.value, market_keys)
            
            if key not in seen:
                seen.add(key)
                unique.append(opp)
        
        return unique
    
    def get_opportunity_history(self) -> List[ArbitrageOpportunity]:
        """Get all detected opportunities"""
        return self._opportunity_history
    
    def clear_flagged(self):
        """Clear flagged markets"""
        self._flagged_markets.clear()
