"""Generic webhook sender for custom integrations."""

import hmac
import hashlib
import json
from typing import Dict, Optional
from datetime import datetime

import aiohttp

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import alerts_sent, alert_delivery_duration
from ..scoring.moon_score import MoonScoreResult
from ..scoring.validators import ValidationResult


class WebhookSender(LoggerMixin):
    """Send alerts via generic webhook with HMAC signature."""
    
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
        Send alert via webhook.
        
        Args:
            moon_score: MoonScore calculation result
            validation: Validation result
            dex: DEX name
            
        Returns:
            True if sent successfully
        """
        if not self.config.webhook_enabled:
            return False
        
        if not self.config.webhook_url:
            self.logger.warning("Webhook URL not configured")
            return False
        
        await self.initialize()
        
        try:
            with alert_delivery_duration.labels(channel="webhook").time():
                payload = self._format_payload(moon_score, validation, dex)
                
                # Generate HMAC signature if secret is configured
                headers = {"Content-Type": "application/json"}
                if self.config.webhook_secret:
                    signature = self._generate_signature(payload)
                    headers["X-Webhook-Signature"] = signature
                
                async with self.session.post(
                    self.config.webhook_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        alerts_sent.labels(channel="webhook", status="success").inc()
                        self.logger.info(f"Webhook alert sent for {moon_score.token_address}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Webhook failed: {response.status} - {error_text}")
                        alerts_sent.labels(channel="webhook", status="error").inc()
                        return False
        
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            alerts_sent.labels(channel="webhook", status="error").inc()
            return False
    
    def _format_payload(
        self,
        moon_score: MoonScoreResult,
        validation: ValidationResult,
        dex: str,
    ) -> Dict:
        """
        Format webhook payload.
        
        Args:
            moon_score: MoonScore result
            validation: Validation result
            dex: DEX name
            
        Returns:
            Payload dictionary
        """
        return {
            "event": "token_alert",
            "timestamp": datetime.now().isoformat(),
            "dex": dex,
            "moon_score": {
                "total_score": moon_score.total_score,
                "rating": self._get_rating(moon_score.total_score),
                "components": moon_score.components.to_dict(),
            },
            "token": {
                "address": moon_score.metrics.token_address,
                "symbol": moon_score.metrics.symbol,
                "name": moon_score.metrics.name,
                "age_minutes": moon_score.metrics.age_minutes,
            },
            "metrics": moon_score.metrics.to_dict(),
            "validation": validation.to_dict(),
            "social": moon_score.social_metrics,
            "links": {
                "solscan": f"https://solscan.io/token/{moon_score.metrics.token_address}",
                "birdeye": f"https://birdeye.so/token/{moon_score.metrics.token_address}",
                "dexscreener": f"https://dexscreener.com/solana/{moon_score.metrics.token_address}",
            },
        }
    
    def _generate_signature(self, payload: Dict) -> str:
        """
        Generate HMAC signature for payload.
        
        Args:
            payload: Payload dictionary
            
        Returns:
            Hex-encoded HMAC signature
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        secret_bytes = self.config.webhook_secret.encode()
        
        signature = hmac.new(
            secret_bytes,
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        
        return signature
    
    def _get_rating(self, score: float) -> str:
        """Get rating text for score."""
        if score >= 90:
            return "MOON_SHOT"
        elif score >= 80:
            return "VERY_STRONG"
        elif score >= 70:
            return "STRONG"
        elif score >= 60:
            return "PROMISING"
        else:
            return "MODERATE"
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
