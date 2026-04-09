"""End-to-end pipeline: FLUX.MD → Parser → FIR → Optimizer → Bytecode → VM.

The FluxPipeline class chains all compilation layers together, providing
a single entry point for compiling and executing FLUX programs.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

from flux.fir.types import TypeContext
from flux.fir.blocks import FIRModule
from flux.fir.printer import print_fir


@dataclass
class PipelineResult:
    """Result of a full pipeline compilation and execution.

    Attributes
    ----------
    source : str
        Original source text (FLUX.MD, C, or Python).
    module : FIRModule | None
        The FIR module produced by compilation (before optimization).
    optimized_module : FIRModule | None
        The FIR module after optimization passes.
    bytecode : bytes | None
        The compiled FLUX bytecode (with header).
    code_section : bytes | None
        The extracted code section (for VM execution).
    cycles : int
        Number of VM execution cycles consumed.
    halted : bool
        Whether the VM halted normally.
    registers : dict[int, int] | None
        Register state after execution (R0–R15).
    errors : list[str]
        Any errors encountered during compilation/execution.
    """

    source: str = ""
    module: Optional[FIRModule] = None
    optimized_module: Optional[FIRModule] = None
    bytecode: Optional[bytes] = None
    code_section: Optional[bytes] = None
    cycles: int = 0
    halted: bool = False
    registers: Optional[dict[int, int]] = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if the pipeline completed without errors."""
        return len(self.errors) == 0


class FluxPipeline:
    """End-to-end compilation pipeline.

    Chains: FLUX.MD Parser → FIR Builder → Optimizer Passes →
           Bytecode Encoder → VM Execution.

    Parameters
    ----------
    optimize : bool
        Whether to run optimization passes on the FIR.
    execute : bool
        Whether to execute the bytecode on the VM after compilation.
    max_cycles : int
        VM execution cycle budget.
    memory_size : int
        Bytes for each VM memory region.
    """

    def __init__(
        self,
        optimize: bool = True,
        execute: bool = True,
        max_cycles: int = 10_000_000,
        memory_size: int = 65536,
    ) -> None:
        self.optimize = optimize
        self.execute = execute
        self.max_cycles = max_cycles
        self.memory_size = memory_size

    def run(self, source: str, lang: str = "md", module_name: str = "flux_module") -> PipelineResult:
        """Run the full pipeline on the given source.

        Parameters
        ----------
        source : str
            Source code (FLUX.MD, C, or Python).
        lang : str
            Source language: "md", "c", or "python".
        module_name : str
            Name for the FIR module.

        Returns
        -------
        PipelineResult with all intermediate and final results.
        """
        result = PipelineResult(source=source)

        try:
            # Step 1: Parse → FIR
            if lang == "md":
                result.module = self._compile_md(source, module_name)
            elif lang == "c":
                result.module = self._compile_c(source, module_name)
            elif lang in ("python", "py"):
                result.module = self._compile_python(source, module_name)
            else:
                result.errors.append(f"Unsupported language: {lang}")
                return result

            # Step 2: Optimize FIR
            if self.optimize and result.module is not None:
                result.optimized_module = self._optimize(result.module)
            else:
                result.optimized_module = result.module

            # Step 3: Encode to bytecode
            if result.optimized_module is not None:
                result.bytecode = self._encode(result.optimized_module)
                result.code_section = self._extract_code(result.bytecode)

            # Step 4: Execute on VM
            if self.execute and result.code_section is not None:
                self._execute_vm(result)

        except Exception as e:
            result.errors.append(f"{type(e).__name__}: {e}")

        return result

    # ── Compilation Steps ──────────────────────────────────────────────

    def _compile_c(self, source: str, module_name: str) -> FIRModule:
        """Compile C source to FIR."""
        from flux.frontend.c_frontend import CFrontendCompiler
        compiler = CFrontendCompiler()
        return compiler.compile(source, module_name=module_name)

    def _compile_python(self, source: str, module_name: str) -> FIRModule:
        """Compile Python source to FIR."""
        from flux.frontend.python_frontend import PythonFrontendCompiler
        compiler = PythonFrontendCompiler()
        return compiler.compile(source, module_name=module_name)

    def _compile_md(self, source: str, module_name: str) -> FIRModule:
        """Parse FLUX.MD and compile embedded code blocks to FIR."""
        from flux.parser import FluxMDParser
        from flux.parser.nodes import NativeBlock

        parser = FluxMDParser()
        doc = parser.parse(source)

        code_blocks: list[tuple[str, str]] = []
        for child in doc.children:
            if isinstance(child, NativeBlock):
                lang = (child.lang or "").lower().strip()
                if lang in ("c", "python"):
                    code_blocks.append((lang, child.content))

        if not code_blocks:
            # Build empty module
            ctx = TypeContext()
            from flux.fir.builder import FIRBuilder
            builder = FIRBuilder(ctx)
            return builder.new_module(module_name)

        # Compile first code block
        lang, content = code_blocks[0]
        if lang == "c":
            return self._compile_c(content, module_name)
        elif lang == "python":
            return self._compile_python(content, module_name)

        ctx = TypeContext()
        from flux.fir.builder import FIRBuilder
        builder = FIRBuilder(ctx)
        return builder.new_module(module_name)

    def _optimize(self, module: FIRModule) -> FIRModule:
        """Run optimization passes on the FIR module."""
        from flux.optimizer.pipeline import OptimizationPipeline
        pipeline = OptimizationPipeline()
        pipeline.run(module)
        return module

    def _encode(self, module: FIRModule) -> bytes:
        """Encode FIR module to FLUX bytecode."""
        from flux.bytecode.encoder import BytecodeEncoder
        encoder = BytecodeEncoder()
        return encoder.encode(module)

    @staticmethod
    def _extract_code(bytecode: bytes) -> bytes:
        """Extract the code section from compiled FLUX bytecode.

        Header layout (18 bytes):
          offset 0:  magic    (4 bytes, b'FLUX')
          offset 4:  version  (uint16 LE)
          offset 6:  flags    (uint16 LE)
          offset 8:  n_funcs  (uint16 LE)
          offset 10: type_off (uint32 LE)
          offset 14: code_off (uint32 LE)
        """
        code_off = struct.unpack_from("<I", bytecode, 14)[0]
        return bytecode[code_off:]

    def _execute_vm(self, result: PipelineResult) -> None:
        """Execute the code section on the VM and populate the result."""
        from flux.vm.interpreter import Interpreter

        interp = Interpreter(
            result.code_section,
            memory_size=self.memory_size,
            max_cycles=self.max_cycles,
        )
        result.cycles = interp.execute()
        result.halted = interp.halted

        # Capture register state
        result.registers = {}
        for i in range(16):
            result.registers[i] = interp.regs.read_gp(i)

    # ── Convenience methods ────────────────────────────────────────────

    def compile_only(self, source: str, lang: str = "md", module_name: str = "flux_module") -> PipelineResult:
        """Compile source to bytecode without executing."""
        saved = self.execute
        self.execute = False
        try:
            return self.run(source, lang, module_name)
        finally:
            self.execute = saved

    def compile_and_execute(
        self,
        source: str,
        lang: str = "md",
        module_name: str = "flux_module",
    ) -> PipelineResult:
        """Compile source and execute on VM."""
        saved_opt, saved_exec = self.optimize, self.execute
        self.optimize = True
        self.execute = True
        try:
            return self.run(source, lang, module_name)
        finally:
            self.optimize = saved_opt
            self.execute = saved_exec
