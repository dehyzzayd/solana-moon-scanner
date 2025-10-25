"""Solana RPC client with support for QuickNode and Helius providers."""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

import aiohttp
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import rpc_requests, rpc_request_duration


class RPCClient(LoggerMixin):
    """
    Solana RPC client with automatic retry logic and provider switching.
    
    Supports both QuickNode and Helius providers with automatic failover.
    """
    
    def __init__(self):
        self.config = get_config()
        self.primary_client: Optional[AsyncClient] = None
        self.backup_client: Optional[AsyncClient] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize RPC clients and HTTP session."""
        if self._initialized:
            return
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=self.config.rpc_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Initialize primary client
        primary_url = self.config.get_rpc_url()
        if primary_url:
            self.primary_client = AsyncClient(primary_url, commitment=Confirmed)
            self.logger.info(f"Initialized primary RPC client: {self.config.primary_rpc_provider}")
        else:
            self.logger.error("No primary RPC URL configured")
            raise ValueError("Primary RPC URL is required")
        
        # Initialize backup client
        if self.config.primary_rpc_provider == "quicknode" and self.config.helius_rpc_url:
            self.backup_client = AsyncClient(self.config.helius_rpc_url, commitment=Confirmed)
            self.logger.info("Initialized backup RPC client: helius")
        elif self.config.primary_rpc_provider == "helius" and self.config.quicknode_rpc_url:
            self.backup_client = AsyncClient(self.config.quicknode_rpc_url, commitment=Confirmed)
            self.logger.info("Initialized backup RPC client: quicknode")
        
        self._initialized = True
        self.logger.info("RPC client initialization complete")
    
    async def close(self) -> None:
        """Close RPC clients and HTTP session."""
        if self.primary_client:
            await self.primary_client.close()
        if self.backup_client:
            await self.backup_client.close()
        if self.session:
            await self.session.close()
        self._initialized = False
        self.logger.info("RPC client closed")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _make_request(
        self,
        client: AsyncClient,
        method: str,
        params: List[Any],
        provider: str,
    ) -> Dict[str, Any]:
        """
        Make RPC request with retry logic and metrics tracking.
        
        Args:
            client: Solana RPC client
            method: RPC method name
            params: Method parameters
            provider: Provider name (for metrics)
            
        Returns:
            RPC response
        """
        start_time = datetime.now()
        
        try:
            # Make RPC request
            response = await client._provider.make_request(method, params)
            
            # Track metrics
            duration = (datetime.now() - start_time).total_seconds()
            rpc_request_duration.labels(provider=provider, method=method).observe(duration)
            rpc_requests.labels(provider=provider, method=method, status="success").inc()
            
            return response
        
        except Exception as e:
            # Track error metrics
            duration = (datetime.now() - start_time).total_seconds()
            rpc_request_duration.labels(provider=provider, method=method).observe(duration)
            rpc_requests.labels(provider=provider, method=method, status="error").inc()
            
            self.logger.error(f"RPC request failed: {method} - {e}")
            raise
    
    async def get_recent_blockhash(self) -> str:
        """Get recent blockhash."""
        if not self._initialized:
            await self.initialize()
        
        try:
            response = await self.primary_client.get_latest_blockhash()
            return str(response.value.blockhash)
        except Exception as e:
            self.logger.error(f"Failed to get recent blockhash: {e}")
            if self.backup_client:
                self.logger.info("Trying backup client...")
                response = await self.backup_client.get_latest_blockhash()
                return str(response.value.blockhash)
            raise
    
    async def get_token_account_info(self, token_address: str) -> Dict[str, Any]:
        """
        Get token account information.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Token account info
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert string address to Pubkey object
            pubkey = Pubkey.from_string(token_address)
            params = [pubkey, {"encoding": "jsonParsed"}]
            response = await self._make_request(
                self.primary_client,
                "getAccountInfo",
                params,
                self.config.primary_rpc_provider,
            )
            return response
        except Exception as e:
            self.logger.error(f"Failed to get token account info: {e}")
            if self.backup_client:
                self.logger.info("Trying backup client...")
                provider = "helius" if self.config.primary_rpc_provider == "quicknode" else "quicknode"
                pubkey = Pubkey.from_string(token_address)
                params = [pubkey, {"encoding": "jsonParsed"}]
                response = await self._make_request(
                    self.backup_client,
                    "getAccountInfo",
                    params,
                    provider,
                )
                return response
            raise
    
    async def get_token_supply(self, token_address: str) -> Dict[str, Any]:
        """
        Get token supply information.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Token supply info
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            pubkey = Pubkey.from_string(token_address)
            params = [pubkey]
            response = await self._make_request(
                self.primary_client,
                "getTokenSupply",
                params,
                self.config.primary_rpc_provider,
            )
            return response
        except Exception as e:
            self.logger.error(f"Failed to get token supply: {e}")
            if self.backup_client:
                provider = "helius" if self.config.primary_rpc_provider == "quicknode" else "quicknode"
                pubkey = Pubkey.from_string(token_address)
                params = [pubkey]
                response = await self._make_request(
                    self.backup_client,
                    "getTokenSupply",
                    params,
                    provider,
                )
                return response
            raise
    
    async def get_signatures_for_address(
        self,
        address: str,
        limit: int = 100,
        before: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get transaction signatures for an address.
        
        Args:
            address: Account address
            limit: Maximum number of signatures to return
            before: Start searching backwards from this signature
            
        Returns:
            List of transaction signatures
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            pubkey = Pubkey.from_string(address)
            params = [pubkey, {"limit": limit}]
            if before:
                params[1]["before"] = before
            
            response = await self._make_request(
                self.primary_client,
                "getSignaturesForAddress",
                params,
                self.config.primary_rpc_provider,
            )
            return response.get("result", [])
        except Exception as e:
            self.logger.error(f"Failed to get signatures: {e}")
            if self.backup_client:
                provider = "helius" if self.config.primary_rpc_provider == "quicknode" else "quicknode"
                pubkey = Pubkey.from_string(address)
                params = [pubkey, {"limit": limit}]
                if before:
                    params[1]["before"] = before
                response = await self._make_request(
                    self.backup_client,
                    "getSignaturesForAddress",
                    params,
                    provider,
                )
                return response.get("result", [])
            raise
    
    async def get_transaction(
        self,
        signature: str,
        max_supported_transaction_version: int = 0,
    ) -> Dict[str, Any]:
        """
        Get transaction details.
        
        Args:
            signature: Transaction signature
            max_supported_transaction_version: Max transaction version to support
            
        Returns:
            Transaction details
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            params = [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": max_supported_transaction_version,
                },
            ]
            response = await self._make_request(
                self.primary_client,
                "getTransaction",
                params,
                self.config.primary_rpc_provider,
            )
            return response
        except Exception as e:
            self.logger.error(f"Failed to get transaction: {e}")
            if self.backup_client:
                provider = "helius" if self.config.primary_rpc_provider == "quicknode" else "quicknode"
                response = await self._make_request(
                    self.backup_client,
                    "getTransaction",
                    params,
                    provider,
                )
                return response
            raise
    
    async def get_token_largest_accounts(self, token_address: str) -> List[Dict[str, Any]]:
        """
        Get largest token accounts.
        
        Args:
            token_address: Token mint address
            
        Returns:
            List of largest token accounts
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            pubkey = Pubkey.from_string(token_address)
            params = [pubkey]
            response = await self._make_request(
                self.primary_client,
                "getTokenLargestAccounts",
                params,
                self.config.primary_rpc_provider,
            )
            return response.get("result", {}).get("value", [])
        except Exception as e:
            self.logger.error(f"Failed to get largest accounts: {e}")
            if self.backup_client:
                provider = "helius" if self.config.primary_rpc_provider == "quicknode" else "quicknode"
                pubkey = Pubkey.from_string(token_address)
                params = [pubkey]
                response = await self._make_request(
                    self.backup_client,
                    "getTokenLargestAccounts",
                    params,
                    provider,
                )
                return response.get("result", {}).get("value", [])
            raise
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
