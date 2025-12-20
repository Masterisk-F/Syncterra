# AudioSync

AudioSyncは、PC上の音声ファイルをAndroidデバイスと同期し、Excelファイルを用いてプレイリストやメタデータを管理するためのWebアプリケーションです。

## 主な機能 (Features)

- **Excel連携**: `src/audiosync/AudioSyncData.xlsx` で楽曲情報やプレイリストを一元管理。
- **Android同期**: ADB (Android Debug Bridge) または Rsync を用いた高速・セキュアな同期。
- **Web UI**: モダンなブラウザインターフェースで同期状況を確認・操作。
- **自動メタデータ取得**: Mutagenによるタグ解析機能。
- **リアルタイムログ**: WebSocketを通じた同期ログのリアルタイム表示。

## システムアーキテクチャ (System Architecture)

```mermaid
graph TD
    UserNode(("User")) -->|Browser| FE["Frontend (React)"]
    FE -- "HTTP API" --> BE["Backend (FastAPI)"]
    FE -- WebSocket --> BE
    BE <-->|"Read/Write"| DB[("SQLite")]
    BE <-->|"Read/Write"| Excel["Excel (AudioSyncData.xlsx)"]
    BE -->|Read| LocalFS["Local Audio Files"]
    BE -->|"Sync (ADB/Rsync/FTP)"| Remote["Android Device / Remote Server"]
    
    subgraph "Backend System"
        BE
        DB
        Excel
    end
```

本システムは、モダンなWeb技術とPythonの強力なバックエンド処理を組み合わせたアーキテクチャを採用しています。

- **Frontend**: React (Vite) を採用し、高速でインタラクティブなUIを提供。AG Gridによる大量のデータ操作と、WebSocketを通じたリアルタイムな同期ログ表示を実現しています。
- **Backend**: FastAPI を使用し、非同期処理による高パフォーマンスなAPIを提供。
- **Data Management**: 設定やキャッシュはSQLiteに保存し、ユーザーが編集するプレイリストや楽曲管理情報はExcel (`AudioSyncData.xlsx`) で管理することで、手軽な編集とシステム連携を両立しています。
- **Core Engine**: `ADB`, `Rsync`, `FTP` の3つのプロトコルを抽象化した同期エンジン (`AudioSynchronizer`) を実装し、柔軟なデバイス環境に対応可能です。

## 前提条件 (Prerequisites)

- **Runtime**:
    - Python 3.8+
    - Node.js (v18+ 推奨)
    - ADB (Android Debug Bridge) - ADB同期モードを使用する場合
- **Tools**:
    - [Rye](https://rye-up.com/) (Pythonパッケージ管理)
    - npm (Nodeパッケージ管理)

## セットアップ (Installation & Setup)

### Backend

依存関係をインストールします。

```bash
rye sync
```

### Frontend

フロントエンドの依存関係をインストールします。

```bash
cd frontend
npm install
```

## 実行方法 (Usage)

開発サーバーを起動して使用します。

### 1. Backendの起動

```bash
rye run uvicorn backend.main:app --reload
```

### 2. Frontendの起動

別ターミナルで実行してください。

```bash
cd frontend
npm run dev
```

### 3. アプリケーションへのアクセス

ブラウザで `http://localhost:5173` にアクセスしてください。

## 技術スタック (Tech Stack)

- **Backend**: Python, FastAPI, SQLAlchemy (SQLite), aiosqlite, Websockets
- **Frontend**: TypeScript, React, Vite, Mantine UI, AG Grid
- **Others**: Mutagen (Audio Metadata), OpenPyXL (Excel), Adbutils

## ライセンス (License)

本ソフトウェアは **GPL v3 (GNU General Public License v3)** の下で公開されています。
詳細については [LICENSE](./LICENSE) ファイルを参照してください。
`mutagen` (GPL v2+) などのGPLライブラリを使用しているため、本ソフトウェアの派生物を配布する場合はGPL互換ライセンスを採用する必要があります。
