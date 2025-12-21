# ベースイメージとして uv がインストールされた Python 環境を使用
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピー
COPY pyproject.toml uv.lock README.md ./

# システム全体に依存関係をインストール
RUN uv sync --frozen --no-cache

# 仮想環境のパスを通す
ENV PATH="/app/.venv/bin:$PATH"

# アプリケーションコードのコピー
# .dockerignore により不要なファイルは除外される
COPY . .

# adbとtzdataをインストール
RUN apt-get update && apt-get install -y adb tzdata && rm -rf /var/lib/apt/lists/*

# タイムゾーンの設定
ENV TZ=Asia/Tokyo

# コンテナ起動時に実行するコマンド
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
