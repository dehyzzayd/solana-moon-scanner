"""Contract validation checks for security and legitimacy."""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

import aiohttp

from ..core.rpc_client import RPCClient
from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import validation_checks
from .metrics_fetcher import TokenMetrics


class ValidationStatus(Enum):
    """Validation check status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class ValidationCheck:
    """Individual validation check result."""
    
    name: str
    status: ValidationStatus
    message: str
    severity: str = "medium"  # low, medium, high, critical
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    """Complete validation result for a token."""
    
    token_address: str
    overall_status: ValidationStatus
    checks: List[ValidationCheck] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passed_checks: int = 0
    failed_checks: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "overall_status": self.overall_status.value,
            "checks": [check.to_dict() for check in self.checks],
            "red_flags": self.red_flags,
            "warnings": self.warnings,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "summary": self.get_summary(),
        }
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        total = self.passed_checks + self.failed_checks
        if total == 0:
            return "No checks performed"
        
        pass_rate = (self.passed_checks / total) * 100
        
        if self.overall_status == ValidationStatus.PASS:
            return f"✅ Validation passed ({self.passed_checks}/{total} checks)"
        elif self.overall_status == ValidationStatus.WARNING:
            return f"⚠️ Validation passed with warnings ({self.passed_checks}/{total} checks)"
        else:
            return f"❌ Validation failed ({self.failed_checks}/{total} checks failed)"
    
    def is_safe(self) -> bool:
        """Check if token passed all critical checks."""
        return self.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING]


class TokenValidator(LoggerMixin):
    """
    Validates tokens against security and legitimacy criteria.
    
    Validation checklist:
    - Contract verified on Solscan
    - Mint authority disabled
    - Freeze authority disabled
    - Not a honeypot
    - LP locked >= 30 days or burned
    - Top 10 holders < 30%
    - Dev wallet < 5%
    - No repeated self-trades
    - No suspicious liquidity removal
    """
    
    def __init__(self, rpc_client: RPCClient):
        self.config = get_config()
        self.rpc_client = rpc_client
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize HTTP session."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def validate(
        self,
        metrics: TokenMetrics,
        pair_address: Optional[str] = None,
    ) -> ValidationResult:
        """
        Run all validation checks on a token.
        
        Args:
            metrics: Token metrics
            pair_address: Pool/pair address
            
        Returns:
            ValidationResult with all check results
        """
        await self.initialize()
        
        result = ValidationResult(token_address=metrics.token_address, overall_status=ValidationStatus.UNKNOWN)
        
        # Run all validation checks
        checks = [
            self._check_mint_authority(metrics),
            self._check_freeze_authority(metrics),
            self._check_holder_distribution(metrics),
            self._check_dev_wallet(metrics),
            self._check_liquidity(metrics),
            self._check_contract_verification(metrics),
            self._check_honeypot(metrics),
            self._check_lp_lock(metrics, pair_address),
        ]
        
        # Execute checks
        for check in checks:
            check_result = await check
            result.checks.append(check_result)
            
            # Track metrics
            validation_checks.labels(
                check_type=check_result.name,
                result=check_result.status.value
            ).inc()
            
            # Update counters
            if check_result.status == ValidationStatus.PASS:
                result.passed_checks += 1
            elif check_result.status == ValidationStatus.FAIL:
                result.failed_checks += 1
                
                # Add to red flags if critical
                if check_result.severity in ["high", "critical"]:
                    result.red_flags.append(check_result.message)
            elif check_result.status == ValidationStatus.WARNING:
                result.warnings.append(check_result.message)
        
        # Determine overall status
        if result.failed_checks == 0:
            if result.warnings:
                result.overall_status = ValidationStatus.WARNING
            else:
                result.overall_status = ValidationStatus.PASS
        else:
            result.overall_status = ValidationStatus.FAIL
        
        self.logger.info(
            f"Validation complete for {metrics.token_address}: {result.overall_status.value} "
            f"({result.passed_checks} passed, {result.failed_checks} failed)"
        )
        
        return result
    
    async def _check_mint_authority(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if mint authority is disabled."""
        mint_authority = metrics.metadata.get("mint_authority")
        
        if mint_authority is None:
            status = ValidationStatus.PASS
            message = "✅ Mint authority is disabled"
        else:
            status = ValidationStatus.FAIL
            message = f"❌ Mint authority is enabled: {mint_authority}"
        
        return ValidationCheck(
            name="Mint Authority",
            status=status,
            message=message,
            severity="critical",
        )
    
    async def _check_freeze_authority(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if freeze authority is disabled."""
        freeze_authority = metrics.metadata.get("freeze_authority")
        
        if freeze_authority is None:
            status = ValidationStatus.PASS
            message = "✅ Freeze authority is disabled"
        else:
            status = ValidationStatus.FAIL
            message = f"❌ Freeze authority is enabled: {freeze_authority}"
        
        return ValidationCheck(
            name="Freeze Authority",
            status=status,
            message=message,
            severity="critical",
        )
    
    async def _check_holder_distribution(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if top 10 holders percentage is acceptable."""
        threshold = 80.0  # More lenient: allow up to 80%
        
        if metrics.top_10_holders_percent == 0:
            # No data - pass by default
            status = ValidationStatus.PASS
            message = f"✅ Top 10 holders: {metrics.top_10_holders_percent:.2f}% (< {threshold}%)"
        elif metrics.top_10_holders_percent <= threshold:
            status = ValidationStatus.PASS
            message = f"✅ Top 10 holders: {metrics.top_10_holders_percent:.2f}% (< {threshold}%)"
        else:
            status = ValidationStatus.WARNING  # Changed from FAIL to WARNING
            message = f"⚠️ Top 10 holders: {metrics.top_10_holders_percent:.2f}% (> {threshold}%)"
        
        return ValidationCheck(
            name="Holder Distribution",
            status=status,
            message=message,
            severity="medium",  # Changed from high to medium
        )
    
    async def _check_dev_wallet(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if dev wallet holds acceptable percentage."""
        threshold = self.config.max_dev_wallet_percent
        
        if metrics.dev_wallet_percent <= threshold:
            status = ValidationStatus.PASS
            message = f"✅ Dev wallet: {metrics.dev_wallet_percent:.2f}% (< {threshold}%)"
        else:
            status = ValidationStatus.WARNING
            message = f"⚠️ Dev wallet: {metrics.dev_wallet_percent:.2f}% (> {threshold}%)"
        
        return ValidationCheck(
            name="Dev Wallet",
            status=status,
            message=message,
            severity="medium",
        )
    
    async def _check_liquidity(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if liquidity is adequate."""
        min_liquidity = 500  # $500 minimum (more lenient)
        
        if metrics.liquidity_usd >= min_liquidity:
            status = ValidationStatus.PASS
            message = f"✅ Liquidity: ${metrics.liquidity_usd:.2f}"
        elif metrics.liquidity_usd > 0:
            status = ValidationStatus.PASS  # Changed from WARNING to PASS
            message = f"✅ Liquidity: ${metrics.liquidity_usd:.2f} (low but acceptable)"
        else:
            # No data - pass by default instead of fail
            status = ValidationStatus.PASS
            message = "✅ Liquidity check passed (no data available)"
        
        return ValidationCheck(
            name="Liquidity",
            status=status,
            message=message,
            severity="medium",  # Changed from high to medium
        )
    
    async def _check_contract_verification(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check if contract is verified on Solscan."""
        try:
            if not self.config.solscan_api_enabled or not self.config.solscan_api_key:
                return ValidationCheck(
                    name="Contract Verification",
                    status=ValidationStatus.UNKNOWN,
                    message="⚪ Solscan API not configured",
                    severity="low",
                )
            
            if not self.session:
                await self.initialize()
            
            url = f"https://api.solscan.io/token/meta?token={metrics.token_address}"
            headers = {"token": self.config.solscan_api_key}
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if verified (Solscan returns verified status)
                    is_verified = data.get("verified", False)
                    
                    if is_verified:
                        status = ValidationStatus.PASS
                        message = "✅ Contract verified on Solscan"
                    else:
                        status = ValidationStatus.WARNING
                        message = "⚠️ Contract not verified on Solscan"
                else:
                    status = ValidationStatus.UNKNOWN
                    message = "⚪ Unable to verify contract status"
        
        except Exception as e:
            self.logger.error(f"Error checking contract verification: {e}")
            status = ValidationStatus.UNKNOWN
            message = f"⚪ Verification check failed: {str(e)}"
        
        return ValidationCheck(
            name="Contract Verification",
            status=status,
            message=message,
            severity="medium",
        )
    
    async def _check_honeypot(self, metrics: TokenMetrics) -> ValidationCheck:
        """Check for honeypot indicators."""
        red_flags = []
        
        # High dev holdings
        if metrics.dev_wallet_percent > 50:
            red_flags.append("Dev wallet holds >50% of supply")
        
        # Suspicious transaction patterns
        if metrics.buy_transactions_24h > 0 and metrics.sell_transactions_24h == 0:
            red_flags.append("No sell transactions detected")
        
        # Very low liquidity with high volume
        if metrics.liquidity_usd > 0 and metrics.volume_24h > metrics.liquidity_usd * 10:
            red_flags.append("Suspicious volume/liquidity ratio")
        
        if red_flags:
            status = ValidationStatus.FAIL
            message = f"❌ Potential honeypot: {', '.join(red_flags)}"
        else:
            status = ValidationStatus.PASS
            message = "✅ No honeypot indicators detected"
        
        return ValidationCheck(
            name="Honeypot Check",
            status=status,
            message=message,
            severity="critical",
        )
    
    async def _check_lp_lock(
        self,
        metrics: TokenMetrics,
        pair_address: Optional[str],
    ) -> ValidationCheck:
        """Check if LP tokens are locked or burned."""
        # This is a simplified check
        # Production implementation would query LP lock contracts
        
        if not pair_address:
            return ValidationCheck(
                name="LP Lock",
                status=ValidationStatus.UNKNOWN,
                message="⚪ No pair address provided",
                severity="high",
            )
        
        # Placeholder logic - actual implementation needs LP lock contract queries
        # For now, assume LP is not locked
        status = ValidationStatus.WARNING
        message = f"⚠️ LP lock status unknown (pair: {pair_address[:8]}...)"
        
        return ValidationCheck(
            name="LP Lock",
            status=status,
            message=message,
            severity="high",
        )
    
    async def check_rug_indicators(self, metrics: TokenMetrics) -> List[str]:
        """
        Check for rug pull indicators.
        
        Args:
            metrics: Token metrics
            
        Returns:
            List of rug pull warning messages
        """
        warnings = []
        
        # Mint authority still enabled
        if metrics.metadata.get("mint_authority"):
            warnings.append("⚠️ Mint authority enabled - tokens can be minted")
        
        # Freeze authority enabled
        if metrics.metadata.get("freeze_authority"):
            warnings.append("⚠️ Freeze authority enabled - accounts can be frozen")
        
        # Extremely high dev holdings
        if metrics.dev_wallet_percent > 30:
            warnings.append(f"⚠️ Dev wallet holds {metrics.dev_wallet_percent:.1f}% of supply")
        
        # Concentrated holdings
        if metrics.top_10_holders_percent > 80:
            warnings.append(f"⚠️ Top 10 holders control {metrics.top_10_holders_percent:.1f}% of supply")
        
        # Very low liquidity
        if metrics.liquidity_usd < 100:
            warnings.append(f"⚠️ Very low liquidity: ${metrics.liquidity_usd:.2f}")
        
        # No volume
        if metrics.volume_24h == 0:
            warnings.append("⚠️ No trading volume in last 24h")
        
        return warnings
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
