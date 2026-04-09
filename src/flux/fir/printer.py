"""FIR Printer — human-readable text representation of FIR modules."""

from __future__ import annotations
from typing import Optional

from .types import (
    FIRType, IntType, FloatType, BoolType, UnitType, StringType,
    RefType, ArrayType, VectorType, FuncType, StructType, EnumType,
    RegionType, CapabilityType, AgentType, TrustType,
)
from .values import Value
from .instructions import (
    Instruction,
    IAdd, ISub, IMul, IDiv, IMod, INeg,
    FAdd, FSub, FMul, FDiv, FNeg,
    IAnd, IOr, IXor, IShl, IShr, INot,
    IEq, INe, ILt, IGt, ILe, IGe,
    FEq, FLt, FGt, FLe, FGe,
    ITrunc, ZExt, SExt, FTrunc, FExt, Bitcast,
    Load, Store, Alloca, GetField, SetField, GetElem, SetElem, MemCopy, MemSet,
    Jump, Branch, Switch, Call, Return, Unreachable,
    Tell, Ask, Delegate, TrustCheck, CapRequire,
)
from .blocks import FIRModule, FIRFunction, FIRBlock


# ── Type rendering ──────────────────────────────────────────────────────────

def _type_str(t: FIRType) -> str:
    """Render a FIRType to a short human-readable string."""
    if isinstance(t, IntType):
        prefix = "i" if t.signed else "u"
        return f"{prefix}{t.bits}"
    if isinstance(t, FloatType):
        return f"f{t.bits}"
    if isinstance(t, BoolType):
        return "bool"
    if isinstance(t, UnitType):
        return "unit"
    if isinstance(t, StringType):
        return "string"
    if isinstance(t, RefType):
        return f"&{_type_str(t.element)}"
    if isinstance(t, ArrayType):
        return f"[{_type_str(t.element)}; {t.length}]"
    if isinstance(t, VectorType):
        return f"<{t.lanes} x {_type_str(t.element)}>"
    if isinstance(t, FuncType):
        params = ", ".join(_type_str(p) for p in t.params)
        rets = ", ".join(_type_str(r) for r in t.returns)
        return f"({params}) -> ({rets})"
    if isinstance(t, StructType):
        fields = ", ".join(f"{n}: {_type_str(ft)}" for n, ft in t.fields)
        return f"struct {{ {fields} }}"
    if isinstance(t, EnumType):
        variants = ", ".join(
            f"{n}" if ft is None else f"{n}({_type_str(ft)})"
            for n, ft in t.variants
        )
        return f"enum {{ {variants} }}"
    if isinstance(t, RegionType):
        return f"region<{t.name}>"
    if isinstance(t, CapabilityType):
        return f"cap({t.permission}, {t.resource})"
    if isinstance(t, AgentType):
        return "agent"
    if isinstance(t, TrustType):
        return "trust"
    return f"?<{t.type_id}>"


# ── Value rendering ─────────────────────────────────────────────────────────

def _val_str(v: Value) -> str:
    """Render a Value reference as %name."""
    return f"%{v.name}"


# ── Instruction rendering ───────────────────────────────────────────────────

