"""FLUX JIT Module — just-in-time compilation framework.

Provides:
- JITCompiler: compiles FIR functions to optimized native-like code
- JITCache: LRU cache for compiled functions
- ExecutionTracer: profiles hot paths for JIT decisions
- Optimization passes: const_fold_pass, dead_code_pass, inline_pass, block_layout_pass
"""

from .cache import CacheEntry, JITCache
from .compiler import JITCompiler, JITFunction, RegisterAllocation
from .ir_optimize import (
    block_layout_pass,
    const_fold_pass,
    dead_code_pass,
    inline_pass,
)
from .tracing import BlockProfile, ExecutionTracer, FunctionProfile

__all__ = [
    "BlockProfile",
    "CacheEntry",
    "ExecutionTracer",
    "FunctionProfile",
    "JITCache",
    "JITCompiler",
    "JITFunction",
    "RegisterAllocation",
    "block_layout_pass",
    "const_fold_pass",
    "dead_code_pass",
    "inline_pass",
]
