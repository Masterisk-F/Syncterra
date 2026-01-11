"""
Integration Tests: 共通Fixture
目的: Integrationテストで利用する共通のセットアップ（DB、ファイルシステム、クライアント等）を提供する。

主要なFixture:
- temp_db: テスト専用のインメモリSQLiteデータベースセッション
- override_get_db: FastAPIの依存性注入をオーバーライドし、temp_dbを使用させる
- client: FastAPIテストクライアント
- temp_fs: ダミー音楽ファイルを含む一時ディレクトリ
- create_settings: テスト用設定を簡単にDBに追加するヘルパー
- patch_db_session: Scanner/Syncerなど独自セッションを持つサービス用のパッチ
"""

import os
import shutil
import tempfile

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.database import Base, get_db
from backend.main import app

# テスト用データベースURL
# :memory: を使用することで、テストごとに独立したDBが生成され、高速かつ安全にテストできる
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def temp_db():
    """
    テスト専用のインメモリSQLiteデータベースセッションを提供するFixture。

    特徴:
    - 各テストで独立したDBインスタンスを使用（並列実行セーフ）
    - StaticPoolによりコネクションを維持（インメモリDBの永続性を確保）
    - テスト終了後に自動的にクリーンアップ

    使用例:
        async def test_example(temp_db):
            temp_db.add(SomeModel(...))
            await temp_db.commit()
    """
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # インメモリDBでセッション間のデータ共有に必要
    )

    # テーブル作成
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # セッションファクトリ作成
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.close()

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_get_db(temp_db):
    """
    FastAPIの依存性注入をオーバーライドし、temp_dbセッションを使用させるFixture。
    autouse=Trueにより、すべてのテストで自動的に適用される。

    目的:
    APIエンドポイントが本番のDBではなく、テスト用のtemp_dbを使用するようにする。
    これにより、APIテスト時にDBアクセスがインメモリDBにリダイレクトされる。
    """

    async def _get_db():
        yield temp_db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_get_db):
    """
    FastAPIテストクライアントを提供するFixture。

    特徴:
    - override_get_dbと組み合わせることで、temp_dbを使用したAPIテストが可能
    - 同期的なTestClientを使用（シンプルなAPIテスト向け）

    使用例:
    def test_api(client):
        response = client.post("/api/scan")
        assert response.status_code == 200
    """
    return TestClient(app)


@pytest.fixture
def temp_fs():
    """
    ダミー音楽ファイルを含む一時ディレクトリを作成するFixture。

    ディレクトリ構造:
    /ROOT
      /Artist1
        /Album1
          song1.mp3 (タイトル: "Song 1", アーティスト: "Artist 1", アルバム: "Album 1")
          song2.mp3 (タイトル: "Song 2", アーティスト: "Artist 1", アルバム: "Album 1")
      /Artist2
        song3.mp3 (タイトル: "Song 3", アーティスト: "Artist 2", アルバム: "Unknown Album")
      /Excluded
        ignored.mp3 (メタデータなし、除外テスト用)
      info.txt (非音楽ファイル、拡張子フィルタテスト用)

    特徴:
    - mutagenを使用して実際のID3タグを書き込み（メタデータ抽出テストに対応）
    - テスト終了後に自動削除

    使用例:
        def test_scan(temp_fs):
            # temp_fsはディレクトリパス（str）
            assert os.path.exists(os.path.join(temp_fs, "Artist1", "Album1", "song1.mp3"))
    """
    tmp_dir = tempfile.mkdtemp()

    # ディレクトリ作成
    os.makedirs(os.path.join(tmp_dir, "Artist1", "Album1"))
    os.makedirs(os.path.join(tmp_dir, "Artist2"))
    os.makedirs(os.path.join(tmp_dir, "Excluded"))

    def create_file(path, content="dummy content", title=None, artist=None, album=None):
        """ダミーファイルを作成し、必要に応じてID3タグを追加"""
        with open(path, "w") as f:
            f.write(content)

        # ID3タグを追加（mutagen使用）
        if title or artist or album:
            from mutagen.id3 import ID3, TALB, TIT2, TPE1

            try:
                tags = ID3()
                if title:
                    tags["TIT2"] = TIT2(encoding=3, text=title)
                if artist:
                    tags["TPE1"] = TPE1(encoding=3, text=artist)
                if album:
                    tags["TALB"] = TALB(encoding=3, text=album)
                tags.save(path)
            except Exception as e:
                print(f"Warning: Failed to save tags to {path}: {e}")

    # メタデータ付きファイル
    create_file(
        os.path.join(tmp_dir, "Artist1", "Album1", "song1.mp3"),
        title="Song 1",
        artist="Artist 1",
        album="Album 1",
    )
    create_file(
        os.path.join(tmp_dir, "Artist1", "Album1", "song2.mp3"),
        title="Song 2",
        artist="Artist 1",
        album="Album 1",
    )
    create_file(
        os.path.join(tmp_dir, "Artist2", "song3.mp3"),
        title="Song 3",
        artist="Artist 2",
        album="Unknown Album",
    )

    # メタデータなしファイル（除外テスト用）
    create_file(os.path.join(tmp_dir, "Excluded", "ignored.mp3"))

    # 非音楽ファイル（拡張子フィルタテスト用）
    create_file(os.path.join(tmp_dir, "info.txt"))

    yield tmp_dir

    # クリーンアップ
    shutil.rmtree(tmp_dir)