def _instr_str(instr: Instruction, val_counter: list[int]) -> str:
    """Render a single instruction to a string.

    val_counter is a mutable [int] used to assign names to result values.
    Returns the rendered string.
    """
    op = instr.opcode

    # ── Binary ops (arithmetic, bitwise, comparison) ─────────────────
    binary_ops = {
        "iadd", "isub", "imul", "idiv", "imod",
        "fadd", "fsub", "fmul", "fdiv",
        "iand", "ior", "ixor", "ishl", "ishr",
        "ieq", "ine", "ilt", "igt", "ile", "ige",
        "feq", "flt", "fgt", "fle", "fge",
    }
    if op in binary_ops:
        lhs = _val_str(instr.lhs)
        rhs = _val_str(instr.rhs)
        return f"    {lhs} = {op} {lhs}, {rhs}"

    # ── Unary ops ────────────────────────────────────────────────────
    unary_ops = {"ineg", "fneg", "inot"}
    if op in unary_ops:
        v = _val_str(instr.lhs)
        return f"    {v} = {op} {v}"

    # ── Conversion ops ───────────────────────────────────────────────
    conv_ops = {"itrunc", "zext", "sext", "ftrunc", "fext", "bitcast"}
    if op in conv_ops:
        v = _val_str(instr.value)
        return f"    {v} = {op} {v} to {_type_str(instr.target_type)}"

    # ── Memory ops ───────────────────────────────────────────────────
    if op == "load":
        ptr = _val_str(instr.ptr)
        off = f" + {instr.offset}" if instr.offset else ""
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        return f"    {vname} = load {_type_str(instr.type)}, {ptr}{off}"

    if op == "store":
        val = _val_str(instr.value)
        ptr = _val_str(instr.ptr)
        off = f" + {instr.offset}" if instr.offset else ""
        return f"    store {val}, {ptr}{off}"

    if op == "alloca":
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        count = f", {instr.count}" if instr.count > 1 else ""
        return f"    {vname} = alloca {_type_str(instr.type)}{count}"

    if op == "getfield":
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        sv = _val_str(instr.struct_val)
        return f'    {vname} = {op} {sv}, "{instr.field_name}"'

    if op == "setfield":
        sv = _val_str(instr.struct_val)
        val = _val_str(instr.value)
        return f'    {op} {sv}, "{instr.field_name}", {val}'

    if op == "getelem":
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        av = _val_str(instr.array_val)
        idx = _val_str(instr.index)
        return f"    {vname} = {op} {av}, {idx}"

    if op == "setelem":
        av = _val_str(instr.array_val)
        idx = _val_str(instr.index)
        val = _val_str(instr.value)
        return f"    {op} {av}, {idx}, {val}"

    if op == "memcpy":
        src = _val_str(instr.src)
        dst = _val_str(instr.dst)
        return f"    {op} {dst}, {src}, {instr.size}"

    if op == "memset":
        dst = _val_str(instr.dst)
        return f"    {op} {dst}, {instr.value}, {instr.size}"

    # ── Control flow ─────────────────────────────────────────────────
    if op == "jump":
        args = ", ".join(_val_str(a) for a in instr.args)
        if args:
            return f"    jump {instr.target_block}({args})"
        return f"    jump {instr.target_block}"

    if op == "branch":
        cond = _val_str(instr.cond)
        args = ", ".join(_val_str(a) for a in instr.args)
        arg_suffix = f"({args})" if args else ""
        return (
            f"    branch {cond}, {instr.true_block}{arg_suffix}, "
            f"{instr.false_block}{arg_suffix}"
        )

    if op == "switch":
        v = _val_str(instr.value)
        cases = ", ".join(f"{k}: {t}" for k, t in instr.cases.items())
        return f"    switch {v}, [{cases}], default: {instr.default_block}"

    if op == "call":
        args = ", ".join(_val_str(a) for a in instr.args)
        ret = _type_str(instr.return_type) if instr.return_type else "void"
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        if instr.return_type:
            return f"    {vname} = call @{instr.func}({args}) : {ret}"
        return f"    call @{instr.func}({args}) : {ret}"

    if op == "return":
        if instr.value is not None:
            return f"    return {_val_str(instr.value)}"
        return "    return"

    if op == "unreachable":
        return "    unreachable"

    # ── A2A primitives ───────────────────────────────────────────────
    if op == "tell":
        msg = _val_str(instr.message)
        cap = _val_str(instr.cap)
        return f'    {op} @{instr.target_agent}, {msg}, {cap}'

    if op == "ask":
        msg = _val_str(instr.message)
        cap = _val_str(instr.cap)
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        ret = _type_str(instr.return_type)
        return f'    {vname} = {op} @{instr.target_agent}, {msg}, {cap} : {ret}'

    if op == "delegate":
        auth = _val_str(instr.authority)
        cap = _val_str(instr.cap)
        return f'    {op} @{instr.target_agent}, {auth}, {cap}'

    if op == "trustcheck":
        thresh = _val_str(instr.threshold)
        cap = _val_str(instr.cap)
        vname = f"%_v{val_counter[0]}"
        val_counter[0] += 1
        return f'    {vname} = {op} @{instr.agent}, {thresh}, {cap}'

    if op == "caprequire":
        cap = _val_str(instr.cap)
        return f'    {op} "{instr.capability}", "{instr.resource}", {cap}'

    return f"    <unknown op: {op}>"


# ── Module rendering ────────────────────────────────────────────────────────

def print_fir(module: FIRModule) -> str:
    """Render a FIRModule to a human-readable string."""
    lines: list[str] = []
    lines.append(f'module "{module.name}"')

    # Structs
    for sname, stype in module.structs.items():
        fields = ", ".join(f"{n}: {_type_str(ft)}" for n, ft in stype.fields)
        lines.append(f"  type {sname} = struct {{ {fields} }}")

    # Functions
    for fname, func in module.functions.items():
        params = ", ".join(_type_str(t) for t in func.sig.params)
        rets = ", ".join(_type_str(r) for r in func.sig.returns)
        ret_str = f" -> {rets}" if rets else ""
        lines.append(f"")
        lines.append(f"  function {fname}({params}){ret_str} {{")

        for block in func.blocks:
            blk_params = ""
            if block.params:
                blk_params = "(" + ", ".join(
                    f"%{n}:{_type_str(t)}" for n, t in block.params
                ) + ")"
            lines.append(f"  {block.label}{blk_params}:")

            val_counter = [0]
            for instr in block.instructions:
                lines.append(_instr_str(instr, val_counter))

        lines.append("  }")

    lines.append("")
    return "\n".join(lines)
