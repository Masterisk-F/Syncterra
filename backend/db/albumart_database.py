from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .albumart_models import Base

# Main app uses /db/syncterra.db, so we use /db/syncterra_albumart.db
DATABASE_URL = "sqlite+aiosqlite:///./db/syncterra_albumart.db"

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


import os


async def init_albumart_db():
    # データベースディレクトリが存在することを確認
    db_dir = os.path.dirname(DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_albumart_db():
    async with AsyncSessionLocal() as session:
        yield session
