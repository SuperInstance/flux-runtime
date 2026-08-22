"""FIR — FLUX Intermediate Representation.

Core IR layer for the FLUX bytecode system. Provides:
- Type system with interning (TypeContext)
- SSA values (Value)
- Instructions (arithmetic, memory, control flow, A2A primitives)
- Blocks, functions, and modules (structural IR)
- Builder for ergonomic IR construction
- Validator for structural invariants
- Printer for human-readable output
"""

from .blocks import FIRBlock, FIRFunction, FIRModule
from .builder import FIRBuilder
from .instructions import (
    Alloca,
    Ask,
    Bitcast,
    Branch,
    Call,
    CapRequire,
    Delegate,
    FAdd,
    FDiv,
    FEq,
    FExt,
    FGe,
    FGt,
    FLe,
    FLt,
    FMul,
    FNeg,
    FSub,
    FTrunc,
    GetElem,
    GetField,
    # Arithmetic
    IAdd,
    # Bitwise
    IAnd,
    IDiv,
    # Comparison
    IEq,
    IGe,
    IGt,
    ILe,
    ILt,
    IMod,
    IMul,
    INe,
    INeg,
    INot,
    Instruction,
    IOr,
    IShl,
    IShr,
    ISub,
    # Conversion
    ITrunc,
    IXor,
    # Control flow
    Jump,
    # Memory
    Load,
    MemCopy,
    MemSet,
    Return,
    SetElem,
    SetField,
    SExt,
    Store,
    Switch,
    # A2A
    Tell,
    TrustCheck,
    Unreachable,
    ZExt,
    # Helpers
    is_terminator,
)
from .printer import print_fir
from .types import (
    AgentType,
    ArrayType,
    BoolType,
    CapabilityType,
    EnumType,
    FIRType,
    FloatType,
    FuncType,
    IntType,
    RefType,
    RegionType,
    StringType,
    StructType,
    TrustType,
    TypeContext,
    UnitType,
    VectorType,
)
from .validator import FIRValidator
from .values import Value

__all__ = [
    "AgentType",
    "Alloca",
    "ArrayType",
    "Ask",
    "Bitcast",
    "BoolType",
    "Branch",
    "Call",
    "CapRequire",
    "CapabilityType",
    "Delegate",
    "EnumType",
    "FAdd",
    "FDiv",
    "FEq",
    "FExt",
    "FGe",
    "FGt",
    # Blocks
    "FIRBlock",
    # Builder
    "FIRBuilder",
    "FIRFunction",
    "FIRModule",
    # Types
    "FIRType",
    # Validator
    "FIRValidator",
    "FLe",
    "FLt",
    "FMul",
    "FNeg",
    "FSub",
    "FTrunc",
    "FloatType",
    "FuncType",
    "GetElem",
    "GetField",
    "IAdd",
    "IAnd",
    "IDiv",
    "IEq",
    "IGe",
    "IGt",
    "ILe",
    "ILt",
    "IMod",
    "IMul",
    "INe",
    "INeg",
    "INot",
    "IOr",
    "IShl",
    "IShr",
    "ISub",
    "ITrunc",
    "IXor",
    # Instructions
    "Instruction",
    "IntType",
    "Jump",
    "Load",
    "MemCopy",
    "MemSet",
    "RefType",
    "RegionType",
    "Return",
    "SExt",
    "SetElem",
    "SetField",
    "Store",
    "StringType",
    "StructType",
    "Switch",
    "Tell",
    "TrustCheck",
    "TrustType",
    "TypeContext",
    "UnitType",
    "Unreachable",
    # Values
    "Value",
    "VectorType",
    "ZExt",
    "is_terminator",
    # Printer
    "print_fir",
]
