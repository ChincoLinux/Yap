#!/usr/bin/env bash
# PR preflight for Yap: run tests + smoke test yap.py
# Adapted from os-santiago/homedir/scripts/ci/pr_preflight.sh
set -euo pipefail

echo "=== Yap PR Preflight ==="
echo ""

# 1. Unit tests (49+ tests)
echo "--- Unit tests (pytest) ---"
python3 -m pytest tests/ -v --tb=short 2>&1
TESTS_EXIT=$?
if [ $TESTS_EXIT -ne 0 ]; then
    echo "FAIL: unit tests failed (exit $TESTS_EXIT)"
    exit 1
fi
echo "PASS: unit tests"
echo ""

# 2. Smoke test: yap.py loads without syntax errors
echo "--- Smoke test (yap.py import) ---"
python3 -c "import ast; ast.parse(open('yap.py').read()); print('PASS: yap.py parses cleanly')"
echo ""

# 3. Security static checks (HD-YAP-SEC-001)
echo "--- Security static checks (HD-YAP-SEC-001) ---"
FAIL=0
for pattern in "shell=True" "eval(" "os.system(" "import socket" "import ctypes" "import pickle" "import base64"; do
    if grep -n "$pattern" yap.py 2>/dev/null | grep -v "^.*#" | grep -q .; then
        echo "FAIL: found '$pattern' in yap.py"
        grep -n "$pattern" yap.py | grep -v "^.*#" || true
        FAIL=1
    fi
done
if [ $FAIL -ne 0 ]; then
    echo "FAIL: security checks failed"
    exit 1
fi
echo "PASS: no prohibited patterns in yap.py"
echo ""

# 4. Conventional Commits check (HD-YAP-BRANCH-001)
echo "--- Branch name check (HD-YAP-BRANCH-001) ---"
BRANCH="${GITHUB_HEAD_REF:-$(git branch --show-current 2>/dev/null || echo unknown)}"
if echo "$BRANCH" | grep -qE '^(feat|fix|refactor|docs|chore|test|ci)/.*'; then
    echo "PASS: branch '$BRANCH' follows Conventional Commits"
elif [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "SKIP: on trunk branch '$BRANCH'"
else
    echo "WARN: branch '$BRANCH' does not follow Conventional Commits (advisory, not blocking)"
fi
echo ""

echo "=== All preflight checks passed ==="
