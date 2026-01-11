from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DATABASE_URL = "sqlite+aiosqlite:///./db/syncterra.db"

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
                logger.info(
                    f"Initializing scan_paths with {docker_scan_paths} from environment"
                )
                new_setting = Setting(key="scan_paths", value=docker_scan_paths)
                session.add(new_setting)
                await session.commit()

    # 同期設定の自動初期化 (FTP/Rsync)
    sync_defaults = {
        "sync_mode": os.getenv("DOCKER_SYNC_MODE"),
        "ftp_host": os.getenv("DOCKER_FTP_HOST"),
        "ftp_port": os.getenv("DOCKER_FTP_PORT"),
        "ftp_user": os.getenv("DOCKER_FTP_USER"),
        "ftp_pass": os.getenv("DOCKER_FTP_PASS"),
        "rsync_host": os.getenv("DOCKER_RSYNC_HOST"),
        "rsync_port": os.getenv("DOCKER_RSYNC_PORT"),
        "rsync_user": os.getenv("DOCKER_RSYNC_USER"),
        "rsync_pass": os.getenv("DOCKER_RSYNC_PASS"),
        "rsync_use_key": os.getenv("DOCKER_RSYNC_USE_KEY"),
        "rsync_key_path": os.getenv("DOCKER_RSYNC_KEY_PATH"),
        "rsync_dest": os.getenv("DOCKER_RSYNC_DEST"),
    }

    async with AsyncSessionLocal() as session:
        import logging

        logger = logging.getLogger(__name__)
        for key, value in sync_defaults.items():
            if value is not None and str(value).strip() != "":
                # Check if already exists
                stmt = select(Setting).where(Setting.key == key)
                res = await session.execute(stmt)
                existing = res.scalar()
                if existing:
                    if existing.value != value:
                        logger.info(
                            f"Updating setting {key}: {existing.value} -> {value}"
                        )
                        existing.value = value
                else:
                    logger.info(f"Initializing setting {key}: {value}")
                    setting = Setting(key=key, value=value)
                    session.add(setting)
        await session.commit()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
