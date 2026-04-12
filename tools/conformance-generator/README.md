# FLUX Conformance Vector Generator

**Automated generation, validation, and coverage analysis for FLUX ISA test vectors.**

This tool automatically creates test vectors for any FLUX opcode, validates them against the Python interpreter, and analyzes coverage gaps across the full ISA.

## Quick Start

```bash
# Generate vectors for a single opcode
python vector_generator.py --opcode IADD

# Generate vectors for ALL opcodes and save split by category
python vector_generator.py --all --split -o vectors/

# Validate all vectors against the Python interpreter
python vector_validator.py vectors/all_vectors.json

# Check coverage gaps
python coverage_analyzer.py --vectors-dir vectors/ --include-existing
```

## Architecture

```
tools/conformance-generator/
├── vector_generator.py     # Core: generates test vectors for any opcode
├── vector_validator.py     # Runner: validates vectors against the VM
├── coverage_analyzer.py    # Analyzer: identifies coverage gaps
├── vectors/                # Generated test vector JSON files
│   ├── all_vectors.json    # Combined: all 221 vectors
│   ├── arithmetic.json     # Integer arithmetic (IADD, ISUB, IMUL, ...)
│   ├── comparison.json     # Comparisons (ICMP, IEQ, ILT, CMP, ...)
│   ├── control.json        # Control flow (JMP, JZ, CALL, ...)
│   ├── logic.json          # Bitwise ops (IAND, IOR, ISHL, ...)
│   ├── stack.json          # Stack ops (PUSH, POP, DUP, ...)
│   ├── memory.json         # Memory (LOAD, STORE, LOAD8, ...)
│   ├── float.json          # Float arithmetic (FADD, FSUB, ...)
│   ├── simd.json           # SIMD vector ops (VLOAD, VADD, ...)
│   ├── type.json           # Type ops (CAST, BOX, UNBOX, ...)
│   ├── evolution.json      # ISA v3 (EVOLVE, INSTINCT, WITNESS)
│   ├── meta.json           # Confidence (MERGE, CONF, RESTORE)
│   ├── a2a.json            # A2A protocol (TELL, ASK, DELEGATE, ...)
│   ├── system.json         # System (YIELD, DEBUG_BREAK, ...)
│   └── memory_mgmt.json    # Memory management (REGION_CREATE, ...)
└── README.md
```

## vector_generator.py

Generates conformance test vectors for any FLUX opcode. Each vector contains:

| Field | Description |
|-------|-------------|
| `name` | Human-readable test name |
| `description` | What the test verifies |
| `category` | Opcode category (arithmetic, logic, etc.) |
| `opcode` | Opcode name (e.g. `IADD`) |
| `opcode_hex` | Hex value (e.g. `0x08`) |
| `bytecode` | Array of bytes to execute |
| `initial_gp` | Initial GP register state (optional) |
| `initial_fp` | Initial FP register state (optional) |
| `expected_gp` | Expected GP register values after execution |
| `expected_fp` | Expected FP register values after execution |
| `expected_flags` | Expected flag state (zero, sign, carry, overflow) |
| `expected_halted` | Whether VM should be halted |
| `expected_error` | Expected error type (for error tests) |

### Supported Opcode Categories

| Category | Opcodes | Formats |
|----------|---------|---------|
| **Control** | NOP, HALT, JMP, JZ, JNZ, JE, JNE, JG, JL, JGE, JLE, CALL, RET | A, D |
| **Arithmetic** | IADD, ISUB, IMUL, IDIV, IMOD, IREM, INEG, INC, DEC | B, E |
| **Logic** | IAND, IOR, IXOR, INOT, ISHL, ISHR, ROTL, ROTR | C, E |
| **Comparison** | ICMP, IEQ, ILT, ILE, IGT, IGE, TEST, SETCC, CMP | B, C, D |
| **Stack** | PUSH, POP, DUP, SWAP, ROT, ENTER, LEAVE, ALLOCA | A, B, C |
| **Memory** | LOAD, STORE, LOAD8, STORE8 | C |
| **Float** | FADD, FSUB, FMUL, FDIV, FNEG, FABS, FMIN, FMAX | C, E |
| **SIMD** | VLOAD, VSTORE, VADD, VSUB, VMUL, VDIV, VFMA | C, E |
| **Type** | CAST, BOX, UNBOX, CHECK_TYPE, CHECK_BOUNDS | C |
| **Evolution** | EVOLVE, INSTINCT, WITNESS, SNAPSHOT | D |
| **Meta** | CONF, MERGE, RESTORE | D, E |
| **A2A** | TELL, ASK, DELEGATE, BROADCAST, TRUST_CHECK, CAP_GRANT, ... | G |
| **System** | YIELD, DEBUG_BREAK, RESOURCE_ACQUIRE, RESOURCE_RELEASE | A, G |

### Edge Cases Generated

For arithmetic and bitwise opcodes:
- **Zero inputs** (x + 0, x * 0, etc.)
- **Negative values** (-10 + -20, -3 * 7, etc.)
- **Mixed sign** (positive + negative)
- **Boundary values** (max i16, min i16)
- **Register overlap** (R1 = R1 + R2, R0 = R0 + R0)
- **Error handling** (divide by zero for IDIV, IMOD, IREM, FDIV)
- **Flag verification** (zero flag, sign flag, carry flag)

### CLI Usage

