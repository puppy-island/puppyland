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

```bash
python3 -m http.server 4321 --directory prototype
```

打开 <http://localhost:4321>，手机尺寸窗口效果最佳。详见 [prototype/README.md](prototype/README.md)。

## 不在仓库里的东西

`狗狗生成/`（25 张三视图 PNG，46MB）和 `狗狗sample选择.pdf`（51MB）体积太大没有入库，
原型用到的 4 张姿态图已经抠好放在 [`prototype/assets/`](prototype/assets/)。
