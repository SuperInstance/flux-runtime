"""
ISA v2 Encoder - Fixed 4-byte instruction format
All instructions are exactly 4 bytes: [opcode][byte1][byte2][byte3]
"""

from typing import Union
from dataclasses import dataclass


# Opcode definitions
class Opcode:
    NOP = 0x00
    MOV = 0x01
    IADD = 0x08
    ISUB = 0x09
    IMUL = 0x0A
    IDIV = 0x0B
    INC = 0x0E
    DEC = 0x0F
    JMP = 0x07
    JNZ = 0x06
    JZ = 0x2E
    PUSH = 0x10
    POP = 0x11
    MOVI = 0x2B
    CMP = 0x2D
    HALT = 0x80


@dataclass
class Instruction:
    """Represents a single instruction"""
    opcode: int
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: int = 0
    offset: int = 0


def encode_v2(instruction: Union[Instruction, dict]) -> bytes:
    """
    Encode an instruction into 4-byte format.

    Format: [opcode][byte1][byte2][byte3]

    Specific encodings:
    - ALU (IADD, ISUB, IMUL, IDIV, CMP): [op][rd][rs1][rs2]
    - MOVI: [op][rd][imm_lo][imm_hi]
    - MOV: [op][rd][rs][0x00]
    - INC/DEC: [op][rd][0x00][0x00]
    - JNZ/JZ: [op][rd][off_lo][off_hi]
    - JMP: [op][0x00][off_lo][off_hi]
    - PUSH/POP: [op][rd][0x00][0x00]
    - HALT: [0x80][0x00][0x00][0x00]
    - NOP: [0x00][0x00][0x00][0x00]
    """
    if isinstance(instruction, dict):
        instruction = Instruction(**instruction)

    opcode = instruction.opcode
    rd = instruction.rd & 0xFF
    rs1 = instruction.rs1 & 0xFF
    rs2 = instruction.rs2 & 0xFF

    if opcode == Opcode.NOP:
        return bytes([0x00, 0x00, 0x00, 0x00])

    elif opcode == Opcode.HALT:
        return bytes([0x80, 0x00, 0x00, 0x00])

    elif opcode in (Opcode.IADD, Opcode.ISUB, Opcode.IMUL, Opcode.IDIV, Opcode.CMP):
        # [op][rd][rs1][rs2]
        return bytes([opcode, rd, rs1, rs2])

    elif opcode == Opcode.MOVI:
        # [op][rd][imm_lo][imm_hi]
        imm = instruction.imm & 0xFFFF
        imm_lo = imm & 0xFF
        imm_hi = (imm >> 8) & 0xFF
        return bytes([opcode, rd, imm_lo, imm_hi])

    elif opcode == Opcode.MOV:
        # [op][rd][rs][0x00]
        return bytes([opcode, rd, rs1, 0x00])

    elif opcode in (Opcode.INC, Opcode.DEC, Opcode.PUSH, Opcode.POP):
        # [op][rd][0x00][0x00]
        return bytes([opcode, rd, 0x00, 0x00])

    elif opcode in (Opcode.JNZ, Opcode.JZ):
        # [op][rd][off_lo][off_hi]
        off = instruction.offset & 0xFFFF
        off_lo = off & 0xFF
        off_hi = (off >> 8) & 0xFF
        return bytes([opcode, rd, off_lo, off_hi])

    elif opcode == Opcode.JMP:
        # [op][0x00][off_lo][off_hi]
        off = instruction.offset & 0xFFFF
        off_lo = off & 0xFF
        off_hi = (off >> 8) & 0xFF
        return bytes([opcode, 0x00, off_lo, off_hi])

    else:
        raise ValueError(f"Unknown opcode: 0x{opcode:02X}")


def encode_program(instructions: list[Union[Instruction, dict]]) -> bytes:
    """Encode a list of instructions into bytecode"""
    bytecode = b''
    for instr in instructions:
        bytecode += encode_v2(instr)
    return bytecode
