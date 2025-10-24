"""Telegram bot for sending alerts."""

from typing import Optional
import html

from telegram import Bot
from telegram.error import TelegramError

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import alerts_sent, alert_delivery_duration
from ..scoring.moon_score import MoonScoreResult
from ..scoring.validators import ValidationResult


class TelegramAlerter(LoggerMixin):
    """Send alerts via Telegram bot."""
    
    def __init__(self):
        self.config = get_config()
        self.bot: Optional[Bot] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize Telegram bot."""
        if self._initialized:
            return
        
        if not self.config.telegram_enabled:
            self.logger.info("Telegram alerts disabled")
            return
        
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            self.logger.warning("Telegram credentials not configured")
            return
        
        try:
            self.bot = Bot(token=self.config.telegram_bot_token)
            self._initialized = True
            self.logger.info("Telegram bot initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
    
    async def send_alert(
        self,
        moon_score: MoonScoreResult,
        validation: ValidationResult,
        dex: str,
    ) -> bool:
        """
        Send alert to Telegram.
        
        Args:
            moon_score: MoonScore calculation result
            validation: Validation result
            dex: DEX name
            
        Returns:
            True if sent successfully
        """
        if not self.config.telegram_enabled:
            return False
        
        if not self._initialized:
            self.initialize()
        
        if not self.bot:
            return False
        
        try:
            with alert_delivery_duration.labels(channel="telegram").time():
                message = self._format_message(moon_score, validation, dex)
                
                await self.bot.send_message(
                    chat_id=self.config.telegram_chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
            
            alerts_sent.labels(channel="telegram", status="success").inc()
            self.logger.info(f"Telegram alert sent for {moon_score.token_address}")
            return True
        
        except TelegramError as e:
            self.logger.error(f"Telegram error: {e}")
            alerts_sent.labels(channel="telegram", status="error").inc()
            return False
        
        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")
            alerts_sent.labels(channel="telegram", status="error").inc()
            return False
    
    def _format_message(
        self,
        moon_score: MoonScoreResult,
        validation: ValidationResult,
        dex: str,
    ) -> str:
        """
        Format alert message for Telegram.
        
        Args:
            moon_score: MoonScore result
            validation: Validation result
            dex: DEX name
            
        Returns:
            Formatted HTML message
        """
        metrics = moon_score.metrics
        components = moon_score.components
        
        # Escape HTML
        token_addr = html.escape(metrics.token_address)
        symbol = html.escape(metrics.symbol or "Unknown")
        name = html.escape(metrics.name or "Unknown Token")
        
        # Build message
        lines = [
            "🚀 <b>NEW TOKEN ALERT</b> 🚀",
            "",
            f"<b>MoonScore:</b> {moon_score.total_score:.2f}/100",
            f"<b>Rating:</b> {self._get_rating_emoji(moon_score.total_score)} {self._get_rating(moon_score.total_score)}",
            "",
            "<b>📊 Token Info</b>",
            f"<b>Name:</b> {name}",
            f"<b>Symbol:</b> {symbol}",
            f"<b>DEX:</b> {dex.upper()}",
            f"<b>Age:</b> {metrics.age_minutes:.1f} min",
            "",
            "<b>💰 Metrics</b>",
            f"<b>Liquidity:</b> ${metrics.liquidity_usd:,.2f}",
            f"<b>Volume 24h:</b> ${metrics.volume_24h:,.2f}",
            f"<b>Holders:</b> {metrics.total_holders}",
            f"<b>Transactions 24h:</b> {metrics.transactions_24h}",
            "",
            "<b>📈 Score Breakdown</b>",
            f"Buy Pressure: {components.buy_pressure:.1f}/100",
            f"Volume/Liquidity: {components.volume_liquidity_ratio:.1f}/100",
            f"Social Momentum: {components.social_momentum:.1f}/100",
            f"Holder Growth: {components.holder_growth_rate:.1f}/100",
            f"Dev Behavior: {components.dev_behavior_score:.1f}/100",
            "",
            "<b>✅ Validation</b>",
            f"Status: {validation.get_summary()}",
            f"Passed: {validation.passed_checks}/{validation.passed_checks + validation.failed_checks}",
        ]
        
        # Add red flags
        if validation.red_flags:
            lines.append("")
            lines.append("<b>🚨 Red Flags:</b>")
            for flag in validation.red_flags[:3]:
                lines.append(f"• {html.escape(flag)}")
        
        # Add warnings
        if validation.warnings:
            lines.append("")
            lines.append("<b>⚠️ Warnings:</b>")
            for warning in validation.warnings[:3]:
                lines.append(f"• {html.escape(warning)}")
        
        # Add links
        lines.extend([
            "",
            "<b>🔗 Links</b>",
            f"<a href='https://solscan.io/token/{token_addr}'>Solscan</a> | "
            f"<a href='https://birdeye.so/token/{token_addr}'>Birdeye</a> | "
            f"<a href='https://dexscreener.com/solana/{token_addr}'>DexScreener</a>",
        ])
        
        return "\n".join(lines)
    
    def _get_rating(self, score: float) -> str:
        """Get rating text for score."""
        if score >= 90:
            return "MOON SHOT"
        elif score >= 80:
            return "VERY STRONG"
        elif score >= 70:
            return "STRONG"
        elif score >= 60:
            return "PROMISING"
        else:
            return "MODERATE"
    
    def _get_rating_emoji(self, score: float) -> str:
        """Get emoji for score."""
        if score >= 90:
            return "🌕"
        elif score >= 80:
            return "🚀"
        elif score >= 70:
            return "💎"
        elif score >= 60:
            return "✨"
        else:
            return "📊"
