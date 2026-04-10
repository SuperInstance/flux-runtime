"""Complete Opcode Reference — machine-readable schema for all 104 FLUX opcodes."""

from __future__ import annotations
from typing import Any

# Build the full opcode reference from the canonical Op enum and format sets.
# We import lazily to avoid circular issues.

_OPCODE_DATA: list[tuple[str, int, str, str, float, float, str]] = [
    # (name, value, format, category, cost_ns, energy_nj, description)
    # ── Control flow (0x00-0x07) ──
    ("NOP", 0x00, "A", "control", 0.1, 0.05, "No operation"),
    ("MOV", 0x01, "C", "control", 0.2, 0.1, "Register-to-register move"),
    ("LOAD", 0x02, "C", "control", 0.5, 0.3, "Load value from memory address"),
    ("STORE", 0x03, "C", "control", 0.5, 0.3, "Store value to memory address"),
    ("JMP", 0x04, "D", "control", 0.3, 0.15, "Unconditional jump"),
    ("JZ", 0x05, "D", "control", 0.3, 0.15, "Jump if zero"),
    ("JNZ", 0x06, "D", "control", 0.3, 0.15, "Jump if not zero"),
    ("CALL", 0x07, "D", "control", 2.0, 1.0, "Call function (push return address)"),

    # ── Integer arithmetic (0x08-0x0F) ──
    ("IADD", 0x08, "C", "integer_arithmetic", 0.3, 0.15, "Integer add"),
    ("ISUB", 0x09, "C", "integer_arithmetic", 0.3, 0.15, "Integer subtract"),
    ("IMUL", 0x0A, "C", "integer_arithmetic", 0.5, 0.3, "Integer multiply"),
    ("IDIV", 0x0B, "C", "integer_arithmetic", 1.0, 0.6, "Integer divide"),
    ("IMOD", 0x0C, "C", "integer_arithmetic", 1.0, 0.6, "Integer modulo"),
    ("INEG", 0x0D, "B", "integer_arithmetic", 0.3, 0.15, "Integer negate"),
    ("INC", 0x0E, "B", "integer_arithmetic", 0.2, 0.1, "Increment register"),
    ("DEC", 0x0F, "B", "integer_arithmetic", 0.2, 0.1, "Decrement register"),

    # ── Bitwise (0x10-0x17) ──
    ("IAND", 0x10, "C", "bitwise", 0.3, 0.15, "Bitwise AND"),
    ("IOR", 0x11, "C", "bitwise", 0.3, 0.15, "Bitwise OR"),
    ("IXOR", 0x12, "C", "bitwise", 0.3, 0.15, "Bitwise XOR"),
    ("INOT", 0x13, "B", "bitwise", 0.3, 0.15, "Bitwise NOT"),
    ("ISHL", 0x14, "C", "bitwise", 0.3, 0.15, "Shift left"),
    ("ISHR", 0x15, "C", "bitwise", 0.3, 0.15, "Shift right (arithmetic)"),
    ("ROTL", 0x16, "C", "bitwise", 0.3, 0.15, "Rotate left"),
    ("ROTR", 0x17, "C", "bitwise", 0.3, 0.15, "Rotate right"),

    # ── Comparison (0x18-0x1F) ──
    ("ICMP", 0x18, "C", "comparison", 0.3, 0.15, "Integer compare (set flags)"),
    ("IEQ", 0x19, "C", "comparison", 0.3, 0.15, "Integer equality"),
    ("ILT", 0x1A, "C", "comparison", 0.3, 0.15, "Integer less than"),
    ("ILE", 0x1B, "C", "comparison", 0.3, 0.15, "Integer less or equal"),
    ("IGT", 0x1C, "C", "comparison", 0.3, 0.15, "Integer greater than"),
    ("IGE", 0x1D, "C", "comparison", 0.3, 0.15, "Integer greater or equal"),
    ("TEST", 0x1E, "C", "comparison", 0.3, 0.15, "Test bits (AND without storing)"),
    ("SETCC", 0x1F, "C", "comparison", 0.3, 0.15, "Set condition code"),

    # ── Stack ops (0x20-0x27) ──
    ("PUSH", 0x20, "B", "stack", 0.4, 0.2, "Push register onto stack"),
    ("POP", 0x21, "B", "stack", 0.4, 0.2, "Pop stack top into register"),
    ("DUP", 0x22, "A", "stack", 0.2, 0.1, "Duplicate stack top"),
    ("SWAP", 0x23, "A", "stack", 0.2, 0.1, "Swap top two stack elements"),
    ("ROT", 0x24, "A", "stack", 0.2, 0.1, "Rotate top three stack elements"),
    ("ENTER", 0x25, "B", "stack", 0.5, 0.3, "Enter function (allocate stack frame)"),
    ("LEAVE", 0x26, "B", "stack", 0.5, 0.3, "Leave function (deallocate stack frame)"),
    ("ALLOCA", 0x27, "C", "stack", 0.4, 0.2, "Allocate stack space"),

    # ── Function ops (0x28-0x2F) ──
    ("RET", 0x28, "C", "function", 1.5, 0.8, "Return from function"),
    ("CALL_IND", 0x29, "C", "function", 3.0, 1.5, "Indirect call via register"),
    ("TAILCALL", 0x2A, "C", "function", 2.0, 1.0, "Tail call optimization"),
    ("MOVI", 0x2B, "D", "function", 0.2, 0.1, "Move immediate value into register"),
    ("IREM", 0x2C, "C", "function", 1.0, 0.6, "Integer remainder"),
    ("CMP", 0x2D, "C", "function", 0.3, 0.15, "Compare (set zero/sign flags)"),
    ("JE", 0x2E, "D", "function", 0.3, 0.15, "Jump if equal"),
    ("JNE", 0x2F, "D", "function", 0.3, 0.15, "Jump if not equal"),

    # ── Memory management (0x30-0x37) ──
    ("REGION_CREATE", 0x30, "G", "memory_management", 5.0, 3.0, "Create memory region"),
    ("REGION_DESTROY", 0x31, "G", "memory_management", 2.0, 1.0, "Destroy memory region"),
    ("REGION_TRANSFER", 0x32, "G", "memory_management", 3.0, 1.5, "Transfer region ownership"),
    ("MEMCOPY", 0x33, "G", "memory_management", 2.0, 1.0, "Bulk memory copy"),
    ("MEMSET", 0x34, "G", "memory_management", 1.5, 0.8, "Fill memory region"),
    ("MEMCMP", 0x35, "G", "memory_management", 2.0, 1.0, "Compare memory regions"),
    ("JL", 0x36, "D", "memory_management", 0.3, 0.15, "Jump if less"),
    ("JGE", 0x37, "D", "memory_management", 0.3, 0.15, "Jump if greater or equal"),

    # ── Type operations (0x38-0x3C) ──
    ("CAST", 0x38, "C", "type_ops", 0.5, 0.3, "Type cast / conversion"),
    ("BOX", 0x39, "C", "type_ops", 1.0, 0.5, "Box value into heap-allocated object"),
    ("UNBOX", 0x3A, "C", "type_ops", 0.8, 0.4, "Unbox heap-allocated object"),
    ("CHECK_TYPE", 0x3B, "C", "type_ops", 0.5, 0.3, "Runtime type check"),
    ("CHECK_BOUNDS", 0x3C, "C", "type_ops", 0.5, 0.3, "Bounds check for array access"),

    # ── Float arithmetic (0x40-0x47) ──
    ("FADD", 0x40, "C", "float_arithmetic", 0.5, 0.3, "Float add"),
    ("FSUB", 0x41, "C", "float_arithmetic", 0.5, 0.3, "Float subtract"),
    ("FMUL", 0x42, "C", "float_arithmetic", 0.8, 0.5, "Float multiply"),
    ("FDIV", 0x43, "C", "float_arithmetic", 2.0, 1.2, "Float divide"),
    ("FNEG", 0x44, "B", "float_arithmetic", 0.3, 0.15, "Float negate"),
    ("FABS", 0x45, "B", "float_arithmetic", 0.3, 0.15, "Float absolute value"),
    ("FMIN", 0x46, "C", "float_arithmetic", 0.5, 0.3, "Float minimum"),
    ("FMAX", 0x47, "C", "float_arithmetic", 0.5, 0.3, "Float maximum"),

    # ── Float comparison (0x48-0x4F) ──
    ("FEQ", 0x48, "C", "float_comparison", 0.5, 0.3, "Float equality"),
    ("FLT", 0x49, "C", "float_comparison", 0.5, 0.3, "Float less than"),
    ("FLE", 0x4A, "C", "float_comparison", 0.5, 0.3, "Float less or equal"),
    ("FGT", 0x4B, "C", "float_comparison", 0.5, 0.3, "Float greater than"),
    ("FGE", 0x4C, "C", "float_comparison", 0.5, 0.3, "Float greater or equal"),
    ("JG", 0x4D, "D", "float_comparison", 0.3, 0.15, "Jump if greater"),
    ("JLE", 0x4E, "D", "float_comparison", 0.3, 0.15, "Jump if less or equal"),
    ("LOAD8", 0x4F, "C", "float_comparison", 0.5, 0.3, "Load 8-bit value"),

    # ── SIMD vector ops (0x50-0x57) ──
    ("VLOAD", 0x50, "C", "simd", 1.0, 0.8, "Vector load"),
    ("VSTORE", 0x51, "C", "simd", 1.0, 0.8, "Vector store"),
    ("VADD", 0x52, "C", "simd", 1.0, 0.8, "Vector add"),
    ("VSUB", 0x53, "C", "simd", 1.0, 0.8, "Vector subtract"),
    ("VMUL", 0x54, "C", "simd", 2.0, 1.5, "Vector multiply"),
    ("VDIV", 0x55, "C", "simd", 4.0, 3.0, "Vector divide"),
    ("VFMA", 0x56, "E", "simd", 3.0, 2.0, "Fused multiply-add (a*b+c)"),
    ("STORE8", 0x57, "C", "simd", 0.5, 0.3, "Store 8-bit value"),

    # ── A2A protocol (0x60-0x7B) ──
    ("TELL", 0x60, "G", "a2a_protocol", 10.0, 8.0, "Send message to agent (fire-and-forget)"),
    ("ASK", 0x61, "G", "a2a_protocol", 15.0, 12.0, "Request-response with agent"),
    ("DELEGATE", 0x62, "G", "a2a_protocol", 12.0, 10.0, "Delegate task to agent"),
    ("DELEGATE_RESULT", 0x63, "G", "a2a_protocol", 5.0, 4.0, "Receive delegation result"),
    ("REPORT_STATUS", 0x64, "G", "a2a_protocol", 5.0, 4.0, "Report agent status"),
    ("REQUEST_OVERRIDE", 0x65, "G", "a2a_protocol", 8.0, 6.0, "Request agent override"),
    ("BROADCAST", 0x66, "G", "a2a_protocol", 20.0, 16.0, "Broadcast to all agents"),
    ("REDUCE", 0x67, "G", "a2a_protocol", 25.0, 20.0, "Reduce across agents"),
    ("DECLARE_INTENT", 0x68, "G", "a2a_protocol", 5.0, 4.0, "Declare agent intent"),
    ("ASSERT_GOAL", 0x69, "G", "a2a_protocol", 5.0, 4.0, "Assert goal completion"),
    ("VERIFY_OUTCOME", 0x6A, "G", "a2a_protocol", 8.0, 6.0, "Verify execution outcome"),
    ("EXPLAIN_FAILURE", 0x6B, "G", "a2a_protocol", 5.0, 4.0, "Explain failure reason"),
    ("SET_PRIORITY", 0x6C, "G", "a2a_protocol", 2.0, 1.5, "Set task priority"),
    ("TRUST_CHECK", 0x70, "G", "a2a_protocol", 3.0, 2.0, "Check trust level"),
    ("TRUST_UPDATE", 0x71, "G", "a2a_protocol", 3.0, 2.0, "Update trust level"),
    ("TRUST_QUERY", 0x72, "G", "a2a_protocol", 3.0, 2.0, "Query trust level"),
    ("REVOKE_TRUST", 0x73, "G", "a2a_protocol", 3.0, 2.0, "Revoke trust"),
    ("CAP_REQUIRE", 0x74, "G", "a2a_protocol", 2.0, 1.5, "Require capability"),
    ("CAP_REQUEST", 0x75, "G", "a2a_protocol", 2.0, 1.5, "Request capability"),
    ("CAP_GRANT", 0x76, "G", "a2a_protocol", 2.0, 1.5, "Grant capability"),
    ("CAP_REVOKE", 0x77, "G", "a2a_protocol", 2.0, 1.5, "Revoke capability"),
    ("BARRIER", 0x78, "G", "a2a_protocol", 10.0, 8.0, "Synchronization barrier"),
    ("SYNC_CLOCK", 0x79, "G", "a2a_protocol", 5.0, 4.0, "Synchronize agent clocks"),
    ("FORMATION_UPDATE", 0x7A, "G", "a2a_protocol", 5.0, 4.0, "Update agent formation"),
    ("EMERGENCY_STOP", 0x7B, "A", "a2a_protocol", 1.0, 0.5, "Emergency stop all agents"),

    # ── System (0x80-0x84) ──
    ("HALT", 0x80, "A", "system", 1.0, 0.5, "Halt execution"),
    ("YIELD", 0x81, "A", "system", 2.0, 1.0, "Yield execution to scheduler"),
    ("RESOURCE_ACQUIRE", 0x82, "G", "system", 5.0, 3.0, "Acquire system resource"),
    ("RESOURCE_RELEASE", 0x83, "G", "system", 3.0, 2.0, "Release system resource"),
    ("DEBUG_BREAK", 0x84, "A", "system", 0.5, 0.3, "Debug breakpoint"),
]


