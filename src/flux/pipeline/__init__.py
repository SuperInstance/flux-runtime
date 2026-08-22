"""FLUX Pipeline — end-to-end compilation and execution pipelines.

Provides:
  - FluxPipeline: Full FLUX.MD → FIR → optimize → bytecode → VM execution
  - PolyglotCompiler: Cross-language (C, Python) compilation to unified bytecode
  - PipelineDebugger: Step-by-step execution tracing and debugging utilities
"""

from .debug import PipelineDebugger, disassemble_bytecode, print_fir_module
from .e2e import FluxPipeline, PipelineResult
from .polyglot import PolyglotCompiler

__all__ = [
    "FluxPipeline",
    "PipelineDebugger",
    "PipelineResult",
    "PolyglotCompiler",
    "disassemble_bytecode",
    "print_fir_module",
]
