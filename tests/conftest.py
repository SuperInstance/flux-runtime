"""Shared pytest fixtures for the FLUX test suite.

Provides reusable construction blocks for the core subsystems:
TypeContext, FIRBuilder, FIRModule, bytecode, VM Interpreter,
and FluxSynthesizer. Imports are performed inside each fixture
to avoid import-time side effects and keep test collection fast.
"""

from __future__ import annotations

import struct

import pytest


@pytest.fixture()
def type_ctx():
    """Provide a fresh FIR TypeContext with canonical i32 and f32 shorthands."""
    from flux.fir.types import TypeContext

    ctx = TypeContext()
    return ctx


@pytest.fixture()
def fir_builder(type_ctx):
    """Provide a FIRBuilder wired to the shared TypeContext."""
    from flux.fir.builder import FIRBuilder

    return FIRBuilder(type_ctx)


@pytest.fixture()
def sample_module(fir_builder):
    """Provide a simple FIRModule containing one function with a single block.

    The module contains:
      - Module name: "test_module"
      - Function "main" with signature () -> i32
      - One entry block "entry"
      - One instruction: Return of a constant
    """
    from flux.fir.blocks import FIRBlock

    module = fir_builder.new_module("test_module")

    i32 = fir_builder._ctx.get_int(32, signed=True)
    func = fir_builder.new_function(module, "main", params=[], returns=[i32])

    block = fir_builder.new_block(func, "entry")
    fir_builder.set_block(block)

    # Build a trivial return: load constant via MOVI equivalent, then return
    one = fir_builder._new_value("const_1", i32)
    fir_builder.ret(one)

    return module


@pytest.fixture()
def simple_bytecode():
    """Provide valid bytecode bytes: MOVI R1, 42 followed by HALT.

    Encoding:
        MOVI  R1, 42  ->  [0x2B][0x01][0x2A][0x00]
        HALT          ->  [0x80]

    Format D for MOVI: [opcode][reg:u8][imm_lo:u8][imm_hi:u8]
    """
    return bytes([
        0x2B,                   # Op.MOVI
        0x01,                   # R1
        0x2A, 0x00,             # 42 as little-endian i16
        0x80,                   # Op.HALT
    ])


@pytest.fixture()
def vm(simple_bytecode):
    """Provide an Interpreter instance loaded with the simple_bytecode fixture.

    The VM is created but not yet executed. Use vm.execute() to run it
    and assert register state afterwards.
    """
    from flux.vm.interpreter import Interpreter

    interpreter = Interpreter(simple_bytecode)
    return interpreter


@pytest.fixture()
def synthesizer():
    """Provide a FluxSynthesizer instance for integration-level tests.

    The synthesizer is initialized with a default name "test_synth" and
    has access to all subsystems (modules, profiler, evolution, tiles).
    """
    from flux.synthesis.synthesizer import FluxSynthesizer

    return FluxSynthesizer("test_synth")
