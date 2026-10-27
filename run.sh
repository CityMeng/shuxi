#!/usr/bin/env bash
# 数玺原型一键启动 (规范 §15.5 one-command demo)
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/streamlit ]; then
  echo "未找到虚拟环境, 请先按 README 准备 .venv" >&2; exit 1
fi
exec .venv/bin/streamlit run app.py
