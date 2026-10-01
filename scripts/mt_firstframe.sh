#!/bin/bash
# 抽动作段首帧（motion-transfer agent 第3步用）
# 用法：bash mt_firstframe.sh <seg.mp4> <firstframe.png>
set -e
if [ $# -ne 2 ]; then echo "用法：bash mt_firstframe.sh <seg.mp4> <firstframe.png>"; exit 1; fi
ffmpeg -y -v error -i "$1" -vframes 1 -q:v 2 "$2"
echo "首帧已落盘：$2"
