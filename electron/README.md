# Syncterra Electron App

SyncterraのElectronデスクトップアプリケーションモジュールです。
ReactフロントエンドとPythonバックエンド(FastAPI)を統合し、ローカルアプリケーションとして動作させます。

## アーキテクチャ概要

- **Frontend**: `../frontend` (Vite + React)
- **Backend**: `../backend` (FastAPI)
- **Communication**: Custom Protocol (`webapi://`) + Unix Domain Socket (UDS)
  - セキュリティ強化のため、TCPポートは使用せず、プロセス間通信のみで完結します。

## 前提条件

- Node.js (v18以上推奨)
- Python 3.11以上
- `uv` (Pythonパッケージマネージャ)

## 開発環境のセットアップと起動

1. **依存関係のインストール**
   ```bash
   cd electron
   npm install
   ```

2. **開発モードで起動**
   ```bash
   npm run dev
   ```
   このコマンドは以下の動作を並行して行います：
   - フロントエンドのViteサーバー起動 (HMR有効)
   - TypeScriptのコンパイル
   - Electronアプリの起動（バックエンドプロセスも自動的に立ち上がります）

## ビルド (プロダクション向け)

Linux向けのAppImageを作成します。

```bash
npm run build
```

生成物は `dist/` ディレクトリに出力されます。

## ディレクトリ構成

- `main.ts`: Electronメインプロセス。ウィンドウ管理、バックエンドプロセスのライフサイクル管理、プロトコルハンドリングを行います。
- `preload.ts`: レンダラープロセスへのAPI公開 (Context Bridge)。
- `tsconfig.json`: TypeScript設定。
- `package.json`: Electronアプリとしての依存関係とスクリプト定義。
