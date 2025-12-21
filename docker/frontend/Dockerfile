# Build Stage
FROM node:20-slim AS builder

WORKDIR /app

# 依存関係のインストール
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ソースコードのコピー
COPY frontend/ ./

# ビルド実行
RUN npm run build

# Production Stage
FROM nginx:alpine

# Nginx設定のコピー
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# ビルド成果物のコピー
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
