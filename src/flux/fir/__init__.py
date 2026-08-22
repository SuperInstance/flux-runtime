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
    # Types
    "FIRType", "IntType", "FloatType", "BoolType", "UnitType", "StringType",
    "RefType", "ArrayType", "VectorType", "FuncType", "StructType", "EnumType",
    "RegionType", "CapabilityType", "AgentType", "TrustType",
    "TypeContext",
    # Values
    "Value",
    # Instructions
    "Instruction",
    "IAdd", "ISub", "IMul", "IDiv", "IMod", "INeg",
    "FAdd", "FSub", "FMul", "FDiv", "FNeg",
    "IAnd", "IOr", "IXor", "IShl", "IShr", "INot",
    "IEq", "INe", "ILt", "IGt", "ILe", "IGe",
    "FEq", "FLt", "FGt", "FLe", "FGe",
    "ITrunc", "ZExt", "SExt", "FTrunc", "FExt", "Bitcast",
    "Load", "Store", "Alloca", "GetField", "SetField", "GetElem", "SetElem",
    "MemCopy", "MemSet",
    "Jump", "Branch", "Switch", "Call", "Return", "Unreachable",
    "Tell", "Ask", "Delegate", "TrustCheck", "CapRequire",
    "is_terminator",
    # Blocks
    "FIRBlock", "FIRFunction", "FIRModule",
    # Builder
    "FIRBuilder",
    # Validator
    "FIRValidator",
    # Printer
    "print_fir",
]
