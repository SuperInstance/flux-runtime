"""Tests for FLUX Execution Tracer, Profiler, and Debugger enhancements.

Tests the tracer on the cross_impl test program and verifies that the
profiler and enhanced debugger produce correct results.

The cross_impl program is the canonical cross-implementation test that
produces known register state (R0=13, R1=100, R2=15, R3=5, R4=5040,
R5=42, R6=42, R7=14).
"""

import struct
import sys
import os
import json

# Ensure the project source root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
from flux.tracer import FluxTracer, TraceResult, TraceEntry, ConservationLedger
from flux.profiler import FluxProfiler, ProfileResult
from flux.debugger import FluxDebugger, StepResult


# ── Helper ─────────────────────────────────────────────────────────────────

def _i16_le(val: int) -> bytes:
    """Pack a signed 16-bit integer as little-endian bytes."""
    return struct.pack("<h", val)


def _assemble_simple(asm_text: str) -> bytes:
    """Assemble simple FLUX assembly text using CrossAssembler."""
    from flux.asm import CrossAssembler
    asm = CrossAssembler()
    result = asm.assemble_source(asm_text)
    return result.bytecode


# ── The cross_impl test program ────────────────────────────────────────────

CROSS_IMPL_ASM = """
    MOVI R0, 10
    MOVI R1, 5
    IADD R0, R0, R1
    MOVI R1, 2
    IMUL R0, R0, R1
    MOVI R1, 4
    ISUB R0, R0, R1
    MOVI R1, 2
    IDIV R0, R0, R1

    MOVI R2, 15
    PUSH R2
    MOVI R2, 0
    POP R2

    MOVI R3, 7
    MOVI R4, 1
fact_loop:
    IMUL R4, R4, R3
    DEC R3
    JNZ R3, fact_loop

    MOVI R5, 42
    MOVI R6, 42
    CMP R5, R6

    INC R0
    MOV R7, R0
    IADD R0, R0, R7

    MOVI R0, 13
    MOVI R1, 100
    MOVI R3, 5

    HALT
"""

# Expected final register values from cross_impl
EXPECTED_REGISTERS = {
    "R0": 13,
    "R1": 100,
    "R2": 15,
    "R3": 5,
    "R4": 5040,
    "R5": 42,
    "R6": 42,
    "R7": 14,
}


# ── Tracer tests ───────────────────────────────────────────────────────────


def test_tracer_basic_halt() -> None:
    """Tracer can trace a simple HALT instruction."""
    bytecode = bytes([Op.HALT])
    tracer = FluxTracer()
    result = tracer.trace(bytecode)
    assert result is not None
    assert len(result.entries) == 1
    assert result.entries[0].opcode == Op.HALT
    assert result.halted is True


def test_tracer_basic_nop_halt() -> None:
    """Tracer traces NOP then HALT."""
    bytecode = bytes([Op.NOP, Op.HALT])
    tracer = FluxTracer()
    result = tracer.trace(bytecode)
    assert len(result.entries) == 2
    assert result.entries[0].opcode == Op.NOP
    assert result.entries[1].opcode == Op.HALT
    assert result.halted is True


def test_tracer_movi() -> None:
    """Tracer captures MOVI instruction and register change."""
    # MOVI R0, 42 + HALT
    bytecode = bytes([Op.MOVI, 0,]) + _i16_le(42) + bytes([Op.HALT])
    tracer = FluxTracer()
    result = tracer.trace(bytecode)
    assert len(result.entries) == 2

    # Check the MOVI entry
    movi_entry = result.entries[0]
    assert movi_entry.opcode == Op.MOVI
    assert movi_entry.registers_after["R0"] == 42
    assert movi_entry.registers_before["R0"] == 0  # Was zero before

    # Check final register state
    assert result.final_registers["R0"] == 42


def test_tracer_arithmetic() -> None:
    """Tracer captures arithmetic correctly."""
    # MOVI R0, 10; MOVI R1, 5; IADD R0, R0, R1; HALT
    bytecode = (
        bytes([Op.MOVI, 0]) + _i16_le(10) +
        bytes([Op.MOVI, 1]) + _i16_le(5) +
        bytes([Op.IADD, 0, 0, 1]) +
        bytes([Op.HALT])
    )
    tracer = FluxTracer()
    result = tracer.trace(bytecode)
    assert len(result.entries) == 4  # 3 instructions + HALT
    assert result.final_registers["R0"] == 15