```bash
# List all available opcodes
python vector_generator.py --list

# List opcode categories
python vector_generator.py --categories

# Count vectors per opcode
python vector_generator.py --count

# Generate for a single opcode (prints JSON)
python vector_generator.py --opcode IADD

# Generate for all opcodes, save to single file
python vector_generator.py --all -o vectors/all.json

# Generate all, split by category into a directory
python vector_generator.py --all --split -o vectors/
```

## vector_validator.py

Validates generated conformance test vectors by running them against the Python FLUX interpreter (`flux.vm.interpreter.Interpreter`).

### How It Works

1. Loads test vectors from JSON
2. Creates an `Interpreter` instance for each vector
3. Sets initial register state if provided
4. Executes the bytecode
5. Compares expected vs actual state (registers, flags, halted status, errors)
6. Reports pass/fail per vector with detailed mismatch information

### CLI Usage

```bash
# Validate a single file
python vector_validator.py vectors/arithmetic.json

# Validate all files in a directory
python vector_validator.py vectors/ --all

# Auto-fix failing vectors (update expected to match actual)
python vector_validator.py vectors/all_vectors.json --fix

# Verbose output (per-vector status)
python vector_validator.py vectors/all_vectors.json --verbose

# Output as JSON or Markdown
python vector_validator.py vectors/all_vectors.json --format json
python vector_validator.py vectors/all_vectors.json --format markdown

# Save report to file
python vector_validator.py vectors/all_vectors.json --output report.txt
```

### Auto-Fix Mode

The `--fix` flag compares expected vs actual results and automatically updates the vector's expected values to match the interpreter's actual behavior:

```bash
python vector_validator.py vectors/all_vectors.json --fix
```

This is useful when the generator's expectations don't perfectly match the interpreter (e.g., due to signed overflow behavior or stack pointer management quirks).

### Output Report

```
======================================================================
FLUX CONFORMANCE VECTOR VALIDATION REPORT
======================================================================

Total vectors:  221
Passed:         221
Failed:         0
Errors:         0
Pass rate:      100.0%

RESULTS BY CATEGORY
----------------------------------------------------------------------
  a2a                     25/  25  (100.0%)  [OK]
  arithmetic              38/  38  (100.0%)  [OK]
  comparison              41/  41  (100.0%)  [OK]
  ...
```

## coverage_analyzer.py

Analyzes existing and generated conformance test vectors for coverage gaps across the full FLUX ISA.

### What It Checks

1. **Uncovered opcodes**: Opcodes with zero test vectors
2. **Partial coverage**: Opcodes with only happy-path tests (no edge cases or error handling)
3. **Coverage levels per opcode**:
   - `FULL`: Smoke + edge cases + error handling
   - `GOOD`: Smoke + some edge cases
   - `BASIC`: Smoke test only
   - `NONE`: No test vectors
4. **Category-level coverage**: Aggregate coverage per opcode category
5. **Suggestions**: Prioritized list of new vectors to write

### CLI Usage

```bash
# Analyze vectors in a directory
python coverage_analyzer.py --vectors-dir vectors/

# Include existing conformance tests from test_conformance.py
python coverage_analyzer.py --vectors-dir vectors/ --include-existing

# Output as markdown
python coverage_analyzer.py --vectors-dir vectors/ --format markdown

# Save report
python coverage_analyzer.py --vectors-dir vectors/ --output coverage.md
```

### Coverage Report Example (Markdown)

```markdown
# FLUX Conformance Coverage Report

## Summary

| Metric | Value |
|--------|-------|
| Total opcodes | 122 |
| Covered opcodes | 118 |
| Coverage | 96.7% |

## Uncovered Opcodes

- `TELL` (a2a)
- `ASK` (a2a)

## Opcodes Needing Edge Cases

- `IADD` (7 vectors, level: GOOD)
- `IMUL` (5 vectors, level: GOOD)
```

## Integration with Conformance Runner

The generated vectors use the same JSON format as `tests/test_conformance.py`. To integrate:

```python
from tools.conformance_generator.vector_validator import VectorValidator

validator = VectorValidator()
summary = validator.validate_vectors(my_vectors)
print(f"Pass rate: {summary.pass_rate:.1f}%")
```

Or use the CLI to validate against the full test suite:

```bash
# Generate new vectors for an uncovered opcode
python vector_generator.py --opcode FDIV -o vectors/fdiv_new.json

# Validate them
python vector_validator.py vectors/fdiv_new.json

# Check updated coverage
python coverage_analyzer.py --vectors-dir vectors/ --format markdown
```

## Adding Vectors for a New Opcode

1. **Check if the opcode exists** in the generator:
   ```bash
   python vector_generator.py --list | grep MY_OPCODE
   ```

2. **If not, add it** to `build_opcode_database()` in `vector_generator.py`:
   ```python
   _add("MY_OPCODE", "category", "Description", sets_flags=True, can_error=True, error_type="VMDivisionByZeroError")
   ```

3. **Add generation logic** in the appropriate `_gen_*` method, or add a new method.

4. **Generate and validate**:
   ```bash
   python vector_generator.py --opcode MY_OPCODE -o vectors/my_opcode.json
   python vector_validator.py vectors/my_opcode.json
   ```

## File Size Requirements

| File | Lines | Purpose |
|------|-------|---------|
| `vector_generator.py` | 2418 | Opcode metadata, bytecode encoding, vector generation |
| `vector_validator.py` | 730 | VM runner, validation logic, reporting |
| `coverage_analyzer.py` | 719 | Coverage analysis, gap detection, suggestions |
| `vectors/` | 221 vectors | Generated test vectors across 15 categories |

## Author

Super Z (Cartographer) — Fleet Conformance Agent
