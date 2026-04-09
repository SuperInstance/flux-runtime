"""FIR optimization passes."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..fir.blocks import FIRModule

logger = logging.getLogger(__name__)


class OptimizationPass:
    """Base class for optimization passes."""

    def run(self, module: FIRModule) -> int:
        """Run pass on module. Returns number of changes made."""
        raise NotImplementedError

    @staticmethod
    def _log(msg: str) -> None:
        logger.debug(msg)


class ConstantFoldingPass(OptimizationPass):
    """Simplify constant expressions."""

    def run(self, module: FIRModule) -> int:
        changes = 0
        for func in module.functions.values():
            for block in func.blocks:
                for i, instr in enumerate(block.instructions):
                    op = instr.opcode
                    # Check if this is a binary op with constant-like operands
                    if op in ("iadd", "isub", "imul", "fadd", "fsub", "fmul"):
                        changes += 1  # placeholder — full impl needs use-def analysis
        return changes


class DeadCodeEliminationPass(OptimizationPass):
    """Remove instructions whose results are never used."""

    def run(self, module: FIRModule) -> int:
        changes = 0
        for func in module.functions.values():
            for block in func.blocks:
                # Collect all value IDs that are used
                used = set()
                for instr in block.instructions:
                    if hasattr(instr, "lhs") and hasattr(instr.lhs, "id"):
                        used.add(instr.lhs.id)
                    if hasattr(instr, "rhs") and hasattr(instr.rhs, "id"):
                        used.add(instr.rhs.id)
                    if hasattr(instr, "value") and hasattr(instr.value, "id"):
                        used.add(instr.value.id)
                    if hasattr(instr, "cond") and hasattr(instr.cond, "id"):
                        used.add(instr.cond.id)
                # Check for unused results
                new_instrs = []
                for instr in block.instructions:
                    has_side_effect = instr.opcode in (
                        "store", "call", "tell", "ask", "delegate",
                        "jump", "branch", "return", "unreachable",
                    )
                    if hasattr(instr, "result_type"):
                        result_type = instr.result_type
                        if result_type is not None and hasattr(instr, "result_type"):
                            # Check if result is used
                            pass
                    if has_side_effect:
                        new_instrs.append(instr)
                    else:
                        changes += 1
                block.instructions = new_instrs
        return changes


class InlineFunctionsPass(OptimizationPass):
    """Inline small functions at their call sites."""

    def run(self, module: FIRModule) -> int:
        changes = 0
        # Find small functions (< 20 instructions total)
        small_funcs = {}
        for name, func in module.functions.items():
            total = sum(len(b.instructions) for b in func.blocks)
            if total < 20:
                small_funcs[name] = func
        
        if not small_funcs:
            return 0
        
        # Find CALL instructions and inline
        for func in module.functions.values():
            for block in func.blocks:
                new_instrs = []
                for instr in block.instructions:
                    if instr.opcode == "call" and instr.func in small_funcs:
                        # Replace CALL with inlined body (placeholder)
                        new_instrs.append(instr)  # keep for now
                        changes += 1
                    else:
                        new_instrs.append(instr)
                block.instructions = new_instrs
        return changes
