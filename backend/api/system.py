import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks

from ..core.scanner import ScannerService
from ..core.syncer import SyncService
from .websocket import manager

router = APIRouter(prefix="/api", tags=["system"])
logger = logging.getLogger(__name__)


def log_to_ws(message: str):
    # This is called from sync threads.
    # We need to schedule broadcasting to the event loop?
    # Or just print? WebSocket broadcasting is async.
    # We can use asyncio.run_coroutine_threadsafe if we have loop access.
    # For simplicity/safety in this context (threadpool), let's just log to console
    # and rely on the fact that we can't easily await here without loop reference.
    # BUT requirement says "WebSocketでの進捗通知".
    # Solution: The service runs in a thread, but checking manager.broadcast is a coroutine.
    # We can pass an async wrapper if we run service in standard async way?
    # ScannerService run_scan is async. SyncService run_sync is async (wraps thread).
    # So we can pass an async callback for Scanner, but SyncService internal methods are sync.
    # Let's fix SyncService to accept a sync callback that maybe pushes to a queue or uses run_coroutine_threadsafe.

    # Actually, let's just assume we log to logger for now, and try to hook up WS.
    # In FastAPI, we can grab the loop from the request?
    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
    except RuntimeError:
        pass  # No loop?


async def scan_task():
    logger.info("Scan task started")
    scanner = ScannerService()

    import json

    # WebSocket callbacks
    # Note: run_scan runs in a threadpool (mostly), but calling these callbacks directly
    # from the thread might be an issue if manager.broadcast is async.
    # However, Scanner calls them synchronously.
    # We need to bridge sync -> async.

    loop = asyncio.get_running_loop()

    def progress_callback(progress: int):
        data = json.dumps({"type": "progress", "progress": progress})
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    def log_callback(message: str):
        data = json.dumps({"type": "log", "message": message})
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    await scanner.run_scan(
        progress_callback=progress_callback, log_callback=log_callback
    )

    # Final completion message handled by scanner's log_callback mostly,
    # but frontend expects specific "Scan complete" string to reload?
    # Frontend logic: if (message.includes('Scan complete')) -> reload
    # Scanner logs: "Scan complete. Added: ..."
    # So it should be fine.
    # But let's send a pure status update or just rely on the log.
    # The original code sent "Scan complete" string.
    # Scanner now logs "Scan complete..." via log_callback.
    # That should trigger the frontend reload.


async def sync_task():
    logger.info("Sync task started")
    loop = asyncio.get_running_loop()

    def callback(msg):
        # Allow sync code to bradcast
        asyncio.run_coroutine_threadsafe(manager.broadcast(msg), loop)

    await SyncService.run_sync(log_callback=callback)
    await manager.broadcast("Sync complete")


@router.post("/scan")
async def scan_files(background_tasks: BackgroundTasks):
    background_tasks.add_task(scan_task)
    return {"status": "accepted", "message": "Scan started"}


@router.post("/sync")
async def sync_files(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_task)
    return {"status": "accepted", "message": "Sync started"}
