import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api import album_art, playlists, settings, system, tracks, websocket
from .db.albumart_database import init_albumart_db
from .db.database import init_db

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Syncterra API")

# CORS設定 - フロントエンドからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8280",  # Docker frontend (production)
        "http://localhost",  # Docker frontend (default port 80)
    ],
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
    await init_albumart_db()


app.include_router(settings.router)
app.include_router(tracks.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(playlists.router)
app.include_router(album_art.router)
if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="TCP Port binding (Dev only)")
    parser.add_argument("--uds", type=str, help="Unix Domain Socket path")
    args = parser.parse_args()
    
    if args.uds:
        # UDS binding
        uvicorn.run(app, uds=args.uds)
    elif args.port:
        # Localhost binding
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    else:
        # Default fallback (Dev)
        uvicorn.run(app, host="127.0.0.1", port=8000)
