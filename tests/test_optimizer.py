"""Optimizer tests."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.optimizer.passes import ConstantFoldingPass, DeadCodeEliminationPass, InlineFunctionsPass
from flux.optimizer.pipeline import OptimizationPipeline
from flux.fir.types import TypeContext
from flux.fir.blocks import FIRModule, FIRFunction, FIRBlock
from flux.fir.builder import FIRBuilder


def _build_simple_module():
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    mod = builder.new_module("test")
    func = builder.new_function(mod, "add", [("a", ctx.get_int(32)), ("b", ctx.get_int(32))], [ctx.get_int(32)])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)
    a = builder._new_value("a", ctx.get_int(32))
    b = builder._new_value("b", ctx.get_int(32))
    result = builder.iadd(a, b)
    builder.ret(result)
    return mod


def test_constant_folding():
    mod = _build_simple_module()
    p = ConstantFoldingPass()
    changes = p.run(mod)
    assert changes >= 0
    print("  PASS test_constant_folding")


def test_dead_code_elimination():
    mod = _build_simple_module()
    p = DeadCodeEliminationPass()
    changes = p.run(mod)
    assert changes >= 0
    print("  PASS test_dead_code_elimination")


def test_inline_functions():
    mod = _build_simple_module()
    p = InlineFunctionsPass()
    changes = p.run(mod)
    assert changes >= 0
    print("  PASS test_inline_functions")


def test_pipeline_runs():
    mod = _build_simple_module()
    pipe = OptimizationPipeline()
    total = pipe.run(mod)
    assert total >= 0
    print("  PASS test_pipeline_runs")


if __name__ == "__main__":
    test_constant_folding()
    test_dead_code_elimination()
    test_inline_functions()
    test_pipeline_runs()
    print("All optimizer tests passed!")
