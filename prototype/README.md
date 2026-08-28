# 记忆家园 Memory Home — 前端原型

基于 `puppyisland_PRD_v2.1` 与参考图（`第三部分对话的房子.jpg`、`狗狗生成/*`）的可交互前端原型。
纯前端、零依赖、离线可跑，AI / ASR 全部为 Mock，适合三天 Hackathon 演示。

## 跑起来

```bash
python3 -m http.server 4321 --directory prototype
```

打开 <http://localhost:4321>。演示时用手机尺寸窗口最佳（≤520px 宽自动全屏）。

- 键盘 `1`–`5`：跳到 开场 / 场景一 / 场景二 / 场景三 / Companion
- 键盘 `R`：清空 Guest Session 重来
- 控制台 `__mh`：`{ S, goto, reset, addMemory, addPaw }`

## 文件

| 文件 | 内容 |
|---|---|
| `index.html` | 场景骨架、SVG symbol（爪印/播放/发送/相机） |
| `style.css` | 设计 token、场景与物件样式 |
| `app.js` | 状态机、Mock 记忆解释器、Mock ASR、Story Engine |
| `assets/pet-*.webp` | Base 形象 4 张姿态图（从 `小白狗多种姿势.png` 抠图） |
| `build.py` | 打包成单文件 `dist/index.html`（图片转 data URI） |

## 设计基准

取自参考图，不是新造的：

| Token | 值 | 来源 |
|---|---|---|
| `--kraft` | `#E4CEAC` | 牛皮纸底 |
| `--cream` | `#F7E8CD` | 房子填充 |
| `--terracotta` | `#C87C5C` | 信箱、灯罩 |
| `--dusk-blue` | `#9FBBD1` | 窗、饭盆 |
| `--bulb` | `#F2C56E` | 灯光、亮起的爪印 |
| `--ink` | `#4B3A2E` | 柔褐色文字，不用纯黑 |

字体：旁白与宠物对白用 Noto Serif SC，界面文案用 Noto Sans SC。
参考图里没有地平线——整屏一片牛皮纸，物件靠柔和接触阴影落地，全局叠一层 SVG 噪声做纸纹。

## PRD → 代码对照

| PRD | 实现位置 |
|---|---|
| 场景 0：6–10 秒脚步开场，可跳过 | `initIntro()` / `[data-scene="intro"]` |
| 场景一：发光爪印邀请说名字、可选照片、模糊轮廓 | `initS1()`，清晰度由 `--detail` 驱动 blur |
| 场景二：早晨→夜晚、触碰物件触发动作 | `initS2()` / `TOUCH` 表 / `room[data-time]` |
| 场景三：选一枚爪印，留下最不想失去的记忆 | `initS3()`，`priority: 3` |
| 家园生成 | `initWeave()`，房子描边后填色 |
| Companion：固定 Base 家园背景 + 文字聊天 | `initCompanion()` / `.house` |
| 环境 → 动作 → 对白 → 事件推进 | `BEATS` + `playBeat()` |
| 输入框右侧「继续」推进剧情 | `#btnContinue` |
| 语音录音 → Mock ASR → 发送前编辑 → 退化为文字 | `capture()` |
| 脚步是痕迹不是进度条，记忆进来后爪印发光 | `buildTrail()` / `litTrail()` |
| 敏感 Memory 完全排除出 grounding | `SENSITIVE` → `groundingAllowed: false` |
| 情绪保护：温和陪伴 + 提示寻求支持 | `DISTRESS` 分支 |
| 自然纠正不直接覆盖既有 Memory | `respond()` 的纠正分支 → `StoryState.threads` 候选 |
| Guest Session 当前设备永久保存 | `localStorage['memoryhome.guest.v1']`，`scene==='companion'` 时直接续上 |
| 5 种基础姿态 | `POSE`：idle / approach(靠近·开心) / run(奔跑) / down(低落) |

## 接真服务时要换掉的地方

1. `mockASR()` → 真实 ASR（保留"发送前可编辑"这一步）。
2. `interpret()` → Multimodal Memory Interpreter，输出事实 / 推断 / 未知 / 情绪 / 敏感级别。
3. `BEATS` 常量 → Story Engine，输入 `CharacterProfile` + `NarrativeAssets` + `StoryState`。
4. `SENSITIVE` / `DISTRESS` 正则 → 服务端安全规则（当前只是演示用兜底）。
5. 场景一的照片入口目前只读取文件不上传，接生成服务时替换 `inp.addEventListener('change')`。

## 已知取舍

- 形象是 4 张固定 PNG + CSS 动画，不是按用户描述生成的；`--detail` 用 blur 表达"还没定型"。
- Companion 每轮剧情从 10 条模板里挑，`needs` 字段保证只用这个家里真的出现过的安全物件。
- 没有记忆卡、记忆抽屉、可点击探索——按 PRD 属于后续版本。
