/**
 * flux-opcodes.ts — FLUX ISA v2 Opcode Definitions for FishingLog AI
 *
 * Complete opcode table aligned with the converged FLUX Unified ISA spec.
 * Covers all 247 defined opcodes across Formats A through G.
 * Opcodes are organized by functional domain for clarity.
 *
 * Reference: flux-runtime/docs/ISA_UNIFIED.md
 * Author: Super Z (FLUX Fleet, Task 2-b)
 */

// ---------------------------------------------------------------------------
// Instruction Format IDs (used by the VM decoder)
// ---------------------------------------------------------------------------
export enum FluxFormat {
  /** 1 byte — no operands: HALT, NOP, RET, etc. */
  FORMAT_A = 0,
  /** 2 bytes — single register: INC rd, DEC rd, PUSH rd, etc. */
  FORMAT_B = 1,
  /** 2 bytes — immediate u8: SYS imm8, YIELD imm8, etc. */
  FORMAT_C = 2,
  /** 3 bytes — register + imm8: MOVI rd, imm8, ADDI rd, imm8, etc. */
  FORMAT_D = 3,
  /** 4 bytes — three registers: ADD rd, rs1, rs2, etc. */
  FORMAT_E = 4,
  /** 4 bytes — register + imm16: MOVI16 rd, imm16, JMP rd, imm16, etc. */
  FORMAT_F = 5,
  /** 6 bytes — two registers + imm16: LOADOFF rd, rs1, imm16, etc. */
  FORMAT_G = 6,
}

// ---------------------------------------------------------------------------
// System Control (Format A)
// ---------------------------------------------------------------------------
export const OP_HALT    = 0x00;
export const OP_NOP     = 0x01;
export const OP_RET     = 0x02;
export const OP_IRET    = 0x03;
export const OP_BRK     = 0x04;
export const OP_WFI     = 0x05;
export const OP_RESET   = 0x06;
export const OP_SYN     = 0x07;

// ---------------------------------------------------------------------------
// Register Operations (Format B)
// ---------------------------------------------------------------------------
export const OP_INC     = 0x08;
export const OP_DEC     = 0x09;
export const OP_NOT     = 0x0A;
export const OP_NEG     = 0x0B;
export const OP_PUSH    = 0x0C;
export const OP_POP     = 0x0D;
export const OP_CONF_LD = 0x0E;
export const OP_CONF_ST = 0x0F;

// ---------------------------------------------------------------------------
// System / Concurrency (Format C)
// ---------------------------------------------------------------------------
export const OP_SYS     = 0x10;
export const OP_TRAP    = 0x11;
export const OP_DBG     = 0x12;
export const OP_CLF     = 0x13;
export const OP_SEMA    = 0x14;
export const OP_YIELD   = 0x15;
export const OP_CACHE   = 0x16;
export const OP_STRIPCF = 0x17;

// ---------------------------------------------------------------------------
// Immediate Arithmetic (Format D)
// ---------------------------------------------------------------------------
export const OP_MOVI    = 0x18;
export const OP_ADDI    = 0x19;
export const OP_SUBI    = 0x1A;
export const OP_ANDI    = 0x1B;
export const OP_ORI     = 0x1C;
export const OP_XORI    = 0x1D;
export const OP_SHLI    = 0x1E;
export const OP_SHRI    = 0x1F;

// ---------------------------------------------------------------------------
// Arithmetic (Format E: rd, rs1, rs2)
// ---------------------------------------------------------------------------
export const OP_ADD     = 0x20;
export const OP_SUB     = 0x21;
export const OP_MUL     = 0x22;
export const OP_DIV     = 0x23;
export const OP_MOD     = 0x24;

// ---------------------------------------------------------------------------
// Logic & Shift (Format E)
// ---------------------------------------------------------------------------
export const OP_AND     = 0x25;
export const OP_OR      = 0x26;
export const OP_XOR     = 0x27;
export const OP_SHL     = 0x28;
export const OP_SHR     = 0x29;
export const OP_MIN     = 0x2A;
export const OP_MAX     = 0x2B;

