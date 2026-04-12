/*
 * flux_vm_unified.c — FLUX Unified ISA Interpreter (C Reference Implementation)
 *
 * Standalone C implementation of the converged FLUX ISA for cross-runtime
 * conformance testing. Matches the Python unified_interpreter.py behavior
 * exactly for all 20 conformance test vectors.
 *
 * Instruction encoding formats:
 *   Format A (1 byte):  [op]
 *   Format B (2 bytes): [op][rd]
 *   Format C (2 bytes): [op][imm8]
 *   Format D (3 bytes): [op][rd][imm8]           (sign-extended)
 *   Format E (4 bytes): [op][rd][rs1][rs2]
 *   Format F (4 bytes): [op][rd][imm16hi][imm16lo]
 *   Format G (5 bytes): [op][rd][rs1][imm16hi][imm16lo]
 *
 * Build:  gcc -O2 -Wall -o flux_vm_unified flux_vm_unified.c
 * Usage:  ./flux_vm_unified [bytecode_file | -]   (stdin if no file or "-")
 *         echo -ne '\x01\x00' | ./flux_vm_unified
 *
 * Author: Super Z (C runtime)
 * Date:   2026-04-12
 * License: MIT
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

/* ── Configuration ─────────────────────────────────────────────────────────── */

#define NUM_REGISTERS    16
#define MEMORY_SIZE      65536   /* 64 KB, matching Python VM */
#define STACK_CAPACITY   4096
#define MAX_CYCLES       10000000
#define MAX_BYTECODE     (1 << 20)  /* 1 MB max bytecode */

/* ── Opcode Constants ──────────────────────────────────────────────────────── */

/* Format A — System Control (0x00-0x03) */
#define OP_HALT   0x00
#define OP_NOP    0x01
#define OP_RET    0x02
#define OP_IRET   0x03

/* Format A — Interrupt/Debug (0x04-0x07) */
#define OP_BRK    0x04
#define OP_WFI    0x05
#define OP_RESET  0x06
#define OP_SYN    0x07

/* Format B — Single Register (0x08-0x0F) */
#define OP_INC     0x08
#define OP_DEC     0x09
#define OP_NOT     0x0A
#define OP_NEG     0x0B
#define OP_PUSH    0x0C
#define OP_POP     0x0D
#define OP_CONF_LD 0x0E
#define OP_CONF_ST 0x0F

/* Format C — Immediate Only (0x10-0x17) */
#define OP_SYS     0x10
#define OP_TRAP    0x11
#define OP_DBG     0x12
#define OP_CLF     0x13
#define OP_SEMA    0x14
#define OP_YIELD   0x15
#define OP_CACHE   0x16
#define OP_STRIPCF 0x17

/* Format D — Register + imm8 (0x18-0x1F) */
#define OP_MOVI   0x18
#define OP_ADDI   0x19
#define OP_SUBI   0x1A
#define OP_ANDI   0x1B
#define OP_ORI    0x1C
#define OP_XORI   0x1D
#define OP_SHLI   0x1E
#define OP_SHRI   0x1F

/* Format E — Integer Arithmetic (0x20-0x2F) */
#define OP_ADD    0x20
#define OP_SUB    0x21
#define OP_MUL    0x22
#define OP_DIV    0x23
#define OP_MOD    0x24
#define OP_AND    0x25
#define OP_OR     0x26
#define OP_XOR    0x27
#define OP_SHL    0x28
#define OP_SHR    0x29
#define OP_MIN    0x2A
#define OP_MAX    0x2B
#define OP_CMP_EQ 0x2C
#define OP_CMP_LT 0x2D
#define OP_CMP_GT 0x2E
#define OP_CMP_NE 0x2F

/* Format E — Float / Memory / Control (0x30-0x3F) */
#define OP_FADD   0x30
#define OP_FSUB   0x31
#define OP_FMUL   0x32
#define OP_FDIV   0x33
#define OP_FMIN   0x34
#define OP_FMAX   0x35
#define OP_FTOI   0x36
#define OP_ITOF   0x37
#define OP_LOAD   0x38
#define OP_STORE  0x39
#define OP_MOV    0x3A
#define OP_SWP    0x3B
#define OP_JZ_E   0x3C
#define OP_JNZ_E  0x3D
#define OP_JLT    0x3E
#define OP_JGT    0x3F

