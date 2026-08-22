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
    # Intrinsics
    "IntrinsicFunction", "PrintFn", "AssertFn", "PanicFn",
    "SizeofFn", "AlignofFn", "TypeOfFn", "STDLIB_INTRINSICS",
    # Collections
    "ListImpl", "MapImpl", "SetImpl", "QueueImpl", "StackImpl",
    "STDLIB_COLLECTIONS",
    # Math
    "MinFn", "MaxFn", "AbsFn", "ClampFn", "LerpFn", "SqrtFn",
    "STDLIB_MATH",
    # Strings
    "ConcatFn", "SubstringFn", "SplitFn", "JoinFn", "LengthFn",
    "FormatFn", "STDLIB_STRINGS",
    # Agents
    "AgentRegistryImpl", "MessageQueueImpl", "TaskSchedulerImpl",
    "STDLIB_AGENTS",
]
