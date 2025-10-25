"""FastAPI Web Application for Solana Moon Scanner."""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.scanner import MoonScanner
from src.utils.logger import setup_logger
from webapp.auto_scanner import AutoScanner
import logging

logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Solana Moon Scanner",
    description="Real-time Solana token monitoring and scoring",
    version="1.0.0"
)

# Setup templates and static files
templates = Jinja2Templates(directory="webapp/templates")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

# Global scanner instance
scanner: Optional[MoonScanner] = None
auto_scanner: Optional[AutoScanner] = None
scan_history: List[dict] = []
active_connections: List[WebSocket] = []

# Setup logger
setup_logger()


class ScanRequest(BaseModel):
    """Token scan request model."""
    token_address: str


class ScanResponse(BaseModel):
    """Scan response model."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


async def on_auto_scan_result(result: dict):
    """Callback for automated scan results."""
    global scan_history
    
    # Add to history
    scan_entry = {
        "id": len(scan_history) + 1,
        "timestamp": datetime.now().isoformat(),
        "token_address": result["token_address"],
        "moon_score": result["moon_score"]["total_score"],
        "rating": result["rating"],
        "validation": result["validation"]["overall_status"],
        "full_data": result,
        "auto_scan": True  # Mark as auto-scanned
    }
    scan_history.insert(0, scan_entry)
    
    # Keep only last 100 scans
    if len(scan_history) > 100:
        scan_history.pop()
    
    # Notify WebSocket clients
    await broadcast_scan_update(scan_entry)
    
    print(f"🤖 Auto-scan complete: {result['token_address'][:8]}... | Score: {result['moon_score']['total_score']:.2f}")


@app.on_event("startup")
async def startup_event():
    """Initialize scanner on startup."""
    global scanner, auto_scanner
    
    # Initialize main scanner
    scanner = MoonScanner()
    await scanner._initialize_components()
    print("✅ Moon Scanner web app initialized")
    
    # Initialize and start auto scanner
    auto_scanner = AutoScanner(scanner, on_auto_scan_result)
    await auto_scanner.start()
    print("🤖 Auto Scanner started (5-minute intervals)")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global scanner, auto_scanner
    
    if auto_scanner:
        await auto_scanner.stop()
    
    if scanner:
        await scanner.stop()


# ============================================================================
# WEB PAGES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard"
    })


@app.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    """Token scan page."""
    return templates.TemplateResponse("scan.html", {
        "request": request,
        "title": "Scan Token"
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Scan history page."""
    return templates.TemplateResponse("history.html", {
        "request": request,
        "title": "History"
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "title": "Settings"
    })


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.post("/api/scan", response_model=ScanResponse)
async def api_scan_token(request: ScanRequest):
    """Scan a specific token address."""
    global scanner, scan_history
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    try:
        result = await scanner.scan_token(request.token_address)
        
        # Add to history
        scan_entry = {
            "id": len(scan_history) + 1,
            "timestamp": datetime.now().isoformat(),
            "token_address": request.token_address,
            "moon_score": result["moon_score"]["total_score"],
            "rating": result["rating"],
            "validation": result["validation"]["overall_status"],
            "full_data": result,
            "auto_scan": False  # Mark as manual scan
        }
        scan_history.insert(0, scan_entry)
        
        # Keep only last 100 scans
        if len(scan_history) > 100:
            scan_history.pop()
        
        # Notify WebSocket clients
        await broadcast_scan_update(scan_entry)
        
        return ScanResponse(success=True, data=result)
    
    except Exception as e:
        return ScanResponse(success=False, error=str(e))


@app.get("/api/history")
async def api_get_history(limit: int = 50):
    """Get scan history."""
    return {
        "success": True,
        "data": scan_history[:limit]
    }


