#!/usr/bin/env python3
"""
Simple demo scan using direct HTTP calls to Helius RPC.
This bypasses the solana-py library issues.
"""

import asyncio
import json
import aiohttp
from datetime import datetime


async def get_token_info(rpc_url: str, token_address: str):
    """Get token information from Solana."""
    
    async with aiohttp.ClientSession() as session:
        print(f"\n{'='*60}")
        print(f"🔍 Scanning Token: {token_address}")
        print(f"{'='*60}\n")
        
        # Get account info
        print("📊 Fetching on-chain data...")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                token_address,
                {"encoding": "jsonParsed"}
            ]
        }
        
        async with session.post(rpc_url, json=payload) as response:
            account_data = await response.json()
        
        if "result" in account_data and account_data["result"]["value"]:
            result = account_data["result"]["value"]
            data = result.get("data", {})
            
            if isinstance(data, dict) and "parsed" in data:
                parsed = data["parsed"]
                info = parsed.get("info", {})
                
                print("\n✅ Token Data Retrieved!")
                print(f"   Owner: {result.get('owner', 'Unknown')}")
                print(f"   Lamports: {result.get('lamports', 0):,}")
                
                if "decimals" in info:
                    print(f"   Decimals: {info['decimals']}")
                if "mintAuthority" in info:
                    if info['mintAuthority']:
                        print(f"   ⚠️  Mint Authority: {info['mintAuthority']}")
                    else:
                        print(f"   ✅ Mint Authority: Disabled")
                if "freezeAuthority" in info:
                    if info['freezeAuthority']:
                        print(f"   ⚠️  Freeze Authority: {info['freezeAuthority']}")
                    else:
                        print(f"   ✅ Freeze Authority: Disabled")
        
        # Get token supply
        print("\n📈 Fetching token supply...")
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "getTokenSupply",
            "params": [token_address]
        }
        
        async with session.post(rpc_url, json=payload) as response:
            supply_data = await response.json()
        
        if "result" in supply_data:
            result = supply_data["result"]
            value = result.get("value", {})
            amount = float(value.get("amount", 0))
            decimals = int(value.get("decimals", 9))
            total_supply = amount / (10 ** decimals)
            
            print(f"   Total Supply: {total_supply:,.2f}")
            print(f"   UI Amount: {value.get('uiAmountString', 'N/A')}")
        
        # Get largest holders
        print("\n👥 Fetching top holders...")
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }
        
        async with session.post(rpc_url, json=payload) as response:
            holders_data = await response.json()
        
        if "result" in holders_data:
            accounts = holders_data["result"].get("value", [])
            print(f"   Total Holders Tracked: {len(accounts)}")
            
            if accounts:
                print("\n   Top 5 Holders:")
                for i, account in enumerate(accounts[:5], 1):
                    amount = float(account.get("amount", 0))
                    if decimals:
                        ui_amount = amount / (10 ** decimals)
                        percent = (ui_amount / total_supply * 100) if total_supply > 0 else 0
                        print(f"   #{i}: {ui_amount:,.2f} ({percent:.2f}%)")
        
        # Calculate simple score
        print(f"\n{'='*60}")
        print("🌙 MOON SCORE ANALYSIS")
        print(f"{'='*60}\n")
        
        # Security checks
        security_score = 0
        security_checks = []
        
        # Initialize defaults
        accounts = []
        total_supply = 0
        decimals = 9
        
        # Check mint authority
        if info.get("mintAuthority") is None:
            security_score += 25
            security_checks.append("✅ Mint authority disabled (+25)")
        else:
            security_checks.append("❌ Mint authority enabled (0)")
        
        # Check freeze authority  
        if info.get("freezeAuthority") is None:
            security_score += 25
            security_checks.append("✅ Freeze authority disabled (+25)")
        else:
            security_checks.append("❌ Freeze authority enabled (0)")
        
        # Holder distribution
        if accounts and total_supply > 0:
            top_10_amount = sum(float(acc.get("amount", 0)) for acc in accounts[:10])
            top_10_percent = (top_10_amount / (total_supply * (10 ** decimals))) * 100
            
            if top_10_percent < 30:
                security_score += 25
                security_checks.append(f"✅ Top 10 holders: {top_10_percent:.1f}% (+25)")
            else:
                security_checks.append(f"⚠️  Top 10 holders: {top_10_percent:.1f}% (concentrated)")
        else:
            security_checks.append("⚪ Holder distribution: Unknown")
        
        # Supply check
        if total_supply > 0:
            security_score += 25
            security_checks.append(f"✅ Has supply: {total_supply:,.0f} tokens (+25)")
        
        print("Security Checks:")
        for check in security_checks:
            print(f"  {check}")
        
        print(f"\n📊 Final Security Score: {security_score}/100")
        
        if security_score >= 75:
            rating = "🚀 STRONG"
        elif security_score >= 50:
            rating = "✨ MODERATE"
        else:
            rating = "⚠️  WEAK"
        
        print(f"🎯 Rating: {rating}")
        
        print(f"\n{'='*60}")
        print("✅ Scan Complete!")
        print(f"{'='*60}\n")
        
        return {
            "token": token_address,
            "supply": total_supply,
            "holders": len(accounts),
            "security_score": security_score,
            "rating": rating
        }


async def main():
    # Configuration
    RPC_URL = "https://mainnet.helius-rpc.com/?api-key=800bfb0a-c49f-4134-9991-74169c35b056"
    
    print("\n🌙 SOLANA MOON SCANNER - DEMO MODE")
    print("="*60)
    
    # Scan USDC (well-known token)
    token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    result = await get_token_info(RPC_URL, token)
    
    print("\n💡 What This Shows:")
    print("   - Real on-chain data from Solana blockchain")
    print("   - Security validation (mint/freeze authority)")
    print("   - Holder distribution analysis")
    print("   - Simple scoring algorithm")
    print("\n🚀 The full scanner monitors NEW tokens in real-time!")
    print("   and applies the complete MoonScore formula.\n")


if __name__ == "__main__":
    asyncio.run(main())
