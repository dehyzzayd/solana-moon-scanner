"""DEX monitor for detecting new token pairs on Raydium, Orca, and Jupiter."""

import asyncio
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import tokens_scanned, active_monitors, last_scan_timestamp
from .rpc_client import RPCClient
from .websocket_manager import WebSocketManager


# Known DEX program IDs on Solana
DEX_PROGRAM_IDS = {
    "raydium": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM v4
    "raydium_v3": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
    "orca": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
    "orca_v2": "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca v2
    "jupiter": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter v6
}


@dataclass
class TokenPair:
    """Represents a DEX token pair."""
    
    token_address: str
    pair_address: str
    dex: str
    base_token: str
    quote_token: str
    created_at: datetime
    signature: str
    pool_info: Dict = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.token_address)
    
    def __eq__(self, other):
        if not isinstance(other, TokenPair):
            return False
        return self.token_address == other.token_address
    
    def age_minutes(self) -> float:
        """Get age of pair in minutes."""
        return (datetime.now() - self.created_at).total_seconds() / 60
    
    def is_eligible(self, max_age_minutes: int = 60) -> bool:
        """Check if pair is eligible for monitoring (age <= max_age_minutes)."""
        return self.age_minutes() <= max_age_minutes
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "pair_address": self.pair_address,
            "dex": self.dex,
            "base_token": self.base_token,
            "quote_token": self.quote_token,
            "created_at": self.created_at.isoformat(),
            "age_minutes": self.age_minutes(),
            "signature": self.signature,
            "pool_info": self.pool_info,
        }


