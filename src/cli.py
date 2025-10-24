#!/usr/bin/env python3
"""CLI interface for Solana Moon Scanner."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .scanner import MoonScanner
from .utils.config import load_config, get_config
from .utils.logger import setup_logger


console = Console()


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
def cli(config: Optional[str], log_level: str):
    """Solana Moon Scanner - Monitor and score new DEX tokens."""
    # Load configuration
    if config:
        load_config(config)
    else:
        load_config()
    
    # Setup logging
    setup_logger(log_level=log_level)


@cli.command()
def monitor():
    """Start monitoring DEXs for new tokens."""
    console.print(Panel.fit(
        "[bold cyan]🌙 Solana Moon Scanner[/bold cyan]\n"
        "[yellow]Monitoring DEXs for new token pairs...[/yellow]",
        border_style="cyan"
    ))
    
    scanner = MoonScanner()
    
    try:
        asyncio.run(scanner.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("token_address")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (JSON)",
)
def scan(token_address: str, output: Optional[str]):
    """Scan a specific token address."""
    console.print(f"[cyan]Scanning token: {token_address}[/cyan]")
    
    scanner = MoonScanner()
    
    async def _scan():
        try:
            result = await scanner.scan_token(token_address)
            
            # Display results
            _display_scan_results(result)
            
            # Save to file if requested
            if output:
                with open(output, "w") as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green]Results saved to: {output}[/green]")
            
            await scanner.stop()
            
        except Exception as e:
            console.print(f"[red]Error scanning token: {e}[/red]")
            await scanner.stop()
            sys.exit(1)
    
    asyncio.run(_scan())


@cli.command()
def config():
    """Display current configuration."""
    cfg = get_config()
    
    table = Table(title="Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="green")
    
    # RPC settings
    table.add_section()
    table.add_row("RPC Provider", cfg.primary_rpc_provider.upper())
    table.add_row("RPC URL", cfg.get_rpc_url()[:50] + "..." if len(cfg.get_rpc_url()) > 50 else cfg.get_rpc_url())
    
    # Monitoring settings
    table.add_section()
    table.add_row("Monitored DEXs", ", ".join(cfg.get_monitored_dexs()))
    table.add_row("Max Token Age", f"{cfg.max_token_age_minutes} minutes")
    table.add_row("Min MoonScore", str(cfg.min_moon_score_threshold))
    table.add_row("Scan Interval", f"{cfg.scan_interval_seconds} seconds")
    table.add_row("WebSocket Enabled", "Yes" if cfg.enable_websocket else "No")
    
    # Alert settings
    table.add_section()
    table.add_row("Telegram", "Enabled" if cfg.telegram_enabled else "Disabled")
    table.add_row("Discord", "Enabled" if cfg.discord_enabled else "Disabled")
    table.add_row("Webhook", "Enabled" if cfg.webhook_enabled else "Disabled")
    
    # Validation thresholds
    table.add_section()
    table.add_row("Max Top Holders %", f"{cfg.max_top_holders_percent}%")
    table.add_row("Max Dev Wallet %", f"{cfg.max_dev_wallet_percent}%")
    table.add_row("Min LP Lock Days", f"{cfg.min_lp_lock_days} days")
    
    console.print(table)


@cli.command()
def test_alerts():
    """Test alert channels with a sample alert."""
    console.print("[cyan]Testing alert channels...[/cyan]")
    
    # Create sample data
    from .scoring.metrics_fetcher import TokenMetrics
    from .scoring.moon_score import MoonScoreCalculator, MoonScoreComponents
    from .scoring.validators import ValidationResult, ValidationStatus, ValidationCheck
    
    # Sample metrics
    metrics = TokenMetrics(
        token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        symbol="MOON",
        name="Moon Token",
        total_supply=1000000,
        liquidity_usd=50000,
        volume_24h=25000,
        total_holders=150,
        transactions_24h=75,
        age_minutes=15.5,
    )
    
    # Sample moon score
    calculator = MoonScoreCalculator()
    moon_score = calculator.calculate(metrics, {"twitter_mentions_24h": 50})
    
    # Sample validation
    validation = ValidationResult(
        token_address=metrics.token_address,
        overall_status=ValidationStatus.PASS,
        passed_checks=7,
        failed_checks=0,
    )
    validation.checks.append(ValidationCheck(
        name="Test Check",
        status=ValidationStatus.PASS,
        message="✅ All tests passed",
    ))
    
    async def _test():
        scanner = MoonScanner()
        await scanner._initialize_components()
        await scanner._send_alerts(moon_score, validation, "raydium")
        await scanner.stop()
    
    try:
        asyncio.run(_test())
        console.print("[green]✅ Alert test complete[/green]")
    except Exception as e:
        console.print(f"[red]❌ Alert test failed: {e}[/red]")
        sys.exit(1)


@cli.command()
def version():
    """Display version information."""
    from . import __version__, __author__, __description__
    
    console.print(Panel.fit(
        f"[bold cyan]Solana Moon Scanner[/bold cyan]\n\n"
        f"[yellow]Version:[/yellow] {__version__}\n"
        f"[yellow]Author:[/yellow] {__author__}\n"
        f"[yellow]Description:[/yellow] {__description__}",
        border_style="cyan"
    ))


def _display_scan_results(result: dict):
    """Display scan results in a formatted table."""
    console.print()
    
    # MoonScore panel
    moon_score = result["moon_score"]
    score_value = moon_score["total_score"]
    rating = result["rating"]
    
    score_panel = Panel.fit(
        f"[bold yellow]MoonScore:[/bold yellow] [bold green]{score_value:.2f}/100[/bold green]\n"
        f"[bold yellow]Rating:[/bold yellow] {rating}",
        title="🌙 Moon Score",
        border_style="green" if score_value >= 70 else "yellow"
    )
    console.print(score_panel)
    
    # Token info table
    token_table = Table(title="Token Information", show_header=False)
    token_table.add_column("Property", style="cyan")
    token_table.add_column("Value", style="white")
    
    metrics = moon_score["metrics"]
    token_table.add_row("Address", result["token_address"])
    token_table.add_row("Symbol", metrics.get("symbol", "N/A"))
    token_table.add_row("Name", metrics.get("name", "N/A"))
    token_table.add_row("Age", f"{metrics.get('age_minutes', 0):.1f} minutes")
    token_table.add_row("Liquidity", f"${metrics.get('liquidity_usd', 0):,.2f}")
    token_table.add_row("Volume 24h", f"${metrics.get('volume_24h', 0):,.2f}")
    token_table.add_row("Holders", str(metrics.get("total_holders", 0)))
    token_table.add_row("Transactions 24h", str(metrics.get("transactions_24h", 0)))
    
    console.print(token_table)
    
    # Score components table
    components_table = Table(title="Score Components", show_header=True)
    components_table.add_column("Component", style="cyan")
    components_table.add_column("Score", style="green")
    
    components = moon_score["components"]
    for key, value in components.items():
        if key != "age_multiplier":
            label = key.replace("_", " ").title()
            components_table.add_row(label, f"{value:.1f}/100")
    
    console.print(components_table)
    
    # Validation results
    validation = result["validation"]
    validation_status = validation["overall_status"]
    
    validation_panel = Panel.fit(
        f"[bold yellow]Status:[/bold yellow] {validation_status.upper()}\n"
        f"[bold yellow]Passed:[/bold yellow] {validation['passed_checks']}/{validation['passed_checks'] + validation['failed_checks']}",
        title="✅ Validation",
        border_style="green" if validation_status == "pass" else "yellow"
    )
    console.print(validation_panel)
    
    # Red flags
    if validation.get("red_flags"):
        console.print("[bold red]🚨 Red Flags:[/bold red]")
        for flag in validation["red_flags"]:
            console.print(f"  • {flag}")
    
    console.print()


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
