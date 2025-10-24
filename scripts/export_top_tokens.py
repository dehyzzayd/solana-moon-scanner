#!/usr/bin/env python3
"""
Export top-scoring tokens to CSV for analysis.

Usage:
    python scripts/export_top_tokens.py --output top_tokens_2024_01_15.csv --limit 50
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import click

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.dex_monitor import TokenPair
from src.scanner import MoonScanner


async def export_tokens(output_path: str, limit: int = 100):
    """
    Export top-scoring tokens to CSV.
    
    Args:
        output_path: Output CSV file path
        limit: Maximum number of tokens to export
    """
    scanner = MoonScanner()
    await scanner._initialize_components()
    
    # Get active pairs from monitor
    if not scanner.dex_monitor:
        print("Error: DEX monitor not initialized")
        return
    
    active_pairs = scanner.dex_monitor.get_active_pairs()
    
    if not active_pairs:
        print("No active token pairs found")
        return
    
    # Score and validate each token
    results = []
    
    print(f"Processing {len(active_pairs)} tokens...")
    
    for i, pair in enumerate(active_pairs[:limit], 1):
        try:
            print(f"[{i}/{min(len(active_pairs), limit)}] Processing {pair.token_address}...")
            
            # Fetch metrics
            metrics = await scanner.metrics_fetcher.fetch_metrics(
                pair.token_address,
                pair.pair_address,
            )
            metrics.age_minutes = pair.age_minutes()
            
            # Fetch social metrics if enabled
            social_metrics = {}
            if scanner.config.twitter_api_enabled and metrics.symbol:
                social_metrics = await scanner.metrics_fetcher.fetch_social_metrics(
                    pair.token_address,
                    metrics.symbol,
                )
            
            # Calculate score
            moon_score = scanner.score_calculator.calculate(metrics, social_metrics)
            
            # Validate
            validation = await scanner.validator.validate(metrics, pair.pair_address)
            
            # Add to results
            results.append({
                'token_address': pair.token_address,
                'symbol': metrics.symbol,
                'name': metrics.name,
                'dex': pair.dex,
                'moon_score': moon_score.total_score,
                'rating': scanner.score_calculator.get_rating(moon_score.total_score),
                'age_minutes': metrics.age_minutes,
                'liquidity_usd': metrics.liquidity_usd,
                'volume_24h': metrics.volume_24h,
                'holders': metrics.total_holders,
                'transactions_24h': metrics.transactions_24h,
                'buy_pressure': moon_score.components.buy_pressure,
                'social_momentum': moon_score.components.social_momentum,
                'dev_behavior': moon_score.components.dev_behavior_score,
                'validation_status': validation.overall_status.value,
                'passed_checks': validation.passed_checks,
                'failed_checks': validation.failed_checks,
                'red_flags': len(validation.red_flags),
                'timestamp': datetime.now().isoformat(),
                'solscan_url': f"https://solscan.io/token/{pair.token_address}",
            })
        
        except Exception as e:
            print(f"Error processing {pair.token_address}: {e}")
            continue
    
    # Sort by moon_score descending
    results.sort(key=lambda x: x['moon_score'], reverse=True)
    
    # Write to CSV
    if results:
        fieldnames = list(results[0].keys())
        
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n✅ Exported {len(results)} tokens to {output_path}")
        print(f"Top 5 tokens by MoonScore:")
        for i, token in enumerate(results[:5], 1):
            print(f"  {i}. {token['symbol']} - Score: {token['moon_score']:.2f} ({token['rating']})")
    else:
        print("No results to export")
    
    await scanner.stop()


@click.command()
@click.option(
    '--output',
    '-o',
    default=f'top_tokens_{datetime.now().strftime("%Y%m%d")}.csv',
    help='Output CSV file path',
)
@click.option(
    '--limit',
    '-l',
    default=100,
    type=int,
    help='Maximum number of tokens to process',
)
def main(output: str, limit: int):
    """Export top-scoring tokens to CSV."""
    asyncio.run(export_tokens(output, limit))


if __name__ == '__main__':
    main()
