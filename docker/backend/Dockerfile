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

# adb, tzdata, rsync, sshpass をインストール
RUN apt-get update && apt-get install -y adb tzdata rsync sshpass && rm -rf /var/lib/apt/lists/*

# タイムゾーンの設定
ENV TZ=Asia/Tokyo

# SSH クライアントの設定 (ホストキーチェックを無効化)
RUN mkdir -p /root/.ssh && \
    echo "Host *\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config

# 起動スクリプトの配置
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