def test_tracer_cross_impl() -> None:
    """Tracer produces correct results for the cross_impl program."""
    bytecode = _assemble_simple(CROSS_IMPL_ASM)
    tracer = FluxTracer()
    result = tracer.trace(bytecode)

    # Verify the trace completed
    assert result.halted is True
    assert result.error is None

    # Verify final register values match expected
    for reg_name, expected_val in EXPECTED_REGISTERS.items():
        actual_val = result.final_registers.get(reg_name, 0)
        assert actual_val == expected_val, (
            f"{reg_name} = {actual_val}, expected {expected_val}"
        )


def test_tracer_report() -> None:
    """Tracer report produces readable output."""
    bytecode = bytes([Op.MOVI, 0]) + _i16_le(42) + bytes([Op.HALT])
    tracer = FluxTracer()
    tracer.trace(bytecode)
    report = tracer.report()
    assert "FLUX Execution Trace" in report
    assert "Summary" in report
    assert "MOVI" in report


def test_tracer_json() -> None:
    """Tracer JSON export is valid JSON."""
    bytecode = bytes([Op.MOVI, 0]) + _i16_le(42) + bytes([Op.HALT])
    tracer = FluxTracer()
    tracer.trace(bytecode)
    json_str = tracer.to_json()

    # Must be valid JSON
    data = json.loads(json_str)
    assert "summary" in data
    assert "entries" in data
    assert data["summary"]["total_steps"] == 2  # MOVI + HALT


def test_tracer_json_schema() -> None:
    """Trace JSON has the expected top-level schema."""
    bytecode = bytes([Op.NOP, Op.HALT])
    tracer = FluxTracer()
    tracer.trace(bytecode)
    data = json.loads(tracer.to_json())

    assert "summary" in data
    assert "final_state" in data
    assert "entries" in data
    assert "conservation_ledger" in data

    # Check summary fields
    summary = data["summary"]
    assert "total_steps" in summary
    assert "total_cycles" in summary
    assert "halted" in summary
    assert "bytecode_size" in summary
    assert "duration_ms" in summary

    # Check entry fields
    entry = data["entries"][0]
    assert "step" in entry
    assert "pc" in entry
    assert "opcode" in entry
    assert "opcode_name" in entry
    assert "registers_before" in entry
    assert "registers_after" in entry
    assert "flags_before" in entry
    assert "flags_after" in entry


def test_tracer_register_changes_detected() -> None:
    """Tracer correctly detects register value changes."""
    # MOVI R0, 10; INC R0; HALT
    bytecode = (
        bytes([Op.MOVI, 0]) + _i16_le(10) +
        bytes([Op.INC, 0]) +
        bytes([Op.HALT])
    )
    tracer = FluxTracer()
    result = tracer.trace(bytecode)

    # After INC, R0 should be 11
    inc_entry = result.entries[1]  # INC entry
    assert inc_entry.registers_before["R0"] == 10
    assert inc_entry.registers_after["R0"] == 11


def test_tracer_flag_changes() -> None:
    """Tracer captures flag state changes."""
    # MOVI R0, 5; MOVI R1, 5; CMP R0, R1; HALT
    # CMP should set the zero flag
    bytecode = (
        bytes([Op.MOVI, 0]) + _i16_le(5) +
        bytes([Op.MOVI, 1]) + _i16_le(5) +
        bytes([Op.CMP, 0, 1]) +
        bytes([Op.HALT])
    )
    tracer = FluxTracer()
    result = tracer.trace(bytecode)

    # Find the CMP entry
    cmp_entry = None
    for entry in result.entries:
        if entry.opcode == Op.CMP:
            cmp_entry = entry
            break

    assert cmp_entry is not None, "CMP entry not found in trace"
    # After CMP of equal values, zero flag should be True
    assert cmp_entry.flags_after["zero"] is True


def test_tracer_max_steps() -> None:
    """Tracer respects max_steps limit."""
    # Create an infinite loop: JMP to self
    # JMP with offset 0 → loops back to the JMP instruction
    bytecode = bytes([Op.JMP, 0]) + _i16_le(-2)  # JMP -2 (back to self)
    tracer = FluxTracer()
    result = tracer.trace(bytecode, max_steps=100)
    # Should stop at max_steps without error
    assert len(result.entries) <= 100


