"""MoonScore calculation engine for ranking token potential."""

from typing import Dict, Optional
from dataclasses import dataclass

from ..utils.logger import LoggerMixin
from ..utils.metrics import moon_score_distribution
from .metrics_fetcher import TokenMetrics


@dataclass
class MoonScoreComponents:
    """Individual components of MoonScore."""
    
    buy_pressure: float = 0.0
    volume_liquidity_ratio: float = 0.0
    social_momentum: float = 0.0
    holder_growth_rate: float = 0.0
    dev_behavior_score: float = 0.0
    technical_pattern_score: float = 0.0
    market_timing_score: float = 0.0
    age_multiplier: float = 1.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "buy_pressure": self.buy_pressure,
            "volume_liquidity_ratio": self.volume_liquidity_ratio,
            "social_momentum": self.social_momentum,
            "holder_growth_rate": self.holder_growth_rate,
            "dev_behavior_score": self.dev_behavior_score,
            "technical_pattern_score": self.technical_pattern_score,
            "market_timing_score": self.market_timing_score,
            "age_multiplier": self.age_multiplier,
        }


@dataclass
class MoonScoreResult:
    """Result of MoonScore calculation."""
    
    token_address: str
    total_score: float
    components: MoonScoreComponents
    metrics: TokenMetrics
    social_metrics: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "total_score": self.total_score,
            "components": self.components.to_dict(),
            "metrics": self.metrics.to_dict(),
            "social_metrics": self.social_metrics,
        }


