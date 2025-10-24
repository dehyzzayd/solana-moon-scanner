"""WebSocket manager for real-time Solana event monitoring."""

import asyncio
import json
from typing import Callable, Dict, List, Optional, Set
from datetime import datetime

import websockets
from websockets.exceptions import WebSocketException

from ..utils.config import get_config
from ..utils.logger import LoggerMixin
from ..utils.metrics import websocket_connections, errors


class WebSocketManager(LoggerMixin):
    """
    Manages WebSocket connections for real-time event monitoring.
    
    Supports subscriptions to logs, account changes, and program events.
    """
    
    def __init__(self):
        self.config = get_config()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[int, Dict] = {}
        self.subscription_id_counter = 0
        self.callbacks: Dict[int, Callable] = {}
        self.running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
    
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        wss_url = self.config.get_wss_url()
        
        if not wss_url:
            self.logger.warning("No WebSocket URL configured")
            return
        
        if not self.config.enable_websocket:
            self.logger.info("WebSocket monitoring disabled")
            return
        
        try:
            self.ws = await websockets.connect(
                wss_url,
                ping_interval=20,
                ping_timeout=10,
            )
            websocket_connections.inc()
            self.logger.info(f"WebSocket connected to {wss_url}")
            self._reconnect_attempts = 0
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            errors.labels(error_type="websocket_connect", component="websocket_manager").inc()
            raise
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            websocket_connections.dec()
            self.logger.info("WebSocket disconnected")
    
    async def subscribe_logs(
        self,
        program_ids: List[str],
        callback: Callable,
    ) -> int:
        """
        Subscribe to program logs.
        
        Args:
            program_ids: List of program IDs to monitor
            callback: Callback function to handle log events
            
        Returns:
            Subscription ID
        """
        if not self.ws:
            await self.connect()
        
        subscription_id = self.subscription_id_counter
        self.subscription_id_counter += 1
        
        for program_id in program_ids:
            request = {
                "jsonrpc": "2.0",
                "id": subscription_id,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [program_id]},
                    {"commitment": "confirmed"},
                ],
            }
            
            await self.ws.send(json.dumps(request))
            self.logger.info(f"Subscribed to logs for program {program_id}")
        
        self.subscriptions[subscription_id] = {
            "type": "logs",
            "program_ids": program_ids,
            "callback": callback,
        }
        self.callbacks[subscription_id] = callback
        
        return subscription_id
    
    async def subscribe_account(
        self,
        account_address: str,
        callback: Callable,
    ) -> int:
        """
        Subscribe to account changes.
        
        Args:
            account_address: Account address to monitor
            callback: Callback function to handle account change events
            
        Returns:
            Subscription ID
        """
        if not self.ws:
            await self.connect()
        
        subscription_id = self.subscription_id_counter
        self.subscription_id_counter += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": subscription_id,
            "method": "accountSubscribe",
            "params": [
                account_address,
                {"encoding": "jsonParsed", "commitment": "confirmed"},
            ],
        }
        
        await self.ws.send(json.dumps(request))
        self.logger.info(f"Subscribed to account {account_address}")
        
        self.subscriptions[subscription_id] = {
            "type": "account",
            "address": account_address,
            "callback": callback,
        }
        self.callbacks[subscription_id] = callback
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: int) -> None:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID to cancel
        """
        if subscription_id not in self.subscriptions:
            self.logger.warning(f"Subscription {subscription_id} not found")
            return
        
        subscription = self.subscriptions[subscription_id]
        
        if subscription["type"] == "logs":
            method = "logsUnsubscribe"
        elif subscription["type"] == "account":
            method = "accountUnsubscribe"
        else:
            self.logger.error(f"Unknown subscription type: {subscription['type']}")
            return
        
        request = {
            "jsonrpc": "2.0",
            "id": subscription_id,
            "method": method,
            "params": [subscription_id],
        }
        
        if self.ws:
            await self.ws.send(json.dumps(request))
        
        del self.subscriptions[subscription_id]
        del self.callbacks[subscription_id]
        
        self.logger.info(f"Unsubscribed from {subscription_id}")
    
    async def listen(self) -> None:
        """
        Listen for WebSocket events and dispatch to callbacks.
        
        This method runs in a loop and should be executed as a task.
        """
        if not self.ws:
            await self.connect()
        
        self.running = True
        self.logger.info("WebSocket listener started")
        
        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                    data = json.loads(message)
                    
                    # Handle subscription confirmations
                    if "result" in data and "id" in data:
                        self.logger.debug(f"Subscription confirmed: {data}")
                        continue
                    
                    # Handle subscription events
                    if "method" in data and "params" in data:
                        await self._handle_event(data)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    if self.ws:
                        await self.ws.ping()
                    continue
                
                except WebSocketException as e:
                    self.logger.error(f"WebSocket error: {e}")
                    errors.labels(error_type="websocket_error", component="websocket_manager").inc()
                    
                    # Attempt reconnection
                    if self._reconnect_attempts < self._max_reconnect_attempts:
                        self._reconnect_attempts += 1
                        self.logger.info(f"Reconnecting... (attempt {self._reconnect_attempts})")
                        await asyncio.sleep(2 ** self._reconnect_attempts)
                        await self.disconnect()
                        await self.connect()
                        
                        # Re-establish subscriptions
                        await self._resubscribe_all()
                    else:
                        self.logger.error("Max reconnection attempts reached")
                        break
        
        except Exception as e:
            self.logger.error(f"Fatal error in WebSocket listener: {e}")
            errors.labels(error_type="websocket_fatal", component="websocket_manager").inc()
            raise
        
        finally:
            self.running = False
            await self.disconnect()
    
    async def _handle_event(self, data: Dict) -> None:
        """
        Handle incoming WebSocket events.
        
        Args:
            data: Event data
        """
        try:
            method = data.get("method")
            params = data.get("params", {})
            
            if method == "logsNotification":
                result = params.get("result", {})
                subscription_id = params.get("subscription")
                
                if subscription_id in self.callbacks:
                    callback = self.callbacks[subscription_id]
                    await callback(result)
            
            elif method == "accountNotification":
                result = params.get("result", {})
                subscription_id = params.get("subscription")
                
                if subscription_id in self.callbacks:
                    callback = self.callbacks[subscription_id]
                    await callback(result)
            
            else:
                self.logger.debug(f"Unhandled event method: {method}")
        
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")
            errors.labels(error_type="event_handler", component="websocket_manager").inc()
    
    async def _resubscribe_all(self) -> None:
        """Re-establish all subscriptions after reconnection."""
        subscriptions_copy = list(self.subscriptions.items())
        self.subscriptions.clear()
        self.callbacks.clear()
        
        for sub_id, subscription in subscriptions_copy:
            if subscription["type"] == "logs":
                await self.subscribe_logs(
                    subscription["program_ids"],
                    subscription["callback"],
                )
            elif subscription["type"] == "account":
                await self.subscribe_account(
                    subscription["address"],
                    subscription["callback"],
                )
    
    async def stop(self) -> None:
        """Stop the WebSocket listener."""
        self.running = False
        await self.disconnect()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
