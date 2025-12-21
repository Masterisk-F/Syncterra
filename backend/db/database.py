from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = "sqlite+aiosqlite:///./db/audiosync.db"

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


import os
from sqlalchemy.future import select
from .models import Setting

async def init_db():
    # データベースディレクトリが存在することを確認
    db_dir = os.path.dirname(DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Docker環境向けの初期設定（スキャンパス）
    docker_scan_paths = os.getenv("DOCKER_DEFAULT_SCAN_PATHS")
    if docker_scan_paths:
        async with AsyncSessionLocal() as session:
            # 既に設定が存在するか確認
            result = await session.execute(
                select(Setting).where(Setting.key == "scan_paths")
            )
            existing = result.scalars().first()
            
            if not existing:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Initializing scan_paths with {docker_scan_paths} from environment")
                new_setting = Setting(key="scan_paths", value=docker_scan_paths)
                session.add(new_setting)
                await session.commit()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
