#!/bin/bash
set -e

SHARED_SSH_DIR="/shared_ssh"
SSH_DIR="/root/.ssh"

# /root/.ssh ディレクトリの準備
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

# 共有ボリュームがマウントされている場合 (テスト環境) はエフェメラル鍵を管理する
if [ -d "$SHARED_SSH_DIR" ]; then
    echo "Shared SSH directory found. Managing ephemeral keys..."
    
    # 共有ボリューム内に鍵が存在しない場合は生成する
    if [ ! -f "$SHARED_SSH_DIR/id_rsa" ]; then
        echo "Generating new SSH key pair in shared volume..."
        ssh-keygen -t rsa -b 4096 -f "$SHARED_SSH_DIR/id_rsa" -N "" -q
        cp "$SHARED_SSH_DIR/id_rsa.pub" "$SHARED_SSH_DIR/authorized_keys"
    fi

    # 共有ボリュームから最新の鍵をコンテナ内にコピーして適切なパーミッションを設定
    # (コンテナ内の .ssh/id_rsa として配置することでデフォルト設定で動作するようにする)
    cp "$SHARED_SSH_DIR/id_rsa" "$SSH_DIR/id_rsa"
    cp "$SHARED_SSH_DIR/id_rsa.pub" "$SSH_DIR/id_rsa.pub"
    chmod 600 "$SSH_DIR/id_rsa"
    chmod 644 "$SSH_DIR/id_rsa.pub"
else
    echo "No shared SSH directory. Skipping ephemeral key generation."
fi

# アプリケーションの起動
exec "$@"
