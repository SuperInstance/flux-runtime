"""
FLUX Expanded Conformance Test Suite — 68 bytecode test vectors.

Extends the original 22-vector suite with 46 new vectors covering:
- Memory operations (STORE, LOAD, STOREOFF, LOADOFF)
- Control flow (JMP, JZ, JNZ, JAL, LOOP)
- Shift operations (SHL, SHR, SHLI, SHRI)
- Full comparison coverage (CMP_LT, CMP_GT, CMP_NE)
- Edge cases (overflow, underflow, boundary values)
- Register operations (MOV, SWP, multiple MOVs)
- Immediate arithmetic (ADDI, SUBI, ANDI, ORI, XORI, ADDI16, SUBI16)
- Format coverage (A through G)
- Overlap safety for SUB and MUL

Each test is a dict with:
  - name: human-readable description
  - bytecode: list of ints (the program)
  - expected: expected result or condition
  - category: which opcode category this tests
  - notes: optional reasoning

Author: Super Z (Cartographer)
Date: 2026-04-12
Status: DRAFT — Phase 2 (expanded coverage)
"""

TEST_VECTORS = [
    # =========================================================================
    # Category: System Control — Format A (0x00-0x07)
    # =========================================================================
    {
        "name": "NOP does nothing",
        "bytecode": [0x01, 0x00],
        "expected": "no_crash",
        "category": "control",
        "notes": "NOP (0x01) should execute without modifying any state.",
    },
    {
        "name": "HALT terminates execution",
        "bytecode": [0x00],
        "expected": "no_crash",
        "category": "control",
        "notes": "HALT (0x00) should stop the VM immediately.",
    },

    # =========================================================================
    # Category: Data Movement — Format D (0x18), Format F (0x40)
    # =========================================================================
    {
        "name": "MOVI loads immediate value",
        "bytecode": [0x18, 0, 42, 0x00],
        "expected": {"register": 0, "value": 42},
        "category": "data",
        "notes": "MOVI (0x18) Format D: opcode, rd, imm8. R0 = 42.",
    },
    {
        "name": "MOVI loads negative value",
        "bytecode": [0x18, 0, 0x80, 0x00],
        "expected": {"register": 0, "value": -128},
        "category": "data",
        "notes": "MOVI sign-extends imm8. 0x80 = -128 in two's complement.",
    },
    {
        "name": "MOVI16 loads large immediate",
        "bytecode": [0x40, 0, 0x10, 0x00, 0x00],
        "expected": {"register": 0, "value": 4096},
        "category": "data",
        "notes": "MOVI16 (0x40) Format F: opcode, rd, imm16hi, imm16lo. 4096 = 0x1000.",
    },

    # =========================================================================
    # Category: Arithmetic — Format E (0x20-0x24)
    # =========================================================================
    {
        "name": "ADD two registers",
        "bytecode": [0x18, 0, 10, 0x18, 1, 20, 0x20, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 30},
        "category": "arithmetic",
        "notes": "ADD (0x20): R2 = R0 + R1 = 10 + 20 = 30.",
    },
    {
        "name": "SUB two registers",
        "bytecode": [0x18, 0, 30, 0x18, 1, 12, 0x21, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 18},
        "category": "arithmetic",
        "notes": "SUB (0x21): R2 = R0 - R1 = 30 - 12 = 18.",
    },
    {
        "name": "MUL two registers",
        "bytecode": [0x18, 0, 7, 0x18, 1, 6, 0x22, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 42},
        "category": "arithmetic",
        "notes": "MUL (0x22): R2 = R0 * R1 = 7 * 6 = 42.",
    },
    {
        "name": "MOD two registers",
        "bytecode": [0x18, 0, 17, 0x18, 1, 5, 0x24, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 2},
        "category": "arithmetic",
        "notes": "MOD (0x24): R2 = R0 mod R1 = 17 mod 5 = 2.",
    },
    {
        "name": "DIV integer division",
        "bytecode": [0x18, 0, 20, 0x18, 1, 4, 0x23, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 5},
        "category": "arithmetic",
        "notes": "DIV (0x23): R2 = R0 / R1 = 20 / 4 = 5.",
    },
    {
        "name": "MIN of two values",
        "bytecode": [0x18, 0, 10, 0x18, 1, 20, 0x2A, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 10},
        "category": "arithmetic",
        "notes": "MIN (0x2A): R2 = min(R0, R1) = min(10, 20) = 10.",
    },
    {
        "name": "MAX of two values",
        "bytecode": [0x18, 0, 10, 0x18, 1, 20, 0x2B, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 20},
        "category": "arithmetic",
        "notes": "MAX (0x2B): R2 = max(R0, R1) = max(10, 20) = 20.",
    },

    # =========================================================================
    # Category: Comparison — Format E (0x2C-0x2F)
    # =========================================================================
    {
        "name": "CMP_EQ sets result for equal values",
        "bytecode": [0x18, 0, 5, 0x18, 1, 5, 0x2C, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value_neq_zero": True},
        "category": "comparison",
        "notes": "CMP_EQ (0x2C): R2 = (R0 == R1) ? 1 : 0. 5 == 5, so R2 != 0.",
    },
    {
        "name": "CMP_EQ sets result for unequal values",
        "bytecode": [0x18, 0, 5, 0x18, 1, 3, 0x2C, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "comparison",
        "notes": "CMP_EQ: 5 != 3, so R2 = 0.",
    },
    {
        "name": "CMP_LT less than is true",
        "bytecode": [0x18, 0, 3, 0x18, 1, 7, 0x2D, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 1},
        "category": "comparison",
        "notes": "CMP_LT (0x2D): R2 = (3 < 7) ? 1 : 0 = 1.",
    },
    {
        "name": "CMP_GT greater than is true",
        "bytecode": [0x18, 0, 10, 0x18, 1, 3, 0x2E, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 1},
        "category": "comparison",
        "notes": "CMP_GT (0x2E): R2 = (10 > 3) ? 1 : 0 = 1.",
    },
    {
        "name": "CMP_LT equal values is false",
        "bytecode": [0x18, 0, 5, 0x18, 1, 5, 0x2D, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "comparison",
        "notes": "CMP_LT: (5 < 5) is false, so R2 = 0.",
    },
    {
        "name": "CMP_GT equal values is false",
        "bytecode": [0x18, 0, 5, 0x18, 1, 5, 0x2E, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "comparison",
        "notes": "CMP_GT: (5 > 5) is false, so R2 = 0.",
    },
    {
        "name": "CMP_NE not equal is true",
        "bytecode": [0x18, 0, 5, 0x18, 1, 3, 0x2F, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 1},
        "category": "comparison",
        "notes": "CMP_NE (0x2F): R2 = (5 != 3) ? 1 : 0 = 1.",
    },
    {
        "name": "CMP_NE equal values is false",
        "bytecode": [0x18, 0, 5, 0x18, 1, 5, 0x2F, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "comparison",
        "notes": "CMP_NE: (5 != 5) is false, so R2 = 0.",
    },

    # =========================================================================
    # Category: Register Overlap Safety — Format E
    # =========================================================================
    {
        "name": "ADD with rd=rs1 overlap (R1 = R1 + R2)",
        "bytecode": [0x18, 0, 10, 0x18, 1, 5, 0x18, 2, 3, 0x20, 1, 1, 2, 0x00],
        "expected": {"register": 1, "value": 8},
        "category": "arithmetic",
        "notes": "CRITICAL: VM MUST read R1 before writing R1. R1 = 5 + 3 = 8.",
    },
    {
        "name": "ADD with rd=rs2 overlap (R2 = R0 + R2)",
        "bytecode": [0x18, 0, 10, 0x18, 1, 5, 0x18, 2, 3, 0x20, 2, 0, 2, 0x00],
        "expected": {"register": 2, "value": 13},
        "category": "arithmetic",
        "notes": "CRITICAL: R2 = R0 + R2 = 10 + 3 = 13.",
    },
    {
        "name": "ADD with all-three overlap (R0 = R0 + R0)",
        "bytecode": [0x18, 0, 7, 0x20, 0, 0, 0, 0x00],
        "expected": {"register": 0, "value": 14},
        "category": "arithmetic",
        "notes": "CRITICAL: All three registers same. R0 = 7 + 7 = 14.",
    },
    {
        "name": "SUB with rd=rs1 overlap (R0 = R0 - R1)",
        "bytecode": [0x18, 0, 10, 0x18, 1, 3, 0x21, 0, 0, 1, 0x00],
        "expected": {"register": 0, "value": 7},
        "category": "arithmetic",
        "notes": "CRITICAL: SUB overlap. VM reads R0=10 before writing. R0 = 10 - 3 = 7.",
    },
    {
        "name": "MUL with rd=rs1 overlap (R0 = R0 * R1)",
        "bytecode": [0x18, 0, 5, 0x18, 1, 3, 0x22, 0, 0, 1, 0x00],
        "expected": {"register": 0, "value": 15},
        "category": "arithmetic",
        "notes": "CRITICAL: MUL overlap. R0 = 5 * 3 = 15.",
    },
    {
        "name": "SUB self-zero (R0 = R0 - R0)",
        "bytecode": [0x18, 0, 42, 0x21, 0, 0, 0, 0x00],
        "expected": {"register": 0, "value": 0},
        "category": "arithmetic",
        "notes": "x - x always equals 0. Tests max overlap for SUB.",
    },

    # =========================================================================
    # Category: Stack Operations — Format B (0x0C-0x0D)
    # =========================================================================
    {
        "name": "PUSH and POP preserve value",
        "bytecode": [0x18, 0, 99, 0x0C, 0, 0x0D, 1, 0x00],
        "expected": {"register": 1, "value": 99},
        "category": "stack",
        "notes": "PUSH (0x0C) and POP (0x0D) should preserve values exactly.",
    },
    {
        "name": "Multiple PUSH and POP (LIFO order)",
        "bytecode": [0x18, 0, 10, 0x18, 1, 20, 0x0C, 0, 0x0C, 1, 0x0D, 2, 0x0D, 3, 0x00],
        "expected": {"register": 2, "value": 20},
        "category": "stack",
        "notes": "Push R0=10, R1=20. Pop R2=20, Pop R3=10. Stack is LIFO.",
    },

    # =========================================================================
    # Category: Logic / Bitwise — Format E (0x25-0x27), Format B (0x0A)
    # =========================================================================
    {
        "name": "AND bitwise",
        "bytecode": [0x18, 0, 0x0F, 0x18, 1, 0x03, 0x25, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 3},
        "category": "logic",
        "notes": "AND (0x25): 15 & 3 = 3.",
    },
    {
        "name": "OR bitwise",
        "bytecode": [0x18, 0, 0x0A, 0x18, 1, 0x05, 0x26, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 15},
        "category": "logic",
        "notes": "OR (0x26): 10 | 5 = 15.",
    },
    {
        "name": "XOR bitwise",
        "bytecode": [0x18, 0, 0x0F, 0x18, 1, 0x0F, 0x27, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "logic",
        "notes": "XOR (0x27): 15 ^ 15 = 0. Self-XOR always produces zero.",
    },
    {
        "name": "NOT bitwise (Format B)",
        "bytecode": [0x18, 0, 0, 0x0A, 0, 0x00],
        "expected": {"register": 0, "value": -1},
        "category": "logic",
        "notes": "NOT (0x0A): ~0 = -1 in Python two's complement.",
    },

    # =========================================================================
    # Category: Increment / Decrement — Format B (0x08-0x09)
    # =========================================================================
    {
        "name": "INC increments register",
        "bytecode": [0x18, 0, 41, 0x08, 0, 0x00],
        "expected": {"register": 0, "value": 42},
        "category": "arithmetic",
        "notes": "INC (0x08): R0 = 41 + 1 = 42.",
    },
    {
        "name": "DEC decrements register",
        "bytecode": [0x18, 0, 43, 0x09, 0, 0x00],
        "expected": {"register": 0, "value": 42},
        "category": "arithmetic",
        "notes": "DEC (0x09): R0 = 43 - 1 = 42.",
    },

    # =========================================================================
    # Category: NEG — Format B (0x0B)
    # =========================================================================
    {
        "name": "NEG negates register",
        "bytecode": [0x18, 0, 42, 0x0B, 0, 0x00],
        "expected": {"register": 0, "value": -42},
        "category": "arithmetic",
        "notes": "NEG (0x0B): R0 = -42.",
    },

    # =========================================================================
    # Category: Memory Operations — Format E (0x38-0x39), Format G (0x48-0x49)
    # =========================================================================
    {
        "name": "STORE then LOAD at address 0",
        "bytecode": [0x18, 0, 100, 0x18, 1, 0, 0x18, 2, 0,
                      0x39, 0, 1, 2, 0x38, 3, 1, 2, 0x00],
        "expected": {"register": 3, "value": 100},
        "category": "memory",
        "notes": "STORE (0x39): mem[R1+R2] = R0 = 100. LOAD (0x38): R3 = mem[R1+R2] = 100.",
    },
    {
        "name": "STORE then LOAD at non-zero address",
        "bytecode": [0x40, 0, 0, 42, 0x40, 1, 0, 8, 0x18, 2, 0,
                      0x39, 0, 1, 2, 0x38, 3, 1, 2, 0x00],
        "expected": {"register": 3, "value": 42},
        "category": "memory",
        "notes": "STORE at addr 8+0=8, LOAD from addr 8+0=8. Tests non-zero addressing.",
    },
    {
        "name": "Multiple memory locations (addr 0 and addr 4)",
        "bytecode": [0x40, 0, 0, 100, 0x40, 1, 0, 200, 0x18, 2, 0, 0x18, 3, 4,
                      0x39, 0, 2, 2, 0x39, 1, 3, 2, 0x38, 4, 2, 2, 0x38, 5, 3, 2, 0x00],
        "expected": {"register": 5, "value": 200},
        "category": "memory",
        "notes": "Write R0=100 to addr 0, R1=200 to addr 4. Read back R5 from addr 4.",
    },
    {
        "name": "STOREOFF then LOADOFF at offset 0 (Format G)",
        "bytecode": [0x40, 0, 0, 99, 0x40, 1, 0, 0,
                      0x49, 0, 1, 0, 0, 0x48, 2, 1, 0, 0, 0x00],
        "expected": {"register": 2, "value": 99},
        "category": "memory",
        "notes": "STOREOFF (0x49) Format G: mem[R1+0] = R0. LOADOFF (0x48): R2 = mem[R1+0].",
    },
    {
        "name": "STOREOFF then LOADOFF at offset 16 (Format G)",
        "bytecode": [0x40, 0, 0, 77, 0x40, 1, 0, 0,
                      0x49, 0, 1, 0, 16, 0x48, 2, 1, 0, 16, 0x00],
        "expected": {"register": 2, "value": 77},
        "category": "memory",
        "notes": "Format G with non-zero imm16 offset. mem[0+16] = 77, then read back.",
    },

    # =========================================================================
    # Category: Control Flow — Format E (0x3C-0x3D), Format F (0x43-0x44, 0x46)
    # =========================================================================
    {
        "name": "JMP forward skips instruction",
        "bytecode": [0x18, 0, 42, 0x43, 0, 0, 3, 0x18, 0, 99, 0x00],
        "expected": {"register": 0, "value": 42},
        "category": "control",
        "notes": "JMP (0x43) Format F: pc += 3. Skips MOVI R0,99. R0 stays 42.",
    },
    {
        "name": "JNZ taken (conditional branch)",
        "bytecode": [0x18, 0, 1, 0x18, 1, 3, 0x3D, 0, 1, 0, 0x18, 0, 0, 0x00],
        "expected": {"register": 0, "value": 1},
        "category": "control",
        "notes": "JNZ (0x3D): R0=1 != 0, so pc += R1=3. Skips MOVI R0,0. R0 stays 1.",
    },
    {
        "name": "JNZ not taken (falls through)",
        "bytecode": [0x18, 0, 0, 0x18, 1, 3, 0x3D, 0, 1, 0, 0x18, 0, 99, 0x00],
        "expected": {"register": 0, "value": 99},
        "category": "control",
        "notes": "JNZ: R0=0, no branch. Falls through to MOVI R0,99.",
    },
    {
        "name": "JZ taken (zero branch)",
        "bytecode": [0x18, 0, 0, 0x18, 1, 3, 0x3C, 0, 1, 0, 0x18, 0, 99, 0x00],
        "expected": {"register": 0, "value": 0},
        "category": "control",
        "notes": "JZ (0x3C): R0=0, so pc += R1=3. Skips MOVI R0,99.",
    },
    {
        "name": "JAL saves return address (Format F)",
        "bytecode": [0x44, 1, 0, 0, 0x00],
        "expected": {"register": 1, "value": 4},
        "category": "control",
        "notes": "JAL (0x44): R1 = pc (after fetch = 4), then pc += 0.",
    },
    {
        "name": "LOOP counts down (3 iterations)",
        "bytecode": [0x18, 0, 3, 0x18, 1, 0, 0x08, 1, 0x46, 0, 0, 6, 0x00],
        "expected": {"register": 1, "value": 3},
        "category": "control",
        "notes": "LOOP (0x46) Format F: R0--; if R0>0: pc-=6. R1 incremented 3 times.",
    },

    # =========================================================================
    # Category: Shift Operations — Format E (0x28-0x29), Format D (0x1E-0x1F)
    # =========================================================================
    {
        "name": "SHL shift left by register",
        "bytecode": [0x18, 0, 1, 0x18, 1, 4, 0x28, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 16},
        "category": "shift",
        "notes": "SHL (0x28): R2 = R0 << R2 = 1 << 4 = 16.",
    },
    {
        "name": "SHR shift right by register",
        "bytecode": [0x18, 0, 32, 0x18, 1, 2, 0x29, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 8},
        "category": "shift",
        "notes": "SHR (0x29): R2 = R0 >> R1 = 32 >> 2 = 8.",
    },
    {
        "name": "SHLI shift left by immediate (Format D)",
        "bytecode": [0x18, 0, 1, 0x1E, 0, 4, 0x00],
        "expected": {"register": 0, "value": 16},
        "category": "shift",
        "notes": "SHLI (0x1E) Format D: R0 = R0 << 4 = 1 << 4 = 16.",
    },
    {
        "name": "SHRI shift right by immediate (Format D)",
        "bytecode": [0x18, 0, 64, 0x1F, 0, 3, 0x00],
        "expected": {"register": 0, "value": 8},
        "category": "shift",
        "notes": "SHRI (0x1F) Format D: R0 = R0 >> 3 = 64 >> 3 = 8.",
    },

    # =========================================================================
    # Category: Immediate Arithmetic — Format D (0x19-0x1D)
    # =========================================================================
    {
        "name": "ADDI add immediate",
        "bytecode": [0x18, 0, 10, 0x19, 0, 5, 0x00],
        "expected": {"register": 0, "value": 15},
        "category": "arithmetic",
        "notes": "ADDI (0x19) Format D: R0 = R0 + 5 = 10 + 5 = 15.",
    },
    {
        "name": "SUBI subtract immediate",
        "bytecode": [0x18, 0, 10, 0x1A, 0, 3, 0x00],
        "expected": {"register": 0, "value": 7},
        "category": "arithmetic",
        "notes": "SUBI (0x1A) Format D: R0 = R0 - 3 = 10 - 3 = 7.",
    },
    {
        "name": "ANDI and immediate",
        "bytecode": [0x40, 0, 0, 0xFF, 0x1B, 0, 0x0F, 0x00],
        "expected": {"register": 0, "value": 15},
        "category": "logic",
        "notes": "ANDI (0x1B) Format D: R0 = R0 & 0x0F = 255 & 15 = 15.",
    },
    {
        "name": "ORI or immediate",
        "bytecode": [0x18, 0, 0, 0x1C, 0, 0xF0, 0x00],
        "expected": {"register": 0, "value": 240},
        "category": "logic",
        "notes": "ORI (0x1C) Format D: R0 = R0 | 0xF0 = 0 | 240 = 240.",
    },
    {
        "name": "XORI xor immediate",
        "bytecode": [0x40, 0, 0, 0xFF, 0x1D, 0, 0x0F, 0x00],
        "expected": {"register": 0, "value": 240},
        "category": "logic",
        "notes": "XORI (0x1D) Format D: R0 = R0 ^ 0x0F = 255 ^ 15 = 240.",
    },

    # =========================================================================
    # Category: 16-bit Immediate Arithmetic — Format F (0x41-0x42)
    # =========================================================================
    {
        "name": "ADDI16 add 16-bit immediate",
        "bytecode": [0x40, 0, 0, 100, 0x41, 0, 0, 23, 0x00],
        "expected": {"register": 0, "value": 123},
        "category": "arithmetic",
        "notes": "ADDI16 (0x41) Format F: R0 = R0 + 23 = 100 + 23 = 123.",
    },
    {
        "name": "SUBI16 subtract 16-bit immediate",
        "bytecode": [0x40, 0, 0, 100, 0x42, 0, 0, 37, 0x00],
        "expected": {"register": 0, "value": 63},
        "category": "arithmetic",
        "notes": "SUBI16 (0x42) Format F: R0 = R0 - 37 = 100 - 37 = 63.",
    },

    # =========================================================================
    # Category: Register Move — Format E (0x3A, 0x3B)
    # =========================================================================
    {
        "name": "MOV between registers",
        "bytecode": [0x18, 0, 42, 0x3A, 1, 0, 0, 0x00],
        "expected": {"register": 1, "value": 42},
        "category": "data",
        "notes": "MOV (0x3A): R1 = R0 = 42. Format E, rs2 is ignored.",
    },
    {
        "name": "Multiple MOVs in sequence",
        "bytecode": [0x18, 0, 10, 0x3A, 1, 0, 0, 0x3A, 2, 1, 0, 0x3A, 3, 2, 0, 0x00],
        "expected": {"register": 3, "value": 10},
        "category": "data",
        "notes": "MOV chain: R0→R1→R2→R3. Verifies data propagates correctly.",
    },
    {
        "name": "SWP swaps two registers",
        "bytecode": [0x18, 0, 10, 0x18, 1, 20, 0x3B, 0, 1, 0, 0x00],
        "expected": {"register": 0, "value": 20},
        "category": "data",
        "notes": "SWP (0x3B): swap(R0, R1). R0 was 10, R1 was 20. Now R0 = 20.",
    },

    # =========================================================================
    # Category: Edge Cases
    # =========================================================================
    {
        "name": "MOVI with 0",
        "bytecode": [0x18, 0, 0, 0x00],
        "expected": {"register": 0, "value": 0},
        "category": "data",
        "notes": "MOVI R0, 0. Tests that zero immediate loads correctly.",
    },
    {
        "name": "MOVI with 255 (sign-extended to -1)",
        "bytecode": [0x18, 0, 0xFF, 0x00],
        "expected": {"register": 0, "value": -1},
        "category": "data",
        "notes": "MOVI sign-extends imm8: 0xFF = -1 as signed i8.",
    },
    {
        "name": "ADD overflow (255 + 1 = 256)",
        "bytecode": [0x40, 0, 0, 255, 0x40, 1, 0, 1, 0x20, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 256},
        "category": "arithmetic",
        "notes": "Python has arbitrary precision, so no overflow. 255 + 1 = 256.",
    },
    {
        "name": "SUB underflow (0 - 1 = -1)",
        "bytecode": [0x18, 0, 0, 0x18, 1, 1, 0x21, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": -1},
        "category": "arithmetic",
        "notes": "0 - 1 = -1. No underflow trap in Python arbitrary precision.",
    },
    {
        "name": "MUL by zero",
        "bytecode": [0x18, 0, 0, 0x18, 1, 42, 0x22, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "arithmetic",
        "notes": "0 * 42 = 0. Zero times anything is zero.",
    },
    {
        "name": "MUL identity (x * 1 = x)",
        "bytecode": [0x18, 0, 42, 0x18, 1, 1, 0x22, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 42},
        "category": "arithmetic",
        "notes": "42 * 1 = 42. Multiplicative identity.",
    },
    {
        "name": "MOD by 1 (always 0)",
        "bytecode": [0x18, 0, 42, 0x18, 1, 1, 0x24, 2, 0, 1, 0x00],
        "expected": {"register": 2, "value": 0},
        "category": "arithmetic",
        "notes": "42 mod 1 = 0. Any number mod 1 is 0.",
    },
    {
        "name": "INC from 254 to 255",
        "bytecode": [0x40, 0, 0, 254, 0x08, 0, 0x00],
        "expected": {"register": 0, "value": 255},
        "category": "arithmetic",
        "notes": "MOVI16 loads 254 (needs Format F since 254 > 127). INC → 255.",
    },
    {
        "name": "DEC from 1 to 0",
        "bytecode": [0x18, 0, 1, 0x09, 0, 0x00],
        "expected": {"register": 0, "value": 0},
        "category": "arithmetic",
        "notes": "DEC: R0 = 1 - 1 = 0. Boundary case for decrement.",
    },
    {
        "name": "INC from -1 to 0",
        "bytecode": [0x18, 0, 0xFF, 0x08, 0, 0x00],
        "expected": {"register": 0, "value": 0},
        "category": "arithmetic",
        "notes": "MOVI R0, -1 (0xFF sign-extended). INC → 0. Tests sign boundary.",
    },
    {
        "name": "DEC from 0 to -1",
        "bytecode": [0x18, 0, 0, 0x09, 0, 0x00],
        "expected": {"register": 0, "value": -1},
        "category": "arithmetic",
        "notes": "DEC: R0 = 0 - 1 = -1. Tests underflow boundary.",
    },

    # =========================================================================
    # Category: Complex Programs (source-description only — need compiler)
    # =========================================================================
    {
        "name": "GCD of 48 and 18 = 6 (Euclid's algorithm)",
        "bytecode": None,
        "expected": {"register": 0, "value": 6},
        "category": "complex",
        "notes": "Classic GCD algorithm. Tests LOOP, CMP, conditional jump, modulo.",
        "source_description": """
        MOVI R0, 48      ; a = 48
        MOVI R1, 18      ; b = 18
        loop:
        CMP_EQ R2, R0, R1
        JNZ R2, done
        CMP_GT R2, R0, R1
        JNZ R2, a_sub
        MOD R2, R1, R0
        MOV R1, R2
        JMP loop
        a_sub:
        MOD R2, R0, R1
        MOV R0, R2
        JMP loop
        done:
        HALT
        """,
    },
    {
        "name": "Fibonacci(10) = 55",
        "bytecode": None,
        "expected": {"register": 0, "value": 55},
        "category": "complex",
        "notes": "Computes the 10th Fibonacci number. Tests loop, MOV, ADD, CMP.",
        "source_description": """
        MOVI R0, 0
        MOVI R1, 1
        MOVI R2, 10
        MOVI R3, 1
        loop:
        ADD R4, R0, R1
        MOV R0, R1
        MOV R1, R4
        INC R3
        CMP_LT R4, R3, R2
        JNZ R4, loop
        HALT
        """,
    },
    {
        "name": "Sum of squares 1..5 = 55",
        "bytecode": None,
        "expected": {"register": 0, "value": 55},
        "category": "complex",
        "notes": "Computes 1^2 + 2^2 + 3^2 + 4^2 + 5^2 = 55.",
        "source_description": """
        MOVI R0, 0
        MOVI R1, 1
        MOVI R2, 5
        loop:
        MUL R3, R1, R1
        ADD R0, R0, R3
        INC R1
        CMP_LT R3, R1, R2
        JNZ R3, loop
        HALT
        """,
    },
]
