# Syncterra Integration Test Cases

作成された統合テスト（`tests/integration/`）に基づくテストケース仕様書です。
これらのテストは、実際のファイルスキャン処理および外部コマンド（ADB/Rsync/FTP）の生成ロジックを結合レベルで自動検証します。

## 1. Scanner Functionality
**Test File**: `tests/integration/test_scanner_integration.py`
**Scope**: ファイルシステム操作、メタデータ抽出、DB更新

| ID | Test Case Name | Pre-conditions (Settings) | Execution Steps | Expected Result |
|----|----------------|---------------------------|-----------------|-----------------|
| SCN-001 | 新規ファイルスキャン (New Files) | `scan_paths`: [TempDir]<br>`target_exts`: "mp3" | コピーした音楽ファイルを配置してスキャンを実行 | ・DBに正しくTrackが追加されること<br>・ファイルパス、相対パスが正しいこと<br>・対象外ファイル（txtなど）が含まれないこと |
| SCN-002 | ファイル更新検知 (Update Files) | 同上 | ファイルの `mtime` を更新して再スキャンを実行 | ・DB上のTrack情報は維持されること<br>・エラーなく再スキャンが完了すること |
| SCN-003 | ファイル削除検知 (Missing Files) | 同上 | ファイルを削除して再スキャンを実行 | ・DB上の該当Trackの `msg` カラムが "Missing" に更新されること |
| SCN-004 | ディレクトリ除外 (Excludes) | `exclude_dirs`: "Excluded" | 除外対象フォルダにファイルを配置してスキャンを実行 | ・除外フォルダ内のファイルがDBに追加されないこと |
| SCN-005 | 拡張子フィルタ (Extensions) | `target_exts`: "wav" (存在しない拡張子) | mp3ファイルが存在する状態でスキャンを実行 | ・DBにファイルが追加されないこと（0件であること） |

## 2. Sync Functionality
**Test File**: `tests/integration/test_syncer_integration.py`
**Scope**: 同期ロジック、外部コマンド生成検証 (Mock使用)

| ID | Test Case Name | Pre-conditions (Settings) | Execution Steps | Expected Result |
|----|----------------|---------------------------|-----------------|-----------------|
| SYN-001 | ADB Sync Mode | `sync_mode`: "adb"<br>`sync_dest`: "/sdcard/Music" | ・同期ON/OFFのトラックを用意<br>・Syncを実行 | Command must be **exact**: `['adb', 'push', '/local/song1.mp3', '/sdcard/Music/Artist/Album/song1.mp3']`<br>パスのエスケープ処理も厳密に確認 |
| SYN-002-A | Rsync Remote (User+Host) | `sync_mode`: "rsync"<br>`rsync_user`: "u"<br>`rsync_host`: "h" | ・Syncを実行 | Command ends with: `['-e', 'ssh -p 22', 'u@h:/remote/music']` |
| SYN-002-B | Rsync Remote (Host only) | `sync_mode`: "rsync"<br>`rsync_user`: ""<br>`rsync_host`: "h" | ・Syncを実行 | Command ends with: `['-e', 'ssh -p 22', 'h:/remote/music']` |
| SYN-002-C | Rsync Local (No Host) | `sync_mode`: "rsync"<br>`rsync_host`: "" | ・Syncを実行 | Command ends with: `['/local/backup']` (No SSH flags) |
| SYN-002-D | Rsync Multiple Sources | `scan_paths`: ["/src1", "/src2"] | ・Syncを実行 | Command contains both `/src1` and `/src2` as source arguments |
| SYN-003 | FTP Sync Mode | `sync_mode`: "ftp"<br>`ftp_host`: "localhost" | ・同期ONのトラックを用意<br>・Syncを実行 | FTP Command must be **exact**: `STOR song1.mp3` sent via `storbinary` |

## 3. API Functionality
**Test File**: `tests/integration/test_api_integration.py`
**Scope**: FastAPIエンドポイント、データ永続化

| ID | Test Case Name | Pre-conditions | Execution Steps | Expected Result |
|----|----------------|----------------|-----------------|-----------------|
| API-001 | 設定の保存と参照 (Settings CRUD) | なし | 1. PUT /api/settings で値を保存<br>2. GET /api/settings で確認<br>3. 値を更新して再度確認 | ・保存した設定値がGETで取得できること<br>・更新後に新しい値が取得できること<br>・DBに永続化されていること |
| API-002 | スキャン実行トリガー (Trigger Scan) | なし | POST /api/scan を実行 | ・HTTP 200/202 が返却されること<br>・status: "accepted" であること |
| API-003 | 同期実行トリガー (Trigger Sync) | なし | POST /api/sync を実行 | ・HTTP 200/202 が返却されること<br>・status: "accepted" であること |

## 4. Scanner Progress & Logging
**Test File**: `tests/test_scanner_progress.py`
**Scope**: スキャン進捗通知、ログコールバック機能

| ID | Test Case Name | Pre-conditions | Execution Steps | Expected Result |
|----|----------------|----------------|-----------------|-----------------|
| SCN-PRG-001 | 進捗・ログコールバック (Progress & Log Callbacks) | ・モックファイルシステム (20ファイル)<br>・空のDB | 1. `run_scan` を `progress_callback` と `log_callback` 付きで実行<br>2. コールバック呼び出しを検証 | ・`progress_callback` が20回以上呼ばれること<br>・最終的に100%で完了すること<br>・`log_callback` が22回呼ばれること (開始 + 20ファイル + 完了)<br>・各ファイル追加ログが出力されること |

## Automation Info
自動テストは以下のコマンドで実行可能です。

```bash
# 統合テスト
PYTHONPATH=. rye run pytest tests/integration -v

# 全テスト
rye run python -m pytest tests/ -v
```
