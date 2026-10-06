#!/bin/sh
set -eu
maa_tmp=$(mktemp -d)
trap 'rm -rf "$maa_tmp"' EXIT HUP INT TERM
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/bootstrap.py -o "$maa_tmp/bootstrap.py"
python3 "$maa_tmp/bootstrap.py" "$@"