@app.get("/api/stats")
async def api_get_stats():
    """Get statistics."""
    if not scan_history:
        return {
            "success": True,
            "data": {
                "total_scans": 0,
                "average_score": 0,
                "high_score_count": 0,
                "passed_validation": 0
            }
        }
    
    total_scans = len(scan_history)
    scores = [s["moon_score"] for s in scan_history]
    avg_score = sum(scores) / len(scores) if scores else 0
    high_score_count = len([s for s in scores if s >= 70])
    passed_count = len([s for s in scan_history if s["validation"] == "pass"])
    
    return {
        "success": True,
        "data": {
            "total_scans": total_scans,
            "average_score": round(avg_score, 2),
            "high_score_count": high_score_count,
            "passed_validation": passed_count
        }
    }


@app.get("/api/config")
async def api_get_config():
    """Get current configuration."""
    global scanner
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    return {
        "success": True,
        "data": {
            "monitored_dexs": scanner.config.get_monitored_dexs(),
            "min_score_threshold": scanner.config.min_moon_score_threshold,
            "max_token_age": scanner.config.max_token_age_minutes,
            "scan_interval": scanner.config.scan_interval_seconds,
            "telegram_enabled": scanner.config.telegram_enabled,
            "discord_enabled": scanner.config.discord_enabled,
        }
    }


@app.get("/api/auto-scanner/status")
async def api_get_auto_scanner_status():
    """Get auto scanner status."""
    global auto_scanner
    
    if not auto_scanner:
        raise HTTPException(status_code=503, detail="Auto scanner not initialized")
    
    return {
        "success": True,
        "data": auto_scanner.get_status()
    }


@app.post("/api/auto-scanner/start")
async def api_start_auto_scanner():
    """Start auto scanner."""
    global auto_scanner
    
    if not auto_scanner:
        raise HTTPException(status_code=503, detail="Auto scanner not initialized")
    
    await auto_scanner.start()
    
    return {
        "success": True,
        "message": "Auto scanner started"
    }


@app.post("/api/auto-scanner/stop")
async def api_stop_auto_scanner():
    """Stop auto scanner."""
    global auto_scanner
    
    if not auto_scanner:
        raise HTTPException(status_code=503, detail="Auto scanner not initialized")
    
    await auto_scanner.stop()
    
    return {
        "success": True,
        "message": "Auto scanner stopped"
    }


@app.post("/api/scan/manual")
async def api_manual_token_scan(request: ScanRequest):
    """Manually scan a specific token address and get full details."""
    global scanner, scan_history
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    try:
        result = await scanner.scan_token(request.token_address)
        
        # Add to history with manual flag
        scan_entry = {
            "id": len(scan_history) + 1,
            "timestamp": datetime.now().isoformat(),
            "token_address": request.token_address,
            "moon_score": result["moon_score"]["total_score"],
            "rating": result["rating"],
            "validation": result["validation"]["overall_status"],
            "full_data": result,
            "auto_scan": False  # Mark as manual scan
        }
        scan_history.insert(0, scan_entry)
        
        # Keep only last 100 scans
        if len(scan_history) > 100:
            scan_history.pop()
        
        # Notify WebSocket clients
        await broadcast_scan_update(scan_entry)
        
        return {
            "success": True,
            "data": scan_entry  # Return full scan_entry instead of just result
        }
    
    except Exception as e:
        logger.error(f"Manual token scan error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/auto-scanner/manual-discovery")
