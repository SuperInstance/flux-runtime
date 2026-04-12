#!/usr/bin/env bash
# run_conformance.sh — FLUX C VM Conformance Test Runner
#
# Compiles the C unified VM and runs all 20 conformance test vectors,
# comparing output against expected results from test_conformance.py.
#
# Usage:
#   ./run_conformance.sh              # compile and run all tests
#   ./run_conformance.sh --skip-build # skip compilation, just run tests
#
# Works on Linux x86_64 and ARM64.
#
# Author: Super Z (C runtime)
# Date:   2026-04-12

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VM_BINARY="${SCRIPT_DIR}/flux_vm_unified"
VM_SOURCE="${SCRIPT_DIR}/flux_vm_unified.c"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── Build ────────────────────────────────────────────────────────────────────

build_vm() {
    echo -e "${CYAN}=== Building C Unified VM ===${NC}"
    if command -v gcc &>/dev/null; then
        gcc -O2 -Wall -Wextra -o "$VM_BINARY" "$VM_SOURCE"
    elif command -v cc &>/dev/null; then
        cc -O2 -Wall -o "$VM_BINARY" "$VM_SOURCE"
    else
        echo -e "${RED}ERROR: No C compiler found (need gcc or cc)${NC}"
        exit 1
    fi
    echo -e "${GREEN}Build successful: ${VM_BINARY}${NC}"
    echo ""
}

if [[ "${1:-}" != "--skip-build" ]]; then
    build_vm
fi

if [[ ! -x "$VM_BINARY" ]]; then
    echo -e "${RED}ERROR: ${VM_BINARY} not found or not executable${NC}"
    exit 1
fi

# ── Helper: run a single bytecode test ───────────────────────────────────────

# Global counters (using functions to avoid set -e issues with ((x++)) )
_passed=0
_failed=0
_skipped=0

run_test() {
    local name="$1"
    local expected_type="$2"  # "no_crash" or "register"
    local expected_reg="${3:-}"   # register number for register tests
    local expected_val="${4:-}"   # expected value (or "nonzero")
    local bytecode_hex="${5:-}"   # hex string of bytecode

    # Write bytecode to temp file (handles null bytes correctly)
    local tmpfile
    tmpfile=$(mktemp)
    printf "%b" "$bytecode_hex" > "$tmpfile"

    # Run the VM
    local exit_code=0
    local output
    output=$("$VM_BINARY" "$tmpfile" 2>&1) || exit_code=$?
    rm -f "$tmpfile"

    if [[ $exit_code -ne 0 ]]; then
        echo -e "  ${RED}FAIL${NC} ${name} — VM crashed (exit code ${exit_code})"
        _failed=$((_failed + 1))
        return
    fi

    if [[ "$expected_type" == "no_crash" ]]; then
        # Check that "crashed=0" appears in output
        if echo "$output" | grep -q "crashed=0"; then
            echo -e "  ${GREEN}PASS${NC} ${name}"
            _passed=$((_passed + 1))
        else
            echo -e "  ${RED}FAIL${NC} ${name} — VM reports crashed"
            _failed=$((_failed + 1))
        fi
    elif [[ "$expected_type" == "register" ]]; then
        # Extract the register value from output like "R0=42"
        local reg_val
        reg_val=$(echo "$output" | grep -oP "R${expected_reg}=(-?\d+)" | head -1 | sed "s/R${expected_reg}=//")

        if [[ -z "$reg_val" ]]; then
            echo -e "  ${RED}FAIL${NC} ${name} — could not parse R${expected_reg}"
            _failed=$((_failed + 1))
            return
        fi

        if [[ "$expected_val" == "nonzero" ]]; then
            if [[ "$reg_val" != "0" ]]; then
                echo -e "  ${GREEN}PASS${NC} ${name} (R${expected_reg}=${reg_val}, nonzero)"
                _passed=$((_passed + 1))
            else
                echo -e "  ${RED}FAIL${NC} ${name} — R${expected_reg}=${reg_val}, expected nonzero"
                _failed=$((_failed + 1))
            fi
        else
            if [[ "$reg_val" == "$expected_val" ]]; then
                echo -e "  ${GREEN}PASS${NC} ${name} (R${expected_reg}=${reg_val})"
                _passed=$((_passed + 1))
            else
                echo -e "  ${RED}FAIL${NC} ${name} — R${expected_reg}=${reg_val}, expected ${expected_val}"
                _failed=$((_failed + 1))
            fi
        fi
    else
        echo -e "  ${YELLOW}SKIP${NC} ${name} — unknown expected type"
        _skipped=$((_skipped + 1))
    fi
}

# ── Run all 20 conformance tests ─────────────────────────────────────────────

echo -e "${CYAN}=== Running FLUX Conformance Tests (C VM) ===${NC}"
echo ""

# Test 1: NOP does nothing
# NOP, HALT → [0x01, 0x00]
run_test "NOP does nothing" "no_crash" "" "" '\x01\x00'

# Test 2: HALT terminates execution
# HALT → [0x00]
run_test "HALT terminates execution" "no_crash" "" "" '\x00'

# Test 3: MOVI loads immediate value
# MOVI R0, 42; HALT → [0x18, 0x00, 0x2A, 0x00]
run_test "MOVI loads immediate value" "register" 0 "42" '\x18\x00\x2a\x00'

# Test 4: MOVI loads negative value
# MOVI R0, -128; HALT → [0x18, 0x00, 0x80, 0x00]
run_test "MOVI loads negative value" "register" 0 "-128" '\x18\x00\x80\x00'

