"""
FLUX Unified ISA — The Complete Opcode Table

Three agents, one ISA. This is the converged opcode space:

Oracle1 🔮: 115 base opcodes (Python runtime, semantic layer)
JetsonClaw1 ⚡: 128 opcodes (C runtime, hardware layer, biology/energy)
Babel 🌐: 120 opcodes (104 base + 16 viewpoint, multilingual layer)

Converged: ~200 opcodes organized by FORMAT and function.
Confidence-OPTIONAL: base ops are plain, CONF_ variants at 0x60+.

Encoding: Variable-length by FORMAT (A=1B through G=5B)
All multi-byte formats are little-endian for the immediate fields.

Opcode ranges:
  0x00-0x03  Format A  System control
  0x04-0x07  Format A  Interrupt/control
  0x08-0x0F  Format B  Single register ops
  0x10-0x17  Format C  Immediate-only ops
  0x18-0x1F  Format D  Register + imm8
  0x20-0x2F  Format E  Integer arithmetic (3-reg)
  0x30-0x3F  Format E  Float/memory/control (3-reg)
  0x40-0x47  Format F  Register + imm16
  0x48-0x4F  Format G  Register + register + imm16
  0x50-0x5F  Format E  Agent-to-Agent (fleet ops)
  0x60-0x6F  Format E  Confidence-aware variants
  0x70-0x7F  Format E  Viewpoint ops (Babel reserved)
  0x80-0x8F  Format E  Biology/sensor ops (JetsonClaw1)
  0x90-0x9F  Format E  Extended math/crypto
  0xA0-0xAF  Format D  String/collection ops
  0xB0-0xBF  Format E  Vector/SIMD ops
  0xC0-0xCF  Format E  Tensor/neural ops
  0xD0-0xDF  Format G  Extended memory/mapped I/O
  0xE0-0xEF  Format F  Long jumps/calls
  0xF0-0xFF  Format A  Extended system/debug

Total: 256 opcode slots, ~200 defined, ~56 reserved for future expansion.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import IntEnum


class FormatType(str):
    A = "A"  # 1 byte
    B = "B"  # 2 bytes
    C = "C"  # 2 bytes
    D = "D"  # 3 bytes
    E = "E"  # 4 bytes
    F = "F"  # 4 bytes
    G = "G"  # 5 bytes


@dataclass
class OpcodeDef:
    """Definition of a single opcode in the unified ISA."""
    opcode: int
    mnemonic: str
    format: str
    operands: str
    description: str
    category: str
    source: str  # oracle1, jetsonclaw1, babel, converged
    confidence: bool = False
    reserved: bool = False
    
    def byte_size(self) -> int:
        sizes = {"A": 1, "B": 2, "C": 2, "D": 3, "E": 4, "F": 4, "G": 5}
        return sizes.get(self.format, 1)


def build_unified_isa() -> List[OpcodeDef]:
    """Build the complete unified opcode table."""
    ops = []
    
    def op(code, mnem, fmt, operands, desc, cat, src, conf=False, reserved=False):
        ops.append(OpcodeDef(code, mnem, fmt, operands, desc, cat, src, confidence=conf, reserved=reserved))
    
    def reserved(code, fmt="A"):
        ops.append(OpcodeDef(code, f"RESERVED_{code:02X}", fmt, "-", "Reserved for future use", "reserved", "none", reserved=True))
    
    # ═══════════════════════════════════════════
    # 0x00-0x03: Format A — System Control
    # ═══════════════════════════════════════════
    op(0x00, "HALT",   "A", "-",         "Stop execution",                          "system",   "converged")
    op(0x01, "NOP",    "A", "-",         "No operation (pipeline sync)",             "system",   "converged")
    op(0x02, "RET",    "A", "-",         "Return from subroutine",                  "system",   "oracle1")
    op(0x03, "IRET",   "A", "-",         "Return from interrupt handler",            "system",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0x04-0x07: Format A — Interrupt/Debug
    # ═══════════════════════════════════════════
    op(0x04, "BRK",    "A", "-",         "Breakpoint (trap to debugger)",            "debug",    "converged")
    op(0x05, "WFI",    "A", "-",         "Wait for interrupt (low-power idle)",      "system",   "jetsonclaw1")
    op(0x06, "RESET",  "A", "-",         "Soft reset of register file",              "system",   "jetsonclaw1")
    op(0x07, "SYN",    "A", "-",         "Memory barrier / synchronize",             "system",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0x08-0x0F: Format B — Single Register
    # ═══════════════════════════════════════════
    op(0x08, "INC",    "B", "rd",        "rd = rd + 1",                             "arithmetic", "converged")
    op(0x09, "DEC",    "B", "rd",        "rd = rd - 1",                             "arithmetic", "converged")
    op(0x0A, "NOT",    "B", "rd",        "rd = ~rd (bitwise NOT)",                  "arithmetic", "converged")
    op(0x0B, "NEG",    "B", "rd",        "rd = -rd (arithmetic negate)",            "arithmetic", "converged")
    op(0x0C, "PUSH",   "B", "rd",        "Push rd onto stack",                      "stack",    "converged")
    op(0x0D, "POP",    "B", "rd",        "Pop stack into rd",                       "stack",    "converged")
    op(0x0E, "CONF_LD","B", "rd",        "Load confidence register rd to accumulator", "confidence", "converged")
    op(0x0F, "CONF_ST","B", "rd",        "Store confidence accumulator to register rd", "confidence", "converged")
    
    # ═══════════════════════════════════════════
    # 0x10-0x17: Format C — Immediate Only
    # ═══════════════════════════════════════════
    op(0x10, "SYS",    "C", "imm8",      "System call with code imm8",              "system",   "converged")
    op(0x11, "TRAP",   "C", "imm8",      "Software interrupt vector imm8",           "system",   "jetsonclaw1")
    op(0x12, "DBG",    "C", "imm8",      "Debug print register imm8",               "debug",    "converged")
    op(0x13, "CLF",    "C", "imm8",      "Clear flags register bits imm8",           "system",   "oracle1")
    op(0x14, "SEMA",   "C", "imm8",      "Semaphore operation imm8",                "concurrency", "jetsonclaw1")
    op(0x15, "YIELD",  "C", "imm8",      "Yield execution for imm8 cycles",         "concurrency", "converged")
    op(0x16, "CACHE",  "C", "imm8",      "Cache control (flush/invalidate by imm8)", "system",   "jetsonclaw1")
    op(0x17, "STRIPCF","C", "imm8",      "Strip confidence from next imm8 ops",      "confidence", "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0x18-0x1F: Format D — Register + Imm8
    # ═══════════════════════════════════════════
    op(0x18, "MOVI",   "D", "rd, imm8",  "rd = sign_extend(imm8)",                  "move",     "converged")
    op(0x19, "ADDI",   "D", "rd, imm8",  "rd = rd + imm8",                          "arithmetic", "converged")
    op(0x1A, "SUBI",   "D", "rd, imm8",  "rd = rd - imm8",                          "arithmetic", "converged")
    op(0x1B, "ANDI",   "D", "rd, imm8",  "rd = rd & imm8",                          "logic",    "converged")
    op(0x1C, "ORI",    "D", "rd, imm8",  "rd = rd | imm8",                          "logic",    "converged")
    op(0x1D, "XORI",   "D", "rd, imm8",  "rd = rd ^ imm8",                          "logic",    "converged")
    op(0x1E, "SHLI",   "D", "rd, imm8",  "rd = rd << imm8",                         "shift",    "converged")
    op(0x1F, "SHRI",   "D", "rd, imm8",  "rd = rd >> imm8",                         "shift",    "converged")
    
    # ═══════════════════════════════════════════
    # 0x20-0x2F: Format E — Integer Arithmetic
    # ═══════════════════════════════════════════
    op(0x20, "ADD",    "E", "rd, rs1, rs2", "rd = rs1 + rs2",                       "arithmetic", "converged")
    op(0x21, "SUB",    "E", "rd, rs1, rs2", "rd = rs1 - rs2",                       "arithmetic", "converged")
    op(0x22, "MUL",    "E", "rd, rs1, rs2", "rd = rs1 * rs2",                       "arithmetic", "converged")
    op(0x23, "DIV",    "E", "rd, rs1, rs2", "rd = rs1 / rs2 (signed)",              "arithmetic", "converged")
    op(0x24, "MOD",    "E", "rd, rs1, rs2", "rd = rs1 % rs2",                       "arithmetic", "converged")
    op(0x25, "AND",    "E", "rd, rs1, rs2", "rd = rs1 & rs2",                       "logic",    "converged")
    op(0x26, "OR",     "E", "rd, rs1, rs2", "rd = rs1 | rs2",                       "logic",    "converged")
    op(0x27, "XOR",    "E", "rd, rs1, rs2", "rd = rs1 ^ rs2",                       "logic",    "converged")
    op(0x28, "SHL",    "E", "rd, rs1, rs2", "rd = rs1 << rs2",                      "shift",    "converged")
    op(0x29, "SHR",    "E", "rd, rs1, rs2", "rd = rs1 >> rs2",                      "shift",    "converged")
    op(0x2A, "MIN",    "E", "rd, rs1, rs2", "rd = min(rs1, rs2)",                    "arithmetic", "converged")
    op(0x2B, "MAX",    "E", "rd, rs1, rs2", "rd = max(rs1, rs2)",                    "arithmetic", "converged")
    op(0x2C, "CMP_EQ", "E", "rd, rs1, rs2", "rd = (rs1 == rs2) ? 1 : 0",            "compare",  "converged")
    op(0x2D, "CMP_LT", "E", "rd, rs1, rs2", "rd = (rs1 < rs2) ? 1 : 0",             "compare",  "converged")
    op(0x2E, "CMP_GT", "E", "rd, rs1, rs2", "rd = (rs1 > rs2) ? 1 : 0",             "compare",  "converged")
    op(0x2F, "CMP_NE", "E", "rd, rs1, rs2", "rd = (rs1 != rs2) ? 1 : 0",            "compare",  "converged")
    
    # ═══════════════════════════════════════════
    # 0x30-0x3F: Format E — Float, Memory, Control
    # ═══════════════════════════════════════════
    op(0x30, "FADD",   "E", "rd, rs1, rs2", "rd = f(rs1) + f(rs2)",                 "float",    "oracle1")
    op(0x31, "FSUB",   "E", "rd, rs1, rs2", "rd = f(rs1) - f(rs2)",                 "float",    "oracle1")
    op(0x32, "FMUL",   "E", "rd, rs1, rs2", "rd = f(rs1) * f(rs2)",                 "float",    "oracle1")
    op(0x33, "FDIV",   "E", "rd, rs1, rs2", "rd = f(rs1) / f(rs2)",                 "float",    "oracle1")
    op(0x34, "FMIN",   "E", "rd, rs1, rs2", "rd = fmin(rs1, rs2)",                   "float",    "oracle1")
    op(0x35, "FMAX",   "E", "rd, rs1, rs2", "rd = fmax(rs1, rs2)",                   "float",    "oracle1")
    op(0x36, "FTOI",   "E", "rd, rs1, -",  "rd = int(f(rs1))",                      "convert",  "oracle1")
    op(0x37, "ITOF",   "E", "rd, rs1, -",  "rd = float(rs1)",                       "convert",  "oracle1")
    op(0x38, "LOAD",   "E", "rd, rs1, rs2", "rd = mem[rs1 + rs2]",                  "memory",   "converged")
    op(0x39, "STORE",  "E", "rd, rs1, rs2", "mem[rs1 + rs2] = rd",                  "memory",   "converged")
    op(0x3A, "MOV",    "E", "rd, rs1, -",  "rd = rs1",                              "move",     "converged")
    op(0x3B, "SWP",    "E", "rd, rs1, -",  "swap(rd, rs1)",                         "move",     "converged")
    op(0x3C, "JZ",     "E", "rd, rs1, -",  "if rd == 0: pc += rs1",                 "control",  "converged")
    op(0x3D, "JNZ",    "E", "rd, rs1, -",  "if rd != 0: pc += rs1",                 "control",  "converged")
    op(0x3E, "JLT",    "E", "rd, rs1, -",  "if rd < 0: pc += rs1",                  "control",  "converged")
    op(0x3F, "JGT",    "E", "rd, rs1, -",  "if rd > 0: pc += rs1",                  "control",  "converged")
    
    # ═══════════════════════════════════════════
    # 0x40-0x47: Format F — Register + Imm16
    # ═══════════════════════════════════════════
    op(0x40, "MOVI16", "F", "rd, imm16",  "rd = imm16",                             "move",     "converged")
    op(0x41, "ADDI16", "F", "rd, imm16",  "rd = rd + imm16",                        "arithmetic", "converged")
    op(0x42, "SUBI16", "F", "rd, imm16",  "rd = rd - imm16",                        "arithmetic", "converged")
    op(0x43, "JMP",    "F", "rd, imm16",  "pc += imm16 (relative)",                 "control",  "converged")
    op(0x44, "JAL",    "F", "rd, imm16",  "rd = pc; pc += imm16",                   "control",  "converged")
    op(0x45, "CALL",   "F", "rd, imm16",  "push(pc); pc = rd + imm16",              "control",  "jetsonclaw1")
    op(0x46, "LOOP",   "F", "rd, imm16",  "rd--; if rd > 0: pc -= imm16",           "control",  "jetsonclaw1")
    op(0x47, "SELECT", "F", "rd, imm16",  "pc += imm16 * rd (computed jump)",       "control",  "oracle1")
    
    # ═══════════════════════════════════════════
    # 0x48-0x4F: Format G — Register + Register + Imm16
    # ═══════════════════════════════════════════
    op(0x48, "LOADOFF","G", "rd, rs1, imm16", "rd = mem[rs1 + imm16]",              "memory",   "converged")
    op(0x49, "STOREOF","G", "rd, rs1, imm16", "mem[rs1 + imm16] = rd",              "memory",   "converged")
    op(0x4A, "LOADI",  "G", "rd, rs1, imm16", "rd = mem[mem[rs1] + imm16]",         "memory",   "jetsonclaw1")
    op(0x4B, "STOREI", "G", "rd, rs1, imm16", "mem[mem[rs1] + imm16] = rd",         "memory",   "jetsonclaw1")
    op(0x4C, "ENTER",  "G", "rd, rs1, imm16", "push regs; sp -= imm16; rd=old_sp",  "stack",    "jetsonclaw1")
    op(0x4D, "LEAVE",  "G", "rd, rs1, imm16", "sp += imm16; pop regs; rd=ret",      "stack",    "jetsonclaw1")
    op(0x4E, "COPY",   "G", "rd, rs1, imm16", "memcpy(rd, rs1, imm16)",              "memory",   "jetsonclaw1")
    op(0x4F, "FILL",   "G", "rd, rs1, imm16", "memset(rd, rs1, imm16)",              "memory",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0x50-0x5F: Format E — Agent-to-Agent (Fleet Ops)
    # ═══════════════════════════════════════════
    op(0x50, "TELL",   "E", "rd, rs1, rs2", "Send rs2 to agent rs1, tag rd",         "a2a",      "converged")
    op(0x51, "ASK",    "E", "rd, rs1, rs2", "Request rs2 from agent rs1, resp→rd",    "a2a",      "converged")
    op(0x52, "DELEG",  "E", "rd, rs1, rs2", "Delegate task rs2 to agent rs1",         "a2a",      "converged")
    op(0x53, "BCAST",  "E", "rd, rs1, rs2", "Broadcast rs2 to fleet, tag rd",         "a2a",      "converged")
    op(0x54, "ACCEPT", "E", "rd, rs1, rs2", "Accept delegated task, ctx→rd",          "a2a",      "converged")
    op(0x55, "DECLINE","E", "rd, rs1, rs2", "Decline task with reason rs2",           "a2a",      "converged")
    op(0x56, "REPORT", "E", "rd, rs1, rs2", "Report task status rs2 to rd",           "a2a",      "converged")
    op(0x57, "MERGE",  "E", "rd, rs1, rs2", "Merge results from rs1,rs2→rd",          "a2a",      "converged")
    op(0x58, "FORK",   "E", "rd, rs1, rs2", "Spawn child agent, state→rd",            "a2a",      "converged")
    op(0x59, "JOIN",   "E", "rd, rs1, rs2", "Wait for child rs1, result→rd",          "a2a",      "converged")
    op(0x5A, "SIGNAL", "E", "rd, rs1, rs2", "Emit named signal rs2 on channel rd",    "a2a",      "converged")
    op(0x5B, "AWAIT",  "E", "rd, rs1, rs2", "Wait for signal rs2, data→rd",           "a2a",      "converged")
    op(0x5C, "TRUST",  "E", "rd, rs1, rs2", "Set trust level rs2 for agent rs1",      "a2a",      "converged")
    op(0x5D, "DISCOV", "E", "rd, rs1, rs2", "Discover fleet agents, list→rd",         "a2a",      "oracle1")
    op(0x5E, "STATUS", "E", "rd, rs1, rs2", "Query agent rs1 status, result→rd",      "a2a",      "converged")
    op(0x5F, "HEARTBT","E", "rd, rs1, rs2", "Emit heartbeat, load→rd",                "a2a",      "converged")
    
    # ═══════════════════════════════════════════
    # 0x60-0x6F: Format E — Confidence-Aware Variants
    # ═══════════════════════════════════════════
    op(0x60, "C_ADD",  "E", "rd, rs1, rs2", "rd = rs1+rs2, crd=min(crs1,crs2)",     "confidence", "converged", conf=True)
    op(0x61, "C_SUB",  "E", "rd, rs1, rs2", "rd = rs1-rs2, crd=min(crs1,crs2)",     "confidence", "converged", conf=True)
    op(0x62, "C_MUL",  "E", "rd, rs1, rs2", "rd = rs1*rs2, crd=crs1*crs2",          "confidence", "converged", conf=True)
    op(0x63, "C_DIV",  "E", "rd, rs1, rs2", "rd = rs1/rs2, crd=crs1*crs2*(1-ε)",    "confidence", "converged", conf=True)
    op(0x64, "C_FADD", "E", "rd, rs1, rs2", "Float add + confidence propagation",    "confidence", "oracle1", conf=True)
    op(0x65, "C_FSUB", "E", "rd, rs1, rs2", "Float sub + confidence propagation",    "confidence", "oracle1", conf=True)
    op(0x66, "C_FMUL", "E", "rd, rs1, rs2", "Float mul + confidence propagation",    "confidence", "oracle1", conf=True)
    op(0x67, "C_FDIV", "E", "rd, rs1, rs2", "Float div + confidence propagation",    "confidence", "oracle1", conf=True)
    op(0x68, "C_MERGE","E", "rd, rs1, rs2", "Merge confidences: crd=weighted_avg",   "confidence", "converged", conf=True)
    op(0x69, "C_THRESH","D","rd, imm8",      "Skip next if crd < imm8/255",           "confidence", "converged", conf=True)
    op(0x6A, "C_BOOST","E", "rd, rs1, rs2", "Boost crd by rs2 factor (max 1.0)",     "confidence", "jetsonclaw1", conf=True)
    op(0x6B, "C_DECAY","E", "rd, rs1, rs2", "Decay crd by factor rs2 per cycle",     "confidence", "jetsonclaw1", conf=True)
    op(0x6C, "C_SOURCE","E","rd, rs1, rs2", "Set confidence source (sensor/model/human)", "confidence", "jetsonclaw1", conf=True)
    op(0x6D, "C_CALIB","E", "rd, rs1, rs2", "Calibrate confidence against ground truth", "confidence", "converged", conf=True)
    op(0x6E, "C_EXPLY","E", "rd, rs1, rs2", "Apply confidence to control flow weight","confidence", "oracle1", conf=True)
    op(0x6F, "C_VOTE", "E", "rd, rs1, rs2", "Weighted vote: crd = sum(crs*crs_i)/Σ", "confidence", "converged", conf=True)
    
    # ═══════════════════════════════════════════
    # 0x70-0x7F: Format E — Viewpoint Operations (Babel Reserved)
    # ═══════════════════════════════════════════
    op(0x70, "V_EVID", "E", "rd, rs1, rs2", "Evidentiality: source type rs2→rd",     "viewpoint", "babel")
    op(0x71, "V_EPIST","E", "rd, rs1, rs2", "Epistemic stance: certainty level",     "viewpoint", "babel")
    op(0x72, "V_MIR",  "E", "rd, rs1, rs2", "Mirative: unexpectedness marker",       "viewpoint", "babel")
    op(0x73, "V_NEG",  "E", "rd, rs1, rs2", "Negation scope: predicate vs proposition","viewpoint", "babel")
    op(0x74, "V_TENSE","E", "rd, rs1, rs2", "Temporal viewpoint alignment",           "viewpoint", "babel")
    op(0x75, "V_ASPEC","E", "rd, rs1, rs2", "Aspectual viewpoint: complete/ongoing",  "viewpoint", "babel")
    op(0x76, "V_MODAL","E", "rd, rs1, rs2", "Modal force: necessity/possibility",     "viewpoint", "babel")
    op(0x77, "V_POLIT","E", "rd, rs1, rs2", "Politeness register mapping",            "viewpoint", "babel")
    op(0x78, "V_HONOR","E", "rd, rs1, rs2", "Honorific level → trust tier",          "viewpoint", "babel")
    op(0x79, "V_TOPIC","E", "rd, rs1, rs2", "Topic-comment structure binding",        "viewpoint", "babel")
    op(0x7A, "V_FOCUS","E", "rd, rs1, rs2", "Information focus marking",              "viewpoint", "babel")
    op(0x7B, "V_CASE", "E", "rd, rs1, rs2", "Case-based scope assignment",            "viewpoint", "babel")
    op(0x7C, "V_AGREE","E", "rd, rs1, rs2", "Agreement (gender/number/person)",       "viewpoint", "babel")
    op(0x7D, "V_CLASS","E", "rd, rs1, rs2", "Classifier→type mapping",                "viewpoint", "babel")
    op(0x7E, "V_INFL", "E", "rd, rs1, rs2", "Inflection→control flow mapping",       "viewpoint", "babel")
    op(0x7F, "V_PRAGMA","E","rd, rs1, rs2", "Pragmatic context switch",               "viewpoint", "babel")
    
    # ═══════════════════════════════════════════
    # 0x80-0x8F: Format E — Biology/Sensor Ops (JetsonClaw1)
    # ═══════════════════════════════════════════
    op(0x80, "SENSE",  "E", "rd, rs1, rs2", "Read sensor rs1, channel rs2→rd",       "sensor",   "jetsonclaw1")
    op(0x81, "ACTUATE","E", "rd, rs1, rs2", "Write rd to actuator rs1, channel rs2", "sensor",   "jetsonclaw1")
    op(0x82, "SAMPLE", "E", "rd, rs1, rs2", "Sample ADC channel rs1, avg rs2→rd",    "sensor",   "jetsonclaw1")
    op(0x83, "ENERGY", "E", "rd, rs1, rs2", "Energy budget: available→rd, used→rs1", "sensor",   "jetsonclaw1")
    op(0x84, "TEMP",   "E", "rd, rs1, rs2", "Temperature sensor read→rd",            "sensor",   "jetsonclaw1")
    op(0x85, "GPS",    "E", "rd, rs1, rs2", "GPS coordinates→rd,rs1",                "sensor",   "jetsonclaw1")
    op(0x86, "ACCEL",  "E", "rd, rs1, rs2", "Accelerometer read (3-axis)→rd,rs1,rs2","sensor",   "jetsonclaw1")
    op(0x87, "DEPTH",  "E", "rd, rs1, rs2", "Depth/pressure sensor→rd",              "sensor",   "jetsonclaw1")
    op(0x88, "CAMCAP", "E", "rd, rs1, rs2", "Capture camera frame rs1→buffer rd",    "sensor",   "jetsonclaw1")
    op(0x89, "CAMDET", "E", "rd, rs1, rs2", "Run detection on buffer rd, N results→rs1","sensor","jetsonclaw1")
    op(0x8A, "PWM",    "E", "rd, rs1, rs2", "PWM output: pin rs1, duty rd, freq rs2","sensor",   "jetsonclaw1")
    op(0x8B, "GPIO",   "E", "rd, rs1, rs2", "GPIO: read/write pin rs1, direction rs2","sensor",  "jetsonclaw1")
    op(0x8C, "I2C",    "E", "rd, rs1, rs2", "I2C: addr rs1, register rs2, data rd", "sensor",   "jetsonclaw1")
    op(0x8D, "SPI",    "E", "rd, rs1, rs2", "SPI: send rd, receive→rd, cs=rs1",      "sensor",   "jetsonclaw1")
    op(0x8E, "UART",   "E", "rd, rs1, rs2", "UART: send rd bytes from buf rs1",      "sensor",   "jetsonclaw1")
    op(0x8F, "CANBUS", "E", "rd, rs1, rs2", "CAN bus: send rd with ID rs1",          "sensor",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0x90-0x9F: Format E — Extended Math/Crypto
    # ═══════════════════════════════════════════
    op(0x90, "ABS",    "E", "rd, rs1, -",  "rd = |rs1|",                             "math",     "converged")
    op(0x91, "SIGN",   "E", "rd, rs1, -",  "rd = sign(rs1)",                         "math",     "converged")
    op(0x92, "SQRT",   "E", "rd, rs1, -",  "rd = sqrt(rs1)",                         "math",     "oracle1")
    op(0x93, "POW",    "E", "rd, rs1, rs2", "rd = rs1 ^ rs2",                        "math",     "oracle1")
    op(0x94, "LOG2",   "E", "rd, rs1, -",  "rd = log2(rs1)",                         "math",     "oracle1")
    op(0x95, "CLZ",    "E", "rd, rs1, -",  "rd = count leading zeros(rs1)",          "math",     "jetsonclaw1")
    op(0x96, "CTZ",    "E", "rd, rs1, -",  "rd = count trailing zeros(rs1)",         "math",     "jetsonclaw1")
    op(0x97, "POPCNT", "E", "rd, rs1, -",  "rd = popcount(rs1)",                     "math",     "jetsonclaw1")
    op(0x98, "CRC32",  "E", "rd, rs1, rs2", "rd = crc32(rs1, rs2)",                   "crypto",   "jetsonclaw1")
    op(0x99, "SHA256", "E", "rd, rs1, rs2", "SHA-256 block: msg rs1, len rs2→rd",    "crypto",   "converged")
    op(0x9A, "RND",    "E", "rd, rs1, rs2", "rd = random in [rs1, rs2]",              "math",     "converged")
    op(0x9B, "SEED",   "E", "rd, rs1, -",  "Seed PRNG with rs1",                     "math",     "converged")
    op(0x9C, "FMOD",   "E", "rd, rs1, rs2", "rd = fmod(rs1, rs2)",                   "float",    "oracle1")
    op(0x9D, "FSQRT",  "E", "rd, rs1, -",  "rd = fsqrt(rs1)",                        "float",    "oracle1")
    op(0x9E, "FSIN",   "E", "rd, rs1, -",  "rd = sin(rs1)",                          "float",    "oracle1")
    op(0x9F, "FCOS",   "E", "rd, rs1, -",  "rd = cos(rs1)",                          "float",    "oracle1")
    
    # ═══════════════════════════════════════════
    # 0xA0-0xAF: Format D — String/Collection Ops
    # ═══════════════════════════════════════════
    op(0xA0, "LEN",    "D", "rd, imm8",   "rd = length of collection imm8",          "collection", "oracle1")
    op(0xA1, "CONCAT", "E", "rd, rs1, rs2","rd = concat(rs1, rs2)",                  "collection", "oracle1")
    op(0xA2, "AT",     "E", "rd, rs1, rs2","rd = rs1[rs2]",                          "collection", "oracle1")
    op(0xA3, "SETAT",  "E", "rd, rs1, rs2","rs1[rs2] = rd",                          "collection", "oracle1")
    op(0xA4, "SLICE",  "G", "rd, rs1, imm16","rd = rs1[0:imm16]",                    "collection", "oracle1")
    op(0xA5, "REDUCE", "E", "rd, rs1, rs2","rd = fold(rs1, rs2)",                    "collection", "oracle1")
    op(0xA6, "MAP",    "E", "rd, rs1, rs2","rd = map(rs1, fn rs2)",                  "collection", "oracle1")
    op(0xA7, "FILTER", "E", "rd, rs1, rs2","rd = filter(rs1, fn rs2)",               "collection", "oracle1")
    op(0xA8, "SORT",   "E", "rd, rs1, rs2","rd = sort(rs1, cmp rs2)",                "collection", "oracle1")
    op(0xA9, "FIND",   "E", "rd, rs1, rs2","rd = index of rs2 in rs1 (-1=not found)","collection", "oracle1")
    op(0xAA, "HASH",   "E", "rd, rs1, rs2","rd = hash(rs1, algorithm rs2)",           "crypto",     "converged")
    op(0xAB, "HMAC",   "E", "rd, rs1, rs2","rd = hmac(rs1, key rs2)",                 "crypto",     "converged")
    op(0xAC, "VERIFY", "E", "rd, rs1, rs2","rd = verify sig rs2 on data rs1",         "crypto",     "converged")
    op(0xAD, "ENCRYPT","E", "rd, rs1, rs2","rd = encrypt rs1 with key rs2",           "crypto",     "converged")
    op(0xAE, "DECRYPT","E", "rd, rs1, rs2","rd = decrypt rs1 with key rs2",           "crypto",     "converged")
    op(0xAF, "KEYGEN", "E", "rd, rs1, rs2","rd = generate keypair, pub→rs1 priv→rs2", "crypto",     "converged")
    
    # ═══════════════════════════════════════════
    # 0xB0-0xBF: Format E — Vector/SIMD
    # ═══════════════════════════════════════════
    op(0xB0, "VLOAD",  "E", "rd, rs1, rs2","Load vector from mem[rs1], len rs2",      "vector",   "jetsonclaw1")
    op(0xB1, "VSTORE", "E", "rd, rs1, rs2","Store vector rd to mem[rs1], len rs2",     "vector",   "jetsonclaw1")
    op(0xB2, "VADD",   "E", "rd, rs1, rs2","Vector add: rd[i] = rs1[i] + rs2[i]",     "vector",   "jetsonclaw1")
    op(0xB3, "VMUL",   "E", "rd, rs1, rs2","Vector mul: rd[i] = rs1[i] * rs2[i]",     "vector",   "jetsonclaw1")
    op(0xB4, "VDOT",   "E", "rd, rs1, rs2","Dot product: rd = Σ rs1[i]*rs2[i]",       "vector",   "jetsonclaw1")
    op(0xB5, "VNORM",  "E", "rd, rs1, rs2","L2 norm: rd = sqrt(Σ rs1[i]²)",           "vector",   "jetsonclaw1")
    op(0xB6, "VSCALE", "E", "rd, rs1, rs2","Scale: rd[i] = rs1[i] * rs2 (scalar)",    "vector",   "jetsonclaw1")
    op(0xB7, "VMAXP",  "E", "rd, rs1, rs2","Element-wise max: rd[i] = max(rs1,rs2)",   "vector",   "jetsonclaw1")
    op(0xB8, "VMINP",  "E", "rd, rs1, rs2","Element-wise min",                         "vector",   "jetsonclaw1")
    op(0xB9, "VREDUCE","E", "rd, rs1, rs2","Reduce vector with op rs2",                "vector",   "jetsonclaw1")
    op(0xBA, "VGATHER","E", "rd, rs1, rs2","Gather: rd[i] = mem[rs1[rs2[i]]]",        "vector",   "jetsonclaw1")
    op(0xBB, "VSCATTER","E","rd, rs1, rs2","Scatter: mem[rs1[rs2[i]]] = rd[i]",       "vector",   "jetsonclaw1")
    op(0xBC, "VSHUF",  "E", "rd, rs1, rs2","Shuffle lanes by index rs2",              "vector",   "jetsonclaw1")
    op(0xBD, "VMERGE", "E", "rd, rs1, rs2","Merge vectors by mask rs2",               "vector",   "jetsonclaw1")
    op(0xBE, "VCONF",  "E", "rd, rs1, rs2","Vector confidence propagation",            "vector",   "jetsonclaw1")
    op(0xBF, "VSELECT","E", "rd, rs1, rs2","Conditional select by confidence mask",    "vector",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0xC0-0xCF: Format E — Tensor/Neural
    # ═══════════════════════════════════════════
    op(0xC0, "TMATMUL","E", "rd, rs1, rs2","Tensor matmul: rd = rs1 @ rs2",           "tensor",   "jetsonclaw1")
    op(0xC1, "TCONV",  "E", "rd, rs1, rs2","2D convolution: rd = conv(rs1, rs2)",     "tensor",   "jetsonclaw1")
    op(0xC2, "TPOOL",  "E", "rd, rs1, rs2","Max/avg pool: rd = pool(rs1, rs2)",       "tensor",   "jetsonclaw1")
    op(0xC3, "TRELU",  "E", "rd, rs1, -",  "ReLU: rd = max(0, rs1)",                 "tensor",   "jetsonclaw1")
    op(0xC4, "TSIGM",  "E", "rd, rs1, -",  "Sigmoid: rd = 1/(1+exp(-rs1))",          "tensor",   "jetsonclaw1")
    op(0xC5, "TSOFT",  "E", "rd, rs1, rs2","Softmax over dimension rs2",              "tensor",   "jetsonclaw1")
    op(0xC6, "TLOSS",  "E", "rd, rs1, rs2","Loss function: type rs2, pred rs1",       "tensor",   "jetsonclaw1")
    op(0xC7, "TGRAD",  "E", "rd, rs1, rs2","Gradient: rd = ∂loss/∂rs1, lr=rs2",      "tensor",   "jetsonclaw1")
    op(0xC8, "TUPDATE","E", "rd, rs1, rs2","SGD update: rd -= rs2 * rs1",             "tensor",   "jetsonclaw1")
    op(0xC9, "TADAM",  "E", "rd, rs1, rs2","Adam optimizer step",                     "tensor",   "jetsonclaw1")
    op(0xCA, "TEMBED", "E", "rd, rs1, rs2","Embedding lookup: token rs1, table rs2",   "tensor",   "jetsonclaw1")
    op(0xCB, "TATTN",  "E", "rd, rs1, rs2","Self-attention: Q=rs1, K=V=rs2",          "tensor",   "jetsonclaw1")
    op(0xCC, "TSAMPLE","E", "rd, rs1, rs2","Sample from distribution rs1, temp rs2",   "tensor",   "jetsonclaw1")
    op(0xCD, "TTOKEN", "E", "rd, rs1, rs2","Tokenize: text rs1, vocab rs2→rd",        "tensor",   "oracle1")
    op(0xCE, "TDETOK", "E", "rd, rs1, rs2","Detokenize: tokens rs1, vocab rs2→rd",    "tensor",   "oracle1")
    op(0xCF, "TQUANT", "E", "rd, rs1, rs2","Quantize: fp32 rs1 → int8, scale rs2",    "tensor",   "jetsonclaw1")
    
    # ═══════════════════════════════════════════
    # 0xD0-0xDF: Format G — Extended Memory/Mapped I/O
    # ═══════════════════════════════════════════
    op(0xD0, "DMA_CPY","G", "rd, rs1, imm16","DMA: copy imm16 bytes rd←rs1",         "memory",   "jetsonclaw1")
    op(0xD1, "DMA_SET","G", "rd, rs1, imm16","DMA: fill imm16 bytes at rd with rs1",  "memory",   "jetsonclaw1")
    op(0xD2, "MMIO_R","G", "rd, rs1, imm16","MMIO read: rd = io[rs1 + imm16]",        "memory",   "jetsonclaw1")
    op(0xD3, "MMIO_W","G", "rd, rs1, imm16","MMIO write: io[rs1 + imm16] = rd",       "memory",   "jetsonclaw1")
    op(0xD4, "ATOMIC","G", "rd, rs1, imm16","Atomic RMW: rd = swap(mem[rs1+imm16],rd)","memory", "jetsonclaw1")
    op(0xD5, "CAS",   "G", "rd, rs1, imm16","Compare-and-swap at rs1+imm16",          "memory",   "jetsonclaw1")
    op(0xD6, "FENCE", "G", "rd, rs1, imm16","Memory fence: type imm16 (acq/rel/full)","memory",   "jetsonclaw1")
    op(0xD7, "MALLOC","G", "rd, rs1, imm16","Allocate imm16 bytes, handle→rd",        "memory",   "oracle1")
    op(0xD8, "FREE",  "G", "rd, rs1, imm16","Free allocation at rd",                   "memory",   "oracle1")
    op(0xD9, "MPROT", "G", "rd, rs1, imm16","Memory protect: rd=start, rs1=len, imm16=flags","memory","jetsonclaw1")
    op(0xDA, "MCACHE","G", "rd, rs1, imm16","Cache management: op imm16, addr rd, len rs1","memory","jetsonclaw1")
    op(0xDB, "GPU_LD","G", "rd, rs1, imm16","GPU: load to device mem, offset imm16",  "memory",   "jetsonclaw1")
    op(0xDC, "GPU_ST","G", "rd, rs1, imm16","GPU: store from device mem",              "memory",   "jetsonclaw1")
    op(0xDD, "GPU_EX","G", "rd, rs1, imm16","GPU: execute kernel rd, grid rs1, block imm16","compute","jetsonclaw1")
    op(0xDE, "GPU_SYNC","G","rd, rs1, imm16","GPU: synchronize device imm16",          "compute",  "jetsonclaw1")
    op(0xDF, "RESERVED_DF","G","-", "Reserved", "reserved", "none", reserved=True)
    
    # ═══════════════════════════════════════════
    # 0xE0-0xEF: Format F — Long Jumps/Calls
    # ═══════════════════════════════════════════
    op(0xE0, "JMPL",   "F", "rd, imm16",  "Long relative jump: pc += imm16",          "control",  "converged")
    op(0xE1, "JALL",   "F", "rd, imm16",  "Long jump-and-link: rd = pc; pc += imm16", "control",  "converged")
    op(0xE2, "CALLL",  "F", "rd, imm16",  "Long call: push(pc); pc = rd + imm16",     "control",  "converged")
    op(0xE3, "TAIL",   "F", "rd, imm16",  "Tail call: pop frame; pc = rd + imm16",    "control",  "oracle1")
    op(0xE4, "SWITCH", "F", "rd, imm16",  "Context switch: save state, jump imm16",   "control",  "jetsonclaw1")
    op(0xE5, "COYIELD","F", "rd, imm16",  "Coroutine yield: save, jump to imm16",     "control",  "oracle1")
    op(0xE6, "CORESUM","F", "rd, imm16",  "Coroutine resume: restore, jump to rd",    "control",  "oracle1")
    op(0xE7, "FAULT",  "F", "rd, imm16",  "Raise fault code imm16, context rd",       "system",   "jetsonclaw1")
    op(0xE8, "HANDLER","F", "rd, imm16",  "Install fault handler at pc + imm16",      "system",   "jetsonclaw1")
    op(0xE9, "TRACE",  "F", "rd, imm16",  "Trace: log rd, tag imm16",                 "debug",    "converged")
    op(0xEA, "PROF_ON","F", "rd, imm16",  "Start profiling region imm16",              "debug",    "jetsonclaw1")
    op(0xEB, "PROF_OFF","F","rd, imm16",  "End profiling region imm16",                "debug",    "jetsonclaw1")
    op(0xEC, "WATCH",  "F", "rd, imm16",  "Watchpoint: break on write to rd+imm16",   "debug",    "converged")
    op(0xED, "RESERVED_ED","F","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xEE, "RESERVED_EE","F","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xEF, "RESERVED_EF","F","-",       "Reserved", "reserved", "none", reserved=True)
    
    # ═══════════════════════════════════════════
    # 0xF0-0xFF: Format A — Extended System/Debug
    # ═══════════════════════════════════════════
    op(0xF0, "HALT_ERR","A","-",          "Halt with error (check flags)",             "system",   "converged")
    op(0xF1, "REBOOT", "A", "-",          "Warm reboot (preserve memory)",             "system",   "jetsonclaw1")
    op(0xF2, "DUMP",   "A", "-",          "Dump register file to debug output",        "debug",    "converged")
    op(0xF3, "ASSERT", "A", "-",          "Assert flags, halt if violation",           "debug",    "converged")
    op(0xF4, "ID",     "A", "-",          "Return agent ID to r0",                     "system",   "oracle1")
    op(0xF5, "VER",    "A", "-",          "Return ISA version to r0",                  "system",   "converged")
    op(0xF6, "CLK",    "A", "-",          "Return clock cycle count to r0",            "system",   "jetsonclaw1")
    op(0xF7, "PCLK",   "A", "-",          "Return performance counter to r0",         "system",   "jetsonclaw1")
    op(0xF8, "WDOG",   "A", "-",          "Kick watchdog timer",                       "system",   "jetsonclaw1")
    op(0xF9, "SLEEP",  "A", "-",          "Enter low-power sleep (wake on interrupt)", "system",   "jetsonclaw1")
    op(0xFA, "RESERVED_FA","A","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xFB, "RESERVED_FB","A","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xFC, "RESERVED_FC","A","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xFD, "RESERVED_FD","A","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xFE, "RESERVED_FE","A","-",       "Reserved", "reserved", "none", reserved=True)
    op(0xFF, "ILLEGAL","A", "-",          "Illegal instruction trap",                   "system",   "converged")
    
    return ops


def isa_stats(ops: List[OpcodeDef]) -> dict:
    """Generate statistics about the unified ISA."""
    defined = [o for o in ops if not o.reserved]
    reserved = [o for o in ops if o.reserved]
    
    by_format = {}
    by_category = {}
    by_source = {}
    for o in defined:
        by_format[o.format] = by_format.get(o.format, 0) + 1
        by_category[o.category] = by_category.get(o.category, 0) + 1
        by_source[o.source] = by_source.get(o.source, 0) + 1
    
    return {
        "total_slots": len(ops),
        "defined": len(defined),
        "reserved": len(reserved),
        "confidence_ops": len([o for o in defined if o.confidence]),
        "by_format": by_format,
        "by_category": by_category,
        "by_source": by_source,
    }


def isa_markdown_table(ops: List[OpcodeDef]) -> str:
    """Generate a markdown table of all opcodes."""
    lines = [
        "# FLUX Unified ISA — Complete Opcode Table\n",
        "| Hex | Mnemonic | Fmt | Operands | Category | Source | Description |",
        "|-----|----------|-----|----------|----------|--------|-------------|",
    ]
    for o in ops:
        conf = " 🔒" if o.confidence else ""
        src = {"oracle1": "🔮", "jetsonclaw1": "⚡", "babel": "🌐", "converged": "✅", "none": "—"}.get(o.source, "?")
        lines.append(f"| 0x{o.opcode:02X} | {o.mnemonic}{conf} | {o.format} | {o.operands} | {o.category} | {src} | {o.description} |")
    
    stats = isa_stats(ops)
    lines.append(f"\n**Total:** {stats['defined']} defined, {stats['reserved']} reserved = {stats['total_slots']} slots")
    lines.append(f"**Confidence ops:** {stats['confidence_ops']}")
    return "\n".join(lines)
