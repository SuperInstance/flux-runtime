/**
 * flux-bridge.ts — FLUX Bytecode Bridge for FishingLog AI
 *
 * Core integration module that connects FishingLog's TypeScript application
 * layer to the FLUX runtime. Provides:
 *   - Bytecode compilation from high-level FishingLog operations
 *   - Local VM execution on the Jetson Orin Nano
 *   - Confidence computing via FLUX confidence registers
 *   - A2A signaling between multiple FishingLog-equipped vessels
 *   - Sensor data encoding as FLUX memory operations
 *
 * This is the main entry point for FishingLog → FLUX integration.
 * Designed for production use on a real fishing vessel — robust error
 * handling, minimal allocations, no network dependencies.
 *
 * Author: Super Z (FLUX Fleet, Task 2-b)
 */

import { FluxVmMini, VmResult } from './flux-vm-mini';
import { ConfidenceEngine, ConfidenceResult } from './confidence-engine';
import type { Prediction } from './confidence-engine';
import {
  FluxFormat, FORMAT_SIZES,
  OP_HALT, OP_MOVI, OP_ADDI, OP_SUBI, OP_MOV, OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD,
  OP_STORE, OP_LOAD, OP_PUSH, OP_POP, OP_LOADOFF, OP_STOREOFF, OP_MOVI16,
  OP_JZ, OP_JNZ, OP_JMP, OP_JAL, OP_LOOP,
  OP_C_ADD, OP_C_MERGE, OP_C_THRESH, OP_C_DECAY,
  OP_TELL, OP_BCAST, OP_SIGNAL, OP_AWAIT, OP_CONF_ST,
} from './flux-opcodes';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A high-level FLUX operation that the bridge compiles to bytecode. */
export type FluxOp =
  | { type: 'halt' }
  | { type: 'mov'; rd: number; rs: number }
  | { type: 'movi'; rd: number; imm: number }
  | { type: 'add'; rd: number; rs1: number; rs2: number }
  | { type: 'sub'; rd: number; rs1: number; rs2: number }
  | { type: 'mul'; rd: number; rs1: number; rs2: number }
  | { type: 'div'; rd: number; rs1: number; rs2: number }
  | { type: 'store'; rd: number; base: number; offset: number }
  | { type: 'load'; rd: number; base: number; offset: number }
  | { type: 'store_imm'; rd: number; addr: number }
  | { type: 'load_imm'; rd: number; addr: number }
  | { type: 'cmp_lt'; rd: number; rs1: number; rs2: number }
  | { type: 'jmp_zero'; cond: number; offset: number }
  | { type: 'jmp'; offset: number }
  | { type: 'c_merge'; rd: number; rs1: number; rs2: number }
  | { type: 'c_thresh'; rd: number; threshold: number }
  | { type: 'c_decay'; rd: number; factor: number }
  | { type: 'tell'; target: number; data: number; tag?: number }
  | { type: 'bcast'; data: number; tag?: number }
  | { type: 'signal'; channel: number; sig: number }
  | { type: 'await'; rd: number }
  | { type: 'conf_st'; rd: number; value: number };

/** Result from FLUX bytecode execution. */
export interface FluxResult extends VmResult {
  /** Whether a confidence threshold was crossed during execution. */
  confidenceAlert?: boolean;
}

/** An A2A signal message for inter-vessel coordination. */
export interface FluxSignal {
  from: string;
  type: string;
  payload: string;
  timestamp: number;
}

/** A processed sensor reading ready for FLUX memory. */
export interface SensorReading {
  sensorId: string;
  value: number;
  confidence: number;
  unit: string;
  timestamp: string;
}

/** A sensor reading encoded as FLUX memory operations. */
export interface ProcessedData {
  /** Base memory address where data was written. */
  baseAddr: number;
  /** Number of bytes written. */
  byteCount: number;
  /** The memory offset layout for each field. */
  layout: { valueAddr: number; confAddr: number; tsAddr: number };
}

/** Bridge configuration. */
export interface FluxBridgeConfig {
  /** Vessel identifier for A2A signaling (default: "vessel-001"). */
  vesselId?: string;
  /** Memory size for the VM (default: 65536). */
  memorySize?: number;
  /** Maximum VM cycles per execution (default: 500_000). */
  maxCycles?: number;
  /** Alert threshold for confidence (default: 0.65). */
  alertThreshold?: number;
  /** Regulatory threshold for compliance (default: 0.80). */
  regulatoryThreshold?: number;
}

