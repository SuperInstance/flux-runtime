"""FIR Builder — convenience API for constructing FIR with SSA invariants."""

from __future__ import annotations
from typing import Optional

from .types import FIRType, TypeContext, BoolType, UnitType
from .values import Value
from .instructions import (
    IAdd, ISub, IMul, IDiv, IMod, INeg,
    FAdd, FSub, FMul, FDiv, FNeg,
    IAnd, IOr, IXor, IShl, IShr, INot,
    IEq, INe, ILt, IGt, ILe, IGe,
    FEq, FLt, FGt, FLe, FGe,
    ITrunc, ZExt, SExt, FTrunc, FExt, Bitcast,
    Load, Store, Alloca, GetField, SetField, GetElem, SetElem, MemCopy, MemSet,
    Jump, Branch, Switch, Call, Return, Unreachable,
    Tell, Ask, Delegate, TrustCheck, CapRequire,
    Instruction,
)
from .blocks import FIRModule, FIRFunction, FIRBlock


class FIRBuilder:
    """Convenience builder for constructing FIR with SSA invariants enforced."""

    def __init__(self, type_ctx: TypeContext):
        self._ctx = type_ctx
        self._next_value_id: int = 0
        self._current_block: Optional[FIRBlock] = None

    # ── Module / Function / Block creation ──────────────────────────────

    def new_module(self, name: str) -> FIRModule:
        return FIRModule(name=name, type_ctx=self._ctx)

    def new_function(
        self,
        module: FIRModule,
        name: str,
        params: list[tuple[str, FIRType]],
        returns: list[FIRType],
    ) -> FIRFunction:
        sig = self._ctx.get_func(tuple(t for _, t in params), tuple(returns))
        func = FIRFunction(name=name, sig=sig)
        module.functions[name] = func
        return func

    def new_block(
        self,
        func: FIRFunction,
        label: str,
        params: list[tuple[str, FIRType]] | None = None,
    ) -> FIRBlock:
        blk = FIRBlock(label=label, params=params or [])
        func.blocks.append(blk)
        return blk

    def set_block(self, block: FIRBlock) -> None:
        """Set the current block for emission."""
        self._current_block = block

    # ── Value helpers ───────────────────────────────────────────────────

    def _new_value(self, name: str, type: FIRType) -> Value:
        v = Value(id=self._next_value_id, name=name, type=type)
        self._next_value_id += 1
        return v

    def _emit(self, instr: Instruction) -> Value | None:
        """Append an instruction to the current block. Returns a Value if it produces one."""
        if self._current_block is None:
            raise RuntimeError("No current block set. Call set_block() first.")
        self._current_block.instructions.append(instr)
        rt = instr.result_type
        if rt is not None:
            return self._new_value(f"_v{self._next_value_id}", rt)
        return None

    # ── Integer arithmetic ──────────────────────────────────────────────

    def iadd(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IAdd(lhs, rhs))

    def isub(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(ISub(lhs, rhs))

    def imul(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IMul(lhs, rhs))

    def idiv(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IDiv(lhs, rhs))

    def imod(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IMod(lhs, rhs))

    def ineg(self, lhs: Value) -> Value:
        return self._emit(INeg(lhs))

    # ── Float arithmetic ────────────────────────────────────────────────

    def fadd(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FAdd(lhs, rhs))

    def fsub(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FSub(lhs, rhs))

    def fmul(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FMul(lhs, rhs))

    def fdiv(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FDiv(lhs, rhs))

    def fneg(self, lhs: Value) -> Value:
        return self._emit(FNeg(lhs))

    # ── Bitwise ─────────────────────────────────────────────────────────

    def iand(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IAnd(lhs, rhs))

    def ior(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IOr(lhs, rhs))

    def ixor(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IXor(lhs, rhs))

    def ishl(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IShl(lhs, rhs))

    def ishr(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IShr(lhs, rhs))

    def inot(self, lhs: Value) -> Value:
        return self._emit(INot(lhs))

    # ── Comparison ──────────────────────────────────────────────────────

    def ieq(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IEq(lhs, rhs))

    def ine(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(INe(lhs, rhs))

    def ilt(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(ILt(lhs, rhs))

    def igt(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IGt(lhs, rhs))

    def ile(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(ILe(lhs, rhs))

    def ige(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(IGe(lhs, rhs))

    def feq(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FEq(lhs, rhs))

    def flt(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FLt(lhs, rhs))

    def fgt(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FGt(lhs, rhs))

    def fle(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FLe(lhs, rhs))

    def fge(self, lhs: Value, rhs: Value) -> Value:
        return self._emit(FGe(lhs, rhs))

    # ── Conversion ──────────────────────────────────────────────────────

    def itrunc(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(ITrunc(value, target_type))

    def zext(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(ZExt(value, target_type))

    def sext(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(SExt(value, target_type))

    def ftrunc(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(FTrunc(value, target_type))

    def fext(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(FExt(value, target_type))

    def bitcast(self, value: Value, target_type: FIRType) -> Value:
        return self._emit(Bitcast(value, target_type))

    # ── Memory ──────────────────────────────────────────────────────────

    def load(self, type: FIRType, ptr: Value, offset: int = 0) -> Value:
        return self._emit(Load(type, ptr, offset))

    def store(self, value: Value, ptr: Value, offset: int = 0) -> None:
        self._emit(Store(value, ptr, offset))

    def alloca(self, type: FIRType, count: int = 1) -> Value:
        return self._emit(Alloca(type, count))

    def getfield(self, struct_val: Value, field_name: str, field_index: int, field_type: FIRType) -> Value:
        return self._emit(GetField(struct_val, field_name, field_index, field_type))

    def setfield(self, struct_val: Value, field_name: str, field_index: int, value: Value) -> None:
        self._emit(SetField(struct_val, field_name, field_index, value))

    def getelem(self, array_val: Value, index: Value, elem_type: FIRType) -> Value:
        return self._emit(GetElem(array_val, index, elem_type))

    def setelem(self, array_val: Value, index: Value, value: Value) -> None:
        self._emit(SetElem(array_val, index, value))

    def memcpy(self, src: Value, dst: Value, size: int) -> None:
        self._emit(MemCopy(src, dst, size))

    def memset(self, dst: Value, value: int, size: int) -> None:
        self._emit(MemSet(dst, value, size))

    # ── Control flow ────────────────────────────────────────────────────

    def jump(self, block: str, args: list[Value] | None = None) -> None:
        self._emit(Jump(block, args or []))

    def branch(self, cond: Value, true_block: str, false_block: str, args: list[Value] | None = None) -> None:
        self._emit(Branch(cond, true_block, false_block, args or []))

    def switch(self, value: Value, cases: dict[int, str], default_block: str) -> None:
        self._emit(Switch(value, cases, default_block))

    def call(self, func: str, args: list[Value], return_type: FIRType | None = None) -> Value | None:
        return self._emit(Call(func, args, return_type))

    def ret(self, value: Value | None = None) -> None:
        self._emit(Return(value))

    def unreachable(self) -> None:
        self._emit(Unreachable())

    # ── A2A primitives ──────────────────────────────────────────────────

    def tell(self, target_agent: str, message: Value, cap: Value) -> None:
        self._emit(Tell(target_agent, message, cap))

    def ask(self, target_agent: str, message: Value, return_type: FIRType, cap: Value) -> Value:
        return self._emit(Ask(target_agent, message, return_type, cap))

    def delegate(self, target_agent: str, authority: Value, cap: Value) -> None:
        self._emit(Delegate(target_agent, authority, cap))

    def trustcheck(self, agent: str, threshold: Value, cap: Value) -> Value:
        return self._emit(TrustCheck(agent, threshold, cap))

    def caprequire(self, capability: str, resource: str, cap: Value) -> None:
        self._emit(CapRequire(capability, resource, cap))
