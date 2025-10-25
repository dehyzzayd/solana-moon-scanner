#!/usr/bin/env python3
"""Demo scan of BONK token - a popular Solana meme coin."""

import asyncio
import sys
sys.path.insert(0, '/home/user/solana-moon-scanner')

from demo_scan import get_token_info


async def main():
    RPC_URL = "https://mainnet.helius-rpc.com/?api-key=800bfb0a-c49f-4134-9991-74169c35b056"
    
    print("\n🌙 SOLANA MOON SCANNER - LIVE DEMO")
    print("="*60)
    print("\n🎯 Scanning BONK Token (Popular Meme Coin)")
    
    # BONK token address
    bonk_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    
    result = await get_token_info(RPC_URL, bonk_token)
    
    print("\n" + "="*60)
    print("📈 COMPARISON: What Makes a Good Token?")
    print("="*60)
    print("""
🟢 GOOD INDICATORS:
   ✅ Mint authority: Disabled (can't create more tokens)
   ✅ Freeze authority: Disabled (can't freeze accounts)
   ✅ Top 10 holders: < 30% (distributed ownership)
   ✅ High holder count: 100,000+ holders
   ✅ High liquidity: $100k+ USD
   ✅ Good volume: Active trading

🔴 RED FLAGS:
   ❌ Mint authority: Enabled (can print more tokens)
   ❌ Freeze authority: Enabled (can freeze your tokens)
   ❌ Top 10 holders: > 50% (concentrated ownership)
   ❌ Low holders: < 100 holders
   ❌ Low liquidity: < $1,000 USD
   ❌ No volume: Dead token

💡 The full MoonScore algorithm considers:
   • Buy pressure (% buy vs sell transactions)
   • Volume/Liquidity ratio (trading activity)
   • Social momentum (Twitter/X mentions)
   • Holder growth rate (new holders per hour)
   • Dev behavior (wallet holdings)
   • Technical patterns (price action)
   • Market timing (launch time)
   • Age multiplier (newer = higher score)
    """)


if __name__ == "__main__":
    asyncio.run(main())
