"""Automated Token Discovery and Scanning Service."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import aiohttp
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scanner import MoonScanner
from src.utils.logger import setup_logger, get_logger


@dataclass
class NewTokenDiscovery:
    """Represents a newly discovered token."""
    
    token_address: str
    discovered_at: datetime
    source: str  # 'dexscreener', 'birdeye', 'manual'
    initial_liquidity: float = 0.0
    pair_address: str = ""
    dex: str = ""


class AutoScanner:
    """
    Automated token discovery and scanning service.
    
    Features:
    - Discovers newly created tokens from multiple sources
    - Scans tokens every 5 minutes based on configured rules
    - Filters tokens by age, liquidity, and other criteria
    - Broadcasts results via callback function
    """
    
    def __init__(self, scanner: MoonScanner, result_callback=None):
        """
        Initialize auto scanner.
        
        Args:
            scanner: Initialized MoonScanner instance
            result_callback: Async function to call with scan results
        """
        self.scanner = scanner
        self.result_callback = result_callback
        self.logger = get_logger(__name__)
        
        # Configuration
        self.scan_interval = 300  # 5 minutes in seconds
        self.max_token_age_minutes = 60  # Only scan tokens < 60 minutes old
        self.min_liquidity_usd = 1000  # Minimum liquidity threshold
        
        # Tracking
        self.discovered_tokens: Dict[str, NewTokenDiscovery] = {}
        self.scanned_tokens: Set[str] = set()
        self.running = False
        
        # Task reference
        self.scan_task: Optional[asyncio.Task] = None
        
        self.logger.info("✅ Auto Scanner initialized")
    
    async def start(self):
        """Start automated scanning."""
        if self.running:
            self.logger.warning("Auto scanner already running")
            return
        
        self.running = True
        self.scan_task = asyncio.create_task(self._scan_loop())
        self.logger.info(f"🚀 Auto scanner started (interval: {self.scan_interval}s)")
    
    async def stop(self):
        """Stop automated scanning."""
        self.running = False
        
        if self.scan_task:
            self.scan_task.cancel()
            try:
                await self.scan_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🛑 Auto scanner stopped")
    
    async def _scan_loop(self):
        """Main scanning loop."""
        while self.running:
            try:
                self.logger.info("🔍 Starting automated scan cycle...")
                
                # Step 1: Discover new tokens
                await self._discover_new_tokens()
                
                # Step 2: Filter eligible tokens
                eligible_tokens = self._get_eligible_tokens()
                
                # Step 3: Scan eligible tokens
                if eligible_tokens:
                    self.logger.info(f"📊 Scanning {len(eligible_tokens)} eligible tokens...")
                    await self._scan_tokens(eligible_tokens)
                else:
                    self.logger.info("⚪ No eligible tokens found in this cycle")
                
                # Step 4: Cleanup old tokens
                self._cleanup_old_tokens()
                
                # Wait for next cycle
                self.logger.info(f"⏳ Waiting {self.scan_interval}s until next scan...")
                await asyncio.sleep(self.scan_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scan loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _discover_new_tokens(self):
        """Discover newly created tokens from multiple sources."""
        
        # Source 1: DexScreener API (most reliable for new pairs)
        await self._discover_from_dexscreener()
        
        # Source 2: Birdeye API (alternative source)
        # await self._discover_from_birdeye()  # Uncomment if you have API key
        
        self.logger.info(f"📋 Total discovered tokens: {len(self.discovered_tokens)}")
    
    async def _discover_from_dexscreener(self):
        """Discover tokens from DexScreener API (free, no API key needed)."""
        try:
            # Get latest token profiles (includes newly created tokens)
            url = "https://api.dexscreener.com/token-profiles/latest/v1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        self.logger.error(f"DexScreener API error: {response.status}")
                        return
                    
                    data = await response.json()
                    
                    # Filter and process new tokens (only Solana chain)
                    new_count = 0
                    checked_count = 0
                    solana_count = sum(1 for t in data if t.get("chainId", "").lower() == "solana")
                    self.logger.info(f"🔍 Checking {solana_count} Solana tokens from {len(data)} total profiles")
                    
                    for token_profile in data:
                        chain_id = token_profile.get("chainId", "").lower()
                        
                        # Only process Solana tokens
                        if chain_id != "solana":
                            continue
                        
                        token_address = token_profile.get("tokenAddress")
                        if not token_address:
                            continue
                        
                        # Skip if already discovered
                        if token_address in self.discovered_tokens:
                            continue
                        
                        # Get token pair details to check liquidity and age
                        pair_url = f"https://api.dexscreener.com/token-pairs/v1/solana/{token_address}"
                        
                        try:
                            async with session.get(pair_url, timeout=10) as pair_response:
                                if pair_response.status == 200:
                                    # Response is directly an array of pairs
                                    pairs = await pair_response.json()
                                    
                                    if not pairs or not isinstance(pairs, list):
                                        continue
                                    
                                    # Use the first (most liquid) pair
                                    pair = pairs[0]
                                    
                                    # Extract pair created timestamp
                                    pair_created_at = pair.get("pairCreatedAt")
                                    if not pair_created_at:
                                        continue
                                    
                                    # Calculate age
                                    created_time = datetime.fromtimestamp(pair_created_at / 1000)
                                    age_minutes = (datetime.now() - created_time).total_seconds() / 60
                                    
                                    # Only consider recent tokens (< max age)
                                    if age_minutes > self.max_token_age_minutes:
                                        self.logger.debug(f"Token {token_address[:8]}... too old: {age_minutes:.1f} minutes")
                                        continue
                                    
                                    # Extract liquidity
                                    liquidity = pair.get("liquidity", {}).get("usd", 0)
                                    
                                    # Check minimum liquidity
                                    if liquidity < self.min_liquidity_usd:
                                        self.logger.debug(f"Token {token_address[:8]}... liquidity too low: ${liquidity:.2f}")
                                        continue
                                    
                                    checked_count += 1
                                    self.logger.info(f"✅ Found eligible token: {token_address[:8]}... (age: {age_minutes:.1f}m, liq: ${liquidity:,.2f})")
                                    
                                    # Create discovery entry
                                    discovery = NewTokenDiscovery(
                                        token_address=token_address,
                                        discovered_at=datetime.now(),
                                        source="dexscreener",
                                        initial_liquidity=liquidity,
                                        pair_address=pair.get("pairAddress", ""),
                                        dex=pair.get("dexId", "")
                                    )
                                    
                                    self.discovered_tokens[token_address] = discovery
                                    new_count += 1
                                    
                        except Exception as pair_error:
                            self.logger.debug(f"Failed to fetch pair data for {token_address}: {pair_error}")
                            continue
                    
                    if new_count > 0:
                        self.logger.info(f"🆕 Discovered {new_count} new tokens from DexScreener")
                    else:
                        self.logger.info(f"⚪ No new tokens found (checked {checked_count}/{solana_count} Solana tokens)")
        
        except Exception as e:
            self.logger.error(f"Error discovering from DexScreener: {e}", exc_info=True)
    
    async def _discover_from_birdeye(self):
        """Discover tokens from Birdeye API (requires API key)."""
        # Implementation placeholder for Birdeye API
        # Requires API key: https://birdeye.so/
        pass
    
    def _get_eligible_tokens(self) -> List[str]:
        """
        Get list of tokens eligible for scanning based on rules.
        
        Rules:
        1. Token age < max_token_age_minutes
        2. Not already scanned
        3. Meets minimum liquidity threshold
        """
        eligible = []
        
        for token_address, discovery in self.discovered_tokens.items():
            # Skip if already scanned
            if token_address in self.scanned_tokens:
                continue
            
            # Check age
            age_minutes = (datetime.now() - discovery.discovered_at).total_seconds() / 60
            if age_minutes > self.max_token_age_minutes:
                continue
            
            # Check liquidity
            if discovery.initial_liquidity < self.min_liquidity_usd:
                continue
            
            eligible.append(token_address)
        
        return eligible
    
    async def _scan_tokens(self, token_addresses: List[str]):
        """Scan a list of token addresses."""
        
        for token_address in token_addresses:
            try:
                self.logger.info(f"🔎 Scanning token: {token_address}")
                
                # Scan the token
                result = await self.scanner.scan_token(token_address)
                
                # Mark as scanned
                self.scanned_tokens.add(token_address)
                
                # Add discovery info to result
                discovery = self.discovered_tokens.get(token_address)
                if discovery:
                    result["discovery_info"] = {
                        "discovered_at": discovery.discovered_at.isoformat(),
                        "source": discovery.source,
                        "initial_liquidity": discovery.initial_liquidity,
                        "pair_address": discovery.pair_address,
                        "dex": discovery.dex
                    }
                
                # Call result callback if provided
                if self.result_callback:
                    await self.result_callback(result)
                
                # Log result summary
                moon_score = result.get("moon_score", {}).get("total_score", 0)
                rating = result.get("rating", "UNKNOWN")
                validation = result.get("validation", {}).get("overall_status", "unknown")
                
                self.logger.info(
                    f"✅ Scan complete: {token_address[:8]}... | "
                    f"Score: {moon_score:.2f} | Rating: {rating} | "
                    f"Validation: {validation.upper()}"
                )
                
                # Small delay between scans
                await asyncio.sleep(2)
            
            except Exception as e:
                self.logger.error(f"Error scanning token {token_address}: {e}")
                continue
    
    def _cleanup_old_tokens(self):
        """Remove old tokens from tracking."""
        cutoff_time = datetime.now() - timedelta(minutes=self.max_token_age_minutes * 2)
        
        # Remove old discoveries
        old_tokens = [
            token for token, discovery in self.discovered_tokens.items()
            if discovery.discovered_at < cutoff_time
        ]
        
        for token in old_tokens:
            del self.discovered_tokens[token]
        
        if old_tokens:
            self.logger.info(f"🧹 Cleaned up {len(old_tokens)} old token entries")
    
    def get_status(self) -> Dict:
        """Get current status of auto scanner."""
        return {
            "running": self.running,
            "scan_interval": self.scan_interval,
            "discovered_tokens": len(self.discovered_tokens),
            "scanned_tokens": len(self.scanned_tokens),
            "max_token_age": self.max_token_age_minutes,
            "min_liquidity": self.min_liquidity_usd
        }


# Test function
async def test_auto_scanner():
    """Test the auto scanner."""
    setup_logger()
    logger = get_logger(__name__)
    
    # Initialize scanner
    scanner = MoonScanner()
    await scanner._initialize_components()
    
    # Define callback
    async def on_scan_result(result):
        logger.info(f"📊 Scan result: {result['token_address']}")
    
    # Create and start auto scanner
    auto_scanner = AutoScanner(scanner, on_scan_result)
    await auto_scanner.start()
    
    try:
        # Run for 20 minutes
        await asyncio.sleep(1200)
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        await auto_scanner.stop()
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(test_auto_scanner())
