#!/bin/sh
# Linux の開発環境。リポジトリルートから実行する。
set -eu
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