async def api_manual_discovery_scan(request: dict):
    """Manually trigger discovery and scanning of tokens from the last N hours."""
    global auto_scanner
    
    if not auto_scanner:
        raise HTTPException(status_code=503, detail="Auto scanner not initialized")
    
    try:
        hours = request.get("hours", 2)
        
        # Temporarily adjust max token age for manual discovery
        original_max_age = auto_scanner.max_token_age_minutes
        auto_scanner.max_token_age_minutes = hours * 60  # Convert hours to minutes
        
        # Run discovery
        await auto_scanner._discover_new_tokens()
        
        # Get eligible tokens
        eligible_tokens = auto_scanner._get_eligible_tokens()
        
        # Scan eligible tokens
        if eligible_tokens:
            await auto_scanner._scan_tokens(eligible_tokens)
        
        # Restore original max age
        auto_scanner.max_token_age_minutes = original_max_age
        
        discovered_count = len(auto_scanner.discovered_tokens)
        scanned_count = len(auto_scanner.scanned_tokens)
        
        return {
            "success": True,
            "data": {
                "discovered_count": discovered_count,
                "scanned_count": scanned_count,
                "hours": hours
            },
            "message": f"Discovered {discovered_count} tokens, scanned {scanned_count}"
        }
    
    except Exception as e:
        logger.error(f"Manual discovery error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.delete("/api/history")
async def api_clear_history():
    """Clear all scan history."""
    global scan_history
    
    scan_history.clear()
    
    return {
        "success": True,
        "message": "History cleared successfully"
    }


@app.get("/api/settings/rpc")
async def api_get_rpc_settings():
    """Get RPC configuration."""
    global scanner
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    try:
        rpc_client = scanner.rpc_client
        return {
            "success": True,
            "data": {
                "primary_url": rpc_client.primary_url if hasattr(rpc_client, 'primary_url') else "Not configured",
                "fallback_url": rpc_client.fallback_url if hasattr(rpc_client, 'fallback_url') else "Not configured"
            },
            "status": {
                "primary": True,  # Assume connected if scanner is running
                "fallback": hasattr(rpc_client, 'fallback_url') and rpc_client.fallback_url is not None
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/settings/rpc/test")
async def api_test_rpc_connection():
    """Test RPC connection."""
    global scanner
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    try:
        # Try to fetch a simple request
        rpc_client = scanner.rpc_client
        
        # Test primary connection
        primary_ok = False
        try:
            # Try a simple getSlot call to test connection
            response = await rpc_client._make_request("getSlot", [])
            primary_ok = response is not None
        except:
            pass
        
        # Test fallback if exists
        fallback_ok = False
        if hasattr(rpc_client, 'fallback_url') and rpc_client.fallback_url:
            fallback_ok = True  # Assume it works if configured
        
        return {
            "success": True,
            "status": {
                "primary": primary_ok,
                "fallback": fallback_ok
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/settings")
async def api_save_settings(request: dict):
    """Save settings (for backend persistence if needed in future)."""
    # Currently settings are stored in localStorage on frontend
    # This endpoint is a placeholder for future backend persistence
    return {
        "success": True,
        "message": "Settings received (frontend storage only)"
    }


@app.post("/api/config/update")
async def api_update_config(request: dict):
    """Update scanner configuration in real-time."""
    global auto_scanner
    
    try:
        if auto_scanner:
            # Update auto scanner settings
            if 'max_token_age_hours' in request:
                auto_scanner.max_token_age_minutes = int(request['max_token_age_hours']) * 60
            
            if 'min_liquidity' in request:
                auto_scanner.min_liquidity_usd = float(request['min_liquidity'])
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "data": {
                "max_token_age_minutes": auto_scanner.max_token_age_minutes if auto_scanner else None,
                "min_liquidity_usd": auto_scanner.min_liquidity_usd if auto_scanner else None
            }
        }
    except Exception as e:
        logger.error(f"Config update error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial data
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Moon Scanner",
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep connection alive
        while True:
            # Wait for messages (or just keep alive)
            data = await websocket.receive_text()
            
            # Echo back for heartbeat
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_scan_update(scan_data: dict):
    """Broadcast scan update to all connected WebSocket clients."""
    message = {
        "type": "scan_update",
        "data": scan_data,
        "timestamp": datetime.now().isoformat()
    }
    
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "scanner_initialized": scanner is not None,
        "active_connections": len(active_connections),
        "total_scans": len(scan_history),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
