"""Tests for the ISA v3 opcode extensions:

    Confidence-fused arithmetic:  CAAD, CSUB, CMUL, CDIV
    ATP / energy management:      ATP_SPEND, ATP_QUERY
    A2A messaging:                MSG_SEND, MSG_RECV, MSG_POLL
    Power states:                 SLEEP, WAKE, WDOG_RESET

Each test constructs the bytecode by hand (see ``tests/test_vm.py`` for
the encoding reference) and asserts the interpreter produces the right
register / state results.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter, VMDivisionByZeroError

import pytest


def _i16_le(v: int) -> bytes:
    return struct.pack("<h", v)


def _u16_le(v: int) -> bytes:
    return struct.pack("<H", v)


def _movi(reg: int, imm: int) -> bytes:
    return bytes([Op.MOVI, reg]) + _i16_le(imm)


# ═════════════════════════════════════════════════════════════════════════
# Confidence-fused arithmetic
# ═════════════════════════════════════════════════════════════════════════


def test_caad_adds_and_propagates_min_confidence() -> None:
    bytecode = _movi(1, 40) + _movi(2, 2) + bytes([Op.CAAD, 0, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_confidence(1, 0.9)
    vm.set_confidence(2, 0.5)
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.get_confidence(0) == pytest.approx(0.5)


def test_caad_default_confidence_is_one() -> None:
    bytecode = _movi(1, 10) + _movi(2, 3) + bytes([Op.CAAD, 3, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.execute()
    assert vm.regs.read_gp(3) == 13
    assert vm.get_confidence(3) == pytest.approx(1.0)


def test_csub_propagates_min_confidence() -> None:
    bytecode = _movi(1, 50) + _movi(2, 8) + bytes([Op.CSUB, 0, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_confidence(1, 0.7)
    vm.set_confidence(2, 0.6)
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.get_confidence(0) == pytest.approx(0.6)


def test_cmul_multiplies_confidence() -> None:
    bytecode = _movi(1, 6) + _movi(2, 7) + bytes([Op.CMUL, 0, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_confidence(1, 0.8)
    vm.set_confidence(2, 0.5)
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.get_confidence(0) == pytest.approx(0.4)


def test_cdiv_divides_and_multiplies_confidence() -> None:
    bytecode = _movi(1, 84) + _movi(2, 2) + bytes([Op.CDIV, 0, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_confidence(1, 0.9)
    vm.set_confidence(2, 0.5)
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.get_confidence(0) == pytest.approx(0.45)


def test_cdiv_by_zero_raises() -> None:
    bytecode = _movi(1, 84) + _movi(2, 0) + bytes([Op.CDIV, 0, 1, 2, Op.HALT])
    vm = Interpreter(bytecode)
    with pytest.raises(VMDivisionByZeroError):
        vm.execute()


# ═════════════════════════════════════════════════════════════════════════
# ATP / energy management
# ═════════════════════════════════════════════════════════════════════════


def test_atp_query_reads_default_budget() -> None:
    bytecode = bytes([Op.ATP_QUERY, 0, Op.HALT])
    vm = Interpreter(bytecode)
    vm.execute()
    assert vm.regs.read_gp(0) == 1_000_000


def test_atp_query_reads_custom_budget() -> None:
    bytecode = bytes([Op.ATP_QUERY, 2, Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_atp_budget(12_345)
    vm.execute()
    assert vm.regs.read_gp(2) == 12_345


def test_atp_spend_deducts_from_budget() -> None:
    bytecode = bytes([Op.ATP_SPEND, 1]) + _i16_le(100) + bytes([Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_atp_budget(500)
    vm.execute()
    assert vm.regs.read_gp(1) == 400
    assert vm.get_atp_budget() == 400


def test_atp_spend_returns_minus_one_on_insufficient() -> None:
    bytecode = bytes([Op.ATP_SPEND, 1]) + _i16_le(1000) + bytes([Op.HALT])
    vm = Interpreter(bytecode)
    vm.set_atp_budget(10)
    vm.execute()
    assert vm.regs.read_gp(1) == -1
    assert vm.get_atp_budget() == 10  # budget unchanged


# ═════════════════════════════════════════════════════════════════════════
# A2A messaging
# ═════════════════════════════════════════════════════════════════════════


def test_msg_send_dispatches_and_returns_length() -> None:
    payload = b"hello"
    bytecode = bytes([Op.MSG_SEND]) + _u16_le(len(payload)) + payload + bytes([Op.HALT])
    seen: list[tuple[str, bytes]] = []
    vm = Interpreter(bytecode)
    vm.on_a2a(lambda name, data: seen.append((name, data)))
    vm.execute()
    assert seen == [("MSG_SEND", payload)]
    assert vm.regs.read_gp(0) == len(payload)


def test_msg_recv_drains_pending_inbox() -> None:
    bytecode = bytes([Op.MSG_RECV]) + _u16_le(0) + bytes([Op.HALT])
    vm = Interpreter(bytecode)
    vm.push_message(b"ping")
    delivered: list[bytes] = []
    vm.on_a2a(lambda name, data: delivered.append(data) if name == "MSG_RECV" else None)
    vm.execute()
    assert vm.regs.read_gp(0) == 4
    assert delivered == [b"ping"]


def test_msg_recv_empty_returns_zero() -> None:
    bytecode = bytes([Op.MSG_RECV]) + _u16_le(0) + bytes([Op.HALT])
    vm = Interpreter(bytecode)
    vm.execute()
    assert vm.regs.read_gp(0) == 0


def test_msg_poll_counts_inbox_depth() -> None:
    bytecode = bytes([Op.MSG_POLL, 3, Op.HALT])
    vm = Interpreter(bytecode)
    vm.push_message(b"a")
    vm.push_message(b"b")
    vm.push_message(b"c")
    vm.execute()
    assert vm.regs.read_gp(3) == 3


# ═════════════════════════════════════════════════════════════════════════
# Power states
# ═════════════════════════════════════════════════════════════════════════


def test_sleep_sets_remaining_and_writes_cycles() -> None:
    bytecode = bytes([Op.SLEEP, 0]) + _i16_le(42) + bytes([Op.HALT])
    vm = Interpreter(bytecode)
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm._sleep_remaining == 42


def test_wake_clears_sleep() -> None:
    bytecode = bytes([Op.SLEEP, 0]) + _i16_le(99) + bytes([Op.WAKE, Op.HALT])
    vm = Interpreter(bytecode)
    vm.execute()
    assert vm._sleep_remaining == 0


def test_wdog_reset_reloads_timer() -> None:
    bytecode = bytes([Op.WDOG_RESET, Op.HALT])
    vm = Interpreter(bytecode)
    # Simulate time passing.
    vm._wdog_remaining = 7
    vm.execute()
    assert vm._wdog_remaining == vm._wdog_timeout


# ═════════════════════════════════════════════════════════════════════════
# Opcode metadata sanity — keeps decoder/encoder in sync.
# ═════════════════════════════════════════════════════════════════════════


def test_new_opcodes_have_expected_formats() -> None:
    from flux.bytecode.opcodes import get_format

    assert get_format(Op.CAAD) == "E"
    assert get_format(Op.CSUB) == "E"
    assert get_format(Op.CMUL) == "E"
    assert get_format(Op.CDIV) == "E"
    assert get_format(Op.ATP_SPEND) == "D"
    assert get_format(Op.ATP_QUERY) == "B"
    assert get_format(Op.MSG_SEND) == "G"
    assert get_format(Op.MSG_RECV) == "G"
    assert get_format(Op.MSG_POLL) == "B"
    assert get_format(Op.SLEEP) == "D"
    assert get_format(Op.WAKE) == "A"
    assert get_format(Op.WDOG_RESET) == "A"
