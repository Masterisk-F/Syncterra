from fastapi import APIRouter, BackgroundTasks, Depends
# from ..core.scanner import ScannerService # Phase 3.4
# from ..core.syncer import SyncService # Phase 3.4
import logging

router = APIRouter(prefix="/api", tags=["system"])
logger = logging.getLogger(__name__)

async def scan_task():
    logger.info("Scan task (stub) started")
    # Stub implementation. Real logic in Phase 3.4
    pass

async def sync_task():
    logger.info("Sync task (stub) started")
    # Stub implementation. Real logic in Phase 3.4
    pass

@router.post("/scan")
async def scan_files(background_tasks: BackgroundTasks):
    background_tasks.add_task(scan_task)
    return {"status": "accepted", "message": "Scan started"}

@router.post("/sync")
async def sync_files(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_task)
    return {"status": "accepted", "message": "Sync started"}
