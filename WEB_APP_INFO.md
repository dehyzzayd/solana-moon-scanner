# Solana Moon Scanner - Web App 🚀

## ✅ Server Status: RUNNING

The FastAPI web application is currently running and accessible!

---

## 🌐 Access URLs

### Public Web Interface
**Main Dashboard**: https://8000-ii0ya2o6zvgs4qwpwr9sf-b237eb32.sandbox.novita.ai

### API Documentation
**Swagger UI (Interactive API Docs)**: https://8000-ii0ya2o6zvgs4qwpwr9sf-b237eb32.sandbox.novita.ai/docs
**ReDoc (Alternative API Docs)**: https://8000-ii0ya2o6zvgs4qwpwr9sf-b237eb32.sandbox.novita.ai/redoc

### Local Access (Inside Sandbox)
- Dashboard: http://localhost:8000
- API Stats: http://localhost:8000/api/stats
- API Docs: http://localhost:8000/docs

---

## 📊 Current Features Available

### ✅ Working Pages
1. **Dashboard** (`/`) - Main overview page with:
   - Statistics cards (total scans, average score, high scores, passed validation)
   - Recent scans table (live updates via WebSocket)
   - Score distribution chart
   - Real-time WebSocket connection indicator

### ✅ Working API Endpoints
- `GET /api/stats` - Get scanning statistics
- `GET /api/history` - Get scan history
- `GET /api/config` - Get configuration
- `POST /api/scan` - Scan a token address
- `WS /ws` - WebSocket connection for real-time updates

### ⏳ Pages Under Development
- `/scan` - Token scanning interface (not yet created)
- `/history` - Full scan history page (not yet created)
- `/settings` - Configuration management (not yet created)

---

## 🧪 Test the API

### Get Stats (Working)
```bash
curl http://localhost:8000/api/stats
```

Expected response:
```json
{
  "success": true,
  "data": {
    "total_scans": 0,
    "average_score": 0,
    "high_score_count": 0,
    "passed_validation": 0
  }
}
```

### Scan a Token (Ready to Test)
```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"}'
```

This will scan USDC and return MoonScore + validation results!

---

## 🔧 Technical Details

### Architecture
- **Backend**: FastAPI (Python async web framework)
- **Frontend**: HTML + Tailwind CSS + Alpine.js
- **Real-time**: WebSocket for live updates
- **Scanner**: Full integration with existing MoonScanner
- **Storage**: In-memory scan history (could be upgraded to database)

### Technology Stack
- **Server**: Uvicorn with auto-reload
- **Templates**: Jinja2
- **Styling**: Tailwind CSS (CDN)
- **Interactivity**: Alpine.js (lightweight, no build step)
- **Charts**: Chart.js
- **Icons**: Font Awesome

### Configuration
- Uses existing `.env` file with Helius API key
- All scanner settings preserved
- RPC provider: Helius
- Monitored DEXs: Raydium, Orca, Jupiter

---

## 📝 Server Logs

View live logs:
```bash
tail -f /home/user/solana-moon-scanner/webapp.log
```

Current status:
```
✅ Moon Scanner web app initialized
✅ Uvicorn running on http://0.0.0.0:8000
✅ Application startup complete
✅ All components initialized
```

---

## 🎯 Next Steps

1. **Test Current Features**
   - Open the public URL in your browser
   - Check the dashboard
   - Try the API endpoints via Swagger UI
   - Test a token scan

2. **Build Additional Pages**
   - Create `/scan` page for token scanning interface
   - Create `/history` page for full scan history
   - Create `/settings` page for configuration

3. **Enhancements**
   - Add database for persistent storage
   - Add user authentication
   - Add export functionality (CSV, JSON)
   - Add more charts and visualizations
   - Add alert configuration UI

---

## 🛑 Stop/Restart Server

### Stop Server
```bash
pkill -f "uvicorn webapp.main:app"
```

### Restart Server
```bash
cd /home/user/solana-moon-scanner
python -m uvicorn webapp.main:app --host 0.0.0.0 --port 8000 --reload > webapp.log 2>&1 &
```

### Check if Running
```bash
curl http://localhost:8000/api/stats
```

---

**Last Updated**: 2025-10-24 16:52 UTC
**Server Port**: 8000
**Status**: ✅ ACTIVE
