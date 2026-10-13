#!/usr/bin/env python3
"""Dual-person-swap dispatch: MiniMax H3 人物替换·双人极速版
Workflow 2109881744584429569 (RunningHub .cn, 实派定版 2026-10-13).

云端接口 (OpenAPI v2, 全部实测):
  上传: POST /openapi/v2/media/upload/binary   (multipart, 返回内容寻址文件名 openapi/<sha>.<ext>)
  建单: POST /openapi/v2/run/workflow/<WF_ID>  (body: {"nodeInfoList":[...], "instanceType":"default"})
  轮询: POST /openapi/v2/query                 (body: {"taskId": ...}; 响应可能是扁平结构,
        必须 q.get("data") or q 兜底读取 status/results)

Node map (派发只动这几个, 其余一律不碰):
  137 "image"  <- 人物卡 (三视图白底卡) 或锚帧图 (续段时挂上一段切点帧)
  165 "video"  <- 源视频 (换人模式必填; 纯文字原创模式不挂)
  136 "prompt" <- Ref2VA 六段式提示词, 直填说了算 (压过画布 #218 连线词)
  136 "width"/"height" <- 直填尺寸 (压过 171 连线), 竖屏 768x1344
  136 "length" <- 帧数, 无视频原创/续段时直填 (帧数走 17k+5 网格:
                  124≈5.17s, 192≈8s, 243≈10.13s, 311≈12.96s, 328≈13.67s, 481≈20.04s @24fps)
绝不碰: 219 (第二人物图口, 留画布预置)、171.aspect_ratio (枚举键名不明, 直填会 KeyError)。

特性 (实测):
  - 时长: 喂视频时由流内按源视频自动算帧; 不喂视频时由 136.length 决定。
  - 音轨: 产物音轨 = 源视频原音轨透传 (源片带音乐/人声会原样带过来, 交付前必测音频门)。
  - 极速版采样 steps=3 + Sage Attention, 一条 8~11 秒片约 150~500 秒出片。
  - 失败处置: FAILED/OOM 直接原样重派, 不用请示; query 报 1004 多为用户本人在后台掐单, 不是平台故障。

Auth: Muse 环境走 Secure Vault surrogate; 其他环境 export RUNNINGHUB_API_KEY。
用法:
  换人:   python3 dual_swap_dispatch.py --card 卡.png --video 源.mp4 --prompt 词.txt --outdir out/
  原创:   python3 dual_swap_dispatch.py --card 卡.png --prompt 词.txt --length 328 --outdir out/
  锚帧续段: --card 上一段切点帧.jpg --prompt 续段词.txt --length 311 --outdir out/
"""
import sys
import os
import json
import time
import argparse
import urllib.request

BASE = "https://www.runninghub.cn"
WF = "2109881744584429569"


def _auth(req):
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import add_surrogate_to_request

        add_surrogate_to_request(req, "custom.runninghub", allowed_hosts=["www.runninghub.cn"])
    except Exception:
        key = os.environ.get("RUNNINGHUB_API_KEY", "")
        if not key:
            print("缺少鉴权: 请 export RUNNINGHUB_API_KEY 或在 Muse 环境运行")
            sys.exit(1)
        req.add_header("Authorization", "Bearer " + key)


ap = argparse.ArgumentParser(description="双人极速版人物替换派发")
ap.add_argument("--card", required=True, help="人物卡或锚帧图 -> node 137.image")
ap.add_argument("--video", default=None, help="源视频 -> node 165.video (原创/续段模式不传)")
ap.add_argument("--prompt", required=True, help="提示词文件 (Ref2VA 六段式)")
ap.add_argument("--width", type=int, default=768)
ap.add_argument("--height", type=int, default=1344)
ap.add_argument("--length", type=int, default=None, help="帧数 (无视频或续段时必填, 17k+5 网格)")
ap.add_argument("--instance-type", default="default", choices=["default", "plus", "ultra"])
ap.add_argument("--outdir", required=True)
args = ap.parse_args()

if not args.video and not args.length:
    ap.error("不喂视频时必须给 --length (帧数)")


def post_json(path, payload, timeout=60):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "dual-swap-dispatch/1.0"},
        method="POST",
    )
    _auth(req)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def upload(path):
    boundary = "----MUSEBOUNDARY1234"
    data = open(path, "rb").read()
    body = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="file"; filename="' + os.path.basename(path) + '"\r\n'
         "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
        + data
        + ("\r\n--" + boundary + "--\r\n").encode("utf-8")
    )
    req = urllib.request.Request(
        BASE + "/openapi/v2/media/upload/binary",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                 "User-Agent": "dual-swap-dispatch/1.0"},
        method="POST",
    )
    _auth(req)
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read().decode("utf-8"))
    d = resp.get("data") or resp
    name = d.get("fileName") or d.get("name") or d.get("file_name")
    print("uploaded:", path, "->", name)
    return name


def main():
    os.makedirs(args.outdir, exist_ok=True)
    card = upload(args.card)
    nodes = [{"nodeId": "137", "fieldName": "image", "fieldValue": card}]
    if args.video:
        vid = upload(args.video)
        nodes.append({"nodeId": "165", "fieldName": "video", "fieldValue": vid})
    prompt = open(args.prompt, encoding="utf-8").read()
    nodes.append({"nodeId": "136", "fieldName": "prompt", "fieldValue": prompt})
    nodes.append({"nodeId": "136", "fieldName": "width", "fieldValue": args.width})
    nodes.append({"nodeId": "136", "fieldName": "height", "fieldValue": args.height})
    if args.length:
        nodes.append({"nodeId": "136", "fieldName": "length", "fieldValue": args.length})

    resp = post_json("/openapi/v2/run/workflow/" + WF,
                     {"nodeInfoList": nodes, "instanceType": args.instance_type})
    d = resp.get("data") or resp
    tid = d.get("taskId") or d.get("task_id") or d.get("id")
    print("taskId:", tid)
    t0 = time.time()
    while True:
        time.sleep(10)
        try:
            q = post_json("/openapi/v2/query", {"taskId": tid}, timeout=30)
        except Exception as e:
            print("query err (retry):", e)
            continue
        qd = q.get("data") or q
        st = qd.get("status") or qd.get("state")
        print("[%ds] %s" % (int(time.time() - t0), st))
        if st in ("SUCCESS", "SUCCEEDED", "COMPLETED", "FINISHED"):
            results = qd.get("results") or []
            print("RESULTS_COUNT:", len(results))
            for i, r in enumerate(results):
                url = r.get("url") or r.get("fileUrl") or r.get("downloadUrl")
                if not url:
                    continue
                out = os.path.join(args.outdir, "result_%d.mp4" % i)
                urllib.request.urlretrieve(url, out)
                # 下载易截断: 校验能 ffprobe 打开, 坏了按链接重拉
                print("saved:", out, os.path.getsize(out) // 1024, "KB")
            print("done.")
            return
        if st in ("FAILED", "FAILURE", "ERROR", "CANCELLED"):
            print("FAILED:", json.dumps(qd)[:600])
            sys.exit(2)
        if time.time() - t0 > 3600:
            print("TIMEOUT")
            sys.exit(3)


if __name__ == "__main__":
    main()
