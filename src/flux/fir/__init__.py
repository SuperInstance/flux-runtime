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

from .types import (
    FIRType,
    IntType,
    FloatType,
    BoolType,
    UnitType,
    StringType,
    RefType,
    ArrayType,
    VectorType,
    FuncType,
    StructType,
    EnumType,
    RegionType,
    CapabilityType,
    AgentType,
    TrustType,
    TypeContext,
)

from .values import Value

from .instructions import (
    Instruction,
    # Arithmetic
    IAdd, ISub, IMul, IDiv, IMod, INeg,
    FAdd, FSub, FMul, FDiv, FNeg,
    # Bitwise
    IAnd, IOr, IXor, IShl, IShr, INot,
    # Comparison
    IEq, INe, ILt, IGt, ILe, IGe,
    FEq, FLt, FGt, FLe, FGe,
    # Conversion
    ITrunc, ZExt, SExt, FTrunc, FExt, Bitcast,
    # Memory
    Load, Store, Alloca, GetField, SetField, GetElem, SetElem, MemCopy, MemSet,
    # Control flow
    Jump, Branch, Switch, Call, Return, Unreachable,
    # A2A
    Tell, Ask, Delegate, TrustCheck, CapRequire,
    # Helpers
    is_terminator,
)

from .blocks import FIRBlock, FIRFunction, FIRModule

from .builder import FIRBuilder

from .validator import FIRValidator

from .printer import print_fir

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
