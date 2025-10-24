"""Discord webhook alerter."""

from typing import Dict, Optional
from datetime import datetime

import aiohttp

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import alerts_sent, alert_delivery_duration
from ..scoring.moon_score import MoonScoreResult
from ..scoring.validators import ValidationResult


class DiscordAlerter(LoggerMixin):
    """Send alerts via Discord webhook."""
    
    def __init__(self):
        self.config = get_config()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize HTTP session."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_alert(
        self,
        moon_score: MoonScoreResult,
        validation: ValidationResult,
        dex: str,
    ) -> bool:
        """
        Send alert to Discord.
        
        Args:
            moon_score: MoonScore calculation result
            validation: Validation result
            dex: DEX name
            
        Returns:
            True if sent successfully
        """
        if not self.config.discord_enabled:
            return False
        
        if not self.config.discord_webhook_url:
            self.logger.warning("Discord webhook URL not configured")
            return False
        
        await self.initialize()
        
        try:
            with alert_delivery_duration.labels(channel="discord").time():
                payload = self._format_webhook_payload(moon_score, validation, dex)
                
                async with self.session.post(
                    self.config.discord_webhook_url,
                    json=payload,
                ) as response:
                    if response.status in [200, 204]:
                        alerts_sent.labels(channel="discord", status="success").inc()
                        self.logger.info(f"Discord alert sent for {moon_score.token_address}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Discord webhook failed: {response.status} - {error_text}")
                        alerts_sent.labels(channel="discord", status="error").inc()
                        return False
        
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {e}")
            alerts_sent.labels(channel="discord", status="error").inc()
            return False
    
    def _format_webhook_payload(
        self,
        moon_score: MoonScoreResult,
        validation: ValidationResult,
        dex: str,
    ) -> Dict:
        """
        Format Discord webhook payload.
        
        Args:
            moon_score: MoonScore result
            validation: Validation result
            dex: DEX name
            
        Returns:
            Webhook payload dictionary
        """
        metrics = moon_score.metrics
        components = moon_score.components
        
        # Determine embed color based on score
        color = self._get_embed_color(moon_score.total_score)
        
        # Build embed
        embed = {
            "title": "🚀 New Token Alert",
            "description": f"**{metrics.name or 'Unknown Token'}** ({metrics.symbol or 'N/A'})",
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "📊 MoonScore",
                    "value": f"**{moon_score.total_score:.2f}/100** {self._get_rating(moon_score.total_score)}",
                    "inline": False,
                },
                {
                    "name": "🏦 DEX",
                    "value": dex.upper(),
                    "inline": True,
                },
                {
                    "name": "⏱️ Age",
                    "value": f"{metrics.age_minutes:.1f} min",
                    "inline": True,
                },
                {
                    "name": "💰 Liquidity",
                    "value": f"${metrics.liquidity_usd:,.2f}",
                    "inline": True,
                },
                {
                    "name": "📈 Volume 24h",
                    "value": f"${metrics.volume_24h:,.2f}",
                    "inline": True,
                },
                {
                    "name": "👥 Holders",
                    "value": str(metrics.total_holders),
                    "inline": True,
                },
                {
                    "name": "📊 Transactions 24h",
                    "value": str(metrics.transactions_24h),
                    "inline": True,
                },
                {
                    "name": "🎯 Buy Pressure",
                    "value": f"{components.buy_pressure:.1f}/100",
                    "inline": True,
                },
                {
                    "name": "💎 Social Momentum",
                    "value": f"{components.social_momentum:.1f}/100",
                    "inline": True,
                },
                {
                    "name": "👨‍💻 Dev Behavior",
                    "value": f"{components.dev_behavior_score:.1f}/100",
                    "inline": True,
                },
                {
                    "name": "✅ Validation",
                    "value": f"{validation.passed_checks}/{validation.passed_checks + validation.failed_checks} checks passed",
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Solana Moon Scanner",
            },
        }
        
        # Add red flags field if any
        if validation.red_flags:
            red_flags_text = "\n".join([f"• {flag}" for flag in validation.red_flags[:3]])
            embed["fields"].append({
                "name": "🚨 Red Flags",
                "value": red_flags_text[:1024],  # Discord field limit
                "inline": False,
            })
        
        # Add warnings field if any
        if validation.warnings:
            warnings_text = "\n".join([f"• {warning}" for warning in validation.warnings[:3]])
            embed["fields"].append({
                "name": "⚠️ Warnings",
                "value": warnings_text[:1024],  # Discord field limit
                "inline": False,
            })
        
        # Add links
        token_addr = metrics.token_address
        links = (
            f"[Solscan](https://solscan.io/token/{token_addr}) | "
            f"[Birdeye](https://birdeye.so/token/{token_addr}) | "
            f"[DexScreener](https://dexscreener.com/solana/{token_addr})"
        )
        embed["fields"].append({
            "name": "🔗 Links",
            "value": links,
            "inline": False,
        })
        
        payload = {
            "embeds": [embed],
            "username": "Moon Scanner Bot",
        }
        
        return payload
    
    def _get_embed_color(self, score: float) -> int:
        """Get Discord embed color based on score."""
        if score >= 90:
            return 0xFFD700  # Gold
        elif score >= 80:
            return 0x00FF00  # Green
        elif score >= 70:
            return 0x32CD32  # Lime green
        elif score >= 60:
            return 0x1E90FF  # Dodger blue
        else:
            return 0x808080  # Gray
    
    def _get_rating(self, score: float) -> str:
        """Get rating emoji for score."""
        if score >= 90:
            return "🌕 MOON SHOT"
        elif score >= 80:
            return "🚀 VERY STRONG"
        elif score >= 70:
            return "💎 STRONG"
        elif score >= 60:
            return "✨ PROMISING"
        else:
            return "📊 MODERATE"
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