/* Format F — Register + imm16 (0x40-0x47) */
#define OP_MOVI16  0x40
#define OP_ADDI16  0x41
#define OP_SUBI16  0x42
#define OP_JMP     0x43
#define OP_JAL     0x44
#define OP_CALL_F  0x45
#define OP_LOOP    0x46
#define OP_SELECT  0x47

/* Format G — Register + register + imm16 (0x48-0x4F) */
#define OP_LOADOFF  0x48
#define OP_STOREOFF 0x49
#define OP_LOADI    0x4A
#define OP_STOREI   0x4B
#define OP_ENTER_G  0x4C
#define OP_LEAVE_G  0x4D
#define OP_COPY_G   0x4E
#define OP_FILL_G   0x4F

/* ── VM State ──────────────────────────────────────────────────────────────── */

typedef struct {
    /* Register file R0-R15 — use int64_t to match Python arbitrary precision */
    int64_t regs[NUM_REGISTERS];
    int64_t confidence[NUM_REGISTERS];

    /* Condition flags */
    int flag_zero;
    int flag_sign;

    /* Program counter */
    uint32_t pc;

    /* Stack */
    int64_t stack[STACK_CAPACITY];
    uint32_t sp;  /* stack pointer (number of items) */

    /* Linear memory */
    uint8_t memory[MEMORY_SIZE];

    /* Execution state */
    int halted;
    int crashed;
    uint64_t cycle_count;

    /* Bytecode */
    uint8_t *bytecode;
    uint32_t bytecode_len;

    /* Trace mode */
    int trace;
} flux_vm_t;

/* ── Helper: opcode name for tracing ───────────────────────────────────────── */

static const char *opcode_name(uint8_t op) {
    switch (op) {
    case OP_HALT:   return "HALT";
    case OP_NOP:    return "NOP";
    case OP_RET:    return "RET";
    case OP_IRET:   return "IRET";
    case OP_BRK:    return "BRK";
    case OP_WFI:    return "WFI";
    case OP_RESET:  return "RESET";
    case OP_SYN:    return "SYN";
    case OP_INC:    return "INC";
    case OP_DEC:    return "DEC";
    case OP_NOT:    return "NOT";
    case OP_NEG:    return "NEG";
    case OP_PUSH:   return "PUSH";
    case OP_POP:    return "POP";
    case OP_CONF_LD: return "CONF_LD";
    case OP_CONF_ST: return "CONF_ST";
    case OP_MOVI:   return "MOVI";
    case OP_ADDI:   return "ADDI";
    case OP_SUBI:   return "SUBI";
    case OP_ANDI:   return "ANDI";
    case OP_ORI:    return "ORI";
    case OP_XORI:   return "XORI";
    case OP_SHLI:   return "SHLI";
    case OP_SHRI:   return "SHRI";
    case OP_ADD:    return "ADD";
    case OP_SUB:    return "SUB";
    case OP_MUL:    return "MUL";
    case OP_DIV:    return "DIV";
    case OP_MOD:    return "MOD";
    case OP_AND:    return "AND";
    case OP_OR:     return "OR";
    case OP_XOR:    return "XOR";
    case OP_SHL:    return "SHL";
    case OP_SHR:    return "SHR";
    case OP_MIN:    return "MIN";
    case OP_MAX:    return "MAX";
    case OP_CMP_EQ: return "CMP_EQ";
    case OP_CMP_LT: return "CMP_LT";
    case OP_CMP_GT: return "CMP_GT";
    case OP_CMP_NE: return "CMP_NE";
    case OP_FADD:   return "FADD";
    case OP_FSUB:   return "FSUB";
    case OP_FMUL:   return "FMUL";
    case OP_FDIV:   return "FDIV";
    case OP_FMIN:   return "FMIN";
    case OP_FMAX:   return "FMAX";
    case OP_FTOI:   return "FTOI";
    case OP_ITOF:   return "ITOF";
    case OP_LOAD:   return "LOAD";
    case OP_STORE:  return "STORE";
    case OP_MOV:    return "MOV";
    case OP_SWP:    return "SWP";
    case OP_JZ_E:   return "JZ";
    case OP_JNZ_E:  return "JNZ";
    case OP_JLT:    return "JLT";
    case OP_JGT:    return "JGT";
    case OP_MOVI16: return "MOVI16";
    case OP_ADDI16: return "ADDI16";
    case OP_SUBI16: return "SUBI16";
    case OP_JMP:    return "JMP";
    case OP_JAL:    return "JAL";
    case OP_CALL_F: return "CALL";
    case OP_LOOP:   return "LOOP";
    case OP_SELECT: return "SELECT";
    case OP_LOADOFF: return "LOADOFF";
    case OP_STOREOFF: return "STOREOFF";
    case OP_LOADI:  return "LOADI";
    case OP_STOREI: return "STOREI";
    case OP_ENTER_G: return "ENTER";
    case OP_LEAVE_G: return "LEAVE";
    default:        return "UNKNOWN";
    }
}

