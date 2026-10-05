#!/usr/bin/env bash
# Throwaway venv with a pinned LiteLLM. The wheel's sha256 is checked against PyPI's own
# metadata before install (LiteLLM 1.82.7/1.82.8 were malicious in March 2026), and the
# known indicator file is searched for afterwards.
set -euo pipefail
VER=1.103.0
python -m venv .venv
PY=.venv/Scripts/python
$PY -m pip install -q --upgrade pip
mkdir -p .venv/wheelhouse
$PY -m pip download -q "litellm==$VER" --no-deps -d .venv/wheelhouse
WHEEL=$(ls .venv/wheelhouse/litellm-$VER-*win_amd64.whl)
python - "$WHEEL" "$VER" <<'PYEOF'
import hashlib, json, sys, urllib.request
whl, ver = sys.argv[1], sys.argv[2]
want = {f["filename"]: f["digests"]["sha256"] for f in json.load(urllib.request.urlopen(f"https://pypi.org/pypi/litellm/{ver}/json"))["urls"]}
name = whl.replace("\\", "/").rsplit("/", 1)[-1]
got = hashlib.sha256(open(whl, "rb").read()).hexdigest()
assert want.get(name) == got, f"DIGEST MISMATCH for {name}: pypi={want.get(name)} local={got}"
print("wheel digest matches PyPI:", name, got[:16] + "…")
PYEOF
$PY -m pip install -q --no-deps "$WHEEL"
$PY -m pip install -q "litellm[proxy]==$VER"
$PY -m pip freeze > requirements.lock.txt
if find .venv/Lib/site-packages -name 'litellm_init.pth' | grep -q .; then echo "!! litellm_init.pth FOUND"; exit 1; else echo "no litellm_init.pth (known IoC) in site-packages"; fi
.venv/Scripts/litellm.exe --version 2>&1 | tail -1
