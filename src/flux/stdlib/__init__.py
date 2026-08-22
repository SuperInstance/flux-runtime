"""FLUX Standard Library — built-in intrinsics, collections, math, strings, and agent utilities.

Each stdlib function is represented as a callable that produces FIR instructions
when invoked through a :class:`FIRBuilder`.  This lets the compiler inline stdlib
operations at the IR level before lowering to bytecode.
"""

from .agents import (
    STDLIB_AGENTS,
    AgentRegistryImpl,
    MessageQueueImpl,
    TaskSchedulerImpl,
)
from .collections import (
    STDLIB_COLLECTIONS,
    ListImpl,
    MapImpl,
    QueueImpl,
    SetImpl,
    StackImpl,
)
from .intrinsics import (
    STDLIB_INTRINSICS,
    AlignofFn,
    AssertFn,
    IntrinsicFunction,
    PanicFn,
    PrintFn,
    SizeofFn,
    TypeOfFn,
)
from .math import (
    STDLIB_MATH,
    AbsFn,
    ClampFn,
    LerpFn,
    MaxFn,
    MinFn,
    SqrtFn,
)
from .strings import (
    STDLIB_STRINGS,
    ConcatFn,
    FormatFn,
    JoinFn,
    LengthFn,
    SplitFn,
    SubstringFn,
)

__all__ = [
    "STDLIB_AGENTS",
    "STDLIB_COLLECTIONS",
    "STDLIB_INTRINSICS",
    "STDLIB_MATH",
    "STDLIB_STRINGS",
    "AbsFn",
    # Agents
    "AgentRegistryImpl",
    "AlignofFn",
    "AssertFn",
    "ClampFn",
    # Strings
    "ConcatFn",
    "FormatFn",
    # Intrinsics
    "IntrinsicFunction",
    "JoinFn",
    "LengthFn",
    "LerpFn",
    # Collections
    "ListImpl",
    "MapImpl",
    "MaxFn",
    "MessageQueueImpl",
    # Math
    "MinFn",
    "PanicFn",
    "PrintFn",
    "QueueImpl",
    "SetImpl",
    "SizeofFn",
    "SplitFn",
    "SqrtFn",
    "StackImpl",
    "SubstringFn",
    "TaskSchedulerImpl",
    "TypeOfFn",
]
