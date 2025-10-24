# 🌙 Solana Moon Scanner

**Production-quality Python application for monitoring, scoring, and validating newly created Solana DEX token pairs.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 Features

### Core Functionality
- **Real-time DEX Monitoring**: Tracks new token pairs on Raydium, Orca, and Jupiter
- **MoonScore Calculation**: Advanced scoring algorithm combining multiple metrics
- **Contract Validation**: Comprehensive security checks for mint/freeze authority, honeypot detection, and more
- **Multi-channel Alerts**: Telegram, Discord, and custom webhooks
- **Production-ready**: Async architecture, retry logic, metrics, and comprehensive logging

### MoonScore Formula
```
MoonScore = (
    (BuyPressure% × 0.25) +
    (Volume/Liquidity × 0.20) +
    (SocialMomentum × 0.15) +
    (HolderGrowthRate × 0.15) +
    (DevBehaviorScore × 0.10) +
    (TechnicalPatternScore × 0.10) +
    (MarketTimingScore × 0.05)
) × AgeMultiplier

Age Multiplier:
- 0-15 minutes: 1.5×
- 15-30 minutes: 1.2×
- 30-60 minutes: 1.0×
```

### Validation Checklist
- ✅ Mint authority disabled
- ✅ Freeze authority disabled
- ✅ No honeypot indicators
- ✅ LP locked ≥ 30 days or burned
- ✅ Top 10 holders < 30%
- ✅ Dev wallet < 5%
- ✅ Contract verified on Solscan
- ✅ No repeated self-trades
- ✅ No suspicious liquidity removal

## 📋 Requirements

- Python 3.10 or higher
- Solana RPC provider (QuickNode or Helius)
- Optional: Telegram Bot, Discord webhook, Twitter API

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/solana-moon-scanner.git
cd solana-moon-scanner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example config
cp config.example.env .env

# Edit .env with your API keys and settings
nano .env
```

**Required Configuration:**
```env
# RPC Provider (choose one)
QUICKNODE_RPC_URL=https://your-endpoint.quiknode.pro/your-key/
# OR
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=your-key
HELIUS_API_KEY=your-helius-key

# Alert Channels (optional)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
DISCORD_WEBHOOK_URL=your-discord-webhook
```

### 3. Run the Scanner

```bash
# Start monitoring
python -m src.cli monitor

# Or manually scan a specific token
python -m src.cli scan EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

# Test alert channels
python -m src.cli test-alerts

# View configuration
python -m src.cli config
```

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f moon-scanner

# Stop
docker-compose down

# With Prometheus + Grafana monitoring
docker-compose --profile monitoring up -d
```

### Using Docker Directly

```bash
# Build image
docker build -t solana-moon-scanner .

# Run container
docker run -d \
  --name moon-scanner \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -p 9090:9090 \
  solana-moon-scanner
```

## 📊 Monitoring & Metrics

### Prometheus Metrics

The scanner exposes Prometheus metrics on port 9090:

- `moon_scanner_tokens_scanned_total` - Total tokens scanned
- `moon_scanner_tokens_alerted_total` - Tokens triggering alerts
- `moon_scanner_moon_score_distribution` - MoonScore distribution
- `moon_scanner_rpc_request_duration_seconds` - RPC request latency
- `moon_scanner_alerts_sent_total` - Alerts sent by channel

### Viewing Metrics

```bash
# Access Prometheus UI (if using docker-compose --profile monitoring)
http://localhost:9091

# Access Grafana (if using docker-compose --profile monitoring)
http://localhost:3000
# Default credentials: admin / admin
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_scoring.py -v

# Run specific test
pytest tests/test_validators.py::TestMintAuthorityCheck -v
```

## 📁 Project Structure

