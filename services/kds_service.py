import asyncio
import json
import threading
import websockets
from PySide6.QtCore import QObject, Signal

class KDSBroadcaster(QObject):
    """
    Singleton-style broadcaster to bridge Qt signals and WebSocket messages.
    """
    order_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.clients = set()
        self.loop = None
        self._thread = None

    def start_server(self, host="0.0.0.0", port=8765):
        self._thread = threading.Thread(target=self._run_server, args=(host, port), daemon=True)
        self._thread.start()

    def _run_server(self, host, port):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def server_main():
            async with websockets.serve(self._handle_client, host, port):
                print(f"[KDS] WebSocket server started on ws://{host}:{port}")
                await asyncio.Future()  # Run forever

        try:
            self.loop.run_until_complete(server_main())
        except Exception as e:
            print(f"[KDS] Server Error: {e}")

    async def _handle_client(self, websocket, path=None):
        self.clients.add(websocket)
        print(f"[KDS] Client connected. Total: {len(self.clients)}")
        try:
            # Send initial state or welcome message if needed
            async for message in websocket:
                # Handle incoming messages from KDS screens (e.g. status updates)
                data = json.loads(message)
                # Emit to Qt thread if needed
                self.order_updated.emit(data)
                # Broadcast to others
                await self.broadcast(data, exclude=websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"[KDS] Client disconnected. Total: {len(self.clients)}")

    async def broadcast(self, data: dict, exclude=None):
        if not self.clients:
            return
        message = json.dumps(data)
        tasks = []
        for client in self.clients:
            if client != exclude:
                tasks.append(client.send(message))
        if tasks:
            await asyncio.gather(*tasks)

    def broadcast_sync(self, data: dict):
        """Helper to broadcast from non-async code (Qt threads)."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self.loop)

# Singleton instance
kds_service = KDSBroadcaster()
