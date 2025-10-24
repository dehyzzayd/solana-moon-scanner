"""Main scanner application orchestrator."""

import asyncio
from typing import Optional
from datetime import datetime

from .core.rpc_client import RPCClient
from .core.dex_monitor import DEXMonitor, TokenPair
from .scoring.metrics_fetcher import MetricsFetcher
from .scoring.moon_score import MoonScoreCalculator
from .scoring.validators import TokenValidator
from .alerts.telegram_bot import TelegramAlerter
from .alerts.discord_bot import DiscordAlerter
from .alerts.webhook_sender import WebhookSender
from .utils.config import get_config
from .utils.logger import LoggerMixin, setup_logger
from .utils.metrics import (
    start_metrics_server,
    tokens_alerted,
    token_processing_duration,
    tokens_in_memory,
)


class MoonScanner(LoggerMixin):
    """
    Main scanner application.
    
    Coordinates DEX monitoring, scoring, validation, and alerting.
    """
    
    def __init__(self):
        self.config = get_config()
        setup_logger()
        
        # Core components
        self.rpc_client = RPCClient()
        self.dex_monitor: Optional[DEXMonitor] = None
        self.metrics_fetcher: Optional[MetricsFetcher] = None
        self.score_calculator = MoonScoreCalculator()
        self.validator: Optional[TokenValidator] = None
        
        # Alert channels
        self.telegram = TelegramAlerter()
        self.discord = DiscordAlerter()
        self.webhook = WebhookSender()
        
        # State
        self.running = False
        self.processed_tokens = set()
        
        self.logger.info("Moon Scanner initialized")
    
    async def start(self) -> None:
        """Start the scanner."""
        if self.running:
            self.logger.warning("Scanner already running")
            return
        
        self.running = True
        self.logger.info("=" * 60)
        self.logger.info("🌙 SOLANA MOON SCANNER STARTING 🌙")
        self.logger.info("=" * 60)
        
        try:
            # Start metrics server
            start_metrics_server()
            
            # Initialize components
            await self._initialize_components()
            
            # Register callback for new pairs
            self.dex_monitor.register_callback(self._on_new_pair)
            
            # Start monitoring
            await self.dex_monitor.start()
            
            self.logger.info("Scanner started successfully")
            self.logger.info(f"Monitoring DEXs: {', '.join(self.config.get_monitored_dexs())}")
            self.logger.info(f"Min MoonScore threshold: {self.config.min_moon_score_threshold}")
            self.logger.info("Waiting for new token pairs...")
            
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)
                
                # Update metrics
                active_pairs = len(self.dex_monitor.get_active_pairs())
                tokens_in_memory.set(active_pairs)
        
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        
        except Exception as e:
            self.logger.error(f"Fatal error in scanner: {e}", exc_info=True)
            raise
        
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the scanner."""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping scanner...")
        
        # Stop components
        if self.dex_monitor:
            await self.dex_monitor.stop()
        
        if self.metrics_fetcher:
            await self.metrics_fetcher.close()
        
        if self.validator:
            await self.validator.close()
        
        await self.discord.close()
        await self.webhook.close()
        await self.rpc_client.close()
        
        self.logger.info("Scanner stopped")
    
    async def _initialize_components(self) -> None:
        """Initialize all scanner components."""
        self.logger.info("Initializing components...")
        
        # Initialize RPC client
        await self.rpc_client.initialize()
        
        # Initialize DEX monitor
        self.dex_monitor = DEXMonitor(self.rpc_client)
        
        # Initialize metrics fetcher
        self.metrics_fetcher = MetricsFetcher(self.rpc_client)
        await self.metrics_fetcher.initialize()
        
        # Initialize validator
        self.validator = TokenValidator(self.rpc_client)
        await self.validator.initialize()
        
        # Initialize alert channels
        self.telegram.initialize()
        await self.discord.initialize()
        await self.webhook.initialize()
        
        self.logger.info("All components initialized")
    
    async def _on_new_pair(self, pair: TokenPair) -> None:
        """
        Handle new pair discovery.
        
        Args:
            pair: Newly discovered token pair
        """
        # Skip if already processed
        if pair.token_address in self.processed_tokens:
            return
        
        self.processed_tokens.add(pair.token_address)
        
        self.logger.info(f"Processing new pair: {pair.token_address} on {pair.dex}")
        
        try:
            with token_processing_duration.time():
                # Fetch metrics
                self.logger.debug(f"Fetching metrics for {pair.token_address}")
                metrics = await self.metrics_fetcher.fetch_metrics(
                    pair.token_address,
                    pair.pair_address,
                )
                
                # Set age from pair
                metrics.age_minutes = pair.age_minutes()
                
                # Fetch social metrics if enabled
                social_metrics = {}
                if self.config.twitter_api_enabled and metrics.symbol:
                    social_metrics = await self.metrics_fetcher.fetch_social_metrics(
                        pair.token_address,
                        metrics.symbol,
                    )
                
                # Calculate MoonScore
                self.logger.debug(f"Calculating MoonScore for {pair.token_address}")
                moon_score = self.score_calculator.calculate(metrics, social_metrics)
                
                self.logger.info(
                    f"MoonScore for {pair.token_address}: {moon_score.total_score:.2f} "
                    f"({self.score_calculator.get_rating(moon_score.total_score)})"
                )
                
                # Validate token
                self.logger.debug(f"Validating {pair.token_address}")
                validation = await self.validator.validate(metrics, pair.pair_address)
                
                self.logger.info(
                    f"Validation for {pair.token_address}: {validation.overall_status.value} "
                    f"({validation.passed_checks}/{validation.passed_checks + validation.failed_checks} passed)"
                )
                
                # Check if meets alert threshold
                if moon_score.total_score >= self.config.min_moon_score_threshold:
                    self.logger.info(
                        f"🚀 Token {pair.token_address} meets threshold! "
                        f"Score: {moon_score.total_score:.2f}"
                    )
                    
                    # Send alerts
                    await self._send_alerts(moon_score, validation, pair.dex)
                    
                    # Track metric
                    tokens_alerted.labels(dex=pair.dex).inc()
                else:
                    self.logger.debug(
                        f"Token {pair.token_address} below threshold "
                        f"({moon_score.total_score:.2f} < {self.config.min_moon_score_threshold})"
                    )
        
        except Exception as e:
            self.logger.error(f"Error processing pair {pair.token_address}: {e}", exc_info=True)
    
    async def _send_alerts(
        self,
        moon_score,
        validation,
        dex: str,
    ) -> None:
        """
        Send alerts through all enabled channels.
        
        Args:
            moon_score: MoonScore result
            validation: Validation result
            dex: DEX name
        """
        self.logger.info(f"Sending alerts for {moon_score.token_address}")
        
        # Send alerts in parallel
        tasks = []
        
        if self.config.telegram_enabled:
            tasks.append(self.telegram.send_alert(moon_score, validation, dex))
        
        if self.config.discord_enabled:
            tasks.append(self.discord.send_alert(moon_score, validation, dex))
        
        if self.config.webhook_enabled:
            tasks.append(self.webhook.send_alert(moon_score, validation, dex))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if r is True)
            self.logger.info(f"Alerts sent: {success_count}/{len(tasks)} successful")
        else:
            self.logger.warning("No alert channels enabled")
    
    async def scan_token(self, token_address: str) -> dict:
        """
        Manually scan a specific token.
        
        Args:
            token_address: Token address to scan
            
        Returns:
            Scan results dictionary
        """
        self.logger.info(f"Manual scan requested for {token_address}")
        
        # Initialize if needed
        if not self.metrics_fetcher:
            await self._initialize_components()
        
        # Fetch metrics
        metrics = await self.metrics_fetcher.fetch_metrics(token_address)
        
        # Fetch social metrics
        social_metrics = {}
        if self.config.twitter_api_enabled and metrics.symbol:
            social_metrics = await self.metrics_fetcher.fetch_social_metrics(
                token_address,
                metrics.symbol,
            )
        
        # Calculate score
        moon_score = self.score_calculator.calculate(metrics, social_metrics)
        
        # Validate
        validation = await self.validator.validate(metrics)
        
        # Build result
        result = {
            "token_address": token_address,
            "scan_time": datetime.now().isoformat(),
            "moon_score": moon_score.to_dict(),
            "validation": validation.to_dict(),
            "rating": self.score_calculator.get_rating(moon_score.total_score),
        }
        
        return result


async def main():
    """Main entry point."""
    scanner = MoonScanner()
    
    try:
        await scanner.start()
    except KeyboardInterrupt:
        pass
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())
