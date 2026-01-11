# ベースイメージとして uv がインストールされた Python 環境を使用
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 作業ディレクトリの設定
WORKDIR /app

# タイムゾーンの設定
ENV TZ=Asia/Tokyo

# adb, tzdata, rsync, sshpass をインストール
# 依存関係のインストールをソースコードコピーの前に行うことでキャッシュを活用
RUN apt-get update && apt-get install -y adb tzdata rsync sshpass && rm -rf /var/lib/apt/lists/*

# SSH クライアントの設定 (ホストキーチェックを無効化)
# これもアプリケーションコードに依存しないため先に実行
RUN mkdir -p /root/.ssh && \
    echo "Host *\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config

# 依存関係ファイルのコピー
COPY pyproject.toml uv.lock ./

# README.md は pyproject.toml で参照されているため存在する必要があるが、
# 内容の変更でキャッシュを無効化したくないため、ダミーファイルを作成する
RUN touch README.md

# システム全体に依存関係をインストール
RUN uv sync --frozen --no-cache

# 仮想環境のパスを通す
ENV PATH="/app/.venv/bin:$PATH"

# 起動スクリプトの配置
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# アプリケーションコードのコピー
COPY backend ./backend
COPY asyncapi.yaml ./

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
