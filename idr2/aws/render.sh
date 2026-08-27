#!/usr/bin/env bash
# Render the *.json.tmpl deploy files into idr2/aws/rendered/ using idr2/aws/deploy.env.
# Both deploy.env and rendered/ are git-ignored, so your account/network stay local.
#
#   cp idr2/aws/deploy.env.example idr2/aws/deploy.env   # first time; fill in your values
#   ./idr2/aws/render.sh
#
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f deploy.env ]]; then
  echo "ERROR: idr2/aws/deploy.env not found. Copy deploy.env.example to deploy.env and fill it in." >&2
  exit 1
fi

set -a; . ./deploy.env; set +a

python3 - <<'PY'
import os, glob, json, shutil, pathlib
from string import Template

def unset(v):
    return (not v) or ("REPLACE_ME" in v)

out = pathlib.Path("rendered"); out.mkdir(exist_ok=True)
skipped = []
for tmpl in sorted(glob.glob("*.json.tmpl")):
    text = pathlib.Path(tmpl).read_text()
    t = Template(text)
    # variables this specific template references
    ids = {m.group("named") or m.group("braced")
           for m in Template.pattern.finditer(text)
           if (m.group("named") or m.group("braced"))}
    vals = {k: os.environ.get(k, "") for k in ids}
    missing = sorted(k for k in ids if unset(vals[k]))
    if missing:
        skipped.append((tmpl[:-5], missing))
        print(f"skip     {tmpl[:-5]}  (deploy.env missing: {', '.join(missing)})")
        continue
    rendered = t.substitute(vals)
    json.loads(rendered)  # fail loudly if a substitution broke the JSON
    dest = out / tmpl[:-5]
    dest.write_text(rendered)
    print("rendered", dest)

shutil.copy("iam-ecs-trust-policy.json", out / "iam-ecs-trust-policy.json")
print("copied  rendered/iam-ecs-trust-policy.json")
if skipped:
    print("\nNote: the schedule needs ECS_CLUSTER/SUBNET_A/SUBNET_B/SECURITY_GROUP —")
    print("fill those in deploy.env and re-run to render it.")
print("\nOK -> use  file://idr2/aws/rendered/<name>.json  in the aws CLI commands.")
PY