def test_tracer_step_count() -> None:
    """Tracer step counter increments correctly."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.NOP, Op.HALT])
    tracer = FluxTracer()
    result = tracer.trace(bytecode)

    assert len(result.entries) == 4
    for i, entry in enumerate(result.entries):
        assert entry.step == i, f"Step {i}: expected step={i}, got step={entry.step}"


# ── Conservation ledger tests ──────────────────────────────────────────────


def test_conservation_ledger_basic() -> None:
    """Conservation ledger tracks consumption."""
    ledger = ConservationLedger()
    ledger.record(0, 0, "MOVI", "arithmetic")
    ledger.record(1, 4, "IADD", "arithmetic")
    ledger.record(2, 8, "HALT", "control_flow")

    assert ledger.total_consumed == 3  # 1 + 1 + 1
    assert len(ledger.entries) == 3


def test_conservation_ledger_categories() -> None:
    """Different opcode categories have different weights."""
    ledger = ConservationLedger()
    ledger.record(0, 0, "IADD", "arithmetic")      # 1 unit
    ledger.record(1, 0, "LOAD", "memory")           # 2 units
    ledger.record(2, 0, "TELL", "a2a")              # 5 units

    assert ledger.total_consumed == 8  # 1 + 2 + 5


def test_conservation_ledger_report() -> None:
    """Conservation ledger report is readable."""
    ledger = ConservationLedger()
    ledger.record(0, 0, "IADD", "arithmetic")
    ledger.record(1, 0, "LOAD", "memory")
    report = ledger.report()
    assert "Conservation Ledger" in report
    assert "arithmetic" in report
    assert "memory" in report


def test_conservation_in_trace() -> None:
    """Trace JSON includes conservation ledger data."""
    bytecode = bytes([Op.NOP, Op.HALT])
    tracer = FluxTracer()
    tracer.trace(bytecode)
    data = json.loads(tracer.to_json())
    assert "conservation_ledger" in data
    assert data["conservation_ledger"]["total_consumed"] > 0


# ── Profiler tests ─────────────────────────────────────────────────────────


def test_profiler_basic() -> None:
    """Profiler profiles a simple program."""
    bytecode = bytes([Op.NOP, Op.HALT])
    profiler = FluxProfiler()
    result = profiler.profile(bytecode)

    assert result.total_instructions == 2
    assert result.halted is True
    assert len(result.opcode_stats) == 2  # NOP and HALT


def test_profiler_opcode_counts() -> None:
    """Profiler counts opcodes correctly."""
    # 3 NOPs then HALT
    bytecode = bytes([Op.NOP, Op.NOP, Op.NOP, Op.HALT])
    profiler = FluxProfiler()
    result = profiler.profile(bytecode)

    nop_stats = result.opcode_stats.get(Op.NOP)
    assert nop_stats is not None
    assert nop_stats.count == 3


def test_profiler_cross_impl() -> None:
    """Profiler profiles the cross_impl program."""
    bytecode = _assemble_simple(CROSS_IMPL_ASM)
    profiler = FluxProfiler()
    result = profiler.profile(bytecode)

    assert result.halted is True
    assert result.error is None
    assert result.total_instructions > 0

    # Should have stats for multiple opcode types
    assert len(result.opcode_stats) >= 5

    # MOVI should be the most frequent
    hottest = result.hottest_opcodes
    assert len(hottest) > 0


def test_profiler_report() -> None:
    """Profiler report is readable."""
    bytecode = bytes([Op.NOP, Op.HALT])
    profiler = FluxProfiler()
    profiler.profile(bytecode)
    report = profiler.report()
    assert "FLUX Execution Profile" in report
    assert "Hottest Opcodes" in report
    assert "NOP" in report


def test_profiler_json() -> None:
    """Profiler JSON export is valid."""
    bytecode = bytes([Op.NOP, Op.HALT])
    profiler = FluxProfiler()
    profiler.profile(bytecode)
    data = json.loads(profiler.to_json())

    assert "summary" in data
    assert "opcode_stats" in data
    assert "hottest_opcodes" in data
    assert "memory_patterns" in data
    assert "conservation_by_category" in data


def test_profiler_hotspots() -> None:
    """Profiler identifies execution hotspots."""
    # A loop: MOVI R0, 3; label: DEC R0; JNZ R0, label; HALT
    bytecode = _assemble_simple("""
        MOVI R0, 3
    loop:
        DEC R0
        JNZ R0, loop
        HALT
    """)
    profiler = FluxProfiler()
    result = profiler.profile(bytecode)

    assert len(result.hotspots) > 0
    # The loop body (DEC) should be a hotspot
    top_hotspot = result.hotspots[0]
    assert top_hotspot["execution_count"] > 1


def test_profiler_conservation() -> None:
    """Profiler tracks conservation budget."""
    bytecode = bytes([Op.NOP, Op.HALT])
    profiler = FluxProfiler()
    result = profiler.profile(bytecode)

    assert result.conservation_consumed > 0
    assert len(result.conservation_by_category) > 0


# ── Debugger tests ─────────────────────────────────────────────────────────


def test_debugger_step() -> None:
    """Debugger steps through instructions."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.step()
    assert result.success
    assert result.instruction is not None
    assert result.instruction.opcode == Op.NOP

    result = debugger.step()
    assert result.halted


