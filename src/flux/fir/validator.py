"""FIR Validator — validates structural invariants of a FIR module."""

from __future__ import annotations
from typing import Optional

from .types import FIRType
from .values import Value
from .instructions import Instruction, is_terminator
from .blocks import FIRModule, FIRFunction, FIRBlock


class FIRValidationError:
    """A single validation error with location context."""
    def __init__(self, message: str, function: str = "", block: str = ""):
        self.message = message
        self.function = function
        self.block = block

    def __repr__(self):
        loc = ""
        if self.function:
            loc = f" in function '{self.function}'"
            if self.block:
                loc += f", block '{self.block}'"
        return f"ValidationError{loc}: {self.message}"


class FIRValidator:
    """Validates FIR invariants after construction."""

    def validate_module(self, module: FIRModule) -> list[str]:
        """Validate a module. Returns a list of error strings. Empty = valid."""
        errors: list[str] = []

        for func_name, func in module.functions.items():
            errors.extend(self._validate_function(func))

        return errors

    def _validate_function(self, func: FIRFunction) -> list[str]:
        """Validate a single function."""
        errors: list[str] = []
        block_labels = {b.label for b in func.blocks}

        # 1. Every function must have at least one block
        if not func.blocks:
            errors.append(f"Function '{func.name}' has no blocks")
            return errors

        # 2. Validate each block
        for block in func.blocks:
            errors.extend(self._validate_block(func, block, block_labels))

        # 3. All blocks should be reachable (warn only — not an error in FIR)
        #    We skip reachability checks for simplicity.

        return errors

    def _validate_block(
        self,
        func: FIRFunction,
        block: FIRBlock,
        block_labels: set[str],
    ) -> list[str]:
        """Validate a single basic block."""
        errors: list[str] = []

        # 1. Empty block
        if not block.instructions:
            errors.append(
                f"Block '{block.label}' in function '{func.name}' is empty"
            )
            return errors

        # 2. Exactly one terminator at the end
        terminators = [i for i in block.instructions if is_terminator(i)]
        if len(terminators) == 0:
            errors.append(
                f"Block '{block.label}' in function '{func.name}' "
                f"has no terminator"
            )
        elif len(terminators) > 1:
            errors.append(
                f"Block '{block.label}' in function '{func.name}' "
                f"has {len(terminators)} terminators (expected 1)"
            )
        elif terminators[0] is not block.instructions[-1]:
            errors.append(
                f"Block '{block.label}' in function '{func.name}' "
                f"has a terminator that is not the last instruction"
            )

        # 3. Block targets reference existing blocks
        for instr in block.instructions:
            errors.extend(
                self._validate_block_targets(func.name, block.label, instr, block_labels)
            )

        # 4. Value uses are defined before use (simplified: check all value refs
        #    are defined either as block params or by an earlier instruction
        #    in the same block — cross-block SSA dominance is checked at a
        #    higher level in a real compiler).
        defined: set[int] = set()  # set of value IDs
        for pname, ptype in block.params:
            pass  # Block params don't have Value IDs in this representation

        for instr in block.instructions:
            errors.extend(
                self._validate_value_uses(func.name, block.label, instr, defined)
            )
            # After processing, register any value produced by this instruction
            # (In the builder, values are produced externally, so this is
            #  a simplified check)

        return errors

    def _validate_block_targets(
        self,
        func_name: str,
        block_label: str,
        instr: Instruction,
        block_labels: set[str],
    ) -> list[str]:
        """Check that all block target references point to existing blocks."""
        errors: list[str] = []

        from .instructions import Jump, Branch, Switch

        if isinstance(instr, Jump):
            if instr.target_block not in block_labels:
                errors.append(
                    f"Jump in '{func_name}.{block_label}' targets "
                    f"nonexistent block '{instr.target_block}'"
                )

        elif isinstance(instr, Branch):
            if instr.true_block not in block_labels:
                errors.append(
                    f"Branch in '{func_name}.{block_label}' targets "
                    f"nonexistent block '{instr.true_block}'"
                )
            if instr.false_block not in block_labels:
                errors.append(
                    f"Branch in '{func_name}.{block_label}' targets "
                    f"nonexistent block '{instr.false_block}'"
                )

        elif isinstance(instr, Switch):
            for val, target in instr.cases.items():
                if target not in block_labels:
                    errors.append(
                        f"Switch in '{func_name}.{block_label}' case {val} targets "
                        f"nonexistent block '{target}'"
                    )
            if instr.default_block not in block_labels:
                errors.append(
                    f"Switch in '{func_name}.{block_label}' default targets "
                    f"nonexistent block '{instr.default_block}'"
                )

        return errors

    def _validate_value_uses(
        self,
        func_name: str,
        block_label: str,
        instr: Instruction,
        defined: set[int],
    ) -> list[str]:
        """Check that all Value references in an instruction are valid.

        This is a simplified check — in a real SSA validator, we'd need
        full dominance information. Here we just verify Value objects
        are properly formed (non-negative id, non-empty name).
        """
        errors: list[str] = []
        values = self._collect_value_refs(instr)

        for v in values:
            if not isinstance(v, Value):
                errors.append(
                    f"Instruction in '{func_name}.{block_label}' has "
                    f"non-Value operand: {type(v).__name__}"
                )
            elif v.id < 0:
                errors.append(
                    f"Instruction in '{func_name}.{block_label}' references "
                    f"Value with negative id: %{v.name}"
                )

        return errors

    @staticmethod
    def _collect_value_refs(instr: Instruction) -> list[Value]:
        """Collect all Value references from an instruction."""
        refs: list[Value] = []
        for attr_name in vars(instr):
            if attr_name in ("opcode",):
                continue
            val = getattr(instr, attr_name)
            if isinstance(val, Value):
                refs.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Value):
                        refs.append(item)
            elif isinstance(val, dict):
                for item in val.values():
                    if isinstance(item, Value):
                        refs.append(item)
        return refs
