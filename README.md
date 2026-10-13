# QY-onlyno999 · 动作迁移 Agent

**H3 + Viggle 免提示词动作迁移**：把动作源视频里的人物动作，迁移到目标人物图上，经 RunningHub 云端 ComfyUI 工作流一次出片。

输入一张**目标人物图** + 一段**动作源视频**，输出目标人物做出同样动作的新视频。不用写提示词。

## 第二条线：双人极速版人物替换（2026-10-13 新增）

**MiniMax H3 人物替换·双人极速版**（RunningHub 工作流 `2109881744584429569`）：人物三视图卡 + 源视频 + Ref2VA 六段式提示词，**直接替换**源视频里的人（脸/身材照卡锁定，动作/场景/运镜绑定原片）；同一接口还支持**纯文字原创**（不喂视频、帧数定时长）与**锚帧续段**（切点帧作锚续生拼接）。换人生产走这条线，动作迁移线保留给免提示词场景。规范见 `skills/dual-person-swap/SKILL.md`，派发器 `scripts/dual_swap_dispatch.py`（含云端 OpenAPI v2 接口全注释）。

上游思路：吃猪侠233 / CZX233《H3+Viggle 免提示词动作迁移》（虚空折叠流系列第 5 篇）。

## 目录结构

```
QY-onlyno999/
├── README.md                      # 本文档
├── skills/
│   ├── motion-transfer/
│   │   └── SKILL.md               # 动作迁移 agent 规范：流程、节点映射、铁律（v1.3.1）
│   └── dual-person-swap/
│       └── SKILL.md               # 双人极速版人物替换规范：云端接口、词法三锁、锚帧续段、音频口径（v1.0.0）
└── scripts/
    ├── mt_dispatch.py             # 动作迁移 RunningHub 派发器（探针/派发/轮询/下载一体）
    ├── mt_firstframe.sh           # 抽动作段首帧
    └── dual_swap_dispatch.py      # 双人极速版派发器（换人/纯文字原创/锚帧续段三模式）
```

## 云端工作流

- Workflow ID：`2105133693995151361`（RunningHub **国内版**，`.cn` API）
- 节点映射（2026-10-01 免费探针实测，0 花费）：

| Node | field | 节点类型 | 输入 |
|------|-------|----------|------|
| 3 | `video` | VHS_LoadVideo | 动作源视频 mp4（5 秒一段，不超过 10 秒） |
| 5 | `image` | LoadImage | **首帧合成图**（不是原目标人物图，见流程第 3 步） |
| 73 | `value` | PrimitiveFloat | 数值参数，按输出秒数给（5 秒段就给 5） |

- **不许碰 Node 26**（JWImageResizeToMegapixels，内部连线，覆盖会断图）
- 计费：Standard 机型 0.2 RH币/秒，按实际运行时长结算；results 链接 24h 有效，成功后立即下载

> 注意：帖子 ID `2105145112568598530` 是国际版**文章** ID，不是可运行 ID；AI 应用 `2105294090282762242` 未开 API 权限（901），走不了 API。认准上面的 workflow ID。

## 标准流程（8 步）

1. **切段**：5 秒一段，硬上限 10 秒；超限先剪高潮段。
   `ffmpeg -y -ss <起始秒> -i <源视频> -t 5 -c copy seg.mp4`
2. **选帧**：一个视频只选一次——抽几帧，直接选**有人像、人物最清晰、效果最好的那一张**作为全片海报；不拼九宫格。
3. **1:1 P 首帧**：图编辑三图输入——视频关键帧（定构图：人物位置/大小/姿势/手持物照抄）＋ 主演照片（人物 1:1 植入）＋ 背景图（**整张换掉**，不许和原视频背景一样）。海报必须给用户亲眼确认，确认后才派发。
4. **免费探针**：`python3 scripts/mt_dispatch.py --probe`，回 `ONLINE (803)` 才继续。
5. **派发**：`python3 scripts/mt_dispatch.py --image <海报png> --video <seg.mp4> --value 5 --out <成片>.mp4`
   多段续接：第 2 段起，参考图直接用上一段成片的最后一帧（已是目标人物＋新背景，无需再 P），衔接无闪烁：
   `ffmpeg -y -v error -sseof -0.1 -i <segN.mp4> -frames:v 1 tail.png`
6. **质检**：抽帧查人物一致性、动作跟随、穿帮。
7. **组装**：多段 concat 拼接后，**提取原视频的音频**整轨铺回（以原视频音频为准，不用模型出的音频）：
   `ffmpeg -y -f concat -safe 0 -i list.txt -i <原视频> -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -shortest 成片.mp4`
8. **交付**：24h 内落盘（results 链接过期作废）。

完整规范见 `skills/motion-transfer/SKILL.md`，执行时严格按它走，一步不许省。

## 快速开始

```bash
export RUNNINGHUB_API_KEY=<你的 RunningHub API Key>

# 1. 免费探针（0 花费，验证 Key + 工作流在线）
python3 scripts/mt_dispatch.py --probe

# 2. 派发（海报已 P 好并经用户确认）
python3 scripts/mt_dispatch.py \
  --image poster.png \
  --video seg_0-5.mp4 \
  --value 5 \
  --out out_seg1.mp4
# 脚本自动上传素材、轮询（20s 一次，最长 40 分钟）、下载成片并打印 taskId / 花费
```

## 实测数据（2026-10-01，国内版 Standard）

| 任务 | 输入 | 时长 | 花费 |
|------|------|------|------|
| 5 秒段 #1 | 海报 + 0–5s 动作段 | 243s | 49 币 |
| 5 秒段 #2 | 第 9 秒关键帧海报 + 5–10s 动作段 | 234s | 47 币 |
| 5 秒段 #2b | 第 1 段尾帧 + 5–10s 动作段 | 234s | 47 币 |

- 输出约 672×1184，H.264/AAC。
- 10 秒误派发单：云端任务**没有取消接口**，一旦派发就会跑完扣费——海报必须用户亲眼点头才派发。

## 教训

- 探针扫字段用"合法字段名 + 非法值"会建 junk 任务（校验失败 0 扣费），扫完要确认。
- 多段拼接：第 2 段若用独立海报（不同姿态），衔接处会闪烁；改用上一段尾帧做参考图后干净。
- 成片音频一律用原视频的，模型出的音频不要。
