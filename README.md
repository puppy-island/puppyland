# Memory Home / 记忆家园

宠物记忆 AI 陪伴产品。产品闭环：**看见 TA → 找回记忆 → 继续陪伴**。

## 目录

| 路径 | 内容 |
|---|---|
| [`puppyisland_PRD_v2.1 2.md`](<puppyisland_PRD_v2.1 2.md>) | 产品需求文档 v2.1（完整交互架构整合版） |
| [`prototype/`](prototype/) | 前端可交互原型（纯前端、零依赖、AI/ASR 为 Mock） |
| `宠物记忆AI产品完整交互架构.rtf` | 交互架构原始稿 |
| `77张截图_纯文字转写稿.md` | 参考截图转写 |
| `第三部分对话的房子.jpg` | 视觉参考图：Companion 家园背景 |

## 跑起来

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API 密钥和腾讯云配置
```

**.env 可配置项：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 后端服务端口 | `8001` |
| `HOST` | 后端监听地址（开发用 `0.0.0.0`） | `0.0.0.0` |
| `model` | LLM 模型名称 | `deepseek-v4-flash` |
| `base_url` | LLM API 地址（OpenAI 兼容） | `https://api.openai-next.com/v1` |
| `api_key` | LLM API 密钥 | —（必填） |
| `TENCENT_SECRET_ID` | 腾讯云 SecretId（语音识别用） | — |
| `TENCENT_SECRET_KEY` | 腾讯云 SecretKey | — |
| `ASR_APP_ID` | 腾讯云 AppId | — |

> **LLM 配置**：支持任何 OpenAI-compatible API（DeepSeek、Qwen、通义千问等），填入对应的 `base_url` 和 `api_key` 即可。
>
> **语音识别**：若不配置，语音输入会降级为手动文字输入。

### 2. 启动后端

```bash
python run.py
```

后端启动后运行在 `http://localhost:8001`（端口由 `.env` 中的 `PORT` 控制）。

### 3. 启动前端

```bash
cd prototype
npx http-server -p 3000 -c-1
```

打开 <http://localhost:3000>，手机尺寸窗口效果最佳。

## 不在仓库里的东西

`狗狗生成/`（25 张三视图 PNG，46MB）和 `狗狗sample选择.pdf`（51MB）体积太大没有入库，
原型用到的 4 张姿态图已经抠好放在 [`prototype/assets/`](prototype/assets/)。
