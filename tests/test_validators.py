"""Tests for token validators."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scoring.validators import (
    TokenValidator,
    ValidationStatus,
    ValidationCheck,
    ValidationResult,
)
from src.scoring.metrics_fetcher import TokenMetrics
from src.core.rpc_client import RPCClient


@pytest.fixture
def mock_rpc_client():
    """Create mock RPC client."""
    return MagicMock(spec=RPCClient)


@pytest.fixture
async def validator(mock_rpc_client):
    """Create TokenValidator instance."""
    validator = TokenValidator(mock_rpc_client)
    await validator.initialize()
    yield validator
    await validator.close()


class TestMintAuthorityCheck:
    """Test mint authority validation."""
    
    @pytest.mark.asyncio
    async def test_disabled_mint_authority_passes(self, validator):
        """Test that disabled mint authority passes."""
        metrics = TokenMetrics(
            token_address="test123",
            metadata={"mint_authority": None},
        )
        
        check = await validator._check_mint_authority(metrics)
        
        assert check.status == ValidationStatus.PASS
        assert "disabled" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_enabled_mint_authority_fails(self, validator):
        """Test that enabled mint authority fails."""
        metrics = TokenMetrics(
            token_address="test123",
            metadata={"mint_authority": "some_address_here"},
        )
        
        check = await validator._check_mint_authority(metrics)
        
        assert check.status == ValidationStatus.FAIL
        assert check.severity == "critical"


class TestFreezeAuthorityCheck:
    """Test freeze authority validation."""
    
    @pytest.mark.asyncio
    async def test_disabled_freeze_authority_passes(self, validator):
        """Test that disabled freeze authority passes."""
        metrics = TokenMetrics(
            token_address="test123",
            metadata={"freeze_authority": None},
        )
        
        check = await validator._check_freeze_authority(metrics)
        
        assert check.status == ValidationStatus.PASS
    
    @pytest.mark.asyncio
    async def test_enabled_freeze_authority_fails(self, validator):
        """Test that enabled freeze authority fails."""
        metrics = TokenMetrics(
            token_address="test123",
            metadata={"freeze_authority": "some_address_here"},
        )
        
        check = await validator._check_freeze_authority(metrics)
        
        assert check.status == ValidationStatus.FAIL
        assert check.severity == "critical"


class TestHolderDistributionCheck:
    """Test holder distribution validation."""
    
    @pytest.mark.asyncio
    async def test_acceptable_holder_distribution_passes(self, validator):
        """Test that acceptable distribution passes."""
        metrics = TokenMetrics(
            token_address="test123",
            top_10_holders_percent=25.0,  # Below 30% threshold
        )
        
        check = await validator._check_holder_distribution(metrics)
        
        assert check.status == ValidationStatus.PASS
    
    @pytest.mark.asyncio
    async def test_high_holder_concentration_fails(self, validator):
        """Test that high concentration fails."""
        metrics = TokenMetrics(
            token_address="test123",
            top_10_holders_percent=85.0,  # Above 30% threshold
        )
        
        check = await validator._check_holder_distribution(metrics)
        
        assert check.status == ValidationStatus.FAIL
        assert check.severity == "high"


class TestDevWalletCheck:
    """Test dev wallet percentage validation."""
    
    @pytest.mark.asyncio
    async def test_acceptable_dev_holdings_passes(self, validator):
        """Test that acceptable dev holdings pass."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=3.0,  # Below 5% threshold
        )
        
        check = await validator._check_dev_wallet(metrics)
        
        assert check.status == ValidationStatus.PASS
    
    @pytest.mark.asyncio
    async def test_high_dev_holdings_warns(self, validator):
        """Test that high dev holdings trigger warning."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=15.0,  # Above 5% threshold
        )
        
        check = await validator._check_dev_wallet(metrics)
        
        assert check.status == ValidationStatus.WARNING
        assert check.severity == "medium"


class TestLiquidityCheck:
    """Test liquidity validation."""
    
    @pytest.mark.asyncio
    async def test_adequate_liquidity_passes(self, validator):
        """Test that adequate liquidity passes."""
        metrics = TokenMetrics(
            token_address="test123",
            liquidity_usd=50000.0,
        )
        
        check = await validator._check_liquidity(metrics)
        
        assert check.status == ValidationStatus.PASS
    
    @pytest.mark.asyncio
    async def test_low_liquidity_warns(self, validator):
        """Test that low liquidity triggers warning."""
        metrics = TokenMetrics(
            token_address="test123",
            liquidity_usd=500.0,  # Below $1000 minimum
        )
        
        check = await validator._check_liquidity(metrics)
        
        assert check.status == ValidationStatus.WARNING
    
    @pytest.mark.asyncio
    async def test_no_liquidity_fails(self, validator):
        """Test that no liquidity fails."""
        metrics = TokenMetrics(
            token_address="test123",
            liquidity_usd=0.0,
        )
        
        check = await validator._check_liquidity(metrics)
        
        assert check.status == ValidationStatus.FAIL


class TestHoneypotCheck:
    """Test honeypot detection."""
    
    @pytest.mark.asyncio
    async def test_normal_token_passes(self, validator):
        """Test that normal token passes honeypot check."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=5.0,
            buy_transactions_24h=50,
            sell_transactions_24h=50,
            volume_24h=10000,
            liquidity_usd=5000,
        )
        
        check = await validator._check_honeypot(metrics)
        
        assert check.status == ValidationStatus.PASS
    
    @pytest.mark.asyncio
    async def test_high_dev_holdings_fails(self, validator):
        """Test that excessive dev holdings fail."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=60.0,  # > 50%
            buy_transactions_24h=10,
            sell_transactions_24h=5,
        )
        
        check = await validator._check_honeypot(metrics)
        
        assert check.status == ValidationStatus.FAIL
        assert check.severity == "critical"
    
    @pytest.mark.asyncio
    async def test_no_sells_fails(self, validator):
        """Test that tokens with only buys fail."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=5.0,
            buy_transactions_24h=100,
            sell_transactions_24h=0,  # No sells
        )
        
        check = await validator._check_honeypot(metrics)
        
        assert check.status == ValidationStatus.FAIL
    
    @pytest.mark.asyncio
    async def test_suspicious_volume_ratio_fails(self, validator):
        """Test that suspicious volume/liquidity ratio fails."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=5.0,
            buy_transactions_24h=50,
            sell_transactions_24h=50,
            volume_24h=100000,  # Very high
            liquidity_usd=1000,  # Very low - ratio > 10
        )
        
        check = await validator._check_honeypot(metrics)
        
        assert check.status == ValidationStatus.FAIL


class TestRugIndicators:
    """Test rug pull indicator detection."""
    
    @pytest.mark.asyncio
    async def test_safe_token_no_warnings(self, validator):
        """Test that safe token has no rug indicators."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=2.0,
            top_10_holders_percent=25.0,
            liquidity_usd=10000,
            volume_24h=5000,
            metadata={
                "mint_authority": None,
                "freeze_authority": None,
            },
        )
        
        warnings = await validator.check_rug_indicators(metrics)
        
        assert len(warnings) == 0
    
    @pytest.mark.asyncio
    async def test_risky_token_multiple_warnings(self, validator):
        """Test that risky token has multiple warnings."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=40.0,  # High
            top_10_holders_percent=85.0,  # Concentrated
            liquidity_usd=50,  # Very low
            volume_24h=0,  # No volume
            metadata={
                "mint_authority": "some_address",  # Enabled
                "freeze_authority": "some_address",  # Enabled
            },
        )
        
        warnings = await validator.check_rug_indicators(metrics)
        
        assert len(warnings) >= 4  # Should have multiple warnings
        assert any("mint authority" in w.lower() for w in warnings)
        assert any("freeze authority" in w.lower() for w in warnings)
        assert any("dev wallet" in w.lower() for w in warnings)
        assert any("liquidity" in w.lower() for w in warnings)


class TestValidationResult:
    """Test ValidationResult class."""
    
    @pytest.mark.asyncio
    async def test_overall_pass_status(self, validator):
        """Test overall pass status."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=3.0,
            top_10_holders_percent=25.0,
            liquidity_usd=10000,
            metadata={
                "mint_authority": None,
                "freeze_authority": None,
            },
        )
        
        result = await validator.validate(metrics)
        
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING]
        assert result.is_safe()
    
    @pytest.mark.asyncio
    async def test_overall_fail_status(self, validator):
        """Test overall fail status."""
        metrics = TokenMetrics(
            token_address="test123",
            dev_wallet_percent=60.0,
            top_10_holders_percent=90.0,
            liquidity_usd=0,
            metadata={
                "mint_authority": "enabled",
                "freeze_authority": "enabled",
            },
        )
        
        result = await validator.validate(metrics)
        
        assert result.overall_status == ValidationStatus.FAIL
        assert not result.is_safe()
        assert result.failed_checks > 0
    
    def test_validation_summary(self):
        """Test validation summary generation."""
        result = ValidationResult(
            token_address="test123",
            overall_status=ValidationStatus.PASS,
            passed_checks=8,
            failed_checks=0,
        )
        
        summary = result.get_summary()
        
        assert "passed" in summary.lower()
        assert "8/8" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
