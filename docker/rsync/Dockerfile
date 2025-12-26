FROM linuxserver/openssh-server:latest

# rsync をインストール
RUN apk add --no-cache rsync bash

# 起動スクリプトの配置
COPY rsync/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