class MoonScoreCalculator(LoggerMixin):
    """
    Calculate MoonScore for tokens using the formula:
    
    MoonScore = (
        (BuyPressure% * 0.25) +
        (Volume/Liquidity * 0.20) +
        (SocialMomentum * 0.15) +
        (HolderGrowthRate * 0.15) +
        (DevBehaviorScore * 0.10) +
        (TechnicalPatternScore * 0.10) +
        (MarketTimingScore * 0.05)
    ) * AgeMultiplier
    
    Where AgeMultiplier:
    - 0-15 minutes: 1.5
    - 15-30 minutes: 1.2
    - 30-60 minutes: 1.0
    """
    
    # Weight factors
    WEIGHTS = {
        "buy_pressure": 0.25,
        "volume_liquidity": 0.20,
        "social_momentum": 0.15,
        "holder_growth": 0.15,
        "dev_behavior": 0.10,
        "technical_pattern": 0.10,
        "market_timing": 0.05,
    }
    
    def calculate(
        self,
        metrics: TokenMetrics,
        social_metrics: Optional[Dict] = None,
    ) -> MoonScoreResult:
        """
        Calculate MoonScore for a token.
        
        Args:
            metrics: Token metrics
            social_metrics: Social media metrics (optional)
            
        Returns:
            MoonScoreResult with score and breakdown
        """
        if social_metrics is None:
            social_metrics = {}
        
        # Calculate individual components
        components = MoonScoreComponents()
        
        components.buy_pressure = self._calculate_buy_pressure(metrics)
        components.volume_liquidity_ratio = self._calculate_volume_liquidity_ratio(metrics)
        components.social_momentum = self._calculate_social_momentum(social_metrics)
        components.holder_growth_rate = self._calculate_holder_growth(metrics)
        components.dev_behavior_score = self._calculate_dev_behavior(metrics)
        components.technical_pattern_score = self._calculate_technical_pattern(metrics)
        components.market_timing_score = self._calculate_market_timing(metrics)
        components.age_multiplier = self._calculate_age_multiplier(metrics.age_minutes)
        
        # Calculate weighted score
        base_score = (
            components.buy_pressure * self.WEIGHTS["buy_pressure"] +
            components.volume_liquidity_ratio * self.WEIGHTS["volume_liquidity"] +
            components.social_momentum * self.WEIGHTS["social_momentum"] +
            components.holder_growth_rate * self.WEIGHTS["holder_growth"] +
            components.dev_behavior_score * self.WEIGHTS["dev_behavior"] +
            components.technical_pattern_score * self.WEIGHTS["technical_pattern"] +
            components.market_timing_score * self.WEIGHTS["market_timing"]
        )
        
        # Apply age multiplier
        total_score = base_score * components.age_multiplier
        
        # Clamp to 0-100 range
        total_score = max(0.0, min(100.0, total_score))
        
        # Track metrics
        moon_score_distribution.observe(total_score)
        
        self.logger.debug(
            f"MoonScore for {metrics.token_address}: {total_score:.2f} "
            f"(base: {base_score:.2f}, multiplier: {components.age_multiplier})"
        )
        
        return MoonScoreResult(
            token_address=metrics.token_address,
            total_score=total_score,
            components=components,
            metrics=metrics,
            social_metrics=social_metrics,
        )
    
    def _calculate_buy_pressure(self, metrics: TokenMetrics) -> float:
        """
        Calculate buy pressure score (0-100).
        
        Buy pressure = (buy_transactions / total_transactions) * 100
        """
        total_txs = metrics.buy_transactions_24h + metrics.sell_transactions_24h
        
        if total_txs == 0:
            return 50.0  # Neutral score if no data
        
        buy_percentage = (metrics.buy_transactions_24h / total_txs) * 100
        
        # Normalize: 50% = neutral (50 points), 100% = maximum (100 points)
        score = buy_percentage
        
        return max(0.0, min(100.0, score))
    
    def _calculate_volume_liquidity_ratio(self, metrics: TokenMetrics) -> float:
        """
        Calculate volume/liquidity ratio score (0-100).
        
        Higher ratio indicates more trading activity relative to liquidity.
        """
        if metrics.liquidity_usd == 0:
            return 0.0
        
        ratio = metrics.volume_24h / metrics.liquidity_usd
        
        # Normalize: ratio of 1.0 = 50 points, 5.0+ = 100 points
        score = min(ratio / 5.0 * 100, 100.0)
        
        return max(0.0, min(100.0, score))
    
    def _calculate_social_momentum(self, social_metrics: Dict) -> float:
        """
        Calculate social momentum score (0-100).
        
        Based on Twitter mentions growth rate.
        """
        mentions_24h = social_metrics.get("twitter_mentions_24h", 0)
        growth_rate = social_metrics.get("twitter_mentions_growth", 0.0)
        
        # Score based on mention volume and growth
        volume_score = min(mentions_24h / 100 * 50, 50)  # Max 50 points for volume
        growth_score = min(growth_rate * 5, 50)  # Max 50 points for growth
        
        score = volume_score + growth_score
        
        return max(0.0, min(100.0, score))
    
    def _calculate_holder_growth(self, metrics: TokenMetrics) -> float:
        """
        Calculate holder growth rate score (0-100).
        
        Based on 24h holder increase.
        """
        if metrics.total_holders == 0:
            return 0.0
        
        # Calculate growth rate as percentage
        growth_rate = (metrics.holder_growth_24h / max(metrics.total_holders, 1)) * 100
        
        # Normalize: 50% growth = 75 points, 100%+ growth = 100 points
        score = min(growth_rate / 100 * 100, 100)
        
        return max(0.0, min(100.0, score))
    
    def _calculate_dev_behavior(self, metrics: TokenMetrics) -> float:
        """
        Calculate dev behavior score (0-100).
        
        Higher score = more trustworthy (low dev holdings, disabled authorities).
        """
        score = 100.0
        
        # Penalize high dev wallet percentage
        if metrics.dev_wallet_percent > 5:
            penalty = (metrics.dev_wallet_percent - 5) * 5
            score -= min(penalty, 50)
        
        # Penalize if mint authority still enabled
        if metrics.metadata.get("mint_authority"):
            score -= 30
        
        # Penalize if freeze authority still enabled
        if metrics.metadata.get("freeze_authority"):
            score -= 20
        
        return max(0.0, min(100.0, score))
    
    def _calculate_technical_pattern(self, metrics: TokenMetrics) -> float:
        """
        Calculate technical pattern score (0-100).
        
        Based on price action and transaction patterns.
        """
        score = 50.0  # Start with neutral score
        
        # Positive indicators
        if metrics.price_change_24h > 0:
            score += min(metrics.price_change_24h / 10, 30)  # Max 30 points for price gain
        
        # Good transaction volume
        if metrics.transactions_24h > 100:
            score += min(metrics.transactions_24h / 100 * 20, 20)  # Max 20 points
        
        # Negative indicators
        if metrics.price_change_24h < -10:
            score -= 20
        
        return max(0.0, min(100.0, score))
    
    def _calculate_market_timing(self, metrics: TokenMetrics) -> float:
        """
        Calculate market timing score (0-100).
        
        Based on launch time and market conditions.
        """
        score = 50.0  # Base score
        
        # Prefer very fresh tokens (< 30 minutes)
        if metrics.age_minutes < 30:
            score += 30
        elif metrics.age_minutes < 45:
            score += 15
        
        # Good liquidity depth
        if metrics.liquidity_usd > 10000:
            score += 20
        elif metrics.liquidity_usd > 5000:
            score += 10
        
        return max(0.0, min(100.0, score))
    
    def _calculate_age_multiplier(self, age_minutes: float) -> float:
        """
        Calculate age multiplier based on token age.
        
        - 0-15 minutes: 1.5x
        - 15-30 minutes: 1.2x
        - 30-60 minutes: 1.0x
        """
        if age_minutes <= 15:
            return 1.5
        elif age_minutes <= 30:
            return 1.2
        else:
            return 1.0
    
    def get_rating(self, score: float) -> str:
        """
        Get human-readable rating for a score.
        
        Args:
            score: MoonScore value
            
        Returns:
            Rating string
        """
        if score >= 90:
            return "🌕 MOON SHOT"
        elif score >= 80:
            return "🚀 VERY STRONG"
        elif score >= 70:
            return "💎 STRONG"
        elif score >= 60:
            return "✨ PROMISING"
        elif score >= 50:
            return "📊 MODERATE"
        elif score >= 40:
            return "⚠️ WEAK"
        else:
            return "🚫 VERY WEAK"
