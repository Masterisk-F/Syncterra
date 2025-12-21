#!/bin/bash
set -e

SHARED_SSH_DIR="/shared_ssh"
CONFIG_SSH_DIR="/config/.ssh"

echo "Waiting for authorized_keys from backend..."
# Backendが鍵を生成して配置するまで待機
until [ -f "$SHARED_SSH_DIR/authorized_keys" ]; do
  sleep 1
done

echo "SSH key found. Configuring rsync server..."
mkdir -p "$CONFIG_SSH_DIR"
cp "$SHARED_SSH_DIR/authorized_keys" "$CONFIG_SSH_DIR/authorized_keys"
chmod 600 "$CONFIG_SSH_DIR/authorized_keys"

# 本来の起動プロセス（linuxserver/openssh-serverのinit）を起動
exec /init