# Test 5: MOVI16 loads large immediate
# MOVI16 R0, 4096; HALT → [0x40, 0x00, 0x10, 0x00, 0x00]
run_test "MOVI16 loads large immediate" "register" 0 "4096" '\x40\x00\x10\x00\x00'

# Test 6: ADD two registers
# MOVI R0,10; MOVI R1,20; ADD R2,R0,R1; HALT
run_test "ADD two registers" "register" 2 "30" \
    '\x18\x00\x0a\x18\x01\x14\x20\x02\x00\x01\x00'

# Test 7: SUB two registers
# MOVI R0,30; MOVI R1,12; SUB R2,R0,R1; HALT
run_test "SUB two registers" "register" 2 "18" \
    '\x18\x00\x1e\x18\x01\x0c\x21\x02\x00\x01\x00'

# Test 8: MUL two registers
# MOVI R0,7; MOVI R1,6; MUL R2,R0,R1; HALT
run_test "MUL two registers" "register" 2 "42" \
    '\x18\x00\x07\x18\x01\x06\x22\x02\x00\x01\x00'

# Test 9: MOD two registers
# MOVI R0,17; MOVI R1,5; MOD R2,R0,R1; HALT
run_test "MOD two registers" "register" 2 "2" \
    '\x18\x00\x11\x18\x01\x05\x24\x02\x00\x01\x00'

# Test 10: CMP_EQ sets result for equal values
# MOVI R0,5; MOVI R1,5; CMP_EQ R2,R0,R1; HALT
run_test "CMP_EQ equal values" "register" 2 "nonzero" \
    '\x18\x00\x05\x18\x01\x05\x2c\x02\x00\x01\x00'

# Test 11: CMP_EQ sets result for unequal values
# MOVI R0,5; MOVI R1,3; CMP_EQ R2,R0,R1; HALT
run_test "CMP_EQ unequal values" "register" 2 "0" \
    '\x18\x00\x05\x18\x01\x03\x2c\x02\x00\x01\x00'

# Test 12: ADD with rd=rs1 overlap (R1 = R1 + R2)
# MOVI R0,10; MOVI R1,5; MOVI R2,3; ADD R1,R1,R2; HALT
run_test "ADD rd=rs1 overlap" "register" 1 "8" \
    '\x18\x00\x0a\x18\x01\x05\x18\x02\x03\x20\x01\x01\x02\x00'

# Test 13: ADD with rd=rs2 overlap (R2 = R0 + R2)
# MOVI R0,10; MOVI R1,5; MOVI R2,3; ADD R2,R0,R2; HALT
run_test "ADD rd=rs2 overlap" "register" 2 "13" \
    '\x18\x00\x0a\x18\x01\x05\x18\x02\x03\x20\x02\x00\x02\x00'

# Test 14: ADD with all-three overlap (R0 = R0 + R0)
# MOVI R0,7; ADD R0,R0,R0; HALT
run_test "ADD all-three overlap" "register" 0 "14" \
    '\x18\x00\x07\x20\x00\x00\x00\x00'

# Test 15: PUSH and POP preserve value
# MOVI R0,99; PUSH R0; POP R1; HALT
run_test "PUSH/POP preserve value" "register" 1 "99" \
    '\x18\x00\x63\x0c\x00\x0d\x01\x00'

# Test 16: AND bitwise
# MOVI R0,15; MOVI R1,3; AND R2,R0,R1; HALT
run_test "AND bitwise" "register" 2 "3" \
    '\x18\x00\x0f\x18\x01\x03\x25\x02\x00\x01\x00'

# Test 17: OR bitwise
# MOVI R0,10; MOVI R1,5; OR R2,R0,R1; HALT
run_test "OR bitwise" "register" 2 "15" \
    '\x18\x00\x0a\x18\x01\x05\x26\x02\x00\x01\x00'

# Test 18: XOR bitwise
# MOVI R0,15; MOVI R1,15; XOR R2,R0,R1; HALT
run_test "XOR bitwise" "register" 2 "0" \
    '\x18\x00\x0f\x18\x01\x0f\x27\x02\x00\x01\x00'

# Test 19: INC increments register
# MOVI R0,41; INC R0; HALT
run_test "INC increments register" "register" 0 "42" \
    '\x18\x00\x29\x08\x00\x00'

# Test 20: DEC decrements register
# MOVI R0,43; DEC R0; HALT
run_test "DEC decrements register" "register" 0 "42" \
    '\x18\x00\x2b\x09\x00\x00'

# ── Source-description tests (SKIPPED — need manual compilation) ─────────────

echo ""
echo -e "${YELLOW}  SKIP  GCD of 48 and 18 = 6 (source description — compile manually)${NC}"
_skipped=$((_skipped + 1))
echo -e "${YELLOW}  SKIP  Fibonacci(10) = 55 (source description — compile manually)${NC}"
_skipped=$((_skipped + 1))
echo -e "${YELLOW}  SKIP  Sum of squares 1..5 = 55 (source description — compile manually)${NC}"
_skipped=$((_skipped + 1))

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}=== Results ===${NC}"
total=$((_passed + _failed + _skipped))
echo -e "  ${GREEN}PASSED:${NC}  ${_passed}/${total}"
echo -e "  ${RED}FAILED:${NC}  ${_failed}/${total}"
echo -e "  ${YELLOW}SKIPPED:${NC} ${_skipped}/${total}"
echo ""

if [[ $_failed -eq 0 ]]; then
    echo -e "${GREEN}All tests passed! C VM is ISA-conformant.${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. C VM has ISA divergences.${NC}"
    exit 1
fi