/* ── VM Initialization ─────────────────────────────────────────────────────── */

static void vm_init(flux_vm_t *vm, uint8_t *bytecode, uint32_t len, int trace) {
    memset(vm, 0, sizeof(flux_vm_t));
    vm->bytecode = bytecode;
    vm->bytecode_len = len;
    vm->trace = trace;
}

/* ── Fetch helpers ─────────────────────────────────────────────────────────── */

static uint8_t fetch_u8(flux_vm_t *vm) {
    if (vm->pc >= vm->bytecode_len) {
        vm->crashed = 1;
        vm->halted = 1;
        return 0;
    }
    return vm->bytecode[vm->pc++];
}

static int8_t fetch_i8(flux_vm_t *vm) {
    uint8_t b = fetch_u8(vm);
    return (int8_t)b;  /* Sign extension via cast */
}

static uint16_t fetch_u16_be(flux_vm_t *vm) {
    uint8_t hi = fetch_u8(vm);
    uint8_t lo = fetch_u8(vm);
    return (uint16_t)((hi << 8) | lo);
}

/* ── Register access ───────────────────────────────────────────────────────── */

static int64_t rd(flux_vm_t *vm, uint8_t idx) {
    return vm->regs[idx & 0xF];
}

static void wr(flux_vm_t *vm, uint8_t idx, int64_t val) {
    vm->regs[idx & 0xF] = val;
}

/* ── Stack helpers ─────────────────────────────────────────────────────────── */

static void push(flux_vm_t *vm, int64_t val) {
    if (vm->sp >= STACK_CAPACITY) {
        vm->crashed = 1;
        vm->halted = 1;
        return;
    }
    vm->stack[vm->sp++] = val;
}

static int64_t pop(flux_vm_t *vm) {
    if (vm->sp == 0) {
        vm->crashed = 1;
        vm->halted = 1;
        return 0;
    }
    return vm->stack[--vm->sp];
}

/* ── Flags ─────────────────────────────────────────────────────────────────── */

static void set_flags(flux_vm_t *vm, int64_t result) {
    vm->flag_zero = (result == 0);
    vm->flag_sign = (result < 0);
}

/* ── Memory helpers (little-endian int32) ──────────────────────────────────── */

static int32_t mem_read_i32(flux_vm_t *vm, int addr) {
    addr &= 0xFFFF;
    return (int32_t)(
        (uint32_t)vm->memory[addr]       |
        ((uint32_t)vm->memory[addr+1] << 8)  |
        ((uint32_t)vm->memory[addr+2] << 16) |
        ((uint32_t)vm->memory[addr+3] << 24)
    );
}

static void mem_write_i32(flux_vm_t *vm, int addr, int32_t val) {
    addr &= 0xFFFF;
    uint32_t uval = (uint32_t)val;
    vm->memory[addr]   = (uint8_t)(uval & 0xFF);
    vm->memory[addr+1] = (uint8_t)((uval >> 8) & 0xFF);
    vm->memory[addr+2] = (uint8_t)((uval >> 16) & 0xFF);
    vm->memory[addr+3] = (uint8_t)((uval >> 24) & 0xFF);
}

/* ── Instruction size (for CONF_THRESHOLD skip) ───────────────────────────── */

static int instruction_size(uint8_t op) {
    if (op <= 0x07) return 1;  /* Format A */
    if (op <= 0x0F) return 2;  /* Format B */
    if (op <= 0x17) return 2;  /* Format C */
    if (op <= 0x1F) return 3;  /* Format D */
    if (op <= 0x3F) return 4;  /* Format E */
    if (op <= 0x47) return 4;  /* Format F */
    if (op <= 0x4F) return 5;  /* Format G */
    if (op <= 0x68) return 4;  /* Format E (CONF_ variants) */
    if (op == 0x69) return 3;  /* Format D (CONF_THRESHOLD) */
    if (op <= 0x9F) return 4;  /* Format E (extended) */
    if (op <= 0xCF) return 4;  /* Format E (SIMD/tensor) */
    if (op <= 0xDF) return 5;  /* Format G (MMIO/GPU) */
    if (op <= 0xEF) return 4;  /* Format F (long jumps) */
    return 1;                  /* Format A (0xF0-0xFF) */
}