```
solana-moon-scanner/
├── src/
│   ├── core/
│   │   ├── rpc_client.py          # Solana RPC communication
│   │   ├── dex_monitor.py         # DEX pair monitoring
│   │   └── websocket_manager.py   # WebSocket subscriptions
│   ├── scoring/
│   │   ├── metrics_fetcher.py     # On-chain metrics collection
│   │   ├── moon_score.py          # MoonScore calculation
│   │   └── validators.py          # Contract validation
│   ├── alerts/
│   │   ├── telegram_bot.py        # Telegram alerts
│   │   ├── discord_bot.py         # Discord webhooks
│   │   └── webhook_sender.py      # Generic webhooks
│   ├── utils/
│   │   ├── config.py              # Configuration management
│   │   ├── logger.py              # Logging setup
│   │   └── metrics.py             # Prometheus metrics
│   ├── scanner.py                 # Main orchestrator
│   └── cli.py                     # CLI interface
├── tests/
│   ├── test_scoring.py            # MoonScore tests
│   └── test_validators.py         # Validation tests
├── config.example.env             # Example configuration
├── docker-compose.yml             # Docker Compose setup
├── Dockerfile                     # Docker image
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## 🔧 CLI Commands

```bash
# Start continuous monitoring
python -m src.cli monitor

# Scan specific token
python -m src.cli scan <TOKEN_ADDRESS> [--output results.json]

# Test alert channels
python -m src.cli test-alerts

# Show configuration
python -m src.cli config

# Show version
python -m src.cli version
```

## 🔐 Security Best Practices

### API Key Storage

**Never commit API keys to version control!**

```bash
# Use environment variables
export HELIUS_API_KEY="your-key-here"

# Or use .env file (ensure it's in .gitignore)
echo "HELIUS_API_KEY=your-key-here" >> .env

# For production, use secrets management
# - AWS Secrets Manager
# - HashiCorp Vault
# - Docker Secrets
# - Kubernetes Secrets
```

### Secure Webhook Endpoints

Webhooks include HMAC signatures for verification:

```python
import hmac
import hashlib
import json

def verify_webhook(payload, signature, secret):
    """Verify webhook signature."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    expected = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## 📈 Performance Tuning

### RPC Rate Limiting

```env
# Adjust based on your RPC plan
RATE_LIMIT_PER_MINUTE=60
MAX_CONCURRENT_REQUESTS=10
RPC_TIMEOUT=30
RPC_MAX_RETRIES=3
```

### Monitoring Configuration

```env
# Scan interval (seconds)
SCAN_INTERVAL_SECONDS=10

# Token age threshold
MAX_TOKEN_AGE_MINUTES=60

# MoonScore alert threshold
MIN_MOON_SCORE_THRESHOLD=70.0
```

## 🐛 Troubleshooting

### Common Issues

**1. RPC Connection Errors**
```bash
# Check RPC connectivity
curl -X POST https://your-endpoint.quiknode.pro/your-key/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

**2. WebSocket Disconnections**
```env
# Disable WebSocket monitoring if unstable
ENABLE_WEBSOCKET=false
```

**3. Alert Channel Failures**
```bash
# Test individual channels
python -m src.cli test-alerts
```

**4. Memory Usage**
```env
# Reduce scan interval to decrease memory usage
SCAN_INTERVAL_SECONDS=30
MAX_TOKEN_AGE_MINUTES=30
```

## 📝 Example Output

See [sample_output.json](sample_output.json) for a complete example of alert data.

**Console Output:**
```
🌙 SOLANA MOON SCANNER STARTING 🌙
============================================================
Scanner started successfully
Monitoring DEXs: raydium, orca, jupiter
Min MoonScore threshold: 70.0
Waiting for new token pairs...

🚀 Token EPjFW...t1v meets threshold! Score: 87.50
MoonScore: 87.50 (🚀 VERY STRONG)
Validation: PASS (8/8 checks)
Alerts sent: 3/3 successful
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**This tool is for monitoring and analysis only. It does NOT execute trades automatically.**

- Use at your own risk
- Always do your own research (DYOR)
- This is not financial advice
- Cryptocurrency investments are highly risky
- Past performance does not guarantee future results

## 🙏 Acknowledgments

- Solana Foundation for blockchain infrastructure
- QuickNode and Helius for RPC services
- Raydium, Orca, and Jupiter DEX teams

## 📞 Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/solana-moon-scanner/issues)
- Documentation: See this README and inline code documentation
- Community: Join our [Discord](#) or [Telegram](#)

---

**Built with ❤️ by Zayd**

*Happy hunting! 🌙🚀*
