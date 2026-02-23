"""
Data models for Polymarket Arbitrage Monitor
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import json


class OpportunityType(Enum):
    PROB_SUM = "prob_sum"           # Outcome probabilities don't sum to 1
    CROSS_MARKET = "cross_market"   # Same event in different markets
    SPREAD = "spread"               # Wide bid-ask spread
    LIQUIDITY_ARB = "liquidity_arb" #流动性差异套利


class MarketStatus(Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"


@dataclass
class Outcome:
    """Single outcome for a market"""
    name: str
    price: float          # Current price (probability)
    volume: Optional[float] = None
    
    def __post_init__(self):
        if isinstance(self.price, str):
            self.price = float(self.price)


@dataclass
class Market:
    """Polymarket market"""
    id: str
    condition_id: str
    question: str
    outcomes: List[Outcome]
    volume: float
    liquidity: float
    status: MarketStatus
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    @property
    def prob_sum(self) -> float:
        return sum(o.price for o in self.outcomes)
    
    @property
    def prob_imbalance(self) -> float:
        """How far from 1.0 is the sum"""
        return abs(self.prob_sum - 1.0)
    
    @property
    def token_ids(self) -> List[str]:
        """Extract token IDs from outcomes if available"""
        # Will be populated by API client
        return []
    
    @classmethod
    def from_api_response(cls, data: Dict) -> "Market":
        """Parse from API response"""
        # Handle both string and list outcomes
        outcome_names = data.get("outcomes", [])
        outcome_prices = data.get("outcomePrices", [])
        
        if isinstance(outcome_names, str):
            # Sometimes comes as JSON string
            try:
                outcome_names = json.loads(outcome_names)
            except:
                outcome_names = [outcome_names]
        
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except:
                outcome_prices = [0.5] * len(outcome_names)
        
        outcomes = []
        for i, name in enumerate(outcome_names):
            price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.5
            outcomes.append(Outcome(name=name, price=price))
        
        status_str = data.get("closed", False)
        status = MarketStatus.CLOSED if status_str else MarketStatus.ACTIVE
        
        return cls(
            id=str(data.get("id", "")),
            condition_id=str(data.get("conditionId", "")),
            question=data.get("question", ""),
            outcomes=outcomes,
            volume=float(data.get("volume", 0) or 0),
            liquidity=float(data.get("liquidity", 0) or 0),
            status=status,
        )


@dataclass
class OrderBook:
    """Order book for a token"""
    token_id: str
    bids: List[Dict]  # [{"price": 0.45, "size": 100}, ...]
    asks: List[Dict]
    spread: float = 0.0
    mid_price: float = 0.5
    
    def __post_init__(self):
        if self.bids and self.asks:
            best_bid = max(b["price"] for b in self.bids)
            best_ask = min(a["price"] for a in self.asks)
            self.spread = best_ask - best_bid
            self.mid_price = (best_bid + best_ask) / 2


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity"""
    id: str
    type: OpportunityType
    markets: List[Market]  # Related markets
    profit_estimate: float  # Expected profit %
    details: Dict[str, Any]
    detected_at: datetime = field(default_factory=datetime.now)
    notified: bool = False
    
    def to_message(self) -> str:
        """Format as Telegram message"""
        emoji = {
            OpportunityType.PROB_SUM: "📊",
            OpportunityType.CROSS_MARKET: "🔄",
            OpportunityType.SPREAD: "📈",
            OpportunityType.LIQUIDITY_ARB: "💧",
        }.get(self.type, "🎯")
        
        msg = f"{emoji} *套利机会 #{self.id[:8]}*\n"
        msg += f"类型: {self.type.value}\n"
        msg += f"预估收益: *{self.profit_estimate:.2%}*\n\n"
        
        for m in self.markets:
            msg += f"• {m.question[:60]}...\n"
            for o in m.outcomes:
                msg += f"  - {o.name}: {o.price:.2%}\n"
        
        if self.details.get("action"):
            msg += f"\n建议: {self.details['action']}"
        
        return msg