/* ── Single step ───────────────────────────────────────────────────────────── */

static void step(flux_vm_t *vm) {
    uint32_t start_pc = vm->pc;
    uint8_t op = fetch_u8(vm);

    if (vm->trace) {
        printf("  [%04X] %s (0x%02X)\n", start_pc, opcode_name(op), op);
    }

    int64_t val, v1, v2;

    /* ── Format A: System Control (0x00-0x03) ─────────────────────────────── */
    if (op == OP_HALT) {
        vm->halted = 1;
        return;
    }
    if (op == OP_NOP) {
        return;
    }
    if (op == OP_RET) {
        if (vm->sp > 0) {
            vm->pc = (uint32_t)pop(vm);
        } else {
            vm->halted = 1;
        }
        return;
    }
    if (op == OP_IRET) {
        vm->halted = 1;
        return;
    }

    /* ── Format A: Interrupt/Debug (0x04-0x07) ───────────────────────────── */
    if (op == OP_BRK) {
        vm->halted = 1;
        return;
    }
    if (op == OP_WFI || op == OP_RESET || op == OP_SYN) {
        return;  /* Stub: no-op */
    }

    /* ── Format B: Single Register (0x08-0x0F) ───────────────────────────── */
    if (op >= 0x08 && op <= 0x0F) {
        uint8_t r = fetch_u8(vm);
        switch (op) {
        case OP_INC:
            val = rd(vm, r) + 1;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_DEC:
            val = rd(vm, r) - 1;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_NOT:
            val = ~rd(vm, r);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_NEG:
            val = -rd(vm, r);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_PUSH:
            push(vm, rd(vm, r));
            break;
        case OP_POP:
            wr(vm, r, pop(vm));
            break;
        case OP_CONF_LD:
            wr(vm, r, vm->confidence[r & 0xF]);
            break;
        case OP_CONF_ST:
            vm->confidence[r & 0xF] = rd(vm, r);
            break;
        }
        return;
    }

    /* ── Format C: Immediate Only (0x10-0x17) ────────────────────────────── */
    if (op >= 0x10 && op <= 0x17) {
        fetch_u8(vm);  /* consume imm8 */
        /* All Format C ops are system/debug — stub as no-ops */
        return;
    }

    /* ── Format D: Register + imm8 (0x18-0x1F) ───────────────────────────── */
    if (op >= 0x18 && op <= 0x1F) {
        uint8_t r = fetch_u8(vm);
        int8_t imm = fetch_i8(vm);

        switch (op) {
        case OP_MOVI:
            wr(vm, r, (int64_t)imm);
            break;
        case OP_ADDI:
            val = rd(vm, r) + (int64_t)imm;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_SUBI:
            val = rd(vm, r) - (int64_t)imm;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_ANDI:
            val = rd(vm, r) & ((int64_t)imm & 0xFF);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_ORI:
            val = rd(vm, r) | ((int64_t)imm & 0xFF);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_XORI:
            val = rd(vm, r) ^ ((int64_t)imm & 0xFF);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_SHLI:
            val = rd(vm, r) << (imm & 0x1F);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_SHRI:
            val = rd(vm, r) >> (imm & 0x1F);
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        }
        return;
    }

    /* ── Format E: 3-register (0x20-0x3F) ────────────────────────────────── */
    if (op >= 0x20 && op <= 0x3F) {
        uint8_t r_dst = fetch_u8(vm);
        uint8_t r_s1  = fetch_u8(vm);
        uint8_t r_s2  = fetch_u8(vm);
        v1 = rd(vm, r_s1);
        v2 = rd(vm, r_s2);

        switch (op) {
        case OP_ADD:
            val = v1 + v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_SUB:
            val = v1 - v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_MUL:
            val = v1 * v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_DIV:
            if (v2 == 0) {
                vm->crashed = 1;
                vm->halted = 1;
                return;
            }
            val = v1 / v2;  /* C99 truncation toward zero, matches Python int(v1/v2) */
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_MOD:
            if (v2 == 0) {
                vm->crashed = 1;
                vm->halted = 1;
                return;
            }
            val = v1 - (v1 / v2) * v2;  /* Match Python: v1 - int(v1/v2)*v2 */
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_AND:
            val = v1 & v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_OR:
            val = v1 | v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_XOR:
            val = v1 ^ v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_SHL:
            val = v1 << (v2 & 0x1F);
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_SHR:
            val = v1 >> (v2 & 0x1F);
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_MIN:
            val = (v1 < v2) ? v1 : v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_MAX:
            val = (v1 > v2) ? v1 : v2;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_CMP_EQ:
            val = (v1 == v2) ? 1 : 0;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_CMP_LT:
            val = (v1 < v2) ? 1 : 0;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_CMP_GT:
            val = (v1 > v2) ? 1 : 0;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;
        case OP_CMP_NE:
            val = (v1 != v2) ? 1 : 0;
            wr(vm, r_dst, val);
            set_flags(vm, val);
            break;

        /* Float ops — convert to float, operate, convert back to int */
        case OP_FADD:
            wr(vm, r_dst, (int64_t)(float)v1 + (float)v2);
            break;
        case OP_FSUB:
            wr(vm, r_dst, (int64_t)(float)v1 - (float)v2);
            break;
        case OP_FMUL:
            wr(vm, r_dst, (int64_t)(float)v1 * (float)v2);
            break;
        case OP_FDIV:
            if (v2 == 0) { vm->crashed = 1; vm->halted = 1; return; }
            wr(vm, r_dst, (int64_t)((float)v1 / (float)v2));
            break;
        case OP_FMIN:
            val = (int64_t)(((float)v1 < (float)v2) ? v1 : v2);
            wr(vm, r_dst, val);
            break;
        case OP_FMAX:
            val = (int64_t)(((float)v1 > (float)v2) ? v1 : v2);
            wr(vm, r_dst, val);
            break;
        case OP_FTOI:
            wr(vm, r_dst, (int64_t)(float)v1);
            break;
        case OP_ITOF:
            wr(vm, r_dst, (int64_t)(float)v1);
            break;

        /* Memory */
        case OP_LOAD: {
            int addr = (int)((v1 + v2) & 0xFFFF);
            wr(vm, r_dst, (int64_t)mem_read_i32(vm, addr));
            break;
        }
        case OP_STORE: {
            int addr = (int)((v1 + v2) & 0xFFFF);
            mem_write_i32(vm, addr, (int32_t)rd(vm, r_dst));
            break;
        }

        /* Data movement */
        case OP_MOV:
            wr(vm, r_dst, v1);  /* rd = rs1, rs2 ignored */
            break;
        case OP_SWP: {
            int64_t tmp = rd(vm, r_dst);
            wr(vm, r_dst, v1);
            wr(vm, r_s1, tmp);
            break;
        }

        /* Conditional jumps — offset is VALUE of rs1 */
        case OP_JZ_E:
            if (rd(vm, r_dst) == 0) {
                vm->pc += (uint32_t)v1;
            }
            break;
        case OP_JNZ_E:
            if (rd(vm, r_dst) != 0) {
                vm->pc += (uint32_t)v1;
            }
            break;
        case OP_JLT:
            if (rd(vm, r_dst) < 0) {
                vm->pc += (uint32_t)v1;
            }
            break;
        case OP_JGT:
            if (rd(vm, r_dst) > 0) {
                vm->pc += (uint32_t)v1;
            }
            break;
        }
        return;
    }

    /* ── Format F: Register + imm16 (0x40-0x47) ──────────────────────────── */
    if (op >= 0x40 && op <= 0x47) {
        uint8_t r = fetch_u8(vm);
        uint16_t imm16 = fetch_u16_be(vm);
        int16_t signed_imm = (int16_t)imm16;

        switch (op) {
        case OP_MOVI16:
            wr(vm, r, (int64_t)signed_imm);
            break;
        case OP_ADDI16:
            val = rd(vm, r) + (int64_t)signed_imm;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_SUBI16:
            val = rd(vm, r) - (int64_t)signed_imm;
            wr(vm, r, val);
            set_flags(vm, val);
            break;
        case OP_JMP:
            vm->pc = (uint32_t)((int32_t)vm->pc + (int32_t)signed_imm);
            break;
        case OP_JAL:
            wr(vm, r, (int64_t)vm->pc);
            vm->pc = (uint32_t)((int32_t)vm->pc + (int32_t)signed_imm);
            break;
        case OP_CALL_F:
            push(vm, (int64_t)vm->pc);
            vm->pc = (uint32_t)((int64_t)rd(vm, r) + (int64_t)signed_imm);
            break;
        case OP_LOOP:
            val = rd(vm, r) - 1;
            wr(vm, r, val);
            if (val > 0) {
                vm->pc = (uint32_t)((int32_t)vm->pc - (int32_t)imm16);
            }
            break;
        case OP_SELECT:
            vm->pc = (uint32_t)((int64_t)vm->pc + (int64_t)signed_imm * rd(vm, r));
            break;
        }
        return;
    }

    /* ── Format G: Register + register + imm16 (0x48-0x4F) ───────────────── */
    if (op >= 0x48 && op <= 0x4F) {
        uint8_t r_dst = fetch_u8(vm);
        uint8_t r_s1  = fetch_u8(vm);
        uint16_t imm16 = fetch_u16_be(vm);
        int16_t signed_imm = (int16_t)imm16;
        int64_t base = rd(vm, r_s1);

        switch (op) {
        case OP_LOADOFF: {
            int addr = (int)((base + (int64_t)signed_imm) & 0xFFFF);
            wr(vm, r_dst, (int64_t)mem_read_i32(vm, addr));
            break;
        }
        case OP_STOREOFF: {
            int addr = (int)((base + (int64_t)signed_imm) & 0xFFFF);
            mem_write_i32(vm, addr, (int32_t)rd(vm, r_dst));
            break;
        }
        case OP_LOADI: {
            int inner_addr = (int)(base & 0xFFFF);
            int outer_addr = (int)((mem_read_i32(vm, inner_addr) + (int64_t)signed_imm) & 0xFFFF);
            wr(vm, r_dst, (int64_t)mem_read_i32(vm, outer_addr));
            break;
        }
        case OP_STOREI: {
            int inner_addr = (int)(base & 0xFFFF);
            int outer_addr = (int)((mem_read_i32(vm, inner_addr) + (int64_t)signed_imm) & 0xFFFF);
            mem_write_i32(vm, outer_addr, (int32_t)rd(vm, r_dst));
            break;
        }
        case OP_ENTER_G:
            push(vm, rd(vm, r_dst));
            wr(vm, r_dst, (int64_t)vm->sp);
            wr(vm, 14, (int64_t)vm->sp + (int64_t)signed_imm);  /* R14 as pseudo-SP */
            break;
        case OP_LEAVE_G:
            wr(vm, r_dst, pop(vm));
            break;
        case OP_COPY_G:
            /* Stub: memcpy */
            break;
        case OP_FILL_G:
            /* Stub: memset */
            break;
        }
        return;
    }

    /* ── Format E: A2A Fleet Ops (0x50-0x5F) — stub ─────────────────────── */
    if (op >= 0x50 && op <= 0x5F) {
        fetch_u8(vm); fetch_u8(vm); fetch_u8(vm);
        return;
    }

    /* ── Format E/D: Confidence-aware variants (0x60-0x6F) ──────────────── */
    if (op >= 0x60 && op <= 0x6F) {
        /* CONF_THRESHOLD (0x69) is Format D */
        if (op == 0x69) {
            uint8_t r = fetch_u8(vm);
            uint8_t imm8 = fetch_u8(vm);
            if (vm->confidence[r & 0xF] < (int64_t)imm8) {
                if (vm->pc < vm->bytecode_len) {
                    uint8_t next_op = vm->bytecode[vm->pc];
                    vm->pc += instruction_size(next_op);
                }
            }
            return;
        }

        /* All other CONF_ ops are Format E */
        uint8_t r_dst = fetch_u8(vm);
        uint8_t r_s1  = fetch_u8(vm);
        uint8_t r_s2  = fetch_u8(vm);
        v1 = rd(vm, r_s1);
        v2 = rd(vm, r_s2);
        int64_t c1 = vm->confidence[r_s1 & 0xF];
        int64_t c2 = vm->confidence[r_s2 & 0xF];

        switch (op) {
        case 0x60: /* C_ADD */
            wr(vm, r_dst, v1 + v2);
            vm->confidence[r_dst & 0xF] = (c1 < c2) ? c1 : c2;
            break;
        case 0x61: /* C_SUB */
            wr(vm, r_dst, v1 - v2);
            vm->confidence[r_dst & 0xF] = (c1 < c2) ? c1 : c2;
            break;
        case 0x62: /* C_MUL */
            wr(vm, r_dst, v1 * v2);
            vm->confidence[r_dst & 0xF] = c1 * c2;
            break;
        case 0x63: /* C_DIV */
            if (v2 != 0) {
                wr(vm, r_dst, v1 / v2);
                vm->confidence[r_dst & 0xF] = c1 * c2;
            }
            break;
        default:
            /* 0x64-0x6F: stub */
            break;
        }
        return;
    }

    /* ── Extended opcodes (0x70+) — consume bytes and stub ───────────────── */
    if (op >= 0x70) {
        if (op <= 0x9F) {
            /* Format E: consume 3 more bytes */
            fetch_u8(vm); fetch_u8(vm); fetch_u8(vm);
        } else if (op <= 0xA0) {
            /* Format D: consume 2 more bytes */
            fetch_u8(vm); fetch_u8(vm);
        } else if (op <= 0xCF) {
            /* Format E: consume 3 more bytes */
            fetch_u8(vm); fetch_u8(vm); fetch_u8(vm);
        } else if (op <= 0xDF) {
            /* Format G: consume 4 more bytes */
            fetch_u8(vm); fetch_u8(vm); fetch_u8(vm); fetch_u8(vm);
        } else if (op <= 0xEF) {
            /* Format F: consume 3 more bytes */
            fetch_u8(vm); fetch_u8(vm); fetch_u8(vm);
        }
        /* 0xF0-0xFF: Format A, no extra bytes */
        return;
    }

    /* Unknown opcode */
    vm->crashed = 1;
    vm->halted = 1;
}

