from fastapi import FastAPI
from .db.database import init_db
from .api import settings, tracks, system, websocket
import logging

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AudioSync API")

@app.on_event("startup")
async def on_startup():
    await init_db()

app.include_router(settings.router)
app.include_router(tracks.router)
app.include_router(system.router)
app.include_router(websocket.router)
