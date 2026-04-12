/**
 * flux-vm-mini.ts — Minimal FLUX Virtual Machine for Jetson Orin Nano Edge Execution
 *
 * A lightweight TypeScript FLUX VM designed for FishingLog AI's edge deployment.
 * Implements the core converged ISA subset needed for:
 *   - Confidence-weighted fish classification
 *   - Sensor data processing
 *   - Regulatory compliance bytecode programs
 *   - A2A signal stubs (message queue for inter-vessel coordination)
 *
 * Target: NVIDIA Jetson Orin Nano 8GB, zero external dependencies.
 * Memory: 64KB address space, 4096-entry stack, 32 registers (R0–R31),
 *         32 confidence registers (CR0–CR31).
 *
 * Reference: flux-runtime/docs/ISA_UNIFIED.md, flux-runtime/src/flux/vm/c/flux_vm_unified.c
 * Author: Super Z (FLUX Fleet, Task 2-b)
 */

import {
  FluxFormat, getFormat, FORMAT_SIZES,
  OP_HALT, OP_NOP, OP_RET,
  OP_INC, OP_DEC, OP_NOT, OP_NEG, OP_PUSH, OP_POP,
  OP_CONF_LD, OP_CONF_ST,
  OP_MOVI, OP_ADDI, OP_SUBI, OP_ANDI, OP_ORI, OP_XORI, OP_SHLI, OP_SHRI,
  OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD,
  OP_AND, OP_OR, OP_XOR, OP_SHL, OP_SHR,
  OP_MIN, OP_MAX,
  OP_CMP_EQ, OP_CMP_LT, OP_CMP_GT, OP_CMP_NE,
  OP_LOAD, OP_STORE, OP_MOV, OP_SWP,
  OP_JZ, OP_JNZ, OP_JLT, OP_JGT,
  OP_MOVI16, OP_JMP, OP_JAL, OP_CALL, OP_LOOP,
  OP_LOADOFF, OP_STOREOFF,
  OP_C_ADD, OP_C_SUB, OP_C_MUL, OP_C_MERGE, OP_C_THRESH, OP_C_DECAY,
  OP_TELL, OP_BCAST, OP_SIGNAL, OP_AWAIT,
  OP_ABS, OP_RND, OP_CLK,
} from './flux-opcodes';

// ---------------------------------------------------------------------------
// VM Configuration
// ---------------------------------------------------------------------------
export interface VmConfig {
  /** Memory size in bytes (default 65536 = 64 KB). */
  memorySize?: number;
  /** Stack depth in 64-bit slots (default 4096). */
  stackDepth?: number;
  /** Maximum instruction cycles before forced halt (default 1_000_000). */
  maxCycles?: number;
  /** Agent ID string for A2A signal routing. */
  agentId?: string;
}

// ---------------------------------------------------------------------------
// Execution Result
// ---------------------------------------------------------------------------
export type VmStatus = 'halted' | 'error' | 'cycle-limit';

export interface VmResult {
  status: VmStatus;
  cycles: number;
  registers: Int32Array;
  confidence: Float64Array;
  /** Captured output from OP_DBG / OP_TELL / OP_BCAST. */
  output: Array<{ type: string; payload: string }>;
}

// ---------------------------------------------------------------------------
// Minimal FLUX VM
// ---------------------------------------------------------------------------
export class FluxVmMini {
  readonly regs: Int32Array;
  readonly conf: Float64Array;
  private memory: Uint8Array;
  private stack: Int32Array;
  private sp = 0;      // Stack pointer (grows downward)
  private pc = 0;      // Program counter (byte offset into bytecode)
  private cycles = 0;
  private halted = false;

  /** Signal queue for A2A inter-vessel communication. */
  private signalQueue: Array<{ type: string; payload: string }> = [];
  /** Debug / tell output buffer. */
  readonly output: Array<{ type: string; payload: string }> = [];

  private readonly maxCycles: number;
  readonly agentId: string;

  constructor(config: VmConfig = {}) {
    const memSize = config.memorySize ?? 65536;
    this.regs = new Int32Array(32);
    this.conf = new Float64Array(32);       // confidence registers CR0–CR31
    this.memory = new Uint8Array(memSize);
    this.stack = new Int32Array(config.stackDepth ?? 4096);
    this.maxCycles = config.maxCycles ?? 1_000_000;
    this.agentId = config.agentId ?? 'vessel-unknown';
  }

