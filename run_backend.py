#!/usr/bin/env python3
"""
PyInstaller用エントリポイント
相対インポートの問題を回避するため、backendをパッケージとしてインポート
"""
import sys
import os

# PyInstallerでパッケージ化された場合のパス設定
if getattr(sys, 'frozen', False):
    # 実行ファイルのディレクトリをパスに追加
    base_path = sys._MEIPASS
    sys.path.insert(0, base_path)

import argparse
import uvicorn

# バックエンドアプリケーションのインポート
from backend.main import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="TCP Port binding")
    parser.add_argument("--uds", type=str, help="Unix Domain Socket path")
    args = parser.parse_args()
    
    if args.uds:
        uvicorn.run(app, uds=args.uds)
    elif args.port:
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    else:
        uvicorn.run(app, host="127.0.0.1", port=8000)
