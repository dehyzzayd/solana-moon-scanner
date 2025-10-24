"""Configuration management using Pydantic settings."""

import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # RPC Configuration
    quicknode_rpc_url: str = Field(default="", description="QuickNode RPC endpoint")
    quicknode_wss_url: str = Field(default="", description="QuickNode WSS endpoint")
    helius_rpc_url: str = Field(default="", description="Helius RPC endpoint")
    helius_api_key: str = Field(default="", description="Helius API key")
    primary_rpc_provider: str = Field(default="quicknode", description="Primary RPC provider")
    rpc_timeout: int = Field(default=30, description="RPC request timeout in seconds")
    rpc_max_retries: int = Field(default=3, description="Maximum number of RPC retries")
    rpc_retry_delay: int = Field(default=2, description="Delay between retries in seconds")

    # Monitoring Configuration
    max_token_age_minutes: int = Field(
        default=60, description="Maximum age of tokens to monitor"
    )
    min_moon_score_threshold: float = Field(
        default=70.0, description="Minimum MoonScore to trigger alerts"
    )
    scan_interval_seconds: int = Field(default=10, description="Scan interval in seconds")
    enable_websocket: bool = Field(
        default=True, description="Enable websocket subscriptions"
    )

    # DEX Configuration
    monitored_dexs: str = Field(
        default="raydium,orca,jupiter", description="Comma-separated list of DEXs to monitor"
    )

    # Alert Configuration
    telegram_bot_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID")
    telegram_enabled: bool = Field(default=False, description="Enable Telegram alerts")
    
    discord_webhook_url: str = Field(default="", description="Discord webhook URL")
    discord_enabled: bool = Field(default=False, description="Enable Discord alerts")
    
    webhook_url: str = Field(default="", description="Generic webhook URL")
    webhook_enabled: bool = Field(default=False, description="Enable generic webhook")
    webhook_secret: str = Field(default="", description="Webhook secret key")

    # Social Media APIs
    twitter_bearer_token: str = Field(default="", description="Twitter/X bearer token")
    twitter_api_enabled: bool = Field(default=False, description="Enable Twitter API")

    # External Data Sources
    solscan_api_key: str = Field(default="", description="Solscan API key")
    solscan_api_enabled: bool = Field(default=True, description="Enable Solscan API")
    
    token_sniffer_api_key: str = Field(default="", description="Token Sniffer API key")
    token_sniffer_enabled: bool = Field(default=False, description="Enable Token Sniffer")

    # Validation Thresholds
    max_top_holders_percent: float = Field(
        default=30.0, description="Maximum percentage held by top 10 holders"
    )
    max_dev_wallet_percent: float = Field(
        default=5.0, description="Maximum percentage held by dev wallet"
    )
    min_lp_lock_days: int = Field(
        default=30, description="Minimum LP lock duration in days"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/moon_scanner.log", description="Log file path")
    log_max_size_mb: int = Field(default=100, description="Maximum log file size in MB")
    log_backup_count: int = Field(default=5, description="Number of log backups to keep")

    # Prometheus Metrics
    prometheus_enabled: bool = Field(default=False, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")

    # Database
    database_enabled: bool = Field(default=False, description="Enable database storage")
    database_path: str = Field(
        default="data/moon_scanner.db", description="Database file path"
    )

    # Simulator Mode
    simulator_mode: bool = Field(default=False, description="Enable simulator mode")
    simulator_start_time: str = Field(
        default="2024-01-01T00:00:00", description="Simulator start time"
    )
    simulator_end_time: str = Field(
        default="2024-01-02T00:00:00", description="Simulator end time"
    )
    simulator_speed: float = Field(default=1.0, description="Simulator speed multiplier")

    # Security
    rate_limit_per_minute: int = Field(
        default=60, description="Rate limit per minute"
    )
    max_concurrent_requests: int = Field(
        default=10, description="Maximum concurrent requests"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper

    @field_validator("primary_rpc_provider")
    @classmethod
    def validate_rpc_provider(cls, v: str) -> str:
        """Validate RPC provider."""
        valid_providers = ["quicknode", "helius"]
        v_lower = v.lower()
        if v_lower not in valid_providers:
            raise ValueError(f"RPC provider must be one of {valid_providers}")
        return v_lower

    def get_monitored_dexs(self) -> List[str]:
        """Get list of monitored DEXs."""
        return [dex.strip().lower() for dex in self.monitored_dexs.split(",")]

    def get_rpc_url(self) -> str:
        """Get primary RPC URL based on provider."""
        if self.primary_rpc_provider == "quicknode":
            return self.quicknode_rpc_url
        return self.helius_rpc_url

    def get_wss_url(self) -> Optional[str]:
        """Get websocket URL if available."""
        if self.primary_rpc_provider == "quicknode":
            return self.quicknode_wss_url
        return None


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def load_config(env_file: Optional[str] = None) -> Config:
    """Load configuration from environment file."""
    global _config
    if env_file and os.path.exists(env_file):
        _config = Config(_env_file=env_file)
    else:
        _config = Config()
    return _config