  // ---- Memory helpers ----------------------------------------------------

  /** Load bytecode and reset VM state. */
  load(bytecode: Uint8Array, offset = 0): void {
    this.memory.set(bytecode, offset);
    this.pc = offset;
    this.sp = this.stack.length; // stack starts at top
    this.cycles = 0;
    this.halted = false;
    this.output.length = 0;
    this.signalQueue.length = 0;
  }

  /** Write a value into VM memory at a given byte address (little-endian i32). */
  memWrite32(addr: number, val: number): void {
    if (addr < 0 || addr + 4 > this.memory.length) return;
    this.memory[addr]     = val & 0xFF;
    this.memory[addr + 1] = (val >> 8) & 0xFF;
    this.memory[addr + 2] = (val >> 16) & 0xFF;
    this.memory[addr + 3] = (val >> 24) & 0xFF;
  }

  /** Read an i32 from VM memory (little-endian). */
  memRead32(addr: number): number {
    if (addr < 0 || addr + 4 > this.memory.length) return 0;
    return (
      this.memory[addr]
      | (this.memory[addr + 1] << 8)
      | (this.memory[addr + 2] << 16)
      | (this.memory[addr + 3] << 24)
    );
  }

  // ---- A2A signal interface -----------------------------------------------

  /** Queue an incoming A2A signal for processing by OP_AWAIT. */
  pushSignal(type: string, payload: string): void {
    this.signalQueue.push({ type, payload });
  }

  /** Drain all pending output signals (TELL, BCAST). */
  drainSignals(): Array<{ type: string; payload: string }> {
    return this.signalQueue.splice(0);
  }

  // ---- Core execution loop ------------------------------------------------

  /** Execute loaded bytecode until HALT or cycle limit. */
  run(): VmResult {
    const maxCycle = this.cycles + this.maxCycles;

    while (!this.halted && this.cycles < maxCycle) {
      if (!this.step()) break;
    }

    return {
      status: this.halted ? 'halted' : 'cycle-limit',
      cycles: this.cycles,
      registers: this.regs,
      confidence: this.conf,
      output: this.output,
    };
  }

  // ---- Single-step decoder + executor -------------------------------------