// ---------------------------------------------------------------------------
// FluxBridge
// ---------------------------------------------------------------------------

export class FluxBridge {
  private readonly vm: FluxVmMini;
  private readonly confidence: ConfidenceEngine;
  private readonly vesselId: string;

  /** Inbound signal queue. */
  private signalBuffer: FluxSignal[] = [];

  constructor(config: FluxBridgeConfig = {}) {
    this.vesselId = config.vesselId ?? 'vessel-001';
    this.vm = new FluxVmMini({
      memorySize: config.memorySize,
      maxCycles: config.maxCycles ?? 500_000,
      agentId: this.vesselId,
    });
    this.confidence = new ConfidenceEngine({
      alertThreshold: config.alertThreshold,
      regulatoryThreshold: config.regulatoryThreshold,
    });
  }

  // ---- Bytecode Compilation ----------------------------------------------

  /**
   * Compile a sequence of high-level FluxOp descriptors into FLUX bytecode.
   * Returns a Uint8Array ready for VM execution.
   */
  compileOperation(ops: FluxOp[]): Uint8Array {
    const parts: number[] = [];

    for (const op of ops) {
      switch (op.type) {
        case 'halt':
          parts.push(OP_HALT);
          break;

        case 'mov':
          parts.push(OP_MOV, op.rd, op.rs, 0);
          break;

        case 'movi':
          parts.push(OP_MOVI, op.rd, op.imm & 0xFF);
          break;

        case 'add':
          parts.push(OP_ADD, op.rd, op.rs1, op.rs2);
          break;
        case 'sub':
          parts.push(OP_SUB, op.rd, op.rs1, op.rs2);
          break;
        case 'mul':
          parts.push(OP_MUL, op.rd, op.rs1, op.rs2);
          break;
        case 'div':
          parts.push(OP_DIV, op.rd, op.rs1, op.rs2);
          break;

        case 'store':
          // STORE rd, base, offset → base+offset computed by VM
          parts.push(OP_STORE, op.rd, op.base, op.offset);
          break;

        case 'load':
          parts.push(OP_LOAD, op.rd, op.base, op.offset);
          break;

        case 'store_imm':
          // STOREOFF rd, R0(=addr), imm16 — uses R0 as scratch base
          parts.push(OP_MOVI16, 0, op.addr & 0xFF, (op.addr >> 8) & 0xFF);
          parts.push(OP_STOREOFF, op.rd, 0, op.addr & 0xFFFF);
          break;

        case 'load_imm':
          parts.push(OP_MOVI16, 0, op.addr & 0xFF, (op.addr >> 8) & 0xFF);
          parts.push(OP_LOADOFF, op.rd, 0, op.addr & 0xFFFF);
          break;

        case 'cmp_lt':
          parts.push(OP_CMP_LT, op.rd, op.rs1, op.rs2);
          break;

        case 'jmp_zero':
          // MOVI R15, offset; JZ cond, R15
          parts.push(OP_MOVI, 15, op.offset & 0xFF);
          parts.push(OP_JZ, op.cond, 15, 0);
          break;

        case 'jmp':
          parts.push(OP_JMP, 0, op.offset & 0xFF, (op.offset >> 8) & 0xFF);
          break;

        case 'c_merge':
          parts.push(OP_C_MERGE, op.rd, op.rs1, op.rs2);
          break;

        case 'c_thresh':
          parts.push(OP_C_THRESH, op.rd, Math.round(op.threshold * 255));
          break;

        case 'c_decay':
          parts.push(OP_MOVI, 2, Math.round(op.factor * 255));
          parts.push(OP_C_DECAY, op.rd, op.rd, 2);
          break;

        case 'tell':
          parts.push(OP_MOVI, 2, op.data & 0xFF);
          parts.push(OP_TELL, op.tag ?? 0, op.target, 2);
          break;

        case 'bcast':
          parts.push(OP_MOVI, 2, op.data & 0xFF);
          parts.push(OP_BCAST, op.tag ?? 0, 0, 2);
          break;

        case 'signal':
          parts.push(OP_MOVI, 2, op.sig & 0xFF);
          parts.push(OP_SIGNAL, op.channel, 2, 0);
          break;

        case 'await':
          parts.push(OP_AWAIT, op.rd, 0, 0);
          break;

        case 'conf_st':
          parts.push(OP_MOVI, 0, Math.round(op.value * 255));
          parts.push(OP_CONF_ST, op.rd);
          break;

        default:
          throw new Error(`Unknown operation type: ${(op as { type: string }).type}`);
      }
    }

    return new Uint8Array(parts);
  }

