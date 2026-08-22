"""System B (unified ISA) opcode table — IntEnum mirror of ``isa_unified.py``.

This is the converged three-agent ISA (Oracle1 + JetsonClaw1 + Babel) — the
canonical numbering the interpreter is converging onto (see
``docs/OPCODE-RECONCILIATION.md``).

It is DISTINCT from System A (``flux.bytecode.opcodes.Op``), the legacy live
numbering used by the current interpreter. Both tables are preserved and
annotated; this module exists so the interpreter can execute unified-ISA
(System B) bytecode without disturbing System A.

Single source of truth: ``build_unified_isa()`` in ``isa_unified.py``. This
module derives an ``IntEnum`` (and a format table) from it rather than
duplicating the numbers by hand.
"""

from __future__ import annotations

from enum import IntEnum

from .isa_unified import build_unified_isa

# ── Build the IntEnum from the single source of truth ─────────────────────
# Reserved slots (RESERVED_xx) are intentionally NOT executable and are skipped.
_NAME_TO_CODE: dict[str, int] = {}
_FORMAT_BY_CODE: dict[int, str] = {}
_DESC_BY_CODE: dict[int, str] = {}

for _def in build_unified_isa():
    if _def.reserved:
        continue
    _NAME_TO_CODE[_def.mnemonic] = _def.opcode
    _FORMAT_BY_CODE[_def.opcode] = _def.format
    _DESC_BY_CODE[_def.opcode] = _def.description


# IntEnum of all defined (non-reserved) System B opcodes.
UnifiedOp = IntEnum("UnifiedOp", _NAME_TO_CODE)  # type: ignore[call-overload]


# ── Format helpers (System B formats) ─────────────────────────────────────
#   A: 1 byte  [op]
#   B: 2 bytes [op][rd]
#   C: 2 bytes [op][imm8]
#   D: 3 bytes [op][rd][imm8]
#   E: 4 bytes [op][rd][rs1][rs2]
#   F: 4 bytes [op][rd][imm16]
#   G: 5 bytes [op][rd][rs1][imm16]
_SIZE_BY_FORMAT = {"A": 1, "B": 2, "C": 2, "D": 3, "E": 4, "F": 4, "G": 5}


def get_unified_format(opcode: int) -> str:
    """Return the System B format letter for an opcode byte (``""`` if unknown)."""
    return _FORMAT_BY_CODE.get(int(opcode), "")


def unified_instruction_size(opcode: int) -> int:
    """Fixed size in bytes for a System B opcode (``-1`` for unknown/reserved)."""
    return _SIZE_BY_FORMAT.get(_FORMAT_BY_CODE.get(int(opcode), ""), -1)


def unified_op_name(opcode: int) -> str | None:
    """Return the System B mnemonic for an opcode byte (``None`` if unknown)."""
    try:
        return UnifiedOp(opcode).name
    except ValueError:
        return None
