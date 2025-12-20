from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .db.database import init_db
from .api import settings, tracks, system, websocket
import logging
import os

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AudioSync API")

# CORS設定 - フロントエンドからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# AsyncAPI仕様の配信
@app.get("/asyncapi.yaml")
async def get_asyncapi():
    asyncapi_path = os.path.join(os.path.dirname(__file__), "..", "asyncapi.yaml")
    return FileResponse(asyncapi_path, media_type="application/x-yaml")


@app.on_event("startup")
async def on_startup():
    await init_db()


app.include_router(settings.router)
app.include_router(tracks.router)
app.include_router(system.router)
app.include_router(websocket.router)
