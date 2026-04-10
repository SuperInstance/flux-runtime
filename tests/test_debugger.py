"""FLUX Debugger and Disassembler Tests.

Tests for the FluxDisassembler and FluxDebugger classes, including:
- Disassembly of known bytecode sequences
- Step-by-step execution
- Breakpoint management
- Watchpoint functionality
- Register/memory inspection
- Integration with existing bytecode
"""

import struct
import sys
import os

# Ensure the project source root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.bytecode.opcodes import Op
from flux.disasm import (
    FluxDisassembler,
    DisassemblyResult,
    DisassembledInstruction,
    disassemble,
    disassemble_to_dict,
    disassemble_to_json,
)
from flux.debugger import (
    FluxDebugger,
    StepResult,
    Breakpoint,
    Watchpoint,
)
from flux.vm.interpreter import VMError


# ── Helper functions ─────────────────────────────────────────────────────────

def _make_flux_binary(code: bytes) -> bytes:
    """Wrap raw bytecode in FLUX binary format."""
    HEADER_SIZE = 18
    type_table = struct.pack("<H", 0)  # 0 types
    name_pool = b""
    func_table = struct.pack("<III", 0, 0, len(code))
    code_off = HEADER_SIZE + len(type_table) + len(name_pool) + len(func_table)
    header = struct.pack("<4sHHHII", b"FLUX", 1, 0, 1, HEADER_SIZE, code_off)
    return header + type_table + name_pool + func_table + code


def _i16_le(val: int) -> bytes:
    """Pack a signed 16-bit integer as little-endian bytes."""
    return struct.pack("<h", val)


# ── Disassembler Tests ────────────────────────────────────────────────────────