def test_debugger_breakpoint() -> None:
    """Debugger stops at breakpoints."""
    # NOP; NOP; HALT
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Set breakpoint at offset 2 (the HALT)
    debugger.add_breakpoint(2)

    result = debugger.continue_exec()
    assert result.breakpoint_hit
    assert debugger.pc == 2  # Should be at the breakpoint


def test_debugger_continue_until_halt() -> None:
    """Debugger runs until HALT without breakpoints."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.continue_exec()
    assert result.halted
    assert debugger.halted


def test_debugger_register_inspection() -> None:
    """Debugger can inspect and modify registers."""
    bytecode = bytes([Op.MOVI, 0]) + _i16_le(42) + bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.step()  # Execute MOVI
    assert debugger.inspect_reg(0) == 42

    # Modify register
    debugger.set_reg(0, 99)
    assert debugger.inspect_reg(0) == 99


def test_debugger_memory_inspection() -> None:
    """Debugger can inspect and modify memory."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Write to stack memory
    debugger.write_mem(0, b"\x01\x02\x03\x04")
    data = debugger.inspect_mem(0, 4)
    assert data == b"\x01\x02\x03\x04"


def test_debugger_backtrace() -> None:
    """Debugger tracks call stack."""
    debugger = FluxDebugger(bytes([Op.HALT]))
    frames = debugger.backtrace()
    assert len(frames) >= 1
    assert frames[0]["type"] == "current"


def test_debugger_disassembly() -> None:
    """Debugger disassembles instructions."""
    bytecode = bytes([Op.NOP, Op.MOVI, 0]) + _i16_le(10) + bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    instrs = debugger.disassemble_at(0, 3)
    assert len(instrs) >= 2
    assert instrs[0].opcode == Op.NOP


def test_debugger_step_result_changes() -> None:
    """Debugger StepResult captures register and flag changes."""
    # MOVI R0, 10; INC R0; HALT
    bytecode = (
        bytes([Op.MOVI, 0]) + _i16_le(10) +
        bytes([Op.INC, 0]) +
        bytes([Op.HALT])
    )
    debugger = FluxDebugger(bytecode)

    debugger.step()  # MOVI R0, 10
    result = debugger.step()  # INC R0

    assert "R0" in result.register_changes
    old_val, new_val = result.register_changes["R0"]
    assert old_val == 10
    assert new_val == 11


def test_debugger_trace_integration() -> None:
    """Debugger can trace execution."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode, enable_trace=True)

    debugger.continue_exec()

    json_str = debugger.export_trace()
    data = json.loads(json_str)
    assert data["total_steps"] == 3
    assert data["final_state"]["halted"] is True


def test_debugger_watchpoints() -> None:
    """Debugger supports register watchpoints."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.watch_reg(0, "accumulator")
    assert "accumulator" in debugger.list_watchpoints()

    debugger.unwatch_reg(0)
    assert len(debugger.list_watchpoints()) == 0


def test_debugger_breakpoint_management() -> None:
    """Debugger supports full breakpoint lifecycle."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Add
    assert debugger.add_breakpoint(1) is True
    assert debugger.add_breakpoint(1) is False  # Duplicate

    # Disable / Enable
    assert debugger.disable_breakpoint(1) is True
    assert debugger.disable_breakpoint(1) is False  # Already disabled
    assert debugger.enable_breakpoint(1) is True

    # Remove
    assert debugger.remove_breakpoint(1) is True
    assert debugger.remove_breakpoint(1) is False


def test_debugger_cross_impl() -> None:
    """Debugger correctly executes the cross_impl program."""
    bytecode = _assemble_simple(CROSS_IMPL_ASM)
    debugger = FluxDebugger(bytecode)

    result = debugger.continue_exec()
    assert result.halted

    # Verify expected register values
    for reg_num, expected in [
        (0, 13), (1, 100), (2, 15), (3, 5),
        (4, 5040), (5, 42), (6, 42), (7, 14),
    ]:
        actual = debugger.inspect_reg(reg_num)
        assert actual == expected, (
            f"R{reg_num} = {actual}, expected {expected}"
        )


def test_debugger_reset() -> None:
    """Debugger can reset to initial state."""
    bytecode = bytes([Op.MOVI, 0]) + _i16_le(42) + bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.continue_exec()
    assert debugger.halted
    assert debugger.inspect_reg(0) == 42

    debugger.reset()
    assert not debugger.halted
    assert debugger.inspect_reg(0) == 0  # Reset clears registers