/* ── Main execution loop ───────────────────────────────────────────────────── */

static int vm_execute(flux_vm_t *vm) {
    while (!vm->halted && vm->cycle_count < MAX_CYCLES) {
        step(vm);
        vm->cycle_count++;
    }

    return vm->crashed ? 1 : 0;
}

/* ── Output VM state ───────────────────────────────────────────────────────── */

static void vm_print_state(flux_vm_t *vm) {
    printf("halted=%d crashed=%d cycles=%llu stack_depth=%u\n",
           vm->halted, vm->crashed,
           (unsigned long long)vm->cycle_count, vm->sp);

    for (int i = 0; i < NUM_REGISTERS; i++) {
        printf("R%d=%lld", i, (long long)vm->regs[i]);
        if (i < NUM_REGISTERS - 1) printf(" ");
    }
    printf("\n");
}

/* ── Read bytecode from file or stdin ──────────────────────────────────────── */

static uint8_t *read_bytecode(const char *path, uint32_t *out_len) {
    FILE *f;
    int use_stdin = (path == NULL || strcmp(path, "-") == 0);

    if (use_stdin) {
        f = stdin;
#ifdef _WIN32
        _setmode(_fileno(stdin), _O_BINARY);
#endif
    } else {
        f = fopen(path, "rb");
        if (!f) {
            fprintf(stderr, "Error: cannot open '%s'\n", path);
            return NULL;
        }
    }

    uint8_t *buf = malloc(MAX_BYTECODE);
    if (!buf) {
        fprintf(stderr, "Error: out of memory\n");
        if (!use_stdin) fclose(f);
        return NULL;
    }

    size_t n = fread(buf, 1, MAX_BYTECODE, f);
    if (ferror(f)) {
        fprintf(stderr, "Error: read failure\n");
        free(buf);
        if (!use_stdin) fclose(f);
        return NULL;
    }

    if (!use_stdin) fclose(f);
    *out_len = (uint32_t)n;
    return buf;
}

/* ── Main ──────────────────────────────────────────────────────────────────── */

int main(int argc, char **argv) {
    const char *input_path = NULL;
    int trace = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-t") == 0 || strcmp(argv[i], "--trace") == 0) {
            trace = 1;
        } else {
            input_path = argv[i];
        }
    }

    uint32_t bytecode_len = 0;
    uint8_t *bytecode = read_bytecode(input_path, &bytecode_len);
    if (!bytecode) {
        return 1;
    }

    flux_vm_t vm;
    vm_init(&vm, bytecode, bytecode_len, trace);

    int result = vm_execute(&vm);

    vm_print_state(&vm);

    free(bytecode);
    return result;
}
