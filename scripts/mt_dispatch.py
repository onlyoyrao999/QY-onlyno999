#!/usr/bin/env python3
"""Motion-transfer dispatch: H3+Viggle免提示词动作迁移
Workflow 2105133693995151361 (RunningHub .cn, verified live 2026-10-01).

Node map (all verified via free probe, 0 coins):
  node 3  "video" = VHS_LoadVideo      <- 动作源视频 (mp4, 5秒一段, 不超过10秒)
  node 5  "image" = LoadImage          <- 首帧合成图 (目标人物P进动作首帧+背景整张换掉)
  node 73 "value" = PrimitiveFloat     <- 数值参数, 按秒数给 (5秒段就给5)
Do NOT touch node 26 (JWImageResizeToMegapixels, internal link).

Billing: Standard 0.2 RH币/秒, 按实际运行时长结算. results URL 24h 有效, 成功后立即下载.

Auth: export RUNNINGHUB_API_KEY=<你的RunningHub API Key> (Bearer).
"""
import sys
import os
import json
import time
import argparse
import urllib.request

BASE = "https://www.runninghub.cn"
WF = "2105133693995151361"


def _auth(req):
    """Muse 环境走 Secure Vault surrogate, 其他环境走 RUNNINGHUB_API_KEY."""
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import add_surrogate_to_request
        add_surrogate_to_request(req, "custom.runninghub", allowed_hosts=["www.runninghub.cn"])
    except Exception:
        key = os.environ.get("RUNNINGHUB_API_KEY", "")
        if not key:
            print("缺少鉴权: 请 export RUNNINGHUB_API_KEY=<RunningHub API Key>")
            sys.exit(1)
        req.add_header("Authorization", "Bearer " + key)


ap = argparse.ArgumentParser(description="H3+Viggle 动作迁移派发")
ap.add_argument("--image", required=False, help="首帧合成图 (人物已P进+背景已换)")
ap.add_argument("--video", required=False, help="动作源视频 (一段5秒)")
ap.add_argument("--value", type=float, default=10, help="数值参数, 按秒数给")
ap.add_argument("--instance-type", default="default", choices=["default", "plus", "ultra"])
ap.add_argument("--out", default=None, help="成片保存路径")
ap.add_argument("--taskfile", default="/tmp/mt_taskid.txt")
ap.add_argument("--probe", action="store_true", help="免费探针 (0花费)")
args = ap.parse_args()
if not args.probe and not (args.image and args.video):
    ap.error("--image 与 --video 为必填 (除非 --probe)")


def post_json(path, payload, timeout=30):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "mt-dispatch/1.0"},
        method="POST",
    )
    _auth(req)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_media(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        print("文件不存在: " + path)
        sys.exit(1)
    boundary = "----MUSEBOUNDARY1234"
    with open(p, "rb") as f:
        data = f.read()
    name = os.path.basename(p)
    head = ('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="'
            + name + '"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
    tail = ("\r\n--" + boundary + "--\r\n").encode()
    req = urllib.request.Request(
        BASE + "/openapi/v2/media/upload/binary",
        data=head + data + tail,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                 "User-Agent": "mt-dispatch/1.0"},
        method="POST",
    )
    _auth(req)
    with urllib.request.urlopen(req, timeout=120) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    fn = (r.get("data") or {}).get("fileName")
    if not fn:
        print("UPLOAD FAILED:", json.dumps(r, ensure_ascii=False)[:200])
        sys.exit(1)
    return fn


def resolve_media(v):
    v = os.path.expanduser(v)
    if v.startswith("openapi/"):
        return v
    fn = upload_media(v)
    print("uploaded " + v + " -> " + fn, flush=True)
    return fn


if args.probe:
    r = post_json(
        "/openapi/v2/run/workflow/" + WF,
        {"nodeInfoList": [{"nodeId": "999999", "fieldName": "bogus", "fieldValue": "x"}]},
    )
    if str(r.get("errorCode")) == "803":
        print("PROBE: ONLINE (803), 0 coins")
    else:
        print("PROBE:", json.dumps(r, ensure_ascii=False)[:200])
    sys.exit(0)

img_fn = resolve_media(args.image)
vid_fn = resolve_media(args.video)

node_list = [
    {"nodeId": "5", "fieldName": "image", "fieldValue": img_fn},
    {"nodeId": "3", "fieldName": "video", "fieldValue": vid_fn},
    {"nodeId": "73", "fieldName": "value", "fieldValue": args.value},
]
r = post_json(
    "/openapi/v2/run/workflow/" + WF,
    {"nodeInfoList": node_list, "instanceType": args.instance_type},
)
if r.get("errorCode") not in (None, "", 0, "0"):
    print("DISPATCH FAILED:", json.dumps(r, ensure_ascii=False)[:400])
    sys.exit(1)
tid = r.get("taskId")
if not tid:
    print("NO TASKID:", json.dumps(r, ensure_ascii=False)[:300])
    sys.exit(1)
print("taskId: " + tid, flush=True)
open(os.path.expanduser(args.taskfile), "w").write(tid)

q = None
for i in range(120):
    try:
        q = post_json("/openapi/v2/query", {"taskId": tid}, timeout=20)
    except Exception as e:
        print("[" + str((i + 1) * 20) + "s] net err: " + str(e), flush=True)
        time.sleep(20)
        continue
    st = q.get("status")
    if i % 5 == 0 or st in ("SUCCESS", "FAILED", "CANCELLED"):
        u = q.get("usage") or {}
        print("[" + str((i + 1) * 20) + "s] " + str(st)
              + " costTime=" + str(u.get("taskCostTime"))
              + " coins=" + str(u.get("consumeCoins")), flush=True)
    if st == "SUCCESS":
        break
    if st in ("FAILED", "CANCELLED"):
        print("FAILED:", json.dumps(q.get("failedReason"), ensure_ascii=False)[:500])
        sys.exit(1)
    time.sleep(20)
else:
    print("TIMEOUT waiting 40min")
    sys.exit(1)

results = q.get("results") or []
mp4 = None
for x in results:
    if (x.get("outputType") or "").lower() == "mp4":
        mp4 = x
        break
if mp4 is None and results:
    mp4 = results[0]
if mp4 is None:
    print("NO RESULTS")
    sys.exit(1)
url = mp4["url"]
if args.out:
    out = os.path.expanduser(args.out)
else:
    out = os.path.expanduser("~/motion_transfer/mt_" + tid[-8:] + ".mp4")
d = os.path.dirname(out)
if d:
    os.makedirs(d, exist_ok=True)
urllib.request.urlretrieve(url, out)
print("saved: " + out + " (" + str(os.path.getsize(out) // 1024) + " KB)")
u = q.get("usage") or {}
print("done. taskCostTime=" + str(u.get("taskCostTime")) + "s consumeCoins=" + str(u.get("consumeCoins")))
