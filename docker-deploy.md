# PuppyIsland Docker 部署指南

## 快速启动

```bash
docker-compose up -d
```

部署完成后：
- **前端 + 后端 API**: https://localhost:4321（自签证书，浏览器会提示不安全）
- **后端 API 单独访问**: http://localhost:8001/api/v1

> ⚠️ **麦克风权限需要 HTTPS**：浏览器要求安全上下文（HTTPS）才能授权麦克风。首次访问时需要手动信任自签证书（见下方"信任自签证书"步骤）。

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

## 信任自签证书（启用麦克风）

Caddy 使用自签 TLS 证书，首次访问会报 `ERR_SSL_PROTOCOL_ERROR`。需导入根证书：

### 获取根证书

```bash
# 从 Caddy 数据卷中导出根证书
docker cp puppyisland-caddy:/data/caddy/pki/authorities/local/ca.crt ./ca.crt
```

### 导入系统受信任根证书

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./ca.crt
```

**Windows:**
```powershell
# 以管理员身份运行 PowerShell
Import-Certificate -FilePath ./ca.crt -CertStoreLocation Cert:\LocalMachine\Root
```

**Linux (Ubuntu/Debian):**
```bash
sudo cp ./ca.crt /usr/local/share/ca-certificates/puppyisland-ca.crt
sudo update-ca-certificates
```

导入后刷新浏览器，访问 https://localhost:4321 即可正常使用麦克风。

## 配置

环境变量从 `.env` 文件读取，包括：
- `model` - LLM 模型名称
- `base_url` - API 地址
- `api_key` - API 密钥
- `ARK_API_KEY` / `ARK_BASE_URL` - 图像生成配置
- `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` / `ASR_APP_ID` - 腾讯云 ASR 配置

## 架构

```
浏览器 (HTTPS :4321)
       │
       ▼
┌─────────────────┐     ┌─────────────────┐
│  Caddy :4321    │────▶│  Backend :8001  │
│  (TLS 终结)     │     │  (FastAPI)      │
└─────────────────┘     └─────────────────┘
       │
       ▼
┌─────────────────┐
│  Frontend :4321 │
│  (Static HTML)  │
└─────────────────┘
```

前端默认连接同源相对路径 `/api/v1`，经 Caddy 反向代理到后端，无需写死域名/IP。