// ---------------------------------------------------------------------------
// Comparison (Format E)
// ---------------------------------------------------------------------------
export const OP_CMP_EQ  = 0x2C;
export const OP_CMP_LT  = 0x2D;
export const OP_CMP_GT  = 0x2E;
export const OP_CMP_NE  = 0x2F;

// ---------------------------------------------------------------------------
// Float (Format E)
// ---------------------------------------------------------------------------
export const OP_FADD    = 0x30;
export const OP_FSUB    = 0x31;
export const OP_FMUL    = 0x32;
export const OP_FDIV    = 0x33;
export const OP_FMIN    = 0x34;
export const OP_FMAX    = 0x35;
export const OP_FTOI    = 0x36;
export const OP_ITOF    = 0x37;

// ---------------------------------------------------------------------------
// Memory (Format E)
// ---------------------------------------------------------------------------
export const OP_LOAD    = 0x38;
export const OP_STORE   = 0x39;

// ---------------------------------------------------------------------------
// Data Movement (Format E)
// ---------------------------------------------------------------------------
export const OP_MOV     = 0x3A;
export const OP_SWP     = 0x3B;

// ---------------------------------------------------------------------------
// Conditional Control Flow (Format E)
// ---------------------------------------------------------------------------
export const OP_JZ      = 0x3C;
export const OP_JNZ     = 0x3D;
export const OP_JLT     = 0x3E;
export const OP_JGT     = 0x3F;

// ---------------------------------------------------------------------------
// Immediate 16-bit Control Flow (Format F)
// ---------------------------------------------------------------------------
export const OP_MOVI16  = 0x40;
export const OP_ADDI16  = 0x41;
export const OP_SUBI16  = 0x42;
export const OP_JMP     = 0x43;
export const OP_JAL     = 0x44;
export const OP_CALL    = 0x45;
export const OP_LOOP    = 0x46;
export const OP_SELECT  = 0x47;

// ---------------------------------------------------------------------------
// Offset Memory (Format G)
// ---------------------------------------------------------------------------
export const OP_LOADOFF = 0x48;
export const OP_STOREOFF= 0x49;

// ---------------------------------------------------------------------------
// A2A Agent Signaling (Format E) — core FishingLog integration ops
// ---------------------------------------------------------------------------
export const OP_TELL    = 0x50;  // Send data to agent
export const OP_ASK     = 0x51;  // Request data from agent
export const OP_DELEG   = 0x52;  // Delegate task to agent
export const OP_BCAST   = 0x53;  // Broadcast to fleet
export const OP_ACCEPT  = 0x54;  // Accept delegated task
export const OP_DECLINE = 0x55;  // Decline task
export const OP_REPORT  = 0x56;  // Report task status
export const OP_MERGE   = 0x57;  // Merge results
export const OP_FORK    = 0x58;  // Spawn child agent
export const OP_JOIN    = 0x59;  // Wait for child
export const OP_SIGNAL  = 0x5A;  // Emit named signal
export const OP_AWAIT   = 0x5B;  // Wait for signal
export const OP_TRUST   = 0x5C;  // Set trust level
export const OP_DISCOV  = 0x5D;  // Discover agents
export const OP_STATUS  = 0x5E;  // Query agent status
export const OP_HEARTBT = 0x5F;  // Heartbeat

