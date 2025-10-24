"""Tests for MoonScore calculation."""

import pytest
from src.scoring.moon_score import MoonScoreCalculator, MoonScoreComponents
from src.scoring.metrics_fetcher import TokenMetrics


class TestMoonScoreCalculator:
    """Test MoonScore calculation logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = MoonScoreCalculator()
    
    def test_perfect_score_conditions(self):
        """Test perfect score conditions."""
        metrics = TokenMetrics(
            token_address="test123",
            total_supply=1000000,
            buy_transactions_24h=100,
            sell_transactions_24h=0,
            volume_24h=100000,
            liquidity_usd=10000,
            total_holders=500,
            holder_growth_24h=250,
            dev_wallet_percent=1.0,
            age_minutes=10.0,
        )
        
        social_metrics = {
            "twitter_mentions_24h": 200,
            "twitter_mentions_growth": 100.0,
        }
        
        result = self.calculator.calculate(metrics, social_metrics)
        
        # Should be very high score
        assert result.total_score >= 80.0
        assert result.components.buy_pressure >= 90.0
        assert result.components.age_multiplier == 1.5  # 0-15 minutes
    
    def test_buy_pressure_calculation(self):
        """Test buy pressure calculation."""
        metrics = TokenMetrics(
            token_address="test123",
            buy_transactions_24h=75,
            sell_transactions_24h=25,
        )
        
        result = self.calculator.calculate(metrics, {})
        
        # 75% buy rate should give 75 score
        assert 70 <= result.components.buy_pressure <= 80
    
    def test_volume_liquidity_ratio(self):
        """Test volume/liquidity ratio calculation."""
        metrics = TokenMetrics(
            token_address="test123",
            volume_24h=50000,
            liquidity_usd=10000,
        )
        
        result = self.calculator.calculate(metrics, {})
        
        # Ratio of 5.0 should give maximum score
        assert result.components.volume_liquidity_ratio == 100.0
    
    def test_age_multiplier(self):
        """Test age multiplier calculation."""
        # Young token (10 minutes)
        assert self.calculator._calculate_age_multiplier(10) == 1.5
        
        # Medium age (20 minutes)
        assert self.calculator._calculate_age_multiplier(20) == 1.2
        
        # Older token (45 minutes)
        assert self.calculator._calculate_age_multiplier(45) == 1.0
    
    def test_dev_behavior_penalties(self):
        """Test dev behavior scoring with penalties."""
        # Good dev behavior
        metrics_good = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=3.0,
            metadata={
                "mint_authority": None,
                "freeze_authority": None,
            },
        )
        
        result_good = self.calculator.calculate(metrics_good, {})
        
        # Bad dev behavior
        metrics_bad = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=15.0,
            metadata={
                "mint_authority": "some_address",
                "freeze_authority": "some_address",
            },
        )
        
        result_bad = self.calculator.calculate(metrics_bad, {})
        
        # Good behavior should score higher
        assert result_good.components.dev_behavior_score > result_bad.components.dev_behavior_score
        assert result_bad.components.dev_behavior_score < 50  # Should be penalized
    
    def test_social_momentum_scoring(self):
        """Test social momentum calculation."""
        social_high = {
            "twitter_mentions_24h": 150,
            "twitter_mentions_growth": 50.0,
        }
        
        social_low = {
            "twitter_mentions_24h": 5,
            "twitter_mentions_growth": 1.0,
        }
        
        metrics = TokenMetrics(token_address="test123")
        
        result_high = self.calculator.calculate(metrics, social_high)
        result_low = self.calculator.calculate(metrics, social_low)
        
        assert result_high.components.social_momentum > result_low.components.social_momentum
    
    def test_score_clamping(self):
        """Test that scores are clamped to 0-100 range."""
        # Extreme values
        metrics = TokenMetrics(
            token_address="test123",
            buy_transactions_24h=1000,
            volume_24h=1000000,
            liquidity_usd=1000,
            total_holders=10000,
            holder_growth_24h=5000,
            age_minutes=5.0,
        )
        
        social_metrics = {
            "twitter_mentions_24h": 1000,
            "twitter_mentions_growth": 500.0,
        }
        
        result = self.calculator.calculate(metrics, social_metrics)
        
        # Score should be clamped to 100
        assert 0 <= result.total_score <= 100
        
        # Components should also be clamped
        assert 0 <= result.components.buy_pressure <= 100
        assert 0 <= result.components.volume_liquidity_ratio <= 100
        assert 0 <= result.components.social_momentum <= 100
    
    def test_rating_labels(self):
        """Test rating label generation."""
        assert "MOON SHOT" in self.calculator.get_rating(95)
        assert "VERY STRONG" in self.calculator.get_rating(85)
        assert "STRONG" in self.calculator.get_rating(75)
        assert "PROMISING" in self.calculator.get_rating(65)
        assert "MODERATE" in self.calculator.get_rating(55)
        assert "WEAK" in self.calculator.get_rating(45)
        assert "VERY WEAK" in self.calculator.get_rating(35)
    
    def test_zero_liquidity_handling(self):
        """Test handling of zero liquidity."""
        metrics = TokenMetrics(
            token_address="test123",
            volume_24h=1000,
            liquidity_usd=0.0,  # Zero liquidity
        )
        
        result = self.calculator.calculate(metrics, {})
        
        # Should not crash and should give 0 for volume/liquidity ratio
        assert result.components.volume_liquidity_ratio == 0.0
    
    def test_no_transactions_handling(self):
        """Test handling of no transactions."""
        metrics = TokenMetrics(
            token_address="test123",
            buy_transactions_24h=0,
            sell_transactions_24h=0,
        )
        
        result = self.calculator.calculate(metrics, {})
        
        # Should give neutral score when no data
        assert result.components.buy_pressure == 50.0


class TestWeightedScoring:
    """Test weighted scoring formula."""
    
    def test_weight_sum(self):
        """Test that weights sum to 1.0."""
        calculator = MoonScoreCalculator()
        weight_sum = sum(calculator.WEIGHTS.values())
        assert abs(weight_sum - 1.0) < 0.001  # Allow small floating point error
    
    def test_individual_weights(self):
        """Test individual weight values."""
        calculator = MoonScoreCalculator()
        
        assert calculator.WEIGHTS["buy_pressure"] == 0.25
        assert calculator.WEIGHTS["volume_liquidity"] == 0.20
        assert calculator.WEIGHTS["social_momentum"] == 0.15
        assert calculator.WEIGHTS["holder_growth"] == 0.15
        assert calculator.WEIGHTS["dev_behavior"] == 0.10
        assert calculator.WEIGHTS["technical_pattern"] == 0.10
        assert calculator.WEIGHTS["market_timing"] == 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