def test_disassembler_nop() -> None:
    """Disassembler handles NOP (Format A)."""
    bytecode = bytes([Op.NOP, Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.NOP
    assert result.instructions[0].opcode_name == "NOP"
    assert result.instructions[0].operands == ""
    assert result.instructions[0].size == 1
    assert result.total_bytes == 2


def test_disassembler_mov() -> None:
    """Disassembler handles MOV (Format C)."""
    # MOV R0, R1; HALT
    bytecode = bytes([Op.MOV, 0x00, 0x01, Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.MOV
    assert result.instructions[0].operands == "R0, R1"
    assert result.instructions[0].size == 3


def test_disassembler_movi() -> None:
    """Disassembler handles MOVI (Format D)."""
    # MOVI R0, 42; HALT
    bytecode = struct.pack("<BBh", Op.MOVI, 0, 42) + bytes([Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.MOVI
    assert result.instructions[0].operands == "R0, 42"
    assert result.instructions[0].size == 4


def test_disassembler_iadd() -> None:
    """Disassembler handles IADD (Format E: [op][rd][rs1][rs2])."""
    # IADD is Format E: opcode + rd + rs1 + rs2
    # IADD R0, R0, R1 means R0 = R0 + R1
    bytecode = bytes([Op.IADD, 0x00, 0x00, 0x01, Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.IADD
    assert result.instructions[0].operands == "R0, R0, R1"
    assert result.instructions[0].size == 4


def test_disassembler_jump() -> None:
    """Disassembler handles JMP (Format D with offset)."""
    # JMP R0, +8; HALT
    bytecode = struct.pack("<BBh", Op.JMP, 0, 8) + bytes([Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.JMP
    # The offset calculation should show the target
    assert "+8" in result.instructions[0].operands


def test_disassembler_extracts_flux_header() -> None:
    """Disassembler extracts code section from FLUX binary format."""
    raw_code = bytes([Op.MOVI, 0, 42, 0, Op.HALT])
    flux_binary = _make_flux_binary(raw_code)

    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(flux_binary)

    # Should only disassemble the code section
    assert len(result.instructions) == 2
    assert result.instructions[0].opcode == Op.MOVI
    assert result.instructions[1].opcode == Op.HALT


def test_disassembler_unknown_opcode() -> None:
    """Disassembler handles unknown opcodes gracefully."""
    # Use 0xFF which is not a valid opcode
    bytecode = bytes([0xFF, Op.HALT])
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)

    assert len(result.instructions) == 2
    assert "UNKNOWN" in result.instructions[0].opcode_name
    assert result.instructions[0].size == 1


def test_disassembler_to_dict() -> None:
    """Disassembler can serialize results to dict."""
    bytecode = bytes([Op.MOVI, 0, 42, 0, Op.HALT])
    result_dict = disassemble_to_dict(bytecode)

    assert "instructions" in result_dict
    assert result_dict["total_bytes"] == 5
    assert result_dict["instruction_count"] == 2
    assert result_dict["instructions"][0]["opcode_name"] == "MOVI"


def test_disassembler_to_json() -> None:
    """Disassembler can serialize results to JSON."""
    bytecode = bytes([Op.MOVI, 0, 42, 0, Op.HALT])
    json_str = disassemble_to_json(bytecode)

    # Should be valid JSON
    import json
    data = json.loads(json_str)
    assert data["instruction_count"] == 2


def test_disassembler_color_output() -> None:
    """Disassembler produces color output when requested."""
    bytecode = bytes([Op.IADD, 0, 1, 2, Op.HALT])

    # With color
    disasm_color = FluxDisassembler(color_output=True)
    result_color = disasm_color.disassemble(bytecode)
    output_color = disasm_color.format_instruction(result_color.instructions[0])
    assert "\033[" in output_color  # ANSI escape sequence

    # Without color
    disasm_plain = FluxDisassembler(color_output=False)
    result_plain = disasm_plain.disassemble(bytecode)
    output_plain = disasm_plain.format_instruction(result_plain.instructions[0])
    assert "\033[" not in output_plain


def test_disassemble_convenience_function() -> None:
    """Convenience function disassemble() works correctly."""
    bytecode = bytes([Op.NOP, Op.HALT])
    output = disassemble(bytecode, color_output=False)

    assert "NOP" in output
    assert "HALT" in output
    assert "Disassembly" in output


# ── Debugger Tests ────────────────────────────────────────────────────────────

def test_debugger_creation() -> None:
    """Debugger can be created from bytecode."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    assert debugger.pc == 0
    assert debugger.halted is False
    assert debugger.cycle_count == 0


def test_debugger_step_nop() -> None:
    """Debugger can step through NOP instructions."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.step()

    assert result.success is True
    assert result.instruction is not None
    assert result.instruction.opcode == Op.NOP
    assert result.cycles == 1
    assert result.halted is False


def test_debugger_step_halt() -> None:
    """Debugger stops on HALT instruction."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.step()

    assert result.success is True
    assert result.halted is True
    assert result.instruction is not None
    assert result.instruction.opcode == Op.HALT


def test_debugger_step_arithmetic() -> None:
    """Debugger can step through arithmetic instructions."""
    # MOVI R0, 10; MOVI R1, 20; IADD R0, R0, R1; HALT
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 10) +
        struct.pack("<BBh", Op.MOVI, 1, 20) +
        bytes([Op.IADD, 0, 0, 1]) +
        bytes([Op.HALT])
    )
    debugger = FluxDebugger(bytecode)

    # Step through MOVI R0, 10
    result1 = debugger.step()
    assert result1.success
    assert debugger.inspect_reg(0) == 10

    # Step through MOVI R1, 20
    result2 = debugger.step()
    assert result2.success
    assert debugger.inspect_reg(1) == 20

    # Step through IADD
    result3 = debugger.step()
    assert result3.success
    assert debugger.inspect_reg(0) == 30


def test_debugger_inspect_register() -> None:
    """Debugger can inspect register values."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.set_reg(5, 42)
    assert debugger.inspect_reg(5) == 42


def test_debugger_set_register() -> None:
    """Debugger can set register values."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.set_reg(3, 12345)
    assert debugger.inspect_reg(3) == 12345


def test_debugger_inspect_memory() -> None:
    """Debugger can inspect memory."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Write to memory
    debugger.write_mem(100, b"\x01\x02\x03\x04")

    # Read back
    data = debugger.inspect_mem(100, 4)
    assert data == b"\x01\x02\x03\x04"


def test_debugger_breakpoint_management() -> None:
    """Debugger can manage breakpoints."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Add breakpoint
    assert debugger.add_breakpoint(2) is True
    assert debugger.add_breakpoint(2) is False  # Already exists

    # List breakpoints
    bps = debugger.list_breakpoints()
    assert len(bps) == 1
    assert bps[0]["offset"] == 2

    # Remove breakpoint
    assert debugger.remove_breakpoint(2) is True
    assert debugger.remove_breakpoint(2) is False  # Already removed

    # List should be empty
    assert len(debugger.list_breakpoints()) == 0


def test_debugger_breakpoint_hit() -> None:
    """Debugger detects when breakpoint is hit."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.add_breakpoint(1)

    # First step (no breakpoint)
    result1 = debugger.step()
    assert result1.breakpoint_hit is False

    # Second step (breakpoint at offset 1)
    result2 = debugger.step()
    assert result2.breakpoint_hit is True

    # Check hit count
    bps = debugger.list_breakpoints()
    assert bps[0]["hit_count"] == 1


def test_debugger_breakpoint_enable_disable() -> None:
    """Debugger can enable and disable breakpoints."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.add_breakpoint(1)

    # Disable breakpoint
    assert debugger.disable_breakpoint(1) is True

    # Step through - should not trigger
    debugger.step()  # NOP at 0
    result = debugger.step()  # NOP at 1 (breakpoint disabled)
    assert result.breakpoint_hit is False

    # Enable breakpoint
    assert debugger.enable_breakpoint(1) is True

    # Reset and try again
    debugger.reset()
    debugger.add_breakpoint(1)
    debugger.step()  # NOP at 0
    result = debugger.step()  # NOP at 1
    assert result.breakpoint_hit is True


def test_debugger_continue() -> None:
    """Debugger can continue until breakpoint or halt."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Add breakpoint at offset 2 (third NOP)
    debugger.add_breakpoint(2)

    # Continue should stop at breakpoint
    result = debugger.continue_exec()

    assert result.breakpoint_hit is True
    # After executing the instruction at offset 2, PC should be at 3
    assert result.pc_after == 3


def test_debugger_continue_to_halt() -> None:
    """Debugger continues to halt when no breakpoints."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.continue_exec()

    assert result.halted is True
    assert result.pc_after == 3


def test_debugger_watchpoint() -> None:
    """Debugger can set and list watchpoints."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.watch_reg(5)
    debugger.watch_reg(10, "my_reg")

    wps = debugger.list_watchpoints()
    assert len(wps) == 2
    assert "R5" in wps
    assert "my_reg" in wps

    # Remove watchpoint
    assert debugger.unwatch_reg(5) is True
    assert len(debugger.list_watchpoints()) == 1


def test_debugger_backtrace() -> None:
    """Debugger can provide call stack backtrace."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    frames = debugger.backtrace()
    assert len(frames) >= 1
    assert frames[0]["type"] == "current"
    assert "pc" in frames[0]


def test_debugger_flags() -> None:
    """Debugger can inspect condition flags."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    flags = debugger.get_flags()
    assert "zero" in flags
    assert "sign" in flags
    assert "carry" in flags
    assert "overflow" in flags


def test_debugger_register_dump() -> None:
    """Debugger can dump all registers."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.set_reg(0, 1)
    debugger.set_reg(5, 42)

    regs = debugger.get_register_dump()
    assert regs["R0"] == 1
    assert regs["R5"] == 42
    assert "R15" in regs


def test_debugger_stack_snapshot() -> None:
    """Debugger can get stack snapshot."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Push some values
    debugger._stack_push(42)
    debugger._stack_push(99)

    snapshot = debugger.get_stack_snapshot(4)
    assert len(snapshot) >= 2
    assert snapshot[0] == 99  # Top of stack
    assert snapshot[1] == 42


def test_debugger_disassemble_at() -> None:
    """Debugger can disassemble at a specific offset."""
    bytecode = bytes([Op.NOP, Op.MOV, 0, 1, Op.HALT])
    debugger = FluxDebugger(bytecode)

    instrs = debugger.disassemble_at(0, 3)
    assert len(instrs) == 3
    assert instrs[0].opcode == Op.NOP
    assert instrs[1].opcode == Op.MOV
    assert instrs[2].opcode == Op.HALT


def test_debugger_disassemble_current() -> None:
    """Debugger can disassemble from current PC."""
    bytecode = bytes([Op.NOP, Op.MOV, 0, 1, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # At PC=0
    instrs = debugger.disassemble_current(2)
    assert len(instrs) == 2
    assert instrs[0].opcode == Op.NOP

    # Advance PC
    debugger.step()
    instrs = debugger.disassemble_current(2)
    assert instrs[0].opcode == Op.MOV


def test_debugger_format_state() -> None:
    """Debugger can format current state for display."""
    bytecode = bytes([Op.HALT])
    debugger = FluxDebugger(bytecode)

    debugger.set_reg(0, 123)

    state = debugger.format_state()
    assert "PC=" in state
    assert "R0" in state
    assert "123" in state
    assert "Registers:" in state


def test_debugger_reset() -> None:
    """Debugger can reset to initial state."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    # Run some instructions
    debugger.step()
    debugger.set_reg(0, 42)

    assert debugger.pc != 0
    assert debugger.cycle_count > 0

    # Reset
    debugger.reset()

    assert debugger.pc == 0
    assert debugger.cycle_count == 0
    assert debugger.halted is False


def test_debugger_run_to_offset() -> None:
    """Debugger can run to a specific offset."""
    bytecode = bytes([Op.NOP, Op.NOP, Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    result = debugger.run_to_offset(2)

    assert result.success
    assert debugger.pc == 2


def test_debugger_step_callback() -> None:
    """Debugger can call callback after each step."""
    bytecode = bytes([Op.NOP, Op.HALT])
    debugger = FluxDebugger(bytecode)

    callback_calls = []

    def my_callback(result: StepResult) -> None:
        callback_calls.append(result)

    debugger.on_step(my_callback)
    debugger.step()
    debugger.step()

    assert len(callback_calls) == 2


def test_debugger_with_complex_bytecode() -> None:
    """Debugger handles complex bytecode sequences."""
    # MOVI R0, 3; MOVI R1, 4; IADD R0, R0, R1; HALT
    # Note: IADD is Format E: [opcode][rd][rs1][rs2]
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 3) +  # offset 0-3 (4 bytes)
        struct.pack("<BBh", Op.MOVI, 1, 4) +  # offset 4-7 (4 bytes)
        bytes([Op.IADD, 0, 0, 1]) +            # offset 8-11 (4 bytes): R0 = R0 + R1
        bytes([Op.HALT])                       # offset 12 (1 byte)
    )

    debugger = FluxDebugger(bytecode)

    # Set breakpoint after the two MOVI instructions (before IADD)
    debugger.add_breakpoint(8)

    # Continue to breakpoint
    result = debugger.continue_exec()
    assert result.breakpoint_hit

    # We're stopped AT the breakpoint (before IADD executes)
    # Step once to execute IADD
    step_result = debugger.step()
    assert step_result.success
    assert debugger.inspect_reg(0) == 7
    assert debugger.inspect_reg(1) == 4

    # Step once more to execute HALT
    debugger.step()
    assert debugger.halted


# ── Integration Tests ─────────────────────────────────────────────────────────

def test_debugger_with_flux_binary() -> None:
    """Debugger works with FLUX binary format."""
    raw_code = (
        struct.pack("<BBh", Op.MOVI, 0, 10) +
        struct.pack("<BBh", Op.MOVI, 1, 20) +
        bytes([Op.IADD, 0, 0, 1]) +
        bytes([Op.HALT])
    )
    flux_binary = _make_flux_binary(raw_code)

    debugger = FluxDebugger(flux_binary)

    # Should execute correctly
    result = debugger.continue_exec()
    assert result.halted
    assert debugger.inspect_reg(0) == 30


def test_disassembler_and_debugger_consistency() -> None:
    """Disassembler and debugger interpret bytecode consistently."""
    bytecode = bytes([Op.IADD, 0, 1, 2, Op.HALT])

    # Disassemble
    disasm = FluxDisassembler(color_output=False)
    disasm_result = disasm.disassemble(bytecode)

    # Debug
    debugger = FluxDebugger(bytecode)
    debug_result = debugger.step()

    # Both should see the same instruction
    assert disasm_result.instructions[0].opcode == debug_result.instruction.opcode
    assert disasm_result.instructions[0].size == debug_result.instruction.size


# ── Run tests ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest

    # Run all tests in this file
    pytest.main([__file__, "-v"])
