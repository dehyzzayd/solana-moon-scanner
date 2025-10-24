# ⚡ Quick Start Guide

**Get up and running with Solana Moon Scanner in 5 minutes!**

---

## 🚀 Installation (2 minutes)

```bash
# Clone repository
git clone https://github.com/yourusername/solana-moon-scanner.git
cd solana-moon-scanner

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Configuration (2 minutes)

```bash
# Copy example config
cp config.example.env .env

# Edit configuration
nano .env  # or use your favorite editor
```

**Minimum required configuration:**
```env
# RPC Provider (get from QuickNode.com or Helius.xyz)
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR-KEY
HELIUS_API_KEY=YOUR-KEY

# Alert Channel (choose at least one)
TELEGRAM_BOT_TOKEN=your-bot-token      # Optional
TELEGRAM_CHAT_ID=your-chat-id          # Optional
DISCORD_WEBHOOK_URL=your-webhook-url   # Optional
```

---

## 🎯 Usage (1 minute)

### Start Monitoring
```bash
python -m src.cli monitor
```

### Scan Specific Token
```bash
python -m src.cli scan EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

### Test Alerts
```bash
python -m src.cli test-alerts
```

### View Configuration
```bash
python -m src.cli config
```

---

## 🐳 Docker Alternative

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f moon-scanner

# Stop
docker-compose down
```

---

## 🔍 What to Expect

When monitoring, you'll see:
```
🌙 SOLANA MOON SCANNER STARTING 🌙
============================================================
Scanner started successfully
Monitoring DEXs: raydium, orca, jupiter
Min MoonScore threshold: 70.0
Waiting for new token pairs...

New pair discovered: ABC123... on raydium
MoonScore: 85.50 (🚀 VERY STRONG)
Validation: PASS (8/8 checks)
🚀 Token ABC123... meets threshold!
Alerts sent: 2/2 successful
```

---

## 📊 Understanding MoonScore

- **90-100** 🌕 MOON SHOT - Exceptional opportunity
- **80-89** 🚀 VERY STRONG - Excellent metrics
- **70-79** 💎 STRONG - Great potential
- **60-69** ✨ PROMISING - Good token
- **50-59** 📊 MODERATE - Average
- **<50** ⚠️ WEAK - Be cautious

---

## 🔐 Security Checks

The scanner validates:
- ✅ Mint authority disabled
- ✅ Freeze authority disabled
- ✅ Holder distribution < 30%
- ✅ Dev wallet < 5%
- ✅ Liquidity adequate
- ✅ No honeypot indicators
- ✅ Contract verified
- ✅ LP tokens locked

---

## 🆘 Troubleshooting

### RPC Connection Failed
```bash
# Test RPC connectivity
curl -X POST $HELIUS_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Configuration Issues
```bash
# Verify setup
bash scripts/test_setup.sh
```

### Alert Not Sending
```bash
# Test alert channels
python -m src.cli test-alerts
```

---

## 📚 Next Steps

1. **Adjust Thresholds** - Edit `.env` to customize scoring thresholds
2. **Setup Monitoring** - Enable Prometheus metrics
3. **Run Tests** - Execute `pytest` to verify installation
4. **Deploy Production** - See `DEPLOYMENT.md` for production setup
5. **Read Full Docs** - Check `README.md` for detailed documentation

---

## 💡 Pro Tips

- **Lower threshold** to see more alerts: `MIN_MOON_SCORE_THRESHOLD=60`
- **Increase scan speed**: `SCAN_INTERVAL_SECONDS=5`
- **Enable WebSocket** for real-time: `ENABLE_WEBSOCKET=true`
- **Monitor metrics** at `http://localhost:9090`
- **Export top tokens**: `python scripts/export_top_tokens.py`

---

## ⚠️ Important Reminders

- **No Auto-Trading**: This tool only monitors and alerts
- **DYOR**: Always research before investing
- **Test First**: Start with small amounts
- **High Risk**: Crypto is extremely volatile
- **Not Financial Advice**: Use at your own risk

---

## 🔗 Quick Links

- 📖 Full Documentation: [README.md](README.md)
- 🚀 Deployment Guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- 📊 Project Summary: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- 🐛 Report Issues: [GitHub Issues](https://github.com/yourusername/solana-moon-scanner/issues)

---

**Happy monitoring! 🌙🚀**
