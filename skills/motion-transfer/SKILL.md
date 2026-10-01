---
name: motion-transfer
description: H3+Viggle 免提示词动作迁移 agent——把动作源视频里的人物动作迁移到目标人物图上，经 RunningHub 云端 ComfyUI 工作流一次出片。输入：一张目标人物图 + 一段动作源视频。
version: 1.3.0
---

# 动作迁移 Agent（H3+Viggle）

把**动作源视频**中的人物动作，迁移到**目标人物图**上，生成新视频。免提示词。
上游：吃猪侠233 / CZX233《H3+Viggle免提示词动作迁移》（虚空折叠流系列第5篇）。

## 云端工作流

- Workflow ID：`2105133693995151361`（RunningHub 国内版，`.cn` API）
- 注意：帖子 ID `2105145112568598530` 是国际版**文章** ID，不是可运行 ID；AI 应用 `2105294090282762242` 未开 API 权限（901），走不了 API。认准上面这个 workflow ID。
- 节点映射（2026-10-01 免费探针实测，0 花费）：
- Node 3 `video`（VHS_LoadVideo）← 动作源视频 mp4（一段 5 秒，不超过 10 秒）
- Node 5 `image`（LoadImage）← **首帧合成图**（见下，不是原目标人物图）
- Node 73 `value`（PrimitiveFloat，默认 10）← 数值参数
- **不许碰 Node 26**（JWImageResizeToMegapixels，内部连线，覆盖会断图）
- 计费：Standard 机型 0.2 RH币/秒，按实际运行时长结算；results 链接 24h 有效，成功后立即下载。

## 标准流程（全自动，用户 2026-10-01 定）

用户发**主演照片** + **动作视频**，agent 自动走完以下全程，中途不请示：

1. **切段**：5 秒一段，硬上限 10 秒；超限剪高潮段。
   `ffmpeg -y -ss <起始秒> -i <源视频> -t 5 -c copy <seg.mp4>`
2. **选帧**（用户 2026-10-01 定）：不许无脑拿第 0 帧——**一个视频只选一次**：抽几帧，直接选**有人像、人物最清晰、效果最好的那一张**作为全片海报；所有 5 秒段共用这张海报。不拼九宫格，不搞仪式。
3. **1:1 P首帧**（按 H3 做图流程）：`media.generate_image` 图编辑，三图输入——
   - 视频首帧（定构图：人物位置/大小/姿势/手持物严格照抄）、
   - 主演照片（人物 1:1 植入首帧人物位置，身形比例/朝向/光影对齐）、
   - 背景图（整张换掉，不许留原视频背景或主演照片背景）。
   背景默认用 `~/workspace/jige/swap/media-generation-jige-room-bg-0-5087ef1d-aa42-4bce-a5e0-e837abce03d0.webp`（新房间）；用户另给背景则用指定的。
   唯一硬要求（用户 2026-10-01）：换上的背景**不许和原视频首帧的背景一样**，其他随意。
   若 integrity_check_failed：停手，不换参数重试，转用户自 P。
   自检：构图与首帧 1:1、人物无多出手脚、背景无穿帮。
4. **免费探针**：`python3 scripts/mt_dispatch.py --probe`，回 `ONLINE (803)` 才继续。
5. **派发**：`python3 scripts/mt_dispatch.py --image <P好的首帧png> --video <seg.mp4> --value <秒数> --out <命名>.mp4`（value 按秒数给：5 秒段就 --value 5）。
   多段续接（2026-10-01 实测）：第 2 段起，参考图直接用上一段成片的最后一帧（已是目标人物＋新背景，无需再 P），衔接无闪烁：
   `ffmpeg -y -v error -sseof -0.1 -i <segN.mp4> -frames:v 1 tail.png`
6. **质检**：抽帧查人物一致性、动作跟随、穿帮；过 `finalize_delivery.py` 门禁。
7. **组装**（用户 2026-10-01 定）：多段时先 concat 拼视频，再**提取原视频的音频**整轨铺回（以原视频音频为准，不用模型出的音频）：
   `ffmpeg -y -f concat -safe 0 -i <list.txt> -i <原视频> -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -shortest <成片.mp4>`
   单段也一样：剥掉模型音频，换上原视频对应时间段的音频。
8. **交付**：`~/workspace/motion_transfer/`，24h 内落盘。

## 参考数（用户随手跑的，不必当铁律）

- 10 秒片约跑 9 分钟；value 默认 10，大概就是按秒数来的。

## 待看效果

- 人物稳不稳、动作跟没跟上，看片说话。
