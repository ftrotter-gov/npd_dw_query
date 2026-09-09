#!/usr/bin/env bash
# Render worksheet/aws/*.json.tmpl into worksheet/aws/rendered/ using deploy.env.
# deploy.env and rendered/ are git-ignored, so account/network values stay local.
#
#   cp worksheet/aws/deploy.env.example worksheet/aws/deploy.env   # first time
#   ./worksheet/aws/render.sh
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f deploy.env ]]; then
  echo "ERROR: worksheet/aws/deploy.env not found. Copy deploy.env.example and fill it in." >&2
  exit 1
fi
set -a; . ./deploy.env; set +a

python3 - <<'PY'
import os, glob, pathlib, shutil
from string import Template

def unset(v):
    return (not v) or ("REPLACE_ME" in v)

out = pathlib.Path("rendered"); out.mkdir(exist_ok=True)
for tmpl in sorted(glob.glob("*.json.tmpl")):
    text = pathlib.Path(tmpl).read_text()
    ids = {m.group("named") or m.group("braced")
           for m in Template.pattern.finditer(text)
           if (m.group("named") or m.group("braced"))}
    vals = {k: os.environ.get(k, "") for k in ids}
    missing = sorted(k for k in ids if unset(vals[k]))
    if missing:
        print(f"skip     {tmpl[:-5]}  (deploy.env missing: {', '.join(missing)})")
        continue
    dest = out / tmpl[:-5]
    dest.write_text(Template(text).safe_substitute(vals))
    print("rendered", dest)

shutil.copy("iam-ecs-trust-policy.json", out / "iam-ecs-trust-policy.json")
print("copied  rendered/iam-ecs-trust-policy.json")
print("\nOK -> use  file://worksheet/aws/rendered/<name>.json  in the aws CLI commands.")
PY
