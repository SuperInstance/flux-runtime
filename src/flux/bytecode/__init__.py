"""FLUX Bytecode — encoder, decoder, validator, and opcode definitions.

Provides:
- Op: bytecode opcode enum (IntEnum)
- BytecodeEncoder: encodes FIRModule → binary bytecode
- BytecodeDecoder: decodes binary bytecode → structured representation
- BytecodeValidator: validates bytecode structural integrity
"""

from .decoder import (
    BytecodeDecoder,
    DecodedFunction,
    DecodedInstruction,
    DecodedModule,
    DecodedType,
)
from .encoder import BytecodeEncoder
from .opcodes import Op, get_format, instruction_size
from .validator import BytecodeValidator

__all__ = [
    # Decoder
    "BytecodeDecoder",
    # Encoder
    "BytecodeEncoder",
    # Validator
    "BytecodeValidator",
    "DecodedFunction",
    "DecodedInstruction",
    "DecodedModule",
    "DecodedType",
    # Opcodes
    "Op",
    "get_format",
    "instruction_size",
]