@pytest.fixture
def create_settings(temp_db):
    """
    テスト用設定をDBに追加するヘルパーFixture。

    目的:
    テストの前提条件として必要なSettingsを簡潔に設定するためのユーティリティ。
    同じキーが既に存在する場合は更新する。

    使用例:
        async def test_scan(temp_db, create_settings):
            await create_settings(
                sync_mode="adb",
                sync_dest="/sdcard/Music",
                target_exts="mp3,flac"
            )
    """
    from backend.db.models import Setting

    async def _create_settings(**kwargs):
        for key, value in kwargs.items():
            # 既存チェック
            result = await temp_db.execute(select(Setting).where(Setting.key == key))
            existing = result.scalars().first()
            if existing:
                existing.value = str(value)
            else:
                temp_db.add(Setting(key=key, value=str(value)))
        await temp_db.commit()

    return _create_settings


@pytest.fixture(autouse=True)
def patch_db_session(temp_db):
    """
    Scanner/Syncerなど独自にセッションを生成するサービス用のパッチFixture。
    autouse=True: テスト全体で誤って本番DBに接続しないよう強制する。

    目的:
    ScannerServiceやSyncServiceは内部でAsyncSessionLocalを呼び出してDBセッションを取得する。
    このFixtureは、これらのサービスがtemp_dbを使用するようにMockでパッチする。

    パッチ対象:
    - backend.core.scanner.AsyncSessionLocal
    - backend.core.syncer.AsyncSessionLocal
    - backend.api.settings.AsyncSessionLocal (念のため)

    使用例:
        async def test_scanner_flow(temp_db, patch_db_session):
            # ScannerService内部でtemp_dbが使用される
            await ScannerService().run_scan()
    """
    from unittest.mock import MagicMock, patch

    # async context manager をモック
    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    # パッチ対象のモジュールパス
    targets = [
        "backend.core.scanner.AsyncSessionLocal",
        "backend.core.syncer.AsyncSessionLocal",
        "backend.db.database.AsyncSessionLocal",
        "backend.core.album_art_scanner.MainSessionLocal",
    ]

    patches = [patch(target, return_value=mock_session_cls) for target in targets]

    # パッチ開始
    # Note: backend.db.database.AsyncSessionLocal patch might act weird if it's a class not function.
    # But in database.py it is `AsyncSessionLocal = async_sessionmaker(...)` which is a callable (class-like).
    # Setting return_value on it triggers when instantiated: `AsyncSessionLocal()` -> returns mock_session_cls
    # which has __aenter__ returning temp_db. This matches usage `async with AsyncSessionLocal() as db:`

    for p in patches:
        p.start()

    yield

    # パッチ終了
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def patch_init_db():
    """
    startupイベントでのinit_db実行を無効化するFixture。

    理由:
    1. テスト環境ではtemp_db fixtureがテーブル作成を行うためredundant。
    2. init_dbがグローバルなengine(ファイルDB)を使用するため、
       テスト中に意図せずファイルDBへの接続/スレッド作成が発生し、
       pytestがハングする原因になる可能性がある。
    """
    from unittest.mock import AsyncMock, patch

    # backend.mainですでにimportされているinit_dbをパッチする必要がある
    # AsyncMockを使用してawait可能なモックにする
    with (
        patch("backend.main.init_db", new_callable=AsyncMock) as mock_main_init,
        patch("backend.db.database.init_db", new_callable=AsyncMock) as mock_db_init,
        patch("backend.main.init_albumart_db", new_callable=AsyncMock) as mock_main_art_init,
        patch("backend.db.albumart_database.init_albumart_db", new_callable=AsyncMock) as mock_db_art_init,
    ):
        yield


@pytest_asyncio.fixture
async def temp_art_db():
    """
    アルバムアート用DBのテスト用セッションFixture
    """
    from backend.db.albumart_models import Base as ArtBase
    
    # 別個のインメモリDB
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(ArtBase.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.close()

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_get_albumart_db(temp_art_db):
    from backend.db.albumart_database import get_albumart_db
    
    async def _get_db():
        yield temp_art_db

    app.dependency_overrides[get_albumart_db] = _get_db
    yield
    if get_albumart_db in app.dependency_overrides:
        del app.dependency_overrides[get_albumart_db]


@pytest.fixture(autouse=True)
def patch_art_db_session(temp_art_db):
    """
    AlbumArtScanner用のDBセッションパッチ
    """
    from unittest.mock import MagicMock, patch

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_art_db
    mock_session_cls.__aexit__.return_value = None

    targets = [
        "backend.core.album_art_scanner.ArtSessionLocal",
        "backend.db.albumart_database.AsyncSessionLocal",
    ]

    patches = [patch(target, return_value=mock_session_cls) for target in targets]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()

