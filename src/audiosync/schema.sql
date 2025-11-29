-- AudioSync データベーススキーマ
-- SQLite用のスキーマ定義

-- 音楽ファイルテーブル
-- 既存のExcel「Albums」「Not in Albums」シートを統合
CREATE TABLE IF NOT EXISTS audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg TEXT,                           -- メッセージ（エラー表示など）
    sync INTEGER DEFAULT 0,             -- 同期フラグ（0: 未同期, 1: 同期済み）
    title TEXT,                         -- タイトル
    artist TEXT,                        -- アーティスト
    album_artist TEXT,                  -- アルバムアーティスト
    composer TEXT,                      -- 作曲者
    album TEXT,                         -- アルバム
    track_num TEXT,                     -- トラック番号
    length REAL,                        -- 長さ（秒）
    filename TEXT,                      -- ファイル名
    filepath_from TEXT UNIQUE NOT NULL, -- ソースファイルパス（一意キー）
    filepath_to_relative TEXT,          -- 同期先相対パス
    codec TEXT,                         -- コーデック（mp3, mp4など）
    update_date TEXT,                   -- 更新日時（ISO 8601形式）
    added_date TEXT                     -- 追加日時（ISO 8601形式）
);

-- ファイルパスにインデックスを作成（検索高速化）
CREATE INDEX IF NOT EXISTS idx_audio_files_filepath ON audio_files(filepath_from);
CREATE INDEX IF NOT EXISTS idx_audio_files_sync ON audio_files(sync);
CREATE INDEX IF NOT EXISTS idx_audio_files_album ON audio_files(album);

-- 設定テーブル
-- 既存のExcel「設定」シートを格納
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,               -- 設定キー
    value TEXT                          -- 設定値
);

-- 設定の初期値を挿入
INSERT OR IGNORE INTO settings (key, value) VALUES 
    ('sync_dir_from', ''),              -- 対象ディレクトリ（カンマ区切りで複数）
    ('exclude_dir', ''),                -- 除外ディレクトリ
    ('include_ext', 'mp3,m4a,mp4'),     -- 対象拡張子
    ('sync_dir_to', '');                -- 同期先ディレクトリ

-- プレイリストテーブル
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,          -- プレイリスト名
    created_date TEXT,                  -- 作成日時
    updated_date TEXT                   -- 更新日時
);

-- プレイリストアイテムテーブル
-- プレイリストと音楽ファイルの多対多リレーション
CREATE TABLE IF NOT EXISTS playlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,       -- プレイリストID
    audio_file_id INTEGER NOT NULL,     -- 音楽ファイルID
    position INTEGER DEFAULT 0,         -- プレイリスト内の順序
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (audio_file_id) REFERENCES audio_files(id) ON DELETE CASCADE,
    UNIQUE(playlist_id, audio_file_id)  -- 同一プレイリスト内で重複を防ぐ
);

CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist ON playlist_items(playlist_id);
CREATE INDEX IF NOT EXISTS idx_playlist_items_audio ON playlist_items(audio_file_id);

-- キャッシュテーブルは廃止されました
-- 以前はExcel読み込み高速化のために使用していましたが、
-- SQLite移行により不要となりました。
