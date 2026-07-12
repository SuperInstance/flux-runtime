# FLUX Cross-Implementation Showcase

Demonstrates that the Python, Rust, and JavaScript FLUX VMs produce identical
register state when running the same program.

## Quick Start

```bash
# Run on Python VM only
python3 showcase/compile_and_run.py

# Run on all available VMs and compare
./showcase/run_all.sh
```

## What It Does

1. **Assembles** `tests/cross_impl.flx` → 99 bytes of FLUX bytecode
2. **Fixes** jump offsets (cross-assembler emits absolute addresses; VM expects relative)
3. **Executes** the bytecode on the Python VM
4. **Outputs** the register state and an MD5 hash of R0–R15
5. **Compares** with expected values from the bytecode spec

## Expected Register State

| Register | Value | Source |
|----------|-------|--------|
| R0 | 13 | `((10 + 5) * 2 - 4) / 2` |
| R1 | 100 | Signature constant |
| R2 | 15 | Stack push/pop |
| R3 | 5 | Signature constant |
| R4 | 5040 | `factorial(7)` |
| R5 | 42 | CMP operand |
| R6 | 42 | CMP operand |
| R7 | 14 | MOV + IADD test |

## Cross-Implementation Verification

When all three VMs are installed, `run_all.sh` produces:

```
  Python:     0e77c903e2b4c44c637cbcd670b8768b
  Rust:       0e77c903e2b4c44c637cbcd670b8768b
  JS:         0e77c903e2b4c44c637cbcd670b8768b
```

All hashes should match, confirming byte-identical execution semantics.

## Files

- `compile_and_run.py` — Python VM runner with bytecode fixup
- `run_all.sh` — Multi-VM comparison script

## See Also

- [FLUX Bytecode Spec](../AI-Writings/FLUX_BYTECODE_SPEC.md)
- [cross_impl.flx](../tests/cross_impl.flx) — The test program
- [deadband.flx](../examples/deadband.flx) — Thermostat controller example
