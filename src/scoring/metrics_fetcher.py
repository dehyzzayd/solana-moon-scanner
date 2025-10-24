"""Fetches on-chain metrics for token analysis."""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import aiohttp

from ..core.rpc_client import RPCClient
from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import rpc_requests


@dataclass
class TokenMetrics:
    """Container for token metrics."""
    
    token_address: str
    
    # Basic info
    symbol: str = ""
    name: str = ""
    decimals: int = 9
    
    # Supply metrics
    total_supply: float = 0.0
    circulating_supply: float = 0.0
    
    # Liquidity metrics
    liquidity_usd: float = 0.0
    liquidity_sol: float = 0.0
    
    # Volume metrics
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    
    # Holder metrics
    total_holders: int = 0
    holder_growth_24h: int = 0
    top_10_holders_percent: float = 0.0
    dev_wallet_percent: float = 0.0
    
    # Transaction metrics
    total_transactions: int = 0
    buy_transactions_24h: int = 0
    sell_transactions_24h: int = 0
    transactions_24h: int = 0
    
    # Price metrics
    price_usd: float = 0.0
    price_change_24h: float = 0.0
    market_cap_usd: float = 0.0
    
    # Age metrics
    age_minutes: float = 0.0
    
    # Additional data
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "total_supply": self.total_supply,
            "circulating_supply": self.circulating_supply,
            "liquidity_usd": self.liquidity_usd,
            "liquidity_sol": self.liquidity_sol,
            "volume_24h": self.volume_24h,
            "volume_1h": self.volume_1h,
            "total_holders": self.total_holders,
            "holder_growth_24h": self.holder_growth_24h,
            "top_10_holders_percent": self.top_10_holders_percent,
            "dev_wallet_percent": self.dev_wallet_percent,
            "total_transactions": self.total_transactions,
            "buy_transactions_24h": self.buy_transactions_24h,
            "sell_transactions_24h": self.sell_transactions_24h,
            "transactions_24h": self.transactions_24h,
            "price_usd": self.price_usd,
            "price_change_24h": self.price_change_24h,
            "market_cap_usd": self.market_cap_usd,
            "age_minutes": self.age_minutes,
            "metadata": self.metadata,
        }


