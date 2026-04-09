"""FLUX Pipeline — end-to-end compilation and execution pipelines.

Provides:
  - FluxPipeline: Full FLUX.MD → FIR → optimize → bytecode → VM execution
  - PolyglotCompiler: Cross-language (C, Python) compilation to unified bytecode
  - PipelineDebugger: Step-by-step execution tracing and debugging utilities
"""

from .e2e import FluxPipeline, PipelineResult
from .polyglot import PolyglotCompiler
from .debug import PipelineDebugger, disassemble_bytecode, print_fir_module

__all__ = [
    "FluxPipeline",
    "PipelineResult",
    "PolyglotCompiler",
    "PipelineDebugger",
    "disassemble_bytecode",
    "print_fir_module",
]