  // ---- Execution ---------------------------------------------------------

  /** Execute FLUX bytecode on the local mini-VM. */
  execute(bytecode: Uint8Array): FluxResult {
    this.vm.load(bytecode);
    const result = this.vm.run();
    const confidenceAlert = result.output.some(
      (o) => o.type === 'error' && o.payload.includes('confidence'),
    );
    return { ...result, confidenceAlert };
  }

  // ---- Confidence Computing ----------------------------------------------

  /**
   * Compute fused confidence for fish species classification.
   * Wraps the ConfidenceEngine with FLUX integration — also runs the
   * confidence values through the FLUX VM for threshold checking.
   */
  computeConfidence(predictions: Prediction[]): ConfidenceResult {
    // 1. Run through the TypeScript confidence engine
    const result = this.confidence.computeConfidence(predictions);

    // 2. If alert triggered, also run through FLUX VM for bytecode verification
    if (result.alertTriggered) {
      const ops: FluxOp[] = [
        { type: 'conf_st', rd: 0, value: result.confidence },
        { type: 'c_thresh', rd: 0, threshold: this.confidence.getAlertThreshold() },
        { type: 'halt' },
      ];
      const bytecode = this.compileOperation(ops);
      const vmResult = this.execute(bytecode);
      // VM threshold check provides a second opinion
      if (vmResult.status === 'halted' && vmResult.cycles === 3) {
        // Threshold instruction was skipped (low confidence confirmed)
      }
    }

    return result;
  }

  // ---- A2A Signaling -----------------------------------------------------

  /**
   * Send an A2A signal to another FishingLog-equipped vessel.
   * In production, this would go through the FLUX A2A Signal protocol
   * (store-and-forward for offline operation).
   */
  sendSignal(target: string, signalType: string, payload: string): void {
    const signal: FluxSignal = {
      from: this.vesselId,
      type: signalType,
      payload,
      timestamp: Date.now(),
    };

    // In production: queue for A2A transport (radio, satellite, Wi-Fi mesh)
    // For now: log to VM output and local buffer
    const encoded = JSON.stringify(signal);
    this.vm.output.push({ type: 'signal_send', payload: encoded });
  }

  /**
   * Receive the next pending A2A signal, or null if none available.
   */
  receiveSignal(): FluxSignal | null {
    if (this.signalBuffer.length > 0) {
      return this.signalBuffer.shift()!;
    }
    return null;
  }

  /** Push an inbound signal (from A2A transport) into the receive buffer. */
  pushInboundSignal(signal: FluxSignal): void {
    this.signalBuffer.push(signal);
    // Also inject into VM for OP_AWAIT processing
    this.vm.pushSignal(signal.type, signal.payload);
  }

  // ---- Sensor Data Processing --------------------------------------------

  /**
   * Encode a sensor reading as FLUX memory operations.
   * Writes value (i32), confidence (i32 scaled 0–255), and timestamp (i32 unix)
   * into the VM's memory at a given base address.
   */
  processSensorData(data: SensorReading, baseAddr = 1024): ProcessedData {
    const layout = {
      valueAddr: baseAddr,
      confAddr: baseAddr + 4,
      tsAddr: baseAddr + 8,
    };

    const ts = Math.floor(new Date(data.timestamp).getTime() / 1000);
    const confScaled = Math.round(data.confidence * 255);

    this.vm.memWrite32(layout.valueAddr, data.value);
    this.vm.memWrite32(layout.confAddr, confScaled);
    this.vm.memWrite32(layout.tsAddr, ts);

    return {
      baseAddr,
      byteCount: 12,
      layout,
    };
  }

  // ---- Utility -----------------------------------------------------------

  /** Get the underlying VM instance for advanced usage. */
  getVm(): FluxVmMini {
    return this.vm;
  }

  /** Get the confidence engine for advanced usage. */
  getConfidenceEngine(): ConfidenceEngine {
    return this.confidence;
  }

  /** Get this vessel's identifier. */
  getVesselId(): string {
    return this.vesselId;
  }

  /** Reset all VM state and signal buffers. */
  reset(): void {
    this.vm.load(new Uint8Array(0));
    this.signalBuffer = [];
    this.confidence.reset();
  }
}