class DEXMonitor(LoggerMixin):
    """
    Monitor DEXs for new token pairs.
    
    Supports Raydium, Orca, and Jupiter with both polling and WebSocket monitoring.
    """
    
    def __init__(self, rpc_client: RPCClient):
        self.config = get_config()
        self.rpc_client = rpc_client
        self.ws_manager = WebSocketManager()
        
        # Track discovered pairs
        self.discovered_pairs: Dict[str, TokenPair] = {}
        self.seen_signatures: Set[str] = set()
        
        # Callbacks for new pair events
        self.callbacks: List[Callable] = []
        
        # Monitoring state
        self.running = False
        self.monitored_dexs = self.config.get_monitored_dexs()
        
        self.logger.info(f"Initialized DEX monitor for: {', '.join(self.monitored_dexs)}")
    
    def register_callback(self, callback: Callable) -> None:
        """
        Register a callback for new pair events.
        
        Args:
            callback: Async function that takes TokenPair as argument
        """
        self.callbacks.append(callback)
        self.logger.info(f"Registered callback: {callback.__name__}")
    
    async def start(self) -> None:
        """Start monitoring DEXs."""
        if self.running:
            self.logger.warning("DEX monitor already running")
            return
        
        self.running = True
        active_monitors.inc()
        self.logger.info("Starting DEX monitor...")
        
        # Start WebSocket monitoring if enabled
        if self.config.enable_websocket:
            asyncio.create_task(self._start_websocket_monitoring())
        
        # Start polling monitoring
        asyncio.create_task(self._start_polling_monitoring())
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_old_pairs())
        
        self.logger.info("DEX monitor started")
    
    async def stop(self) -> None:
        """Stop monitoring DEXs."""
        self.running = False
        active_monitors.dec()
        await self.ws_manager.stop()
        self.logger.info("DEX monitor stopped")
    
    async def _start_websocket_monitoring(self) -> None:
        """Start WebSocket-based monitoring for real-time events."""
        try:
            program_ids = self._get_program_ids()
            
            await self.ws_manager.subscribe_logs(
                program_ids,
                self._handle_log_event,
            )
            
            # Start WebSocket listener
            await self.ws_manager.listen()
        
        except Exception as e:
            self.logger.error(f"WebSocket monitoring error: {e}")
            # Fall back to polling if WebSocket fails
            self.logger.info("Falling back to polling mode")
    
    async def _start_polling_monitoring(self) -> None:
        """Start polling-based monitoring as backup/primary method."""
        self.logger.info("Starting polling monitor...")
        
        while self.running:
            try:
                await self._scan_dexs()
                last_scan_timestamp.set(datetime.now().timestamp())
                
                # Wait for next scan
                await asyncio.sleep(self.config.scan_interval_seconds)
            
            except Exception as e:
                self.logger.error(f"Polling monitoring error: {e}")
                await asyncio.sleep(5)
    
    async def _scan_dexs(self) -> None:
        """Scan all monitored DEXs for new pairs."""
        program_ids = self._get_program_ids()
        
        for program_id in program_ids:
            try:
                await self._scan_program(program_id)
            except Exception as e:
                self.logger.error(f"Error scanning program {program_id}: {e}")
    
    async def _scan_program(self, program_id: str) -> None:
        """
        Scan a specific program for new pairs.
        
        Args:
            program_id: Program ID to scan
        """
        try:
            # Get recent signatures
            signatures = await self.rpc_client.get_signatures_for_address(
                program_id,
                limit=50,
            )
            
            for sig_info in signatures:
                signature = sig_info["signature"]
                
                # Skip if already seen
                if signature in self.seen_signatures:
                    continue
                
                self.seen_signatures.add(signature)
                
                # Get transaction details
                tx = await self.rpc_client.get_transaction(signature)
                
                if not tx or "result" not in tx:
                    continue
                
                # Parse transaction for pair creation
                pair = await self._parse_transaction(tx["result"], program_id, signature)
                
                if pair:
                    await self._handle_new_pair(pair)
        
        except Exception as e:
            self.logger.error(f"Error in _scan_program: {e}")
    
    async def _parse_transaction(
        self,
        tx_data: Dict,
        program_id: str,
        signature: str,
    ) -> Optional[TokenPair]:
        """
        Parse transaction data to extract token pair information.
        
        Args:
            tx_data: Transaction data
            program_id: Program ID
            signature: Transaction signature
            
        Returns:
            TokenPair if found, None otherwise
        """
        try:
            # Check if transaction was successful
            if tx_data.get("meta", {}).get("err"):
                return None
            
            # Get block time
            block_time = tx_data.get("blockTime")
            if not block_time:
                created_at = datetime.now()
            else:
                created_at = datetime.fromtimestamp(block_time)
            
            # Only process recent transactions
            age_minutes = (datetime.now() - created_at).total_seconds() / 60
            if age_minutes > self.config.max_token_age_minutes:
                return None
            
            # Parse instructions to find pair creation
            instructions = tx_data.get("transaction", {}).get("message", {}).get("instructions", [])
            
            for instruction in instructions:
                # Look for initialize pool instructions
                if self._is_pool_creation_instruction(instruction, program_id):
                    pair = await self._extract_pair_info(
                        instruction,
                        tx_data,
                        program_id,
                        signature,
                        created_at,
                    )
                    if pair:
                        return pair
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error parsing transaction: {e}")
            return None
    
    def _is_pool_creation_instruction(self, instruction: Dict, program_id: str) -> bool:
        """
        Check if instruction is a pool creation.
        
        Args:
            instruction: Instruction data
            program_id: Program ID
            
        Returns:
            True if pool creation instruction
        """
        # This is a simplified check - actual implementation would need
        # detailed instruction parsing for each DEX
        program_id_key = instruction.get("programId", "")
        
        # Check if instruction is from the DEX program
        if program_id_key != program_id:
            return False
        
        # Check for common pool creation patterns
        parsed = instruction.get("parsed", {})
        instruction_type = parsed.get("type", "")
        
        pool_creation_types = [
            "initialize",
            "initializePool",
            "initializeWhirlpool",
            "createPool",
        ]
        
        return any(t in instruction_type.lower() for t in ["initialize", "create"])
    
    async def _extract_pair_info(
        self,
        instruction: Dict,
        tx_data: Dict,
        program_id: str,
        signature: str,
        created_at: datetime,
    ) -> Optional[TokenPair]:
        """
        Extract token pair information from instruction.
        
        Args:
            instruction: Pool creation instruction
            tx_data: Full transaction data
            program_id: Program ID
            signature: Transaction signature
            created_at: Transaction timestamp
            
        Returns:
            TokenPair if successfully extracted
        """
        try:
            # Extract account keys
            accounts = tx_data.get("transaction", {}).get("message", {}).get("accountKeys", [])
            
            if not accounts or len(accounts) < 3:
                return None
            
            # Simplified extraction - actual implementation needs DEX-specific logic
            # For now, we'll create a basic pair structure
            dex_name = self._get_dex_name(program_id)
            
            # Try to identify token mints
            token_mints = []
            for account in accounts[:10]:  # Check first 10 accounts
                if isinstance(account, dict):
                    pubkey = account.get("pubkey", "")
                elif isinstance(account, str):
                    pubkey = account
                else:
                    continue
                
                # Basic heuristic: exclude known system accounts
                if pubkey and len(pubkey) > 30 and not self._is_system_account(pubkey):
                    token_mints.append(pubkey)
            
            if len(token_mints) < 2:
                return None
            
            # Create pair object
            pair = TokenPair(
                token_address=token_mints[0],
                pair_address=accounts[0] if isinstance(accounts[0], str) else accounts[0].get("pubkey", ""),
                dex=dex_name,
                base_token=token_mints[0],
                quote_token=token_mints[1] if len(token_mints) > 1 else "SOL",
                created_at=created_at,
                signature=signature,
            )
            
            return pair
        
        except Exception as e:
            self.logger.error(f"Error extracting pair info: {e}")
            return None
    
    def _get_dex_name(self, program_id: str) -> str:
        """Get DEX name from program ID."""
        for dex_name, pid in DEX_PROGRAM_IDS.items():
            if pid == program_id:
                return dex_name.split("_")[0]  # Remove version suffix
        return "unknown"
    
    def _is_system_account(self, pubkey: str) -> bool:
        """Check if account is a known system account."""
        system_accounts = [
            "11111111111111111111111111111111",  # System Program
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
            "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token Program
        ]
        return pubkey in system_accounts
    
    def _get_program_ids(self) -> List[str]:
        """Get list of program IDs to monitor based on config."""
        program_ids = []
        
        for dex in self.monitored_dexs:
            if dex == "raydium":
                program_ids.extend([
                    DEX_PROGRAM_IDS["raydium"],
                    DEX_PROGRAM_IDS["raydium_v3"],
                ])
            elif dex == "orca":
                program_ids.extend([
                    DEX_PROGRAM_IDS["orca"],
                    DEX_PROGRAM_IDS["orca_v2"],
                ])
            elif dex == "jupiter":
                program_ids.append(DEX_PROGRAM_IDS["jupiter"])
        
        return program_ids
    
    async def _handle_log_event(self, event: Dict) -> None:
        """
        Handle log event from WebSocket.
        
        Args:
            event: Log event data
        """
        try:
            signature = event.get("signature")
            if not signature or signature in self.seen_signatures:
                return
            
            self.seen_signatures.add(signature)
            
            # Get full transaction
            tx = await self.rpc_client.get_transaction(signature)
            
            if not tx or "result" not in tx:
                return
            
            # Try to parse as pair creation
            for program_id in self._get_program_ids():
                pair = await self._parse_transaction(tx["result"], program_id, signature)
                if pair:
                    await self._handle_new_pair(pair)
                    break
        
        except Exception as e:
            self.logger.error(f"Error handling log event: {e}")
    
    async def _handle_new_pair(self, pair: TokenPair) -> None:
        """
        Handle newly discovered pair.
        
        Args:
            pair: Discovered token pair
        """
        # Skip if already discovered
        if pair.token_address in self.discovered_pairs:
            return
        
        # Store pair
        self.discovered_pairs[pair.token_address] = pair
        tokens_scanned.inc()
        
        self.logger.info(f"New pair discovered: {pair.token_address} on {pair.dex}")
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                await callback(pair)
            except Exception as e:
                self.logger.error(f"Error in callback {callback.__name__}: {e}")
    
    async def _cleanup_old_pairs(self) -> None:
        """Remove old pairs from memory to prevent memory leaks."""
        while self.running:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                cutoff = datetime.now() - timedelta(minutes=self.config.max_token_age_minutes * 2)
                
                old_pairs = [
                    token_addr
                    for token_addr, pair in self.discovered_pairs.items()
                    if pair.created_at < cutoff
                ]
                
                for token_addr in old_pairs:
                    del self.discovered_pairs[token_addr]
                
                if old_pairs:
                    self.logger.info(f"Cleaned up {len(old_pairs)} old pairs from memory")
            
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
    
    def get_active_pairs(self) -> List[TokenPair]:
        """Get list of currently active pairs."""
        return [
            pair
            for pair in self.discovered_pairs.values()
            if pair.is_eligible(self.config.max_token_age_minutes)
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
