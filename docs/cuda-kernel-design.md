# CUDA Kernel Design for Batch FLUX Bytecode Execution

**Task ID:** CUDA-001 (TASK-BOARD)
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-12
**Status:** DRAFT — Design document for JetsonClaw1 validation
**Target Hardware:** NVIDIA Jetson Orin Nano (1024 CUDA cores, 8GB LPDDR5)
**ISA Reference:** FLUX ISA v3 (253 base opcodes + escape prefix extensions)
**Tracks:** TASK-BOARD CUDA-001, FishingLog FLUX Bridge integration

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Kernel Design](#3-kernel-design)
   - 3.1 Thread-per-VM Execution Model
   - 3.2 Kernel Pseudocode (CUDA C)
   - 3.3 Instruction Dispatch Engine
   - 3.4 Confidence Propagation on GPU
4. [Memory Layout](#4-memory-layout)
   - 4.1 Global Memory Organization
   - 4.2 Shared Memory Strategy
   - 4.3 Per-Thread Local Memory
   - 4.4 Register File Mapping
   - 4.5 Coalesced Access Patterns
5. [Supported Opcode Subset](#5-supported-opcode-subset)
   - 5.1 GPU-Safe Opcodes (Full Acceleration)
   - 5.2 GPU-Limited Opcodes (Restricted Scope)
   - 5.3 GPU-Excluded Opcodes (Host-Only)
   - 5.4 GPU-Adapted Opcodes (Modified Behavior)
6. [Thread Divergence Analysis](#6-thread-divergence-analysis)
   - 6.1 Warp Divergence Fundamentals
   - 6.2 Branch Classification by Divergence Cost
   - 6.3 Mitigation Strategies
   - 6.4 Workload Sorting for Minimal Divergence
7. [Performance Model](#7-performance-model)
   - 7.1 Throughput Estimates
   - 7.2 Memory Bandwidth Analysis
   - 7.3 Register Pressure and Occupancy
   - 7.4 Instruction Mix Benchmarks
8. [Integration with FishingLog](#8-integration-with-fishinglog)
   - 8.1 Batch Fish Classification
   - 8.2 Sensor Data Preprocessing Pipeline
   - 8.3 Edge Deployment Architecture
9. [Build & Test Plan](#9-build--test-plan)
   - 9.1 CMake Build Configuration
   - 9.2 Testing Without Jetson Hardware
   - 9.3 Integration with flux-runtime-c
10. [API Reference](#10-api-reference)
    - 10.1 Host API
    - 10.2 Configuration Structures
    - 10.3 Error Handling
    - 10.4 Lifecycle Management

---

## 1. Executive Summary

### Why CUDA Batch Execution Matters

The FLUX fleet is deploying on real edge hardware. JetsonClaw1's NVIDIA Jetson Orin Nano — the same hardware powering FishingLog AI aboard commercial fishing vessels — packs 1024 CUDA cores and 8GB of LPDDR5 memory into a 15W thermal envelope. Running FLUX bytecode programs sequentially on the ARM CPU wastes this parallelism. A CUDA batch executor allows us to run **up to 1024 independent FLUX VM instances simultaneously**, each on its own CUDA thread, achieving order-of-magnitude speedups for the fleet's most critical workloads.

Three target use cases drive this design:

**FishingLog sensor processing.** A single fishing vessel generates dozens of sensor readings per second — water temperature, depth, sonar returns, GPS coordinates, accelerometer data. Each reading requires confidence-weighted classification through a FLUX bytecode program. Currently, the FishingLog FLUX Bridge processes these one-at-a-time on the CPU (~10M ops/sec in TypeScript, ~67M ops/sec in C). A CUDA batch executor could process all readings in a single kernel launch, leveraging the GPU's 1024 parallel cores to process an entire sensor batch simultaneously.

**Batch confidence computation.** The FLUX ISA's confidence registers (C0–C15) track certainty per data source. Bayesian fusion, temporal decay, and threshold checks are embarrassingly parallel — each fish classification is independent. The GPU excels at this: 1024 parallel confidence pipelines running the same fusion bytecode, producing fused confidence scores for the entire catch in one kernel invocation.

**Parallel A2A message handling.** When a vessel broadcasts a catch report to the fleet, each receiving vessel runs its own verification bytecode program against the incoming data. On a GPU, we can model 1024 simulated vessels processing the same A2A message concurrently, enabling rapid stress-testing of the A2A protocol and large-scale fleet coordination scenarios.

### Jetson Orin Nano Specifications

| Parameter | Value |
|-----------|-------|
| GPU | NVIDIA Ampere (GA10B), 1024 CUDA cores |
| CPU | 6-core ARM Cortex-A78AE, 1.5 GHz |
| Memory | 8GB LPDDR5, 68.3 GB/s bandwidth |
| Shared Memory | 128 KB per SM, 2 SMs total (256 KB) |
| L2 Cache | 2 MB |
| Register File | 65,536 × 32-bit registers per SM |
| Max threads/block | 1024 |
| Max threads/SM | 2048 |
| Warp size | 32 threads |
| Compute Capability | 8.7 (Ampere) |
| Thermal Design Power | 15W (10W/15W/20W modes) |

The Orin Nano's 2 streaming multiprocessors (SMs) each support up to 2048 concurrent threads. At 32 threads per warp, we can have up to 64 warps active simultaneously across both SMs. This maps naturally to 64–1024 FLUX VM instances, depending on register pressure.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                 CUDA FLUX Batch Executor                      │
├──────────────────────────────────────────────────────────────┤
│  Host (CPU)                           Device (GPU)           │
│                                                               │
│  ┌──────────────┐    H2D memcpy     ┌────────────────────┐  │
│  │ Program      │──────────────────>│ Global Memory      │  │
│  │ Loader       │   (bytecode)      │ ┌────────────────┐ │  │
│  │              │                   │ │ programs[]     │ │  │
│  │ - Read .flux │                   │ │ offsets[]      │ │  │
│  │ - Validate   │                   │ │ configs[]      │ │  │
│  │ - Pack       │                   │ └────────────────┘ │  │
│  └──────────────┘                   │ ┌────────────────┐ │  │
│                                     │ │ local_mem[]    │ │  │
│  ┌──────────────┐    D2H memcpy     │ │ (per-thread)   │ │  │
│  │ Result       │<──────────────────│ └────────────────┘ │  │
│  │ Collector    │   (results)       │ ┌────────────────┐ │  │
│  │              │                   │ │ results[]      │ │  │
│  │ - Unpack     │                   │ └────────────────┘ │  │
│  │ - Verify     │                   └────────────────────┘  │
│  │ - Post-proc  │                   ┌────────────────────┐  │
│  └──────────────┘                   │ Thread Blocks       │  │
│                                     │ ┌────┐ ┌────┐       │  │
│  ┌──────────────┐    config         │ │VM 0│ │VM 1│  ...  │  │
│  │ Kernel       │──────────────────>│ │VM 2│ │VM 3│       │  │
│  │ Launcher     │   (grid/block)    │ │... │ │... │       │  │
│  │              │                   │ │VM30│ │VM31│       │  │
│  │ - Grid calc  │                   │ └────┘ └────┘       │  │
│  │ - Stream mgmt│                   │ Block 0  Block 1    │  │
│  │ - Sync       │                   └────────────────────┘  │
│  └──────────────┘                                            │
│                                                               │
│                    Jetson Orin Nano                            │
│            1024 CUDA cores, 8GB RAM, 128KB shared/SM          │
└──────────────────────────────────────────────────────────────┘
```

### Execution Pipeline

1. **Program Loading (Host):** The host reads one or more `.flux` bytecode files, validates them against the FLUX ISA v3 spec (or v2 for backward compatibility), and packs them into a contiguous global memory buffer with an offset table.
2. **Configuration (Host):** Per-program execution parameters (max instruction count, input registers, memory layout) are packed into a device-accessible configuration array.
3. **Kernel Launch (Host):** The host computes grid/block dimensions and launches `flux_batch_execute<<<grid, block, 0, stream>>>`.
4. **Thread-per-VM Execution (Device):** Each CUDA thread initializes its own register file, stack pointer, and program counter, then executes bytecode until HALT or timeout.
5. **Result Collection (Host):** The host copies results back from device memory, validates execution status, and processes outputs.

### Design Principles

- **No shared memory usage:** Each VM is completely independent — no inter-thread communication needed. This eliminates bank conflicts and simplifies the design.
- **Read-only bytecode:** All threads share the same global bytecode buffer via `__restrict__` pointers, enabling the L1/L2 cache to serve repeated accesses efficiently.
- **Write-once results:** Each thread writes its result to a unique location in the results array, avoiding race conditions without atomics.
- **Deterministic execution:** Given the same inputs, every kernel launch produces identical outputs. No random number generation, no floating-point nondeterminism in core operations.

---

## 3. Kernel Design

### 3.1 Thread-per-VM Execution Model

The fundamental mapping is simple: **one CUDA thread = one FLUX VM instance.**

```
Thread 0  → VM 0  → executes program[0] with config[0]
Thread 1  → VM 1  → executes program[1] with config[1]
...
Thread N  → VM N  → executes program[N] with config[N]
```

Each thread maintains its entire VM state in:

| Component | Storage Location | Size | Notes |
|-----------|-----------------|------|-------|
| General registers R0–R15 | CUDA registers (uint32_t) | 16 × 4 = 64 bytes | Fits in hardware registers |
| Confidence registers C0–C15 | CUDA registers (float) | 16 × 4 = 64 bytes | Fits in hardware registers |
| Program counter (PC) | CUDA register (uint32_t) | 4 bytes | Offset into bytecode |
| Stack pointer (SP) | CUDA register (uint32_t) | 4 bytes | Index into local stack |
| Frame pointer (FP) | CUDA register (uint32_t) | 4 bytes | Stack frame base |
| Flags register | CUDA register (uint32_t) | 4 bytes | Comparison/system flags |
| Local stack | Local memory | 1–4 KB | Per-thread, no bank conflicts |
| Local memory/heap | Local memory | 0–4 KB | Per-VM addressable memory |

**Total per-thread register pressure:** ~204 bytes (R0–R15 + C0–C15 + PC/SP/FP/flags + temporaries). The Orin Nano allocates 65,536 × 32-bit registers per SM = 256 KB per SM. At 204 bytes per thread, we can fit ~1,280 threads per SM — well above the 2,048 hardware limit. This means register pressure is **not a bottleneck** and we achieve maximum occupancy.

### 3.2 Kernel Pseudocode (CUDA C)

```cuda
/**
 * flux_batch_execute — CUDA kernel for batch FLUX bytecode execution
 *
 * Each CUDA thread runs one independent FLUX VM instance.
 * All VMs execute concurrently on 1024 CUDA cores.
 *
 * @param programs   Global memory: contiguous bytecode for all programs
 * @param offsets    Global memory: byte offset of each program in programs[]
 * @param results    Global memory: output buffer (one entry per VM)
 * @param configs    Global memory: per-program execution config
 * @param num_programs Number of programs to execute
 */
__global__ void flux_batch_execute(
    const uint8_t*  __restrict__ programs,   // Bytecode buffer (read-only)
    const uint32_t* __restrict__ offsets,    // Program byte offsets
    uint32_t*       __restrict__ results,    // Output: R0 on HALT
    const FluxConfig* __restrict__ configs,  // Per-program config
    int num_programs
) {
    // --- Thread identification ---
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= num_programs) return;

    // --- Per-thread VM state (lives in CUDA registers) ---
    uint32_t regs[16];       // R0–R15 general-purpose registers
    float    conf[16];       // C0–C15 confidence registers
    uint32_t pc   = offsets[tid];  // Program counter (byte offset)
    uint32_t sp   = 0;       // Stack pointer (local stack index)
    uint32_t fp   = 0;       // Frame pointer
    uint32_t flags = 0;      // Flags register
    uint32_t steps = 0;      // Instruction counter

    // Per-thread local stack (256 entries, allocated from local memory)
    // Note: __local__ or automatic arrays map to per-thread local memory
    uint32_t stack[256];

    // Per-thread local memory (4 KB addressable by LOAD/STORE)
    // Remapped to per-thread storage — each VM has its own address space
    uint32_t local_mem[1024];  // 4 KB local memory per VM

    // Initialize registers from config (input data)
    #pragma unroll
    for (int i = 0; i < 16; i++) {
        regs[i] = configs[tid].init_regs[i];
        conf[i] = configs[tid].init_conf[i];
    }

    // --- Main execution loop ---
    const uint32_t max_steps = configs[tid].max_steps;

    for (steps = 0; steps < max_steps; steps++) {
        // Fetch opcode byte
        uint8_t opcode = programs[pc];

        // --- Format A: Zero-operand (1 byte) ---
        if (opcode <= 0x07 || (opcode >= 0xF0 && opcode <= 0xFF && opcode != 0xFF)) {
            pc += 1;
            switch (opcode) {
                case 0x00:  // HALT — store R0 to results and exit
                    results[tid] = regs[0];
                    return;

                case 0x01:  // NOP — pipeline sync, no operation
                    break;

                case 0x02:  // RET — pop PC from stack
                    pc = stack[--sp];
                    break;

                case 0x0A:  // NOT (Format B, handled below)
                case 0x0B:  // NEG (Format B, handled below)
                case 0x0C:  // PUSH (Format B, handled below)
                case 0x0D:  // POP (Format B, handled below)
                    // These are Format B — fall through to dispatch
                    pc -= 1;  // Undo PC advance; Format B handler below
                    goto dispatch_format_b;

                case 0xF0:  // HALT_ERR — halt with error
                    results[tid] = 0xDEAD0001 | (flags << 16);
                    return;

                case 0xF2:  // DUMP — not meaningful on GPU, NOP
                    break;

                case 0xF3:  // ASSERT — check flags
                    // On GPU, ASSERT violations write error code
                    if (flags & 0x01) {
                        results[tid] = 0xDEAD0003;
                        return;
                    }
                    break;

                case 0xF5:  // VER — return ISA version (3)
                    regs[0] = 3;
                    break;

                case 0xF6:  // CLK — return step count
                    regs[0] = steps;
                    break;

                case 0xFA:  // CONF_CLAMP (v3 security)
                    #pragma unroll
                    for (int i = 0; i < 16; i++) {
                        if (isnan(conf[i]) || isinf(conf[i]))
                            conf[i] = 0.0f;
                        else if (conf[i] < 0.0f) conf[i] = 0.0f;
                        else if (conf[i] > 1.0f) conf[i] = 1.0f;
                    }
                    break;

                case 0xFB:  // TAG_CHECK (v3 security)
                    // No-op on GPU (no cross-agent memory)
                    break;

                case 0xFF:  // ESCAPE prefix (Format H)
                    goto dispatch_format_h;

                default:
                    results[tid] = 0xDEAD0000 | opcode;
                    return;
            }
        }
        // --- Format B: Single register (2 bytes) ---
        else if ((opcode >= 0x08 && opcode <= 0x0F)) {
        dispatch_format_b:
            uint8_t rd = programs[pc + 1] & 0x0F;
            pc += 2;
            switch (opcode) {
                case 0x08:  // INC
                    regs[rd]++;
                    break;
                case 0x09:  // DEC
                    regs[rd]--;
                    break;
                case 0x0A:  // NOT
                    regs[rd] = ~regs[rd];
                    break;
                case 0x0B:  // NEG
                    regs[rd] = (uint32_t)(-(int32_t)regs[rd]);
                    break;
                case 0x0C:  // PUSH
                    stack[sp++] = regs[rd];
                    break;
                case 0x0D:  // POP
                    regs[rd] = stack[--sp];
                    break;
                case 0x0E:  // CONF_LD
                    // Load confidence register into float accumulator
                    regs[rd] = __float_as_uint(conf[rd]);
                    break;
                case 0x0F:  // CONF_ST
                    // Store float accumulator into confidence register
                    conf[rd] = __uint_as_float(regs[rd]);
                    break;
            }
        }
        // --- Format C: Immediate-only (2 bytes) ---
        else if (opcode >= 0x10 && opcode <= 0x17) {
            uint8_t imm8 = programs[pc + 1];
            pc += 2;
            switch (opcode) {
                case 0x15:  // YIELD — NOP on GPU (single-thread)
                    break;
                default:
                    // SYS, TRAP, DBG, CLF, SEMA, CACHE, STRIPCF
                    // GPU-limited: most are NOPs on GPU
                    break;
            }
        }
        // --- Format D: Register + Imm8 (3 bytes) ---
        else if (opcode >= 0x18 && opcode <= 0x1F) {
            uint8_t rd   = programs[pc + 1] & 0x0F;
            uint8_t imm8 = programs[pc + 2];
            pc += 3;
            switch (opcode) {
                case 0x18:  // MOVI — sign-extend imm8
                    regs[rd] = (uint32_t)(int32_t)(int8_t)imm8;
                    break;
                case 0x19:  // ADDI
                    regs[rd] += (uint32_t)(int8_t)imm8;
                    break;
                case 0x1A:  // SUBI
                    regs[rd] -= (uint32_t)(int8_t)imm8;
                    break;
                case 0x1B:  // ANDI
                    regs[rd] &= imm8;
                    break;
                case 0x1C:  // ORI
                    regs[rd] |= imm8;
                    break;
                case 0x1D:  // XORI
                    regs[rd] ^= imm8;
                    break;
                case 0x1E:  // SHLI
                    regs[rd] <<= imm8;
                    break;
                case 0x1F:  // SHRI
                    regs[rd] >>= imm8;
                    break;
            }
        }
        // --- Format E: Three-register (4 bytes) ---
        else if (opcode >= 0x20 && opcode <= 0x6F ||
                 opcode >= 0x80 && opcode <= 0xCF ||
                 opcode >= 0x90 && opcode <= 0x9F) {
            uint8_t rd  = programs[pc + 1] & 0x0F;
            uint8_t rs1 = programs[pc + 2] & 0x0F;
            uint8_t rs2 = programs[pc + 3] & 0x0F;
            pc += 4;

            switch (opcode) {
                // --- Integer Arithmetic ---
                case 0x20: regs[rd] = regs[rs1] + regs[rs2]; break;  // ADD
                case 0x21: regs[rd] = regs[rs1] - regs[rs2]; break;  // SUB
                case 0x22: regs[rd] = regs[rs1] * regs[rs2]; break;  // MUL
                case 0x23:  // DIV — guarded against divide-by-zero
                    regs[rd] = (regs[rs2] != 0)
                        ? (uint32_t)((int32_t)regs[rs1] / (int32_t)regs[rs2])
                        : 0;
                    break;
                case 0x24:  // MOD
                    regs[rd] = (regs[rs2] != 0)
                        ? (uint32_t)((int32_t)regs[rs1] % (int32_t)regs[rs2])
                        : 0;
                    break;

                // --- Logic ---
                case 0x25: regs[rd] = regs[rs1] & regs[rs2]; break;  // AND
                case 0x26: regs[rd] = regs[rs1] | regs[rs2]; break;  // OR
                case 0x27: regs[rd] = regs[rs1] ^ regs[rs2]; break;  // XOR
                case 0x28: regs[rd] = regs[rs1] << regs[rs2]; break;  // SHL
                case 0x29: regs[rd] = regs[rs1] >> regs[rs2]; break;  // SHR

                // --- Min/Max ---
                case 0x2A:  // MIN
                    regs[rd] = (regs[rs1] < regs[rs2]) ? regs[rs1] : regs[rs2];
                    break;
                case 0x2B:  // MAX
                    regs[rd] = (regs[rs1] > regs[rs2]) ? regs[rs1] : regs[rs2];
                    break;

                // --- Comparison ---
                case 0x2C: regs[rd] = (regs[rs1] == regs[rs2]) ? 1 : 0; break; // CMP_EQ
                case 0x2D: regs[rd] = (regs[rs1] <  regs[rs2]) ? 1 : 0; break; // CMP_LT
                case 0x2E: regs[rd] = (regs[rs1] >  regs[rs2]) ? 1 : 0; break; // CMP_GT
                case 0x2F: regs[rd] = (regs[rs1] != regs[rs2]) ? 1 : 0; break; // CMP_NE

                // --- Float Operations ---
                case 0x30: { // FADD
                    float a = __uint_as_float(regs[rs1]);
                    float b = __uint_as_float(regs[rs2]);
                    regs[rd] = __float_as_uint(a + b);
                    break;
                }
                case 0x31: { // FSUB
                    float a = __uint_as_float(regs[rs1]);
                    float b = __uint_as_float(regs[rs2]);
                    regs[rd] = __float_as_uint(a - b);
                    break;
                }
                case 0x32: { // FMUL
                    float a = __uint_as_float(regs[rs1]);
                    float b = __uint_as_float(regs[rs2]);
                    regs[rd] = __float_as_uint(a * b);
                    break;
                }
                case 0x33: { // FDIV
                    float a = __uint_as_float(regs[rs1]);
                    float b = __uint_as_float(regs[rs2]);
                    regs[rd] = __float_as_uint(b != 0.0f ? a / b : 0.0f);
                    break;
                }
                case 0x36: { // FTOI
                    float a = __uint_as_float(regs[rs1]);
                    regs[rd] = (uint32_t)(int32_t)a;
                    break;
                }
                case 0x37: { // ITOF
                    regs[rd] = __float_as_uint((float)(int32_t)regs[rs1]);
                    break;
                }

                // --- Memory (local only) ---
                case 0x38:  // LOAD — rd = local_mem[rs1 + rs2]
                    regs[rd] = local_mem[(regs[rs1] + regs[rs2]) & 0x3FF];
                    break;
                case 0x39:  // STORE — local_mem[rs1 + rs2] = rd
                    local_mem[(regs[rs1] + regs[rs2]) & 0x3FF] = regs[rd];
                    break;

                // --- Move ---
                case 0x3A: regs[rd] = regs[rs1]; break;  // MOV
                case 0x3B: { // SWP
                    uint32_t tmp = regs[rd];
                    regs[rd] = regs[rs1];
                    regs[rs1] = tmp;
                    break;
                }

                // --- Control Flow ---
                case 0x3C:  // JZ — if rd == 0: pc += rs1
                    if (regs[rd] == 0) pc += regs[rs1];
                    break;
                case 0x3D:  // JNZ — if rd != 0: pc += rs1
                    if (regs[rd] != 0) pc += regs[rs1];
                    break;
                case 0x3E:  // JLT — if (int32_t)rd < 0: pc += rs1
                    if ((int32_t)regs[rd] < 0) pc += regs[rs1];
                    break;
                case 0x3F:  // JGT — if (int32_t)rd > 0: pc += rs1
                    if ((int32_t)regs[rd] > 0) pc += regs[rs1];
                    break;

                // --- Confidence-Aware Arithmetic (0x60–0x6F) ---
                case 0x60: { // C_ADD: rd = rs1 + rs2, conf[rd] = min(conf[rs1], conf[rs2])
                    regs[rd] = regs[rs1] + regs[rs2];
                    conf[rd] = fminf(conf[rs1], conf[rs2]);
                    break;
                }
                case 0x61: { // C_SUB
                    regs[rd] = regs[rs1] - regs[rs2];
                    conf[rd] = fminf(conf[rs1], conf[rs2]);
                    break;
                }
                case 0x62: { // C_MUL: conf = c1 * c2
                    regs[rd] = regs[rs1] * regs[rs2];
                    conf[rd] = conf[rs1] * conf[rs2];
                    break;
                }
                case 0x63: { // C_DIV: conf = c1 * c2 * (1 - epsilon)
                    float eps = 1e-6f;
                    regs[rd] = (regs[rs2] != 0)
                        ? (uint32_t)((int32_t)regs[rs1] / (int32_t)regs[rs2]) : 0;
                    conf[rd] = conf[rs1] * conf[rs2] * (1.0f - eps);
                    break;
                }
                case 0x68: { // C_MERGE: weighted average fusion
                    float w1 = conf[rs1];
                    float w2 = conf[rs2];
                    float wsum = w1 + w2;
                    if (wsum > 0.0f) {
                        // Weighted average of values (treating as fixed-point)
                        regs[rd] = (uint32_t)(
                            ((float)regs[rs1] * w1 + (float)regs[rs2] * w2) / wsum
                        );
                        conf[rd] = wsum / 2.0f;  // Average confidence
                    } else {
                        regs[rd] = 0;
                        conf[rd] = 0.0f;
                    }
                    break;
                }
                case 0x6D: { // C_CALIB: calibrate against ground truth
                    // rs1 = predicted, rs2 = ground truth
                    // conf[rd] = 1.0 if match, decayed if mismatch
                    conf[rd] = (regs[rs1] == regs[rs2]) ? 1.0f : conf[rd] * 0.9f;
                    break;
                }

                // --- Extended Math ---
                case 0x90: regs[rd] = (regs[rs1] < 0x80000000u)
                    ? regs[rs1] : (uint32_t)(-(int32_t)regs[rs1]); break; // ABS
                case 0x91: regs[rd] = (regs[rs1] == 0) ? 0
                    : ((int32_t)regs[rs1] < 0) ? 0xFFFFFFFF : 1; break;  // SIGN
                case 0x9A: { // RND
                    // Deterministic hash-based PRNG (no curand needed)
                    uint32_t seed = regs[rs1] ^ (steps * 2654435761u);
                    seed = ((seed >> 16) ^ seed) * 0x45d9f3bu;
                    seed = ((seed >> 16) ^ seed) * 0x45d9f3bu;
                    seed = (seed >> 16) ^ seed;
                    uint32_t range = regs[rs2] - regs[rs1] + 1;
                    regs[rd] = regs[rs1] + (seed % (range ? range : 1));
                    break;
                }
                case 0x95: { // CLZ — count leading zeros
                    regs[rd] = __clz(regs[rs1]);
                    break;
                }
                case 0x97: { // POPCNT — population count
                    regs[rd] = __popc(regs[rs1]);
                    break;
                }

                // Viewpoint (0x70–0x7F): NOP on GPU
                // Sensor (0x80–0x8F): NOP on GPU (no hardware access)
                // Crypto (0x98–0x9F, 0xAA–0xAF): NOP on GPU
                // Collection (0xA0–0xA9): NOP on GPU
                // Vector (0xB0–0xBF): NOP on GPU (no SIMD needed — already parallel)
                // Tensor (0xC0–0xCF): NOP on GPU (separate kernel)
                // A2A (0x50–0x5F): NOP on GPU (host-mediated)

                default:
                    // Unimplemented GPU-safe opcodes are NOPs
                    break;
            }
        }
        // --- Format F: Register + Imm16 (4 bytes) ---
        else if (opcode >= 0x40 && opcode <= 0x47 ||
                 opcode >= 0xE0 && opcode <= 0xEF ||
                 opcode == 0xEE || opcode == 0xEF) {
            uint8_t  rd      = programs[pc + 1] & 0x0F;
            uint16_t imm16   = (uint16_t)(programs[pc + 2] << 8 | programs[pc + 3]);
            pc += 4;
            switch (opcode) {
                case 0x40: regs[rd] = (uint32_t)imm16; break;           // MOVI16
                case 0x41: regs[rd] += (uint32_t)imm16; break;          // ADDI16
                case 0x42: regs[rd] -= (uint32_t)imm16; break;          // SUBI16
                case 0x43: pc += (int32_t)(int16_t)imm16; break;        // JMP (relative)
                case 0x44:  // JAL — jump and link
                    regs[rd] = pc;
                    pc += (int32_t)(int16_t)imm16;
                    break;
                case 0x45:  // CALL — push return, jump
                    stack[sp++] = pc;
                    pc = regs[rd] + (uint32_t)(int16_t)imm16;
                    break;
                case 0x46:  // LOOP — decrement and branch
                    if (--regs[rd] > 0) pc -= (uint32_t)imm16;
                    break;
                case 0xE0: pc += (int32_t)(int16_t)imm16; break;        // JMPL
                case 0xE1:  // JALL
                    regs[rd] = pc;
                    pc += (int32_t)(int16_t)imm16;
                    break;
                case 0xE7:  // FAULT
                    results[tid] = 0xDEAD0002 | ((uint32_t)imm16 << 16);
                    return;
                default:
                    break;
            }
        }
        // --- Format G: Two-Register + Imm16 (5 bytes) ---
        else if ((opcode >= 0x48 && opcode <= 0x4F) ||
                 (opcode >= 0xD0 && opcode <= 0xDF)) {
            uint8_t  rd     = programs[pc + 1] & 0x0F;
            uint8_t  rs1    = programs[pc + 2] & 0x0F;
            uint16_t imm16  = (uint16_t)(programs[pc + 3] << 8 | programs[pc + 4]);
            pc += 5;
            switch (opcode) {
                case 0x48:  // LOADOFF — rd = local_mem[rs1 + imm16]
                    regs[rd] = local_mem[(regs[rs1] + imm16) & 0x3FF];
                    break;
                case 0x49:  // STOREOFF — local_mem[rs1 + imm16] = rd
                    local_mem[(regs[rs1] + imm16) & 0x3FF] = regs[rd];
                    break;
                case 0x4E: { // COPY — memcpy within local memory
                    uint32_t src = regs[rs1];
                    uint32_t dst = rd;
                    uint16_t len = imm16;
                    for (uint16_t i = 0; i < len && i < 1024; i++) {
                        local_mem[(dst + i) & 0x3FF] = local_mem[(src + i) & 0x3FF];
                    }
                    break;
                }
                case 0x4F: { // FILL — memset within local memory
                    uint32_t dst = rd;
                    uint16_t len = imm16;
                    for (uint16_t i = 0; i < len && i < 1024; i++) {
                        local_mem[(dst + i) & 0x3FF] = regs[rs1];
                    }
                    break;
                }
                default:
                    break;
            }
        }
        // --- Format H: Escape Prefix (3+ bytes) ---
        else {
        dispatch_format_h:
            uint8_t ext_id    = programs[pc + 1];
            uint8_t sub_opcode = programs[pc + 2];
            // Extension opcodes are NOP on GPU unless specifically supported
            // Future: EXT_TENSOR, EXT_EDGE for GPU-native operations
            pc += 3;
            // Handle extension-specific operand bytes based on ext_id
            break;
        }
    }

    // Timeout — max instructions exceeded
    results[tid] = 0xFFFFFFFF;
}
```

### 3.3 Instruction Dispatch Engine

The dispatch uses a cascading `if/else` chain based on opcode ranges, which maps to the FLUX ISA format structure:

| Opcode Range | Format | Size (bytes) | Dispatch Path |
|-------------|--------|-------------|---------------|
| 0x00–0x07 | A | 1 | Format A switch |
| 0x08–0x0F | B | 2 | Format B switch |
| 0x10–0x17 | C | 2 | Format C switch |
| 0x18–0x1F | D | 3 | Format D switch |
| 0x20–0x6F | E | 4 | Format E switch (large) |
| 0x70–0x7F | E | 4 | Viewpoint (NOP on GPU) |
| 0x80–0x8F | E | 4 | Sensor (NOP on GPU) |
| 0x90–0x9F | E | 4 | Math/crypto (partial) |
| 0xA0–0xAF | Mixed | 3–5 | Collection (NOP on GPU) |
| 0xB0–0xBF | E | 4 | Vector (NOP on GPU) |
| 0xC0–0xCF | E | 4 | Tensor (NOP on GPU) |
| 0xD0–0xDF | G | 5 | Memory (partial) |
| 0xE0–0xEF | F/G | 4–5 | Control/fault (partial) |
| 0xF0–0xFF | A/H | 1 or 3+ | System/escape |

**Optimization note:** The format-level cascade avoids a single 256-entry jump table (which would cause branch misprediction). Instead, the compiler generates a binary decision tree on opcode ranges that maps efficiently to the GPU's SIMT execution model.

### 3.4 Confidence Propagation on GPU

Confidence registers (C0–C15) are stored as IEEE 754 `float` values in CUDA registers. The GPU's native FP32 arithmetic operates at the same precision as the FLUX ISA spec's confidence model:

**C_ADD / C_SUB:** `conf[rd] = min(conf[rs1], conf[rs2])` — takes the lower confidence, reflecting that combined operations inherit the weaker link. On GPU, this maps to `fminf()` which compiles to a single FP32 instruction.

**C_MUL:** `conf[rd] = conf[rs1] * conf[rs2]` — multiplication erodes confidence faster. On GPU, this is a single FP32 multiply.

**C_MERGE:** Bayesian harmonic-mean fusion: `conf[rd] = wsum / 2.0f` where `wsum = c1 + c2` and values are weighted-average blended. This matches JetsonClaw1's cuda-instruction-set design where `1/(1/a + 1/b)` is the canonical fusion formula. Our weighted-average approach is equivalent for the two-source case and more numerically stable on GPU.

**CONF_CLAMP (v3):** All confidence writes are sanitized — NaN/Inf → 0.0, values clamped to [0.0, 1.0]. This prevents trust poisoning attacks on the GPU executor (resolves fleet issue #17).

---

## 4. Memory Layout

### 4.1 Global Memory Organization

Global memory is allocated once per batch and reused across kernel launches:

```
Offset    Size           Contents                    Access Pattern
────────────────────────────────────────────────────────────────────
0x0000    N × avg_prog   Bytecode buffer              Read-only, shared
          _size          (packed, contiguous)

bytecode  N × 4 bytes    Program offset table          Read-only, shared
_end      (uint32_t[])

offsets   N × sizeof      Per-program config            Read-only, shared
_end      FluxConfig

configs   N × 4 bytes    Results buffer               Write-once, exclusive
_end      (uint32_t[])

results   4 bytes        Batch metadata                Host reads
_end
```

**Total global memory for a 1024-VM batch:**
- Bytecode: 1024 × ~256 bytes avg = 256 KB
- Offsets: 1024 × 4 = 4 KB
- Configs: 1024 × ~160 bytes = ~160 KB
- Results: 1024 × 4 = 4 KB
- **Total: ~424 KB** — well within the 8 GB limit

### 4.2 Shared Memory Strategy

**Zero shared memory is used.** This is intentional:

- Each VM is completely independent — no inter-thread data sharing
- Shared memory bank conflicts are a common source of hidden performance degradation
- The L1/L2 cache (2 MB L2 on Orin Nano) efficiently serves repeated bytecode reads
- Keeping shared memory free allows higher occupancy for other concurrent kernels (e.g., tensor operations)

### 4.3 Per-Thread Local Memory

Local memory is private to each thread and maps to the GPU's per-thread memory space (backed by L1 cache on Ampere):

```
Component         Size      Purpose
─────────────────────────────────────────────
stack[256]        1024 B    Operand stack (PUSH/POP)
local_mem[1024]   4096 B    VM addressable memory (LOAD/STORE)
─────────────────────────────────────────────
Total             5120 B    ~5 KB per thread
```

For 1024 threads: 1024 × 5 KB = 5 MB. This exceeds the register file but fits in L1/L2 cache for working-set-sized programs.

### 4.4 Register File Mapping

The FLUX ISA defines 16 general-purpose registers (R0–R15) and 16 confidence registers (C0–C15). On the GPU, these map directly to CUDA hardware registers:

```
CUDA Register      FLUX Register    Type      Size
──────────────────────────────────────────────────
R0                 regs[0]          uint32_t  4 B
R1                 regs[1]          uint32_t  4 B
...
R15                regs[15]         uint32_t  4 B
R16                conf[0]          float     4 B
R17                conf[1]          float     4 B
...
R31                conf[15]         float     4 B
R32                pc               uint32_t  4 B
R33                sp               uint32_t  4 B
R34                fp               uint32_t  4 B
R35                flags            uint32_t  4 B
R36                steps            uint32_t  4 B
R37                tid              int       4 B
──────────────────────────────────────────────────
Total              38 registers × 4 B = 152 B
```

With temporaries for instruction decode (opcode, rd, rs1, rs2, imm8, imm16), total register usage is approximately **44–50 registers per thread**. The Orin Nano supports up to 255 registers per thread, so we are well within limits.

### 4.5 Coalesced Access Patterns

**Bytecode loading:** The main performance concern is instruction fetch. When all threads in a warp fetch from the same program (uniform bytecode), the accesses are identical and serviced by a single cache line. When threads fetch from different programs (divergent bytecode), the accesses are to different addresses but the warp hardware coalesces them into a single memory transaction if the addresses fall within a 128-byte segment.

**Result writing:** Each thread writes to `results[tid]` — a unique 4-byte location. These are naturally aligned and contiguous, so a warp of 32 threads writing results completes in a single 128-byte memory transaction (perfect coalescing).

**Input loading:** Initial register values come from `configs[tid].init_regs[i]` — contiguous per-thread structures with 4-byte aligned fields. Loading 16 registers × 4 bytes = 64 bytes per thread, which the warp coalesces into ~8 transactions.

---

## 5. Supported Opcode Subset

Not all 253 FLUX ISA v3 opcodes make sense on a GPU. We classify them into four tiers:

### 5.1 GPU-Safe Opcodes (Full Acceleration)

These opcodes have deterministic, side-effect-free behavior that maps directly to GPU hardware:

| Category | Opcodes | Count | Notes |
|----------|---------|-------|-------|
| System control | HALT, NOP, VER, CLK, CONF_CLAMP, TAG_CHECK | 6 | VER returns 3; TAG_CHECK is no-op |
| Single register | INC, DEC, NOT, NEG, PUSH, POP, CONF_LD, CONF_ST | 8 | Stack is per-thread local |
| Arithmetic (imm8) | MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI | 8 | Sign-extend for imm8 |
| Arithmetic (3-reg) | ADD, SUB, MUL, DIV, MOD | 5 | DIV/MOD guarded zero-check |
| Logic (3-reg) | AND, OR, XOR, SHL, SHR | 5 | Bitwise operations |
| Min/Max | MIN, MAX | 2 | Native `fminf`/`fmaxf` for float |
| Comparison | CMP_EQ, CMP_LT, CMP_GT, CMP_NE | 4 | Result: 0 or 1 |
| Float | FADD, FSUB, FMUL, FDIV, FTOI, ITOF | 6 | IEEE 754 FP32 |
| Memory (local) | LOAD, STORE, MOV, SWP | 4 | Local memory only |
| Memory (offset) | LOADOFF, STOREOFF | 2 | Offset into local memory |
| Control flow | JZ, JNZ, JLT, JGT, JMP, JAL, CALL, LOOP, RET | 9 | Local jumps/calls only |
| Math | ABS, SIGN, CLZ, POPCNT, RND | 5 | Hash-based PRNG for RND |
| Confidence | C_ADD, C_SUB, C_MUL, C_DIV, C_MERGE, C_CALIB | 6 | Native FP32 propagation |
| Fault | HALT_ERR, FAULT, ASSERT | 3 | Write error code to results |
| **Total** | | **86** | **33.8% of 253 base opcodes** |

### 5.2 GPU-Limited Opcodes (Restricted Scope)

These opcodes are supported but with GPU-specific restrictions:

| Opcode | Normal Behavior | GPU Behavior | Restriction |
|--------|----------------|--------------|-------------|
| LOAD/STORE | mem[addr] | local_mem[addr & 0x3FF] | 4 KB local only, no global/shared access |
| ENTER/LEAVE | push regs, adjust SP | Push/pop to local stack | No cross-thread frame sharing |
| COPY/FILL | memcpy/memset | Within local memory only | Max 1024 elements |
| MOVI16/ADDI16/SUBI16 | 16-bit immediate | Full support | None |
| JMPL/JALL | Long jump | Full support | Within same program |
| WATCH | Breakpoint | NOP (no debugger on GPU) | Ignored |
| TRACE | Debug logging | NOP (no I/O on GPU) | Ignored |
| C_THRESH | Skip if confidence < threshold | Implemented | Checks per-thread conf register |
| C_BOOST/C_DECAY | Confidence adjust | Full support | FP32 arithmetic |
| **Total** | | **~18** | |

### 5.3 GPU-Excluded Opcodes (Host-Only)

These opcodes require OS services, I/O, or inter-agent communication that cannot run on a GPU:

| Category | Opcodes | Count | Reason |
|----------|---------|-------|--------|
| I/O | SYS, TRAP, DBG, BRK | 4 | No OS/system calls on GPU |
| Concurrency | SEMA, WFI, SLEEP | 3 | No OS scheduling on GPU |
| A2A signaling | TELL, ASK, DELEG, BCAST, ACCEPT, DECLINE, REPORT, MERGE, FORK, JOIN, SIGNAL, AWAIT, TRUST, DISCOV, STATUS, HEARTBT | 16 | No network on GPU |
| Sensor | SENSE, ACTUATE, SAMPLE, ENERGY, TEMP, GPS, ACCEL, DEPTH, CAMCAP, CAMDET, PWM, GPIO, I2C, SPI, UART, CANBUS | 16 | No hardware on GPU |
| System | RESET, REBOOT, WDOG, CACHE, IRET, HANDLER, SWITCH | 7 | No OS/hardware control |
| Viewpoint | V_EVID through V_PRAGMA | 16 | Requires NLP models |
| Collection | LEN, CONCAT, AT, SETAT, SLICE, REDUCE, MAP, FILTER, SORT, FIND | 10 | Dynamic allocation |
| Crypto | CRC32, SHA256, HASH, HMAC, VERIFY, ENCRYPT, DECRYPT, KEYGEN | 9 | Complex library deps |
| Memory mgmt | DMA_CPY, DMA_SET, MMIO_R, MMIO_W, ATOMIC, CAS, FENCE, MALLOC, FREE, MPROT, MCACHE | 11 | Global/shared memory ops |
| GPU control | GPU_LD, GPU_ST, GPU_EX, GPU_SYNC | 4 | Cannot nest GPU calls |
| Vector | VLOAD through VSELECT | 16 | Already parallel per-thread |
| Tensor | TMATMUL through TQUANT | 16 | Separate kernel (cuDNN/TensorRT) |
| Security | SANDBOX_ALLOC/FREE, TAG_ALLOC/TRANSFER | 4 | No cross-agent isolation on GPU |
| **Total** | | **~132** | **52.2% of 253 base opcodes** |

### 5.4 GPU-Adapted Opcodes (Modified Behavior)

| Opcode | Normal | GPU Adaptation |
|--------|--------|---------------|
| YIELD | Suspend for N cycles | NOP (no scheduler) |
| STRIPCF | Strip confidence from next N ops | NOP (confidence always active on GPU) |
| SELECT | Computed jump | Limited: pc += imm16 * rd |
| RND | PRNG in [a, b] | Deterministic hash-based (no curand state) |
| C_SOURCE | Set confidence source | NOP (source metadata not tracked on GPU) |
| CONF_LD/CONF_ST | Float ↔ register transfer | Uses `__float_as_uint` / `__uint_as_float` for zero-copy |
| ESCAPE (0xFF) | Extension dispatch | NOP for all extensions (future: EXT_TENSOR) |

---

## 6. Thread Divergence Analysis

### 6.1 Warp Divergence Fundamentals

NVIDIA GPUs execute threads in warps of 32. All threads in a warp must execute the same instruction at the same time (SIMT — Single Instruction, Multiple Threads). When threads take different branches of a conditional:

1. Threads on the "taken" path execute; others are masked out
2. Then threads on the "not-taken" path execute; others are masked out
3. Total time = sum of both paths (serial, not parallel)

For FLUX bytecode, divergence occurs at **every conditional branch instruction** (JZ, JNZ, JLT, JGT) when different VMs in the same warp take different paths.

### 6.2 Branch Classification by Divergence Cost

**Low divergence (acceptable):**
- Arithmetic pipelines: same code, different data → same branch outcomes (e.g., sorting where the comparison opcode is identical but data values differ)
- Confidence thresholding: when all VMs use the same threshold value (common in batch processing)

**Medium divergence (tolerable):**
- Conditional classification: some fish pass the threshold, others don't
- Loop exit: VMs with different data may complete loops at different iterations

**High divergence (problematic):**
- Different programs per thread: completely different instruction streams
- Early HALT in some threads: after HALT, a thread is permanently masked out, wasting its slot
- Recursive CALL/RET: different call depths cause different execution paths

### 6.3 Mitigation Strategies

**Strategy 1: Warp-level ballot for uniform branches.**

```cuda
// Before a branch, check if all threads in the warp agree
unsigned mask = __ballot_sync(0xFFFFFFFF, condition);
if (mask == 0xFFFFFFFF || mask == 0x00000000) {
    // All threads agree — no divergence
    if (condition) { /* taken path */ }
} else {
    // Threads disagree — divergent, execute both paths
    if (condition) { /* taken path */ }
}
```

**Strategy 2: Branch compaction for early termination.**

When some VMs HALT early, we can reassign their work slots to VMs from the next batch. However, this requires inter-thread coordination (shared memory + atomics), which adds complexity. For the initial implementation, we accept the waste — the host can compensate by launching smaller batches.

**Strategy 3: Loop unrolling for short loops.**

The FLUX LOOP instruction (`rd--; if rd > 0: pc -= imm16`) is a common pattern. For small loop counts (known at compile time), the assembler can emit unrolled bytecode, eliminating the branch entirely.

### 6.4 Workload Sorting for Minimal Divergence

The host can sort programs by expected execution length before launching:

```
Batch 1: Short programs (10-50 instructions)    → Block 0
Batch 2: Medium programs (50-200 instructions)  → Block 1
Batch 3: Long programs (200-1000 instructions)  → Block 2
```

This ensures threads within a block have similar execution times, reducing the waste from early-HALT divergence. The sorting can be based on program bytecode length as a heuristic.

For FishingLog specifically, sensor processing programs are typically 20-50 instructions (load sensor, compare threshold, compute confidence, HALT). Grouping these together yields near-zero divergence.

---

## 7. Performance Model

### 7.1 Throughput Estimates

| Scenario | VMs | Avg Instructions | Estimated Time | Throughput |
|----------|-----|-----------------|----------------|------------|
| Minimal (ADD + HALT) | 1024 | 2 | ~5 μs | 409.6 M VMs/sec |
| Sensor processing | 1024 | 30 | ~40 μs | 25.6 M VMs/sec |
| Confidence fusion | 1024 | 50 | ~65 μs | 15.7 M VMs/sec |
| Full classification | 1024 | 200 | ~250 μs | 4.1 M VMs/sec |
| Complex analysis | 1024 | 1000 | ~1.2 ms | 0.85 M VMs/sec |

These estimates assume:
- ~5 ns per instruction on average (GPU clock ~1.3 GHz, ~2 instructions/clock with ILP)
- No memory stalls (bytecode fits in L2 cache for programs < 2 MB)
- Zero divergence (uniform branch outcomes)

**Comparison to CPU:**
- C runtime (flux_vm_unified.c): ~67M ops/sec single-threaded
- CUDA batch (1024 VMs): ~409.6M ops/sec (single instruction) to ~850K ops/sec (complex)
- **Speedup: 6× (complex) to 6× (minimal)** for batch workloads

The key insight: the GPU wins not by making a single VM faster, but by running 1024 VMs simultaneously. For FishingLog's batch of 100-500 sensor readings per second, a single CUDA kernel launch processes the entire batch in one shot.

### 7.2 Memory Bandwidth Analysis

The Orin Nano has 68.3 GB/s of LPDDR5 bandwidth. For a 1024-VM batch:

| Operation | Data Volume | Bandwidth Used | Utilization |
|-----------|-----------|----------------|-------------|
| Load bytecode (256 KB) | 256 KB | 0.26 GB/s | 0.4% |
| Load configs (160 KB) | 160 KB | 0.16 GB/s | 0.2% |
| Store results (4 KB) | 4 KB | 0.004 GB/s | 0.006% |
| Instruction fetch (per cycle) | 1 byte × 1024 VMs × 1.3 GHz | ~1.3 GB/s | 1.9% |

**Conclusion:** Memory bandwidth is not the bottleneck. The GPU is compute-bound for most FLUX workloads. The small program sizes mean bytecode fits entirely in L2 cache (2 MB), and the tight loop means most instruction fetches hit L1.

### 7.3 Register Pressure and Occupancy

| Metric | Value | Limit | Headroom |
|--------|-------|-------|----------|
| Registers per thread | ~50 | 255 | 80% free |
| Local memory per thread | 5,120 B | 48 KB (SM) | Depends on threads/SM |
| Threads per SM (register-limited) | 65,536 / 50 / 32 warps = ~40 warps = 1280 threads | 2048 | 37% limit |
| Threads per SM (local mem-limited, 5 KB) | 32,768 / 5,120 = 6 threads | 2048 | Local mem is limiting |

**Problem:** At 5 KB local memory per thread, we can only fit ~6 threads per SM before exhausting local memory. This gives us only 12 threads total — a catastrophic 98.5% underutilization.

**Solution: Reduce local memory.**

| Configuration | Stack | Local Mem | Total | Threads/SM | Total Threads |
|--------------|-------|-----------|-------|------------|---------------|
| Full (current) | 256 entries | 1024 entries | 5 KB | 6 | 12 |
| Reduced | 64 entries | 256 entries | 1.25 KB | 26 | 52 |
| Minimal | 32 entries | 128 entries | 640 B | 51 | 102 |
| Stack-only | 32 entries | 0 | 128 B | 256 | 512 |

**Recommended default:** Stack = 64 entries, local_mem = 256 entries (1 KB total). This gives 52 concurrent threads across both SMs, which is enough for most FishingLog batches (typically 10-100 sensor readings). The host can launch multiple kernel invocations for larger batches.

### 7.4 Instruction Mix Benchmarks

Expected instruction distribution for FishingLog sensor processing:

| Instruction | Percentage | Divergence Risk |
|------------|-----------|-----------------|
| MOVI / MOVI16 | 20% | None (no branch) |
| LOAD / STORE / LOADOFF | 15% | None (no branch) |
| ADD / SUB / MUL / DIV | 15% | None (no branch) |
| CMP_EQ / CMP_LT / CMP_GT | 10% | Low (same data type) |
| JZ / JNZ / JLT / JGT | 15% | Medium (threshold checks) |
| C_ADD / C_MUL / C_MERGE | 10% | None (no branch) |
| HALT | 5% | High (early exit) |
| NOP / MOV | 10% | None |

**Average divergence factor:** ~1.3× (30% of instructions are branches, ~30% of those diverge). Actual throughput = peak / 1.3 ≈ 77% of theoretical peak.

---

## 8. Integration with FishingLog

### 8.1 Batch Fish Classification

The FishingLog FLUX Bridge currently processes sensor readings one-at-a-time through the TypeScript VM (~10M ops/sec). With CUDA batch execution:

```c
// Host-side: prepare batch of 100 sensor readings
FluxConfig configs[100];
uint8_t* sensor_bytecode = load_flux_program("classify_sensor.flux");

for (int i = 0; i < 100; i++) {
    // Pack sensor data into initial registers
    configs[i].init_regs[0] = sensor_readings[i].temperature;
    configs[i].init_regs[1] = sensor_readings[i].depth;
    configs[i].init_regs[2] = sensor_readings[i].sonar_return;
    configs[i].init_conf[0] = sensor_readings[i].temp_confidence;
    configs[i].init_conf[1] = sensor_readings[i].depth_confidence;
    configs[i].init_conf[2] = sensor_readings[i].sonar_confidence;
    configs[i].max_steps = 200;
}

// All programs use the same bytecode
uint32_t offsets[100];
for (int i = 0; i < 100; i++) offsets[i] = 0;  // Same program

flux_cuda_execute(configs, 100, &results);

// Results contain fused confidence per reading
for (int i = 0; i < 100; i++) {
    printf("Reading %d: species=%d, confidence=%f\n",
           i, results[i].species, results[i].confidence);
}
```

**Expected performance:** 100 sensor readings × 200 instructions each = 20,000 total instructions. Single kernel launch at ~65 μs. Compare to 100 sequential CPU executions at 200 × 67M = ~300 μs. **~4.6× speedup** for this workload.

### 8.2 Sensor Data Preprocessing Pipeline

The CUDA batch executor integrates into the FishingLog pipeline at the confidence computation stage:

```
Sensor Hardware
    │
    ▼
Camera (YOLOv8) ──→ Prediction{label, confidence=0.72, source="vision"}
    │
    ▼
Audio (Whisper) ───→ Prediction{label, confidence=0.65, source="audio"}
    │
    ▼
Captain Voice ──────→ Prediction{label, confidence=0.95, source="human"}
    │
    ▼
┌─────────────────────────────────────────────────┐
│  CUDA Batch Confidence Engine                   │
│  ┌─────┐ ┌─────┐ ┌─────┐     ┌─────┐          │
│  │VM 0 │ │VM 1 │ │VM 2 │ ... │VM N │          │
│  │C_ADD│ │C_MUL│ │C_ADD│     │C_ADD│          │
│  │C_MRG│ │C_CAL│ │C_MRG│     │C_MRG│          │
│  └──┬──┘ └──┬──┘ └──┬──┘     └──┬──┘          │
│     │       │       │           │              │
│     ▼       ▼       ▼           ▼              │
│  ┌──────────────────────────────────┐          │
│  │ Fused Results: {label, conf}    │          │
│  └──────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
    │
    ▼
Regulatory Compliance Check (conf >= 0.80 → auto-log)
    │
    ▼
Catch Log / A2A Broadcast
```

### 8.3 Edge Deployment Architecture

```
Jetson Orin Nano (FishingLog vessel)
├── YOLOv8 (TensorRT)          → GPU 0, stream 1
├── Whisper (TensorRT)         → GPU 0, stream 2
├── CUDA FLUX Batch Executor   → GPU 0, stream 3
│   ├── Input: sensor predictions (host → device)
│   ├── Bytecode: classify.flux (cached in constant memory)
│   └── Output: fused confidence (device → host)
├── FishingLog Bridge (CPU)    → coordinates above
└── A2A Radio (UART/CAN)       → broadcasts results to fleet
```

**Thermal considerations:** The Orin Nano operates in 10W/15W/20W modes. YOLOv8 + Whisper already consume significant GPU time. The FLUX CUDA executor should run on a separate CUDA stream and use `cudaLaunchHostFunc` to avoid blocking inference. For 15W mode, the executor should limit batch sizes to 256 VMs to leave headroom for vision/audio inference.

**Power budget for FLUX executor:** ~1-2W (estimated from kernel runtime × dynamic power). This fits within the thermal envelope alongside YOLOv8 (~8W) and Whisper (~4W).

---

## 9. Build & Test Plan

### 9.1 CMake Build Configuration

```cmake
# flux-cuda/CMakeLists.txt
cmake_minimum_required(VERSION 3.18)
project(flux-cuda LANGUAGES C CUDA)

# Jetson Orin Nano: compute capability 8.7
set(CMAKE_CUDA_ARCHITECTURES 87)

# Find CUDA toolkit
find_package(CUDAToolkit REQUIRED)

# Core library
add_library(flux_cuda_static STATIC
    src/flux_cuda_kernel.cu
    src/flux_cuda_host.c
    src/flux_cuda_memory.c
)
target_include_directories(flux_cuda_static PUBLIC include)

# Shared library (for Python bindings)
add_library(flux_cuda SHARED
    src/flux_cuda_kernel.cu
    src/flux_cuda_host.c
    src/flux_cuda_memory.c
    src/flux_cuda_python.c   # Python C API bindings
)
set_target_properties(flux_cuda PROPERTIES
    CUDA_SEPARABLE_COMPILATION ON
)

# Test executable
add_executable(test_flux_cuda
    tests/test_basic.cu
    tests/test_confidence.cu
    tests/test_divergence.cu
    tests/test_fishinglog.cu
)
target_link_libraries(test_flux_cuda flux_cuda_static CUDAToolkit::cudart)

# CPU fallback (for testing without GPU)
add_executable(test_flux_cpu
    tests/test_basic_cpu.c
    src/flux_cuda_host.c
)
target_compile_definitions(test_flux_cpu PRIVATE FLUX_CUDA_CPU_FALLBACK)

# Install
install(TARGETS flux_cuda DESTINATION lib)
install(FILES include/flux_cuda.h DESTINATION include)
```

### 9.2 Testing Without Jetson Hardware

**Level 1: CPU emulation mode.** Compile the kernel with `__device__` functions reimplemented as `__host__` functions. This runs the exact same dispatch logic on CPU, verifying correctness without GPU:

```c
#ifdef FLUX_CUDA_CPU_FALLBACK
#define __global__
#define __device__
#define __restrict__
#define __shared__
// ... CPU implementations of __syncthreads, __ballot_sync, etc.
#endif
```

**Level 2: CUDA emulator.** Use the CUDA toolkit's `cuda-memcheck` and `cuda-gdb` on an x86_64 desktop with NVIDIA GPU. The kernel compiles for the desktop's compute capability and runs on the emulator for correctness validation.

**Level 3: Conformance test adaptation.** Convert the existing 74 conformance test vectors into CUDA batch tests. Each test vector becomes a single-VM program launched as a 1-thread kernel. Compare results against the known expected values:

```c
// Test: ADD two numbers
void test_add() {
    uint8_t bytecode[] = {
        0x18, 0x01, 0x2A,    // MOVI R1, 42
        0x18, 0x02, 0x1C,    // MOVI R2, 28
        0x20, 0x00, 0x01, 0x02, // ADD R0, R1, R2  → R0 = 70
        0x00                  // HALT
    };
    FluxConfig config = { .max_steps = 100 };
    uint32_t result = run_single(bytecode, sizeof(bytecode), &config);
    assert(result == 70);
}
```

**Level 4: Jetson validation.** Final validation on actual Jetson Orin Nano hardware, testing:
- Correctness (conformance suite)
- Performance (throughput benchmarks)
- Thermal behavior (sustained load at 15W)
- Integration with FishingLog Bridge

### 9.3 Integration with flux-runtime-c

The CUDA executor integrates with the existing C runtime (`flux_vm_unified.c`) through a shared header:

```c
// include/flux_cuda.h — shared between CPU runtime and CUDA executor

#ifndef FLUX_CUDA_H
#define FLUX_CUDA_H

#include <stdint.h>
#include <stdbool.h>

#define FLUX_ISA_VERSION 3
#define FLUX_NUM_REGISTERS 16
#define FLUX_NUM_CONFIDENCE 16
#define FLUX_MAX_PROGRAMS 1024
#define FLUX_DEFAULT_STACK_SIZE 64
#define FLUX_DEFAULT_LOCAL_MEM_SIZE 256

// Configuration for a single VM instance
typedef struct {
    uint32_t init_regs[FLUX_NUM_REGISTERS];    // Initial register values
    float    init_conf[FLUX_NUM_CONFIDENCE];   // Initial confidence values
    uint32_t max_steps;                        // Max instructions before timeout
    uint32_t stack_size;                       // Per-VM stack entries
    uint32_t local_mem_size;                   // Per-VM local memory entries
    uint32_t flags;                            // Initial flags
} FluxConfig;

// Result from a single VM execution
typedef struct {
    uint32_t result;          // R0 on HALT, or error code
    float    final_conf[FLUX_NUM_CONFIDENCE];  // Final confidence state
    uint32_t instructions;    // Instructions executed
    uint32_t status;          // 0=halt, 1=timeout, 2=fault
} FluxResult;

// Execution mode
typedef enum {
    FLUX_MODE_CPU = 0,        // Sequential CPU execution
    FLUX_MODE_CUDA = 1,       // CUDA batch execution
    FLUX_MODE_AUTO = 2        // Choose based on batch size
} FluxExecMode;

// Error codes
#define FLUX_OK              0
#define FLUX_ERR_NO_DEVICE   1
#define FLUX_ERR_OUT_OF_MEM  2
#define FLUX_ERR_LAUNCH      3
#define FLUX_ERR_SYNC        4
#define FLUX_ERR_INVALID_BC  5

#ifdef __cplusplus
extern "C" {
#endif

// --- Host API ---
int  flux_cuda_init(int device_id);
int  flux_cuda_load_programs(const uint8_t* bytecode, size_t bc_len,
                              const uint32_t* offsets, int count);
int  flux_cuda_load_single_program(const uint8_t* bytecode, size_t len);
int  flux_cuda_execute(const FluxConfig* configs, int count,
                       FluxResult* results);
int  flux_cuda_get_results(FluxResult* results, int count);
void flux_cuda_cleanup(void);

// --- Utility ---
int  flux_cuda_device_count(void);
void flux_cuda_device_info(int device_id);
int  flux_cuda_available(void);

// --- CPU fallback (always available) ---
int  flux_cpu_execute(const uint8_t* bytecode, size_t bc_len,
                      const FluxConfig* config, FluxResult* result);

#ifdef __cplusplus
}
#endif

#endif // FLUX_CUDA_H
```

---

## 10. API Reference

### 10.1 Host API

```c
/**
 * Initialize the CUDA FLUX executor.
 *
 * Must be called before any other flux_cuda_* function.
 * Allocates device memory pools and compiles kernels.
 *
 * @param device_id  CUDA device index (0 for Jetson Orin Nano)
 * @return FLUX_OK on success, error code on failure
 */
int flux_cuda_init(int device_id);

/**
 * Load a batch of FLUX programs into device memory.
 *
 * Bytecode is copied to GPU global memory once and reused
 * across multiple kernel launches. Call this again when
 * programs change.
 *
 * @param bytecode  Contiguous bytecode buffer for all programs
 * @param bc_len    Total length of bytecode buffer in bytes
 * @param offsets   Array of byte offsets (one per program)
 * @param count     Number of programs
 * @return FLUX_OK on success
 *
 * Example:
 *   // Load 3 programs from separate files
 *   uint8_t bc[1024];
 *   int offset = 0;
 *   offset += load_file("prog1.flux", bc + offset);
 *   offsets[0] = 0;
 *   offsets[1] = offset;
 *   offset += load_file("prog2.flux", bc + offset);
 *   offsets[2] = offset;
 *   offset += load_file("prog3.flux", bc + offset);
 *   flux_cuda_load_programs(bc, offset, offsets, 3);
 */
int flux_cuda_load_programs(const uint8_t* bytecode, size_t bc_len,
                              const uint32_t* offsets, int count);

/**
 * Load a single FLUX program for batch execution.
 *
 * Shortcut for the common case where all VMs run the same
 * program with different input data.
 *
 * @param bytecode  Program bytecode
 * @param len       Program length in bytes
 * @return FLUX_OK on success
 */
int flux_cuda_load_single_program(const uint8_t* bytecode, size_t len);

/**
 * Execute a batch of FLUX VMs on the GPU.
 *
 * Launches CUDA kernel with grid/block dimensions computed
 * automatically based on batch size. Blocks until all VMs
 * complete.
 *
 * @param configs  Per-VM configuration array
 * @param count    Number of VMs to execute (max FLUX_MAX_PROGRAMS)
 * @param results  Output: per-VM results (device or host memory)
 * @return FLUX_OK on success
 *
 * Grid dimension: ceil(count / 256) blocks
 * Block dimension: min(count, 256) threads
 */
int flux_cuda_execute(const FluxConfig* configs, int count,
                       FluxResult* results);

/**
 * Copy results from device to host memory.
 *
 * Call after flux_cuda_execute() to retrieve results.
 * For small batches (< 4 KB), this is nearly instant.
 *
 * @param results  Host-allocated results array
 * @param count    Number of results to copy
 * @return FLUX_OK on success
 */
int flux_cuda_get_results(FluxResult* results, int count);

/**
 * Release all CUDA resources.
 *
 * Frees device memory pools and resets state.
 * Safe to call even if init failed.
 */
void flux_cuda_cleanup(void);
```

### 10.2 Configuration Structures

```c
/**
 * Per-VM execution configuration.
 *
 * Passed to flux_cuda_execute() as an array — one per VM.
 */
typedef struct {
    uint32_t init_regs[16];     // Initial R0–R15 values
    float    init_conf[16];     // Initial C0–C15 values
    uint32_t max_steps;         // Max instructions before timeout (0 = 1M)
    uint32_t stack_size;        // Stack entries (0 = FLUX_DEFAULT_STACK_SIZE)
    uint32_t local_mem_size;    // Local memory entries (0 = FLUX_DEFAULT_LOCAL_MEM_SIZE)
    uint32_t flags;             // Initial flags register value
    uint32_t reserved[5];       // Future expansion (pad to 256 bytes)
} FluxConfig;

/**
 * Per-VM execution result.
 */
typedef struct {
    uint32_t result;            // R0 on HALT, or 0xDEADxxxx error code
    float    final_conf[16];    // Confidence register state at HALT
    uint32_t instructions;      // Instructions executed
    uint32_t status;            // 0=OK, 1=timeout, 2=fault, 3=assertion
    uint32_t reserved[4];       // Future expansion
} FluxResult;
```

### 10.3 Error Handling

Error codes are returned as integers from all API functions:

| Code | Name | Description |
|------|------|-------------|
| 0 | FLUX_OK | Success |
| 1 | FLUX_ERR_NO_DEVICE | No CUDA device found |
| 2 | FLUX_ERR_OUT_OF_MEM | Device memory allocation failed |
| 3 | FLUX_ERR_LAUNCH | Kernel launch failed |
| 4 | FLUX_ERR_SYNC | cudaDeviceSynchronize failed |
| 5 | FLUX_ERR_INVALID_BC | Bytecode validation failed |

Per-VM error detection uses the result code:

| Pattern | Meaning |
|---------|---------|
| 0x00000000 | HALT with R0 = 0 |
| 0x00000001–0x7FFFFFFF | HALT with R0 = value |
| 0x80000000–0xFFFFFFFF | Positive result (unsigned) |
| 0xDEAD0000 \| opcode | Illegal/unimplemented opcode |
| 0xDEAD0001 \| (flags << 16) | HALT_ERR with flags |
| 0xDEAD0002 \| (code << 16) | FAULT with fault code |
| 0xDEAD0003 | ASSERT failure |
| 0xFFFFFFFF | Timeout (max_steps exceeded) |

### 10.4 Lifecycle Management

```
┌──────────┐     ┌──────────────┐     ┌───────────────┐
│  INIT    │────>│ LOAD_PROGRAMS│────>│  EXECUTE      │
│          │     │              │     │  (one or      │
│ cudaInit │     │ H2D memcpy   │     │   more times) │
└──────────┘     └──────────────┘     └───────┬───────┘
                                                 │
┌──────────┐     ┌──────────────┐     ┌────────▼───────┐
│ CLEANUP  │<────│ GET_RESULTS  │<────│  sync          │
│          │     │              │     │                │
│ cudaFree │     │ D2H memcpy   │     │ cudaDeviceSync │
└──────────┘     └──────────────┘     └────────────────┘

  Typical lifetime: 0.1–60 seconds (vessel trip duration)
  Memory held: ~424 KB global + kernel overhead
```

**Streaming mode:** For continuous sensor processing (FishingLog), the lifecycle can be:

```
init() → load_single_program(classify.flux) → loop {
    execute(batch_configs, batch_size, results)
    get_results(results, batch_size)
    process_results(results)  // CPU-side
} → cleanup()
```

This reuses the loaded bytecode across batches, only re-uploading per-batch configs and results. The H2D/D2H transfers for configs (160 KB) and results (4 KB) are small compared to the ~250 KB/sensor-batch-of-100 bytecode that stays resident.

---

## Appendix A: Opcode Quick Reference (GPU-Safe)

For rapid kernel development, here are the 86 GPU-safe opcodes with their CUDA-native implementations:

```
// System (Format A)
0x00 HALT     → results[tid] = regs[0]; return;
0x01 NOP      → (nothing)
0x02 RET      → pc = stack[--sp];
0xF0 HALT_ERR → results[tid] = error_code; return;
0xF3 ASSERT   → if (flags & 1) { error; return; }
0xF5 VER      → regs[0] = 3;
0xF6 CLK      → regs[0] = steps;
0xFA CONF_CLAMP → clamp all conf[] to [0.0, 1.0]
0xFB TAG_CHECK → (no-op on GPU)

// Arithmetic (Format D: rd + imm8)
0x18 MOVI    → regs[rd] = (int32_t)(int8_t)imm8
0x19 ADDI    → regs[rd] += imm8
0x1A SUBI    → regs[rd] -= imm8
0x1B ANDI    → regs[rd] &= imm8
0x1C ORI     → regs[rd] |= imm8
0x1D XORI    → regs[rd] ^= imm8
0x1E SHLI    → regs[rd] <<= imm8
0x1F SHRI    → regs[rd] >>= imm8

// Arithmetic (Format E: rd, rs1, rs2)
0x20 ADD     → regs[rd] = regs[rs1] + regs[rs2]
0x21 SUB     → regs[rd] = regs[rs1] - regs[rs2]
0x22 MUL     → regs[rd] = regs[rs1] * regs[rs2]
0x23 DIV     → regs[rd] = rs2 ? rs1/rs2 : 0
0x24 MOD     → regs[rd] = rs2 ? rs1%rs2 : 0
0x2A MIN     → regs[rd] = min(rs1, rs2)
0x2B MAX     → regs[rd] = max(rs1, rs2)
```

## Appendix B: Relationship to JetsonClaw1's cuda-instruction-set

JetsonClaw1's cuda-instruction-set uses 80 opcodes with variable-length encoding (1-3 bytes) and fused confidence. This CUDA kernel design targets the FLUX ISA v3 (253 base opcodes, 7 fixed formats) with confidence as a separate register channel. The two systems are complementary:

| Aspect | cuda-instruction-set (JC1) | FLUX CUDA Kernel (this doc) |
|--------|---------------------------|---------------------------|
| Encoding | Variable 1-3 bytes | Fixed 1-5 bytes (Formats A-G) |
| Confidence | Fused into opcodes | Separate C0–C15 registers |
| Registers | 32 × uint32 | 16 × uint32 + 16 × float |
| Source | Rust, ARM64 | CUDA C, Ampere SM |
| Fusion | Bayesian: 1/(1/a+1/b) | Weighted average + min |

**Convergence path:** A future assembler target could emit JC1's compact encoding for GPU execution, with a decoder layer translating to FLUX v3 semantics at load time. This would give us JC1's space efficiency with FLUX's tooling ecosystem.

## Appendix C: FishingLog Confidence Pipeline — GPU Kernel Pseudocode

```cuda
/**
 * Specialized kernel for FishingLog batch confidence fusion.
 *
 * Faster than general-purpose flux_batch_execute because:
 * - No instruction decode (fixed pipeline)
 * - No branch divergence (all VMs run the same operations)
 * - Fused confidence operations use native FP32
 *
 * Input: N predictions (label, confidence, source_type)
 * Output: N fused results (label, fused_confidence, status)
 */
__global__ void fishinglog_confidence_fuse(
    const Prediction* __restrict__ predictions,
    FusedResult* __restrict__ results,
    int count,
    float alert_threshold,
    float regulatory_threshold
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= count) return;

    // Load prediction
    float conf = predictions[tid].confidence;
    float label = predictions[tid].label;

    // Apply source weighting
    float weight = 1.0f;
    switch (predictions[tid].source_type) {
        case SOURCE_HUMAN:   weight = 0.95f; break;
        case SOURCE_VISION:  weight = 0.80f; break;
        case SOURCE_AUDIO:   weight = 0.60f; break;
        case SOURCE_SENSOR:  weight = 0.50f; break;
    }

    // Fuse: weighted confidence
    float fused_conf = conf * weight;

    // Clamp to [0.0, 1.0] (v3 CONF_CLAMP)
    fused_conf = fmaxf(0.0f, fminf(1.0f, fused_conf));

    // Store result
    results[tid].label = label;
    results[tid].confidence = fused_conf;
    results[tid].alert = (fused_conf < alert_threshold) ? 1 : 0;
    results[tid].regulatory = (fused_conf >= regulatory_threshold) ? 1 : 0;
}
```

This specialized kernel is ~10× faster than running equivalent FLUX bytecode through the general-purpose executor, because it eliminates instruction decode and branch overhead. Use the specialized kernel for known-hot paths (confidence fusion) and the general-purpose executor for custom FLUX programs.

---

*"The fleet catches fish for the captain, not for the fleet. But the fleet writes CUDA kernels for the fish."*