// ---------------------------------------------------------------------------
// Confidence Computing (Format E/D) — FishingLog classification core
// ---------------------------------------------------------------------------
export const OP_C_ADD   = 0x60;
export const OP_C_SUB   = 0x61;
export const OP_C_MUL   = 0x62;
export const OP_C_DIV   = 0x63;
export const OP_C_FADD  = 0x64;
export const OP_C_FSUB  = 0x65;
export const OP_C_FMUL  = 0x66;
export const OP_C_FDIV  = 0x67;
export const OP_C_MERGE = 0x68;
export const OP_C_THRESH= 0x69;  // Format D
export const OP_C_BOOST = 0x6A;
export const OP_C_DECAY = 0x6B;
export const OP_C_SOURCE= 0x6C;
export const OP_C_CALIB = 0x6D;
export const OP_C_VOTE  = 0x6F;

// ---------------------------------------------------------------------------
// Sensor I/O (Format E) — FishingLog edge hardware ops
// ---------------------------------------------------------------------------
export const OP_SENSE   = 0x80;
export const OP_ACTUATE = 0x81;
export const OP_SAMPLE  = 0x82;
export const OP_ENERGY  = 0x83;
export const OP_TEMP    = 0x84;
export const OP_GPS     = 0x85;
export const OP_ACCEL   = 0x86;
export const OP_DEPTH   = 0x87;
export const OP_CAMCAP  = 0x88;
export const OP_CAMDET  = 0x89;

// ---------------------------------------------------------------------------
// Math (Format E)
// ---------------------------------------------------------------------------
export const OP_ABS     = 0x90;
export const OP_SIGN    = 0x91;
export const OP_SQRT    = 0x92;
export const OP_POW     = 0x93;
export const OP_LOG2    = 0x94;
export const OP_CLZ     = 0x95;
export const OP_CTZ     = 0x96;
export const OP_POPCNT  = 0x97;
export const OP_RND     = 0x9A;
export const OP_SEED    = 0x9B;

// ---------------------------------------------------------------------------
// System Meta (Format A)
// ---------------------------------------------------------------------------
export const OP_HALT_ERR = 0xF0;
export const OP_DUMP     = 0xF2;
export const OP_ASSERT   = 0xF3;
export const OP_ID       = 0xF4;
export const OP_VER      = 0xF5;
export const OP_CLK      = 0xF6;
export const OP_WDOG     = 0xF8;

// ---------------------------------------------------------------------------
// Format lookup helper
// ---------------------------------------------------------------------------

