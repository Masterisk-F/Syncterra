# AudioSync

PC内の音楽ファイルを管理し、AndroidデバイスやFTPサーバーと同期するためのPythonツールです。
Excelファイルをデータベースとして使用し、音楽ファイルのメタデータを管理します。

## 主な機能

- **音楽ファイルのリスト化**: 指定ディレクトリ内の音楽ファイル（mp3/m4a/mp4）をスキャンし、メタデータ（タイトル、アーティスト、アルバムなど）を自動抽出してExcelに一覧化
- **同期対象の選択**: Excel上で同期したいファイルに「○」を付けて選択
- **デバイスへの同期**:
  - **ADB経由**: Androidデバイスへ USB経由で転送
  - **FTP経由**: FTPサーバーへ転送
  - **rsync経由**: SSH接続したサーバーへ高速転送
- **プレイリスト生成**: Excel上でプレイリストを作成し、m3uファイルとして転送
- **メタデータ自動修復**: 隠しキャッシュシートにより、誤って編集したメタデータを次回実行時に自動修復

## 必要な環境

- Python 3.8以上
- [Rye](https://rye.astral.sh/)（推奨）またはpip

## インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd AudioSync

# Ryeを使用する場合
rye sync

# pipを使用する場合
pip install -r requirements.lock
```

## 使い方

### 1. 設定ファイルの準備

初回実行時に `src/audiosync/AudioSyncData.xlsx` が自動生成されます。
または、`src/audiosync/sample_AudioSyncData.xlsx` をコピーして使用できます。

### 2. 音楽ファイルのリスト化

```bash
# 通常実行（新規ファイルのみ追加）
rye run python src/audiosync/audio_list.py

# 全ファイルのメタデータを更新
rye run python src/audiosync/audio_list.py -all
```

実行後、`AudioSyncData.xlsx` が自動で開きます。

### 3. 設定シートの編集

`AudioSyncData.xlsx` の「設定」シートで以下を設定します：

| 項目 | 説明 | 例 |
|------|------|-----|
| 同期対象ディレクトリ | スキャンする音楽フォルダのパス | `/path/to/music` |
| 除外ディレクトリ | スキャンから除外するフォルダ | - |
| 対象拡張子 | 対象とするファイル形式 | `mp3`, `m4a`, `mp4` |
| 同期先ディレクトリ | 転送先のパス | `/storage/sdcard/music` |

### 4. 同期対象の選択

「Albums」または「Not in Albums」シートで、同期したいファイルの「sync」列に **○** を入力します。

### 5. 同期の実行

#### ADB経由（Androidデバイス）

```bash
# デバイスをUSB接続してから実行
rye run python src/audiosync/audio_sync.py
```

`audio_sync.py` 内で `AdbAudioSynchronizer` または `FtpAudioSynchronizer` を選択してください。

#### rsync経由（SSH）

```bash
rye run python src/audiosync/audio_sync_rsync.py
```

`audio_sync_rsync.py` 内でSSH接続情報を設定してください。

## ファイル構成

```
src/audiosync/
├── audio_list.py              # リスト作成・更新のメインスクリプト
├── audio_sync.py              # 同期実行のメインスクリプト（ADB/FTP）
├── audio_sync_rsync.py        # rsync同期のメインスクリプト
├── audio_sync_data.py         # Excelファイルの読み書き・データ管理
├── audio_synchronizer.py      # 同期ロジックの実装（基底クラス、ADB、FTP）
├── rsync_audio_synchronizer.py # rsync同期ロジックの実装
├── logger.py                  # ログ設定
├── AudioSyncData.xlsx         # 音楽ファイル管理用Excelファイル
└── sample_AudioSyncData.xlsx  # サンプル設定ファイル
```

## Excel自動修復機能

誤ってメタデータ（タイトル、アーティストなど）を編集しても、次回 `audio_list.py` 実行時に自動的に正しい値に戻ります。

- **仕組み**: 隠しシート `_Cache` に正しいメタデータを保持
- **保護対象**: タイトル、アーティスト、アルバム、トラック番号、ファイル名など
- **編集可能**: `sync` 列（同期選択）と `added_date`（追加日時）はユーザー編集を維持
- **並べ替え**: 自由に行や列を並べ替えても問題なし

## 依存ライブラリ

- **mutagen**: 音楽ファイルのメタデータ読み取り
- **openpyxl**: Excelファイルの読み書き
- **adbutils**: Android Debug Bridge（ADB）経由のファイル転送
