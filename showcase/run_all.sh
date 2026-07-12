#!/usr/bin/env bash
#
# FLUX Cross-Implementation Runner
# =================================
# Compiles and runs cross_impl.flx on all available FLUX VMs,
# then compares the output hash to verify cross-implementation correctness.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
FLX_FILE="${1:-$REPO_ROOT/tests/cross_impl.flx}"

echo "═══════════════════════════════════════════════════════════════"
echo "  FLUX Cross-Implementation Integration Test"
echo "  Source: $FLX_FILE"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── Python VM ────────────────────────────────────────────────────────────────
echo "── Python VM (flux-runtime) ────────────────────────────────────"
if python3 "$SCRIPT_DIR/compile_and_run.py" --print-regs "$FLX_FILE" 2>&1; then
    PY_HASH=$(python3 "$SCRIPT_DIR/compile_and_run.py" "$FLX_FILE" 2>&1 | grep "^Result hash:" | awk '{print $3}')
    echo "Python result hash: $PY_HASH"
else
    echo "⚠ Python VM failed or produced errors"
    PY_HASH="ERROR"
fi
echo ""

# ── Rust VM ──────────────────────────────────────────────────────────────────
echo "── Rust VM (flux-core) ────────────────────────────────────────"
if command -v cargo >/dev/null 2>&1 && [ -d "$REPO_ROOT/../flux-core" ]; then
    echo "Running Rust VM..."
    RUST_OUTPUT=$(cd "$REPO_ROOT/../flux-core" && cargo run -- "$FLX_FILE" 2>&1 || true)
    echo "$RUST_OUTPUT"
    RUST_HASH=$(echo "$RUST_OUTPUT" | grep -oE 'Result hash: [a-f0-9]+' | awk '{print $3}' || echo "N/A")
elif command -v fluxvm >/dev/null 2>&1; then
    echo "Running fluxvm CLI..."
    RUST_OUTPUT=$(fluxvm "$FLX_FILE" 2>&1 || true)
    echo "$RUST_OUTPUT"
    RUST_HASH=$(echo "$RUST_OUTPUT" | grep -oE 'Result hash: [a-f0-9]+' | awk '{print $3}' || echo "N/A")
else
    echo "⚠ Rust VM (flux-core) not available"
    echo "  Install from: https://github.com/SuperInstance/flux-core"
    RUST_HASH="SKIPPED"
fi
echo ""

# ── JavaScript VM ────────────────────────────────────────────────────────────
echo "── JavaScript VM (flux-js) ────────────────────────────────────"
if command -v node >/dev/null 2>&1 && [ -d "$REPO_ROOT/../flux-js" ]; then
    echo "Running JS VM..."
    JS_OUTPUT=$(cd "$REPO_ROOT/../flux-js" && node src/index.js "$FLX_FILE" 2>&1 || true)
    echo "$JS_OUTPUT"
    JS_HASH=$(echo "$JS_OUTPUT" | grep -oE 'Result hash: [a-f0-9]+' | awk '{print $3}' || echo "N/A")
elif command -v npx >/dev/null 2>&1; then
    echo "Trying npx flux-js..."
    JS_OUTPUT=$(npx flux-js "$FLX_FILE" 2>&1 || true)
    echo "$JS_OUTPUT"
    JS_HASH=$(echo "$JS_OUTPUT" | grep -oE 'Result hash: [a-f0-9]+' | awk '{print $3}' || echo "N/A")
else
    echo "⚠ JavaScript VM (flux-js) not available"
    echo "  Install from: https://github.com/SuperInstance/flux-js"
    JS_HASH="SKIPPED"
fi
echo ""

# ── Comparison ───────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  Cross-Implementation Comparison"
echo "═══════════════════════════════════════════════════════════════"
echo ""
printf "  %-12s %s\n" "Python:" "$PY_HASH"
printf "  %-12s %s\n" "Rust:"   "$RUST_HASH"
printf "  %-12s %s\n" "JS:"     "$JS_HASH"
echo ""

AVAILABLE=$(echo "$PY_HASH $RUST_HASH $JS_HASH" | tr ' ' '\n' | grep -vE '^(ERROR|SKIPPED)$' | sort -u)
COUNT=$(echo "$AVAILABLE" | wc -l | tr -d ' ')

if [ "$COUNT" -eq 1 ]; then
    echo "✅ All available VMs produce identical output!"
    exit 0
elif [ "$COUNT" -eq 0 ]; then
    echo "⚠ No VMs produced output"
    exit 1
else
    echo "❌ VMs produce DIFFERENT output — investigate!"
    exit 1
fi