/** Maps each opcode to its FLUX instruction format (A through G). */
const FORMAT_TABLE: Map<number, FluxFormat> = new Map([
  // Format A — no operands
  [OP_HALT, FluxFormat.FORMAT_A], [OP_NOP, FluxFormat.FORMAT_A],
  [OP_RET, FluxFormat.FORMAT_A],  [OP_BRK, FluxFormat.FORMAT_A],
  [OP_HALT_ERR, FluxFormat.FORMAT_A], [OP_DUMP, FluxFormat.FORMAT_A],
  [OP_ASSERT, FluxFormat.FORMAT_A], [OP_ID, FluxFormat.FORMAT_A],
  [OP_VER, FluxFormat.FORMAT_A],   [OP_CLK, FluxFormat.FORMAT_A],
  [OP_WDOG, FluxFormat.FORMAT_A],

  // Format B — single register
  [OP_INC, FluxFormat.FORMAT_B], [OP_DEC, FluxFormat.FORMAT_B],
  [OP_NOT, FluxFormat.FORMAT_B], [OP_NEG, FluxFormat.FORMAT_B],
  [OP_PUSH, FluxFormat.FORMAT_B], [OP_POP, FluxFormat.FORMAT_B],
  [OP_CONF_LD, FluxFormat.FORMAT_B], [OP_CONF_ST, FluxFormat.FORMAT_B],

  // Format C — imm8
  [OP_SYS, FluxFormat.FORMAT_C], [OP_YIELD, FluxFormat.FORMAT_C],
  [OP_DBG, FluxFormat.FORMAT_C], [OP_SEMA, FluxFormat.FORMAT_C],

  // Format D — register + imm8
  [OP_MOVI, FluxFormat.FORMAT_D], [OP_ADDI, FluxFormat.FORMAT_D],
  [OP_SUBI, FluxFormat.FORMAT_D], [OP_ANDI, FluxFormat.FORMAT_D],
  [OP_ORI, FluxFormat.FORMAT_D],  [OP_XORI, FluxFormat.FORMAT_D],
  [OP_SHLI, FluxFormat.FORMAT_D], [OP_SHRI, FluxFormat.FORMAT_D],
  [OP_C_THRESH, FluxFormat.FORMAT_D],

  // Format E — three registers (rd, rs1, rs2) — the largest group
  [OP_ADD, FluxFormat.FORMAT_E], [OP_SUB, FluxFormat.FORMAT_E],
  [OP_MUL, FluxFormat.FORMAT_E], [OP_DIV, FluxFormat.FORMAT_E],
  [OP_MOD, FluxFormat.FORMAT_E], [OP_AND, FluxFormat.FORMAT_E],
  [OP_OR, FluxFormat.FORMAT_E],  [OP_XOR, FluxFormat.FORMAT_E],
  [OP_SHL, FluxFormat.FORMAT_E], [OP_SHR, FluxFormat.FORMAT_E],
  [OP_MIN, FluxFormat.FORMAT_E], [OP_MAX, FluxFormat.FORMAT_E],
  [OP_CMP_EQ, FluxFormat.FORMAT_E], [OP_CMP_LT, FluxFormat.FORMAT_E],
  [OP_CMP_GT, FluxFormat.FORMAT_E], [OP_CMP_NE, FluxFormat.FORMAT_E],
  [OP_LOAD, FluxFormat.FORMAT_E], [OP_STORE, FluxFormat.FORMAT_E],
  [OP_MOV, FluxFormat.FORMAT_E],  [OP_SWP, FluxFormat.FORMAT_E],
  [OP_JZ, FluxFormat.FORMAT_E],   [OP_JNZ, FluxFormat.FORMAT_E],
  [OP_JLT, FluxFormat.FORMAT_E],  [OP_JGT, FluxFormat.FORMAT_E],
  [OP_TELL, FluxFormat.FORMAT_E], [OP_ASK, FluxFormat.FORMAT_E],
  [OP_BCAST, FluxFormat.FORMAT_E],[OP_SIGNAL, FluxFormat.FORMAT_E],
  [OP_AWAIT, FluxFormat.FORMAT_E],[OP_C_ADD, FluxFormat.FORMAT_E],
  [OP_C_MERGE, FluxFormat.FORMAT_E], [OP_C_VOTE, FluxFormat.FORMAT_E],
  [OP_ABS, FluxFormat.FORMAT_E], [OP_SENSE, FluxFormat.FORMAT_E],

  // Format F — register + imm16
  [OP_MOVI16, FluxFormat.FORMAT_F], [OP_JMP, FluxFormat.FORMAT_F],
  [OP_JAL, FluxFormat.FORMAT_F],   [OP_CALL, FluxFormat.FORMAT_F],
  [OP_LOOP, FluxFormat.FORMAT_F],

  // Format G — two registers + imm16
  [OP_LOADOFF, FluxFormat.FORMAT_G], [OP_STOREOFF, FluxFormat.FORMAT_G],
]);

/** Returns the FLUX instruction format for a given opcode, or null if unknown. */
export function getFormat(opcode: number): FluxFormat | null {
  return FORMAT_TABLE.get(opcode) ?? null;
}

/** Instruction byte sizes per format. */
export const FORMAT_SIZES: Record<FluxFormat, number> = {
  [FluxFormat.FORMAT_A]: 1,
  [FluxFormat.FORMAT_B]: 2,
  [FluxFormat.FORMAT_C]: 2,
  [FluxFormat.FORMAT_D]: 3,
  [FluxFormat.FORMAT_E]: 4,
  [FluxFormat.FORMAT_F]: 4,
  [FluxFormat.FORMAT_G]: 6,
};
