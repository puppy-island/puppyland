# PuppyIsland Docker 部署指南

## 快速启动

```bash
docker-compose up -d
```

部署完成后：
- **前端**: http://localhost:4321
- **后端 API**: http://localhost:8001/api/v1

## 手动构建

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 配置

环境变量从 `.env` 文件读取，包括：
- `model` - LLM 模型名称
- `base_url` - API 地址
- `api_key` - API 密钥
- `ARK_API_KEY` / `ARK_BASE_URL` - 图像生成配置
- `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` / `ASR_APP_ID` - 腾讯云 ASR 配置

## 架构

```
┌─────────────────┐     ┌─────────────────┐
│  Frontend :4321 │────▶│  Backend :8001  │
│  (Static HTML)  │     │  (FastAPI)      │
└─────────────────┘     └─────────────────┘
```

前端默认连接 `http://localhost:8001/api/v1`，可通过环境变量 `PUPPYLAND_API` 自定义。