class MetricsFetcher(LoggerMixin):
    """
    Fetches on-chain and off-chain metrics for tokens.
    
    Combines data from Solana RPC, Helius, Solscan, and other sources.
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
    
    async def fetch_metrics(
        self,
        token_address: str,
        pair_address: Optional[str] = None,
    ) -> TokenMetrics:
        """
        Fetch all available metrics for a token.
        
        Args:
            token_address: Token mint address
            pair_address: Pair/pool address (optional)
            
        Returns:
            TokenMetrics object
        """
        await self.initialize()
        
        metrics = TokenMetrics(token_address=token_address)
        
        # Fetch metrics in parallel
        tasks = [
            self._fetch_token_info(token_address, metrics),
            self._fetch_holder_metrics(token_address, metrics),
            self._fetch_transaction_metrics(token_address, metrics),
            self._fetch_liquidity_metrics(token_address, pair_address, metrics),
        ]
        
        # Add external API calls if enabled
        if self.config.solscan_api_enabled and self.config.solscan_api_key:
            tasks.append(self._fetch_solscan_data(token_address, metrics))
        
        if self.config.helius_api_key:
            tasks.append(self._fetch_helius_data(token_address, metrics))
        
        # Execute all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return metrics
    
    async def _fetch_token_info(self, token_address: str, metrics: TokenMetrics) -> None:
        """Fetch basic token information."""
        try:
            # Get token account info
            account_info = await self.rpc_client.get_token_account_info(token_address)
            
            if account_info and "result" in account_info:
                result = account_info["result"]
                value = result.get("value", {})
                data = value.get("data", {})
                
                if isinstance(data, dict):
                    parsed = data.get("parsed", {})
                    info = parsed.get("info", {})
                    
                    metrics.decimals = info.get("decimals", 9)
                    metrics.metadata["mint_authority"] = info.get("mintAuthority")
                    metrics.metadata["freeze_authority"] = info.get("freezeAuthority")
            
            # Get token supply
            supply_info = await self.rpc_client.get_token_supply(token_address)
            
            if supply_info and "result" in supply_info:
                result = supply_info["result"]
                value = result.get("value", {})
                
                amount = float(value.get("amount", 0))
                decimals = int(value.get("decimals", 9))
                metrics.total_supply = amount / (10 ** decimals)
                metrics.circulating_supply = metrics.total_supply
        
        except Exception as e:
            self.logger.error(f"Error fetching token info: {e}")
    
    async def _fetch_holder_metrics(self, token_address: str, metrics: TokenMetrics) -> None:
        """Fetch holder distribution metrics."""
        try:
            # Get largest token accounts
            largest_accounts = await self.rpc_client.get_token_largest_accounts(token_address)
            
            if largest_accounts:
                metrics.total_holders = len(largest_accounts)
                
                # Calculate top 10 holders percentage
                total_amount = sum(float(acc.get("amount", 0)) for acc in largest_accounts[:10])
                
                if metrics.total_supply > 0:
                    # Adjust for decimals
                    total_amount_adjusted = total_amount / (10 ** metrics.decimals)
                    metrics.top_10_holders_percent = (
                        total_amount_adjusted / metrics.total_supply * 100
                    )
                
                # Assume first holder is dev wallet
                if largest_accounts:
                    dev_amount = float(largest_accounts[0].get("amount", 0)) / (10 ** metrics.decimals)
                    if metrics.total_supply > 0:
                        metrics.dev_wallet_percent = dev_amount / metrics.total_supply * 100
        
        except Exception as e:
            self.logger.error(f"Error fetching holder metrics: {e}")
    
    async def _fetch_transaction_metrics(self, token_address: str, metrics: TokenMetrics) -> None:
        """Fetch transaction metrics."""
        try:
            # Get recent signatures
            signatures = await self.rpc_client.get_signatures_for_address(
                token_address,
                limit=100,
            )
            
            metrics.total_transactions = len(signatures)
            
            # Analyze transactions from last 24 hours
            cutoff_24h = datetime.now() - timedelta(hours=24)
            
            buy_count = 0
            sell_count = 0
            
            for sig_info in signatures:
                block_time = sig_info.get("blockTime")
                if not block_time:
                    continue
                
                tx_time = datetime.fromtimestamp(block_time)
                if tx_time < cutoff_24h:
                    continue
                
                # Simple heuristic: check if signature contains certain patterns
                # In production, you'd parse the full transaction
                metrics.transactions_24h += 1
                
                # Placeholder logic - actual implementation needs transaction parsing
                # For now, assume 50/50 buy/sell ratio
                if metrics.transactions_24h % 2 == 0:
                    buy_count += 1
                else:
                    sell_count += 1
            
            metrics.buy_transactions_24h = buy_count
            metrics.sell_transactions_24h = sell_count
        
        except Exception as e:
            self.logger.error(f"Error fetching transaction metrics: {e}")
    
    async def _fetch_liquidity_metrics(
        self,
        token_address: str,
        pair_address: Optional[str],
        metrics: TokenMetrics,
    ) -> None:
        """Fetch liquidity metrics from pool."""
        try:
            if not pair_address:
                return
            
            # Get pair account info
            pair_info = await self.rpc_client.get_token_account_info(pair_address)
            
            # This is a simplified implementation
            # Actual implementation would parse pool reserves
            if pair_info and "result" in pair_info:
                # Placeholder: set default liquidity
                metrics.liquidity_sol = 10.0  # Would parse from pool reserves
                
                # Estimate USD value (assuming SOL = $100)
                sol_price_usd = 100.0
                metrics.liquidity_usd = metrics.liquidity_sol * sol_price_usd
        
        except Exception as e:
            self.logger.error(f"Error fetching liquidity metrics: {e}")
    
    async def _fetch_solscan_data(self, token_address: str, metrics: TokenMetrics) -> None:
        """Fetch data from Solscan API."""
        try:
            if not self.session:
                return
            
            url = f"https://api.solscan.io/token/meta?token={token_address}"
            headers = {"token": self.config.solscan_api_key}
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    metrics.symbol = data.get("symbol", "")
                    metrics.name = data.get("name", "")
                    metrics.total_holders = data.get("holder", 0)
                    
                    # Store additional metadata
                    metrics.metadata["solscan_data"] = data
        
        except Exception as e:
            self.logger.error(f"Error fetching Solscan data: {e}")
    
    async def _fetch_helius_data(self, token_address: str, metrics: TokenMetrics) -> None:
        """Fetch enhanced data from Helius API."""
        try:
            if not self.session:
                return
            
            # Helius enriched transaction API
            url = f"https://api.helius.xyz/v0/token-metadata"
            params = {
                "api-key": self.config.helius_api_key,
                "mint": token_address,
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if isinstance(data, list) and data:
                        token_data = data[0]
                        
                        account = token_data.get("account", {})
                        metadata = token_data.get("onChainMetadata", {}).get("metadata", {})
                        
                        metrics.symbol = metadata.get("symbol", metrics.symbol)
                        metrics.name = metadata.get("name", metrics.name)
                        
                        # Store metadata
                        metrics.metadata["helius_data"] = token_data
        
        except Exception as e:
            self.logger.error(f"Error fetching Helius data: {e}")
    
    async def fetch_social_metrics(self, token_address: str, symbol: str) -> Dict:
        """
        Fetch social media metrics for token.
        
        Args:
            token_address: Token address
            symbol: Token symbol
            
        Returns:
            Dictionary with social metrics
        """
        social_metrics = {
            "twitter_mentions_24h": 0,
            "twitter_mentions_growth": 0.0,
            "telegram_members": 0,
            "discord_members": 0,
        }
        
        try:
            if not self.config.twitter_api_enabled or not self.config.twitter_bearer_token:
                return social_metrics
            
            await self.initialize()
            
            # Search Twitter for token mentions
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {"Authorization": f"Bearer {self.config.twitter_bearer_token}"}
            
            # Search for mentions in last 24h
            query = f"${symbol} OR {token_address[:8]}"
            params = {
                "query": query,
                "max_results": 100,
                "start_time": (datetime.now() - timedelta(hours=24)).isoformat() + "Z",
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    meta = data.get("meta", {})
                    social_metrics["twitter_mentions_24h"] = meta.get("result_count", 0)
            
            # Calculate growth (simplified - would need historical data)
            social_metrics["twitter_mentions_growth"] = social_metrics["twitter_mentions_24h"] / 10.0
        
        except Exception as e:
            self.logger.error(f"Error fetching social metrics: {e}")
        
        return social_metrics
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