  /** Decode and execute one instruction. Returns false on HALT / error. */
  step(): boolean {
    if (this.halted) return false;

    const opcode = this.memory[this.pc];
    const fmt = getFormat(opcode);

    if (fmt === null) {
      this.halted = true;
      this.output.push({ type: 'error', payload: `illegal opcode 0x${opcode.toString(16)} at pc=${this.pc}` });
      return false;
    }

    const size = FORMAT_SIZES[fmt];
    const pc = this.pc;

    // --- Fetch operands based on format ---
    const rd  = fmt >= FluxFormat.FORMAT_B ? this.memory[pc + 1] : 0;
    const rs1 = fmt >= FluxFormat.FORMAT_E ? this.memory[pc + 2] : 0;
    const rs2 = fmt >= FluxFormat.FORMAT_E ? this.memory[pc + 3] : 0;
    const imm8 = fmt === FluxFormat.FORMAT_C || fmt === FluxFormat.FORMAT_D
      ? this.memory[pc + 1 + (fmt === FluxFormat.FORMAT_D ? 1 : 0)] : 0;
    const imm16 = (fmt === FluxFormat.FORMAT_F || fmt === FluxFormat.FORMAT_G)
      ? this.memory[pc + 2] | (this.memory[pc + 3] << 8) : 0;

    // Advance PC
    this.pc += size;
    this.cycles++;

    // --- Execute -----------------------------------------------------------
    switch (opcode) {
      // ---- System (Format A) ----
      case OP_HALT:    this.halted = true; return false;
      case OP_NOP:     break;
      case OP_RET:     this.pc = this.stack[--this.sp]; break;
      case OP_CLK:     this.regs[0] = this.cycles; break;

      // ---- Register (Format B) ----
      case OP_INC:     this.regs[rd]++; break;
      case OP_DEC:     this.regs[rd]--; break;
      case OP_NOT:     this.regs[rd] = ~this.regs[rd]; break;
      case OP_NEG:     this.regs[rd] = -this.regs[rd]; break;
      case OP_PUSH:    this.stack[--this.sp] = this.regs[rd]; break;
      case OP_POP:     this.regs[rd] = this.stack[this.sp++]; break;
      case OP_CONF_LD: this.regs[0] = Math.round(this.conf[rd] * 255); break; // c → i32 scaled
      case OP_CONF_ST: this.conf[rd] = this.regs[0] / 255; break;

      // ---- Immediate arithmetic (Format D) ----
      case OP_MOVI:    this.regs[rd] = imm8 > 127 ? imm8 - 256 : imm8; break;
      case OP_ADDI:    this.regs[rd] += imm8 > 127 ? imm8 - 256 : imm8; break;
      case OP_SUBI:    this.regs[rd] -= imm8 > 127 ? imm8 - 256 : imm8; break;
      case OP_ANDI:    this.regs[rd] &= imm8; break;
      case OP_ORI:     this.regs[rd] |= imm8; break;
      case OP_XORI:    this.regs[rd] ^= imm8; break;
      case OP_SHLI:    this.regs[rd] <<= imm8; break;
      case OP_SHRI:    this.regs[rd] >>= imm8; break;

      // ---- Arithmetic (Format E) ----
      case OP_ADD:     this.regs[rd] = this.regs[rs1] + this.regs[rs2]; break;
      case OP_SUB:     this.regs[rd] = this.regs[rs1] - this.regs[rs2]; break;
      case OP_MUL:     this.regs[rd] = this.regs[rs1] * this.regs[rs2]; break;
      case OP_DIV:     this.regs[rd] = this.regs[rs2] !== 0 ? Math.trunc(this.regs[rs1] / this.regs[rs2]) : 0; break;
      case OP_MOD:     this.regs[rd] = this.regs[rs2] !== 0 ? this.regs[rs1] % this.regs[rs2] : 0; break;

      // ---- Logic / Shift (Format E) ----
      case OP_AND:     this.regs[rd] = this.regs[rs1] & this.regs[rs2]; break;
      case OP_OR:      this.regs[rd] = this.regs[rs1] | this.regs[rs2]; break;
      case OP_XOR:     this.regs[rd] = this.regs[rs1] ^ this.regs[rs2]; break;
      case OP_SHL:     this.regs[rd] = this.regs[rs1] << this.regs[rs2]; break;
      case OP_SHR:     this.regs[rd] = this.regs[rs1] >> this.regs[rs2]; break;
      case OP_MIN:     this.regs[rd] = Math.min(this.regs[rs1], this.regs[rs2]); break;
      case OP_MAX:     this.regs[rd] = Math.max(this.regs[rs1], this.regs[rs2]); break;

      // ---- Comparison (Format E) ----
      case OP_CMP_EQ:  this.regs[rd] = this.regs[rs1] === this.regs[rs2] ? 1 : 0; break;
      case OP_CMP_LT:  this.regs[rd] = this.regs[rs1] < this.regs[rs2] ? 1 : 0; break;
      case OP_CMP_GT:  this.regs[rd] = this.regs[rs1] > this.regs[rs2] ? 1 : 0; break;
      case OP_CMP_NE:  this.regs[rd] = this.regs[rs1] !== this.regs[rs2] ? 1 : 0; break;

      // ---- Memory (Format E) ----
      case OP_LOAD:    this.regs[rd] = this.memRead32(this.regs[rs1] + this.regs[rs2]); break;
      case OP_STORE:   this.memWrite32(this.regs[rs1] + this.regs[rs2], this.regs[rd]); break;

      // ---- Data Movement (Format E) ----
      case OP_MOV:     this.regs[rd] = this.regs[rs1]; break;
      case OP_SWP:     { const t = this.regs[rd]; this.regs[rd] = this.regs[rs1]; this.regs[rs1] = t; break; }

      // ---- Control Flow (Format E — conditional use register offset) ----
      case OP_JZ:      if (this.regs[rd] === 0) this.pc += this.regs[rs1]; break;
      case OP_JNZ:     if (this.regs[rd] !== 0) this.pc += this.regs[rs1]; break;
      case OP_JLT:     if (this.regs[rd] < 0) this.pc += this.regs[rs1]; break;
      case OP_JGT:     if (this.regs[rd] > 0) this.pc += this.regs[rs1]; break;

      // ---- Control Flow (Format F) ----
      case OP_MOVI16:  this.regs[rd] = imm16 > 32767 ? imm16 - 65536 : imm16; break;
      case OP_JMP:     this.pc += (imm16 > 32767 ? imm16 - 65536 : imm16); break;
      case OP_JAL:     this.regs[rd] = this.pc; this.pc += (imm16 > 32767 ? imm16 - 65536 : imm16); break;
      case OP_CALL:    this.stack[--this.sp] = this.pc; this.pc = this.regs[rd] + (imm16 > 32767 ? imm16 - 65536 : imm16); break;
      case OP_LOOP:    this.regs[rd]--; if (this.regs[rd] > 0) this.pc -= (imm16 > 32767 ? imm16 - 65536 : imm16); break;

      // ---- Offset Memory (Format G) ----
      case OP_LOADOFF:  this.regs[rd] = this.memRead32(this.regs[rs1] + (imm16 > 32767 ? imm16 - 65536 : imm16)); break;
      case OP_STOREOFF: this.memWrite32(this.regs[rs1] + (imm16 > 32767 ? imm16 - 65536 : imm16), this.regs[rd]); break;

      // ---- Confidence (Format E) ----
      case OP_C_ADD:   this.regs[rd] = this.regs[rs1] + this.regs[rs2]; this.conf[rd] = Math.min(this.conf[rs1], this.conf[rs2]); break;
      case OP_C_SUB:   this.regs[rd] = this.regs[rs1] - this.regs[rs2]; this.conf[rd] = Math.min(this.conf[rs1], this.conf[rs2]); break;
      case OP_C_MUL:   this.regs[rd] = this.regs[rs1] * this.regs[rs2]; this.conf[rd] = this.conf[rs1] * this.conf[rs2]; break;
      case OP_C_MERGE: {
        const c1 = this.conf[rs1], c2 = this.conf[rs2];
        const w = c1 + c2;
        this.regs[rd] = w > 0 ? Math.round((this.regs[rs1] * c1 + this.regs[rs2] * c2) / w) : 0;
        this.conf[rd] = w > 0 ? (c1 + c2) / 2 : 0;
        break;
      }
      case OP_C_THRESH: { // Format D: rd = register, imm8 = threshold/255
        const thresh = imm8 / 255;
        if (this.conf[rd] < thresh) {
          // Skip next instruction by advancing PC by the next instruction's size
          const nextOp = this.memory[this.pc];
          const nextFmt = getFormat(nextOp);
          if (nextFmt !== null) this.pc += FORMAT_SIZES[nextFmt];
        }
        break;
      }
      case OP_C_DECAY: {
        const factor = this.regs[rs2] / 255;
        this.conf[rd] *= (1 - factor);
        break;
      }

      // ---- Math (Format E) ----
      case OP_ABS: this.regs[rd] = Math.abs(this.regs[rs1]); break;
      case OP_RND: this.regs[rd] = this.regs[rs1] + Math.floor(Math.random() * (this.regs[rs2] - this.regs[rs1] + 1)); break;

      // ---- A2A Signals (Format E — stubs for message queue) ----
      case OP_TELL:
        this.output.push({ type: 'tell', payload: `agent=${rs1} data=${this.regs[rs2]}` });
        break;
      case OP_BCAST:
        this.output.push({ type: 'bcast', payload: `tag=${rd} data=${this.regs[rs2]}` });
        break;
      case OP_SIGNAL:
        this.output.push({ type: 'signal', payload: `ch=${rd} sig=${this.regs[rs2]}` });
        break;
      case OP_AWAIT:
        if (this.signalQueue.length > 0) {
          const sig = this.signalQueue.shift()!;
          this.regs[rd] = sig.type.length; // store signal length as data indicator
        } else {
          // No signal available — stall by rewinding PC to re-execute
          this.pc -= size;
        }
        break;

      default:
        this.halted = true;
        this.output.push({ type: 'error', payload: `unimplemented opcode 0x${opcode.toString(16)} at pc=${pc}` });
        return false;
    }

    return true;
  }
}