def get_opcode_schema() -> dict[str, dict[str, Any]]:
    """Complete machine-readable reference for all opcodes.

    Returns:
        Dict mapping opcode name -> {
            value: int, format: str, category: str,
            cost_ns: float, energy_nj: float, description: str
        }
    """
    return {
        name: {
            "value": value,
            "format": fmt,
            "category": category,
            "cost_ns": cost_ns,
            "energy_nj": energy_nj,
            "description": description,
        }
        for name, value, fmt, category, cost_ns, energy_nj, description in _OPCODE_DATA
    }


def get_opcodes_by_category() -> dict[str, list[dict[str, Any]]]:
    """Group opcodes by category.

    Returns:
        Dict mapping category name -> list of opcode dicts.
    """
    schema = get_opcode_schema()
    groups: dict[str, list[dict[str, Any]]] = {}
    for name, info in schema.items():
        cat = info["category"]
        entry = {"name": name, **info}
        groups.setdefault(cat, []).append(entry)
    return groups


def get_opcodes_by_format() -> dict[str, list[dict[str, Any]]]:
    """Group opcodes by encoding format.

    Returns:
        Dict mapping format letter (A/B/C/D/E/G) -> list of opcode dicts.
    """
    schema = get_opcode_schema()
    groups: dict[str, list[dict[str, Any]]] = {}
    for name, info in schema.items():
        fmt = info["format"]
        entry = {"name": name, **info}
        groups.setdefault(fmt, []).append(entry)
    return groups
