"""Pipeline debug utilities — tracing, FIR printing, bytecode disassembly.

Provides:
  - PipelineDebugger: step-by-step pipeline execution with tracing
  - disassemble_bytecode: human-readable bytecode dump
  - print_fir_module: delegate to FIR printer with context
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

from flux.fir.blocks import FIRModule
from flux.fir.printer import print_fir as _print_fir


# ── Bytecode Disassembler ────────────────────────────────────────────────────


def disassemble_bytecode(bytecode: bytes, start: int = 0) -> str:
    """Disassemble FLUX bytecode into human-readable text.

    Parameters
    ----------
    bytecode : bytes
        Full FLUX bytecode (with header) or raw code section.
    start : int
        Starting offset for disassembly.

    Returns
    -------
    Human-readable disassembly string.
    """
    from flux.bytecode.opcodes import Op, get_format

    # Detect header and skip to code section
    offset = start
    if len(bytecode) >= 18 and bytecode[:4] == b"FLUX":
        # Parse header
        magic, version, flags, n_funcs, type_off, code_off = struct.unpack_from(
            "<4sHHHII", bytecode, 0
        )
        lines = [
            f"FLUX Bytecode v{version}",
            f"  flags: {flags:#06x}",
            f"  functions: {n_funcs}",
            f"  type_table_offset: {type_off}",
            f"  code_section_offset: {code_off}",
            "",
        ]

        # Decode function table
        func_table_off = code_off - n_funcs * 12
        name_pool_off = type_off
        # Compute name pool end by scanning type table
        if type_off + 2 <= len(bytecode):
            n_types = struct.unpack_from("<H", bytecode, type_off)[0]
            pos = type_off + 2
            for _ in range(n_types):
                pos = _skip_type(bytecode, pos)
            name_pool_off = pos

        for i in range(n_funcs):
            ft_off = func_table_off + i * 12
            if ft_off + 12 > len(bytecode):
                break
            name_off, entry_off, code_size = struct.unpack_from(
                "<III", bytecode, ft_off
            )
            # Read function name
            fname = _read_null_string(bytecode, name_pool_off + name_off)
            lines.append(f"  function '{fname}' @ offset {entry_off}, {code_size} bytes")

        lines.append("")
        lines.append(f"Code Section (offset {code_off}):")
        lines.append("-" * 40)
        offset = code_off
    else:
        lines = ["Raw Bytecode Disassembly:", "-" * 40]

    # Disassemble instructions
    end = len(bytecode)
    while offset < end:
        raw_op = bytecode[offset]
        try:
            op = Op(raw_op)
        except ValueError:
            lines.append(f"  {offset:04x}:  .byte 0x{raw_op:02x}  ; unknown")
            offset += 1
            continue

        fmt = get_format(op)
        op_name = op.name

        if fmt == "A":
            lines.append(f"  {offset:04x}:  {op_name}")
            offset += 1
        elif fmt == "B":
            if offset + 2 <= end:
                rd = bytecode[offset + 1]
                lines.append(f"  {offset:04x}:  {op_name} r{rd}")
                offset += 2
            else:
                lines.append(f"  {offset:04x}:  {op_name} <truncated>")
                offset += 1
        elif fmt == "C":
            if offset + 3 <= end:
                rd = bytecode[offset + 1]
                rs1 = bytecode[offset + 2]
                lines.append(f"  {offset:04x}:  {op_name} r{rd}, r{rs1}")
                offset += 3
            else:
                lines.append(f"  {offset:04x}:  {op_name} <truncated>")
                offset += 1
        elif fmt == "D":
            if offset + 4 <= end:
                rs1 = bytecode[offset + 1]
                imm = struct.unpack_from("<h", bytecode, offset + 2)[0]
                lines.append(f"  {offset:04x}:  {op_name} r{rs1}, {imm}")
                offset += 4
            else:
                lines.append(f"  {offset:04x}:  {op_name} <truncated>")
                offset += 1
        elif fmt == "E":
            if offset + 4 <= end:
                rd = bytecode[offset + 1]
                rs1 = bytecode[offset + 2]
                rs2 = bytecode[offset + 3]
                lines.append(f"  {offset:04x}:  {op_name} r{rd}, r{rs1}, r{rs2}")
                offset += 4
            else:
                lines.append(f"  {offset:04x}:  {op_name} <truncated>")
                offset += 1
        elif fmt == "G":
            if offset + 3 <= end:
                data_len = struct.unpack_from("<H", bytecode, offset + 1)[0]
                if offset + 3 + data_len <= end:
                    payload = bytecode[offset + 3: offset + 3 + data_len]
                    hex_data = " ".join(f"{b:02x}" for b in payload[:16])
                    suffix = "..." if len(payload) > 16 else ""
                    lines.append(
                        f"  {offset:04x}:  {op_name} [{data_len}] {hex_data}{suffix}"
                    )
                    offset += 3 + data_len
                else:
                    lines.append(f"  {offset:04x}:  {op_name} [{data_len}] <truncated>")
                    offset += 3
            else:
                lines.append(f"  {offset:04x}:  {op_name} <truncated>")
                offset += 1
        else:
            lines.append(f"  {offset:04x}:  {op_name}")
            offset += 1

    return "\n".join(lines)


def _skip_type(data: bytes, pos: int) -> int:
    """Skip past one type entry in the type table."""
    if pos >= len(data):
        return pos
    kind = data[pos]
    pos += 1
    skip_map = {
        0x01: 2,   # INT
        0x02: 1,   # FLOAT
        0x06: 2,   # REF
        0x07: 6,   # ARRAY
        0x08: 3,   # VECTOR
    }
    if kind in skip_map:
        return pos + skip_map[kind]
    if kind in (0x03, 0x04, 0x05, 0x0E, 0x0F):
        return pos
    if kind == 0x09:  # FUNC
        if pos + 4 > len(data):
            return pos
        n_p, n_r = struct.unpack_from("<HH", data, pos)
        return pos + 4 + (n_p + n_r) * 2
    # Fallback: skip nothing
    return pos


def _read_null_string(data: bytes, offset: int) -> str:
    """Read a null-terminated string."""
    end = data.index(0x00, offset) if 0x00 in data[offset:] else len(data)
    return data[offset:end].decode("utf-8", errors="replace")


# ── FIR Pretty Printer ───────────────────────────────────────────────────────


def print_fir_module(module: FIRModule) -> str:
    """Pretty-print a FIR module with optional statistics.

    Parameters
    ----------
    module : FIRModule
        The FIR module to print.

    Returns
    -------
    Human-readable FIR dump with module statistics.
    """
    lines = []

    # Statistics
    total_functions = len(module.functions)
    total_blocks = sum(len(f.blocks) for f in module.functions.values())
    total_instructions = sum(
        len(b.instructions)
        for f in module.functions.values()
        for b in f.blocks
    )
    total_types = len(module.type_ctx._types)
    total_structs = len(module.structs)

    lines.append(f"Module '{module.name}'")
    lines.append(f"  Functions: {total_functions}")
    lines.append(f"  Basic blocks: {total_blocks}")
    lines.append(f"  Instructions: {total_instructions}")
    lines.append(f"  Types (interned): {total_types}")
    lines.append(f"  Structs: {total_structs}")
    lines.append("")

    # FIR dump
    lines.append(_print_fir(module))

    return "\n".join(lines)


# ── Pipeline Debugger ────────────────────────────────────────────────────────


@dataclass
class DebugStep:
    """A single step in the pipeline execution trace."""

    step_name: str
    duration_us: float = 0.0
    success: bool = True
    detail: str = ""
    error: Optional[str] = None


class PipelineDebugger:
    """Step-by-step pipeline execution with tracing.

    Wraps FluxPipeline and records detailed information at each step,
    enabling post-mortem debugging of the compilation pipeline.

    Parameters
    ----------
    trace : bool
        Whether to collect step-by-step traces.
    """

    def __init__(self, trace: bool = True) -> None:
        self.trace = trace
        self.steps: list[DebugStep] = []
        self._fir_before_opt: Optional[str] = None
        self._fir_after_opt: Optional[str] = None
        self._bytecode_hex: str = ""
        self._disassembly: str = ""
        self._vm_state: Optional[dict] = None

    def run_pipeline(
        self,
        source: str,
        lang: str = "md",
        module_name: str = "flux_module",
        optimize: bool = True,
        execute: bool = True,
    ) -> dict:
        """Run the pipeline with full debug tracing.

        Parameters
        ----------
        source : str
            Source code.
        lang : str
            Source language ("md", "c", "python").
        module_name : str
            Module name.
        optimize : bool
            Whether to optimize.
        execute : bool
            Whether to execute on VM.

        Returns
        -------
        Dictionary with all debug information.
        """
        import time
        from flux.pipeline.e2e import FluxPipeline, PipelineResult

        self.steps.clear()
        self._fir_before_opt = None
        self._fir_after_opt = None
        self._bytecode_hex = ""
        self._disassembly = ""
        self._vm_state = None

        pipeline = FluxPipeline(
            optimize=False,
            execute=False,
        )
        result = PipelineResult(source=source)

        # Step 1: Parse + FIR build
        t0 = time.perf_counter()
        try:
            if lang == "md":
                result.module = pipeline._compile_md(source, module_name)
            elif lang == "c":
                result.module = pipeline._compile_c(source, module_name)
            elif lang in ("python", "py"):
                result.module = pipeline._compile_python(source, module_name)
            else:
                result.errors.append(f"Unsupported language: {lang}")
                return self._build_report(result)

            self._fir_before_opt = print_fir_module(result.module)
            self._record_step("parse_and_build_fir", t0, True,
                              f"{len(result.module.functions)} functions")
        except Exception as e:
            self._record_step("parse_and_build_fir", t0, False, error=str(e))
            result.errors.append(str(e))
            return self._build_report(result)

        # Step 2: Optimize
        if optimize and result.module is not None:
            t0 = time.perf_counter()
            try:
                from flux.optimizer.pipeline import OptimizationPipeline
                opt = OptimizationPipeline()
                changes = opt.run(result.module)
                result.optimized_module = result.module
                self._fir_after_opt = print_fir_module(result.optimized_module)
                self._record_step("optimize", t0, True, f"{changes} changes")
            except Exception as e:
                self._record_step("optimize", t0, False, error=str(e))
                result.optimized_module = result.module

        # Step 3: Encode
        t0 = time.perf_counter()
        try:
            result.bytecode = pipeline._encode(result.optimized_module or result.module)
            result.code_section = pipeline._extract_code(result.bytecode)
            self._bytecode_hex = result.bytecode.hex()
            self._disassembly = disassemble_bytecode(result.bytecode)
            self._record_step("encode", t0, True,
                              f"{len(result.bytecode)} bytes bytecode, "
                              f"{len(result.code_section)} bytes code section")
        except Exception as e:
            self._record_step("encode", t0, False, error=str(e))
            result.errors.append(str(e))
            return self._build_report(result)

        # Step 4: VM Execute
        if execute and result.code_section is not None:
            t0 = time.perf_counter()
            try:
                pipeline._execute_vm(result)
                self._vm_state = {
                    "cycles": result.cycles,
                    "halted": result.halted,
                    "registers": result.registers,
                }
                self._record_step("execute", t0, True,
                                  f"{result.cycles} cycles, halted={result.halted}")
            except Exception as e:
                self._record_step("execute", t0, False, error=str(e))
                result.errors.append(str(e))

        return self._build_report(result)

    def _record_step(
        self,
        name: str,
        start: float,
        success: bool,
        detail: str = "",
        error: Optional[str] = None,
    ) -> None:
        import time
        elapsed = (time.perf_counter() - start) * 1_000_000  # microseconds
        step = DebugStep(
            step_name=name,
            duration_us=elapsed,
            success=success,
            detail=detail,
            error=error,
        )
        if self.trace:
            self.steps.append(step)

    def _build_report(self, result) -> dict:
        """Build a comprehensive debug report."""
        return {
            "success": result.success,
            "errors": result.errors,
            "steps": [
                {
                    "name": s.step_name,
                    "duration_us": f"{s.duration_us:.1f}",
                    "success": s.success,
                    "detail": s.detail,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "fir_before_optimization": self._fir_before_opt,
            "fir_after_optimization": self._fir_after_opt,
            "bytecode_size": len(result.bytecode) if result.bytecode else 0,
            "code_section_size": len(result.code_section) if result.code_section else 0,
            "bytecode_hex": self._bytecode_hex[:256] + ("..." if len(self._bytecode_hex) > 256 else ""),
            "disassembly": self._disassembly,
            "vm_state": self._vm_state,
            "functions": list(result.module.functions.keys()) if result.module else [],
        }

    def summary(self, report: Optional[dict] = None) -> str:
        """Generate a human-readable summary of a debug report.

        Parameters
        ----------
        report : dict | None
            Debug report from run_pipeline(). If None, uses the last report.

        Returns
        -------
        Human-readable summary string.
        """
        if report is None and self.steps:
            return self.summary(self._build_report(
                type("R", (), {"success": True, "errors": [], "module": None})()
            ))
        if report is None:
            return "No pipeline execution recorded."

        lines = [
            "=" * 60,
            "FLUX Pipeline Debug Report",
            "=" * 60,
            f"Overall: {'SUCCESS' if report['success'] else 'FAILED'}",
        ]

        for step in report["steps"]:
            status = "OK" if step["success"] else "FAIL"
            duration = step["duration_us"]
            detail = f" — {step['detail']}" if step["detail"] else ""
            error = f" — ERROR: {step['error']}" if step["error"] else ""
            lines.append(f"  [{status}] {step['name']} ({duration} μs){detail}{error}")

        if report["errors"]:
            lines.append("")
            lines.append("Errors:")
            for err in report["errors"]:
                lines.append(f"  • {err}")

        if report["bytecode_size"]:
            lines.append("")
            lines.append(f"Bytecode: {report['bytecode_size']} bytes")
            lines.append(f"Code section: {report['code_section_size']} bytes")
            lines.append(f"Functions: {', '.join(report['functions'])}")

        if report["vm_state"]:
            lines.append("")
            vm = report["vm_state"]
            lines.append(f"VM: {vm['cycles']} cycles, halted={vm['halted']}")
            if vm["registers"]:
                reg_lines = [f"  R{i} = {v}" for i, v in vm["registers"].items()]
                lines.extend(reg_lines)

        lines.append("=" * 60)
        return "\n".join(lines)
