#!/usr/bin/env bash
# Build, verify, commit and push in one step.
#
#   ./publish.sh "what changed"
#
# Runs the build twice — once normally, once under a C/POSIX locale — because a
# CI runner may hand Python an ASCII stdout and that difference has bitten this
# project before. Catching it here is much faster than catching it in Actions.

set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-Update site}"
REPO="$(basename "$(git rev-parse --show-toplevel)")"

echo "→ building tokens"
python3 tokens/build_tokens.py >/dev/null

echo "→ building site (as CI does, base=/$REPO)"
python3 build.py --base="/$REPO" >/dev/null

echo "→ re-checking under a C locale (the CI failure mode)"
env -u LANG -u LC_CTYPE PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 LC_ALL=C \
    python3 tokens/build_tokens.py >/dev/null
env -u LANG -u LC_CTYPE PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 LC_ALL=C \
    python3 build.py --base="/$REPO" >/dev/null

PAGES=$(find dist -name index.html | wc -l | tr -d ' ')
echo "→ $PAGES pages built"

echo "→ rebuilding for local preview (relative URLs)"
python3 build.py >/dev/null

if git diff --quiet && git diff --cached --quiet; then
  echo "nothing to commit — working tree is clean"
  exit 0
fi

git add -A
git commit -m "$MSG"
git push

ORIGIN="$(git remote get-url origin)"
SLUG="$(echo "$ORIGIN" | sed -E 's#.*github\.com[:/]([^/]+)/(.+)$#\1/\2#; s#\.git$##')"
echo
echo "pushed. watch the build:  https://github.com/$SLUG/actions"
echo "site (once green):        https://$(echo "$SLUG" | cut -d/ -f1).github.io/$REPO/about-nid/"
