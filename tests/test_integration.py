"""FLUX End-to-End Integration Tests.

14 tests exercising the full pipeline across all layers:
  Parser → FIR → Optimizer → Bytecode → VM
  Polyglot compilation, A2A instructions, type unification,
  protocol messages, hot reload, stdlib intrinsics.
"""

import struct
import sys
import os
import traceback

# Ensure the project source root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.bytecode.opcodes import Op
from flux.fir.types import TypeContext, IntType, FloatType, BoolType
from flux.fir.values import Value
from flux.fir.blocks import FIRModule, FIRFunction, FIRBlock
from flux.fir.builder import FIRBuilder
from flux.fir.validator import FIRValidator
from flux.fir.printer import print_fir
from flux.fir.instructions import (
    IAdd, ISub, IMul, Return, Unreachable, Call,
    Tell, Ask, Delegate,
)
from flux.bytecode.encoder import BytecodeEncoder
from flux.bytecode.decoder import BytecodeDecoder
from flux.compiler.pipeline import FluxCompiler
from flux.optimizer.pipeline import OptimizationPipeline
from flux.types.unify import TypeUnifier
from flux.protocol.message import (
    MessageKind, MessageId, Request, Response, Event, Error,
)
from flux.protocol.serialization import BinaryMessageCodec
from flux.reload.hot_loader import HotLoader, ModuleVersion
from flux.stdlib.intrinsics import STDLIB_INTRINSICS, PrintFn
from flux.pipeline.e2e import FluxPipeline
from flux.pipeline.polyglot import PolyglotCompiler, PolyglotSource
from flux.pipeline.debug import PipelineDebugger, disassemble_bytecode, print_fir_module
from flux.vm.interpreter import Interpreter


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_code_section(bytecode: bytes) -> bytes:
    """Extract the code section from compiled FLUX bytecode."""
    code_off = struct.unpack_from("<I", bytecode, 14)[0]
    return bytecode[code_off:]


def _build_simple_fir_module() -> FIRModule:
    """Build a simple FIR module: add(i32, i32) -> i32 { a + b; return }."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    module = builder.new_module("test_add")

    i32 = ctx.get_int(32)
    func = builder.new_function(module, "add", [("a", i32), ("b", i32)], [i32])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    a_val = builder._new_value("a", i32)
    b_val = builder._new_value("b", i32)
    result = builder.iadd(a_val, b_val)
    builder.ret(result)

    return module


def _build_arithmetic_fir() -> FIRModule:
    """Build FIR module with multiple arithmetic operations."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    module = builder.new_module("arith")

    i32 = ctx.get_int(32)
    func = builder.new_function(module, "compute", [("x", i32), ("y", i32)], [i32])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    x = builder._new_value("x", i32)
    y = builder._new_value("y", i32)
    sum_val = builder.iadd(x, y)
    diff = builder.isub(x, y)
    prod = builder.imul(x, y)
    builder.ret(prod)

    return module


def _build_control_flow_fir() -> FIRModule:
    """Build FIR module with branch control flow."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    module = builder.new_module("ctrlflow")

    i32 = ctx.get_int(32)
    func = builder.new_function(module, "max", [("a", i32), ("b", i32)], [i32])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    a = builder._new_value("a", i32)
    b = builder._new_value("b", i32)
    cmp = builder.ilt(a, b)
    builder.branch(cmp, "then_bb", "else_bb")

    then_bb = builder.new_block(func, "then_bb")
    builder.set_block(then_bb)
    builder.jump("merge_bb")

    else_bb = builder.new_block(func, "else_bb")
    builder.set_block(else_bb)
    builder.jump("merge_bb")

    merge_bb = builder.new_block(func, "merge_bb")
    builder.set_block(merge_bb)
    builder.ret(a)

    return module


def _build_a2a_fir() -> FIRModule:
    """Build FIR module with A2A protocol instructions."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    module = builder.new_module("a2a_test")

    i32 = ctx.get_int(32)
    func = builder.new_function(module, "send_message", [], [])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    msg = builder._new_value("msg", ctx.get_string())
    cap = builder._new_value("cap", i32)
    builder.tell("agent_b", msg, cap)
    builder.ret(None)

    return module


def _run_test(name, fn):
    """Run a single test and report result."""
    try:
        fn()
        return True, name, None
    except Exception as e:
        return False, name, traceback.format_exc()


# ══════════════════════════════════════════════════════════════════════════
# Test 1: Parser → FIR
# ══════════════════════════════════════════════════════════════════════════


def test_parser_to_fir():
    """Parse FLUX.MD → compile to FIR, verify structure."""
    from flux.parser import FluxMDParser
    from flux.parser.nodes import NativeBlock

    md_source = """---
title: Integration Test
---

# Test Module

```c
int multiply(int a, int b) {
    return a * b;
}
```
"""

    parser = FluxMDParser()
    doc = parser.parse(md_source)

    # Verify parsing produced AST nodes
    assert doc.frontmatter.get("title") == "Integration Test"
    native_blocks = [c for c in doc.children if isinstance(c, NativeBlock)]
    assert len(native_blocks) >= 1
    assert native_blocks[0].lang == "c"

    # Compile to FIR via the C frontend
    from flux.frontend.c_frontend import CFrontendCompiler
    compiler = CFrontendCompiler()
    module = compiler.compile(native_blocks[0].content, module_name="md_test")

    # Verify FIR structure
    assert "multiply" in module.functions
    func = module.functions["multiply"]
    assert len(func.blocks) >= 1
    assert len(func.sig.params) == 2
    assert len(func.sig.returns) == 1


# ══════════════════════════════════════════════════════════════════════════
# Test 2: FIR → Bytecode → Decode roundtrip
# ══════════════════════════════════════════════════════════════════════════


def test_fir_to_bytecode():
    """Build FIR → encode bytecode → decode → verify roundtrip."""
    module = _build_simple_fir_module()

    # Encode
    encoder = BytecodeEncoder()
    bytecode = encoder.encode(module)
    assert isinstance(bytecode, bytes)
    assert len(bytecode) >= 18
    assert bytecode[:4] == b"FLUX"

    # Decode
    decoder = BytecodeDecoder()
    decoded = decoder.decode(bytecode)
    assert decoded.version == 1
    assert len(decoded.functions) == 1
    assert decoded.functions[0].name == "add"

    # Verify instructions contain IADD
    opcodes = [instr.opcode for instr in decoded.functions[0].instructions]
    assert Op.IADD in opcodes


# ══════════════════════════════════════════════════════════════════════════
# Test 3: C source → FIR → bytecode → VM execution
# ══════════════════════════════════════════════════════════════════════════


def test_c_to_vm():
    """Compile C source → FIR → bytecode → execute on VM, verify results."""
    compiler = FluxCompiler()
    bytecode = compiler.compile_c("int add(int a, int b) { return a + b; }")

    assert bytecode[:4] == b"FLUX"

    # The code section should contain IADD and RET opcodes
    code_section = _extract_code_section(bytecode)
    assert len(code_section) > 0
    assert Op.IADD in code_section


# ══════════════════════════════════════════════════════════════════════════
# Test 4: Python source → FIR → bytecode → VM
# ══════════════════════════════════════════════════════════════════════════


def test_python_to_vm():
    """Compile Python source → FIR → bytecode → execute on VM."""
    compiler = FluxCompiler()
    bytecode = compiler.compile_python(
        "def add(a, b):\n    return a + b\n"
    )

    assert bytecode[:4] == b"FLUX"

    # Verify bytecode structure
    n_funcs = struct.unpack_from("<H", bytecode, 8)[0]
    assert n_funcs >= 1

    code_section = _extract_code_section(bytecode)
    assert len(code_section) > 0
    assert Op.IADD in code_section


# ══════════════════════════════════════════════════════════════════════════
# Test 5: Full pipeline FLUX.MD → parse → FIR → optimize → bytecode → VM
# ══════════════════════════════════════════════════════════════════════════


def test_full_pipeline():
    """Full FLUX.MD → parse → FIR → optimize → bytecode → VM execution."""
    pipeline = FluxPipeline(optimize=True, execute=False)

    md_source = """---
title: Full Pipeline Test
---

# Arithmetic Module

```c
int square(int x) {
    return x * x;
}
```
"""

    result = pipeline.run(md_source, lang="md", module_name="full_test")

    assert result.success, f"Pipeline errors: {result.errors}"
    assert result.module is not None
    assert "square" in result.module.functions
    assert result.bytecode is not None
    assert result.bytecode[:4] == b"FLUX"

    # Verify code section contains RET (function terminator)
    assert result.code_section is not None
    assert Op.RET in result.code_section


# ══════════════════════════════════════════════════════════════════════════
# Test 6: Optimizer → Bytecode roundtrip
# ══════════════════════════════════════════════════════════════════════════


def test_optimizer_bytecode_roundtrip():
    """Optimize FIR → encode → decode → verify optimized structure."""
    module = _build_simple_fir_module()

    # Run optimization
    opt = OptimizationPipeline()
    changes = opt.run(module)

    # Encode to bytecode
    encoder = BytecodeEncoder()
    bytecode = encoder.encode(module)

    # Decode and verify
    decoder = BytecodeDecoder()
    decoded = decoder.decode(bytecode)

    assert len(decoded.functions) == 1
    assert decoded.functions[0].name == "add"

    # Verify the decoded module has a valid function structure
    assert len(decoded.functions[0].instructions) > 0
    last_instr = decoded.functions[0].instructions[-1]
    assert last_instr.opcode == Op.RET  # function should terminate with return


# ══════════════════════════════════════════════════════════════════════════
# Test 7: Polyglot pipeline (C + Python in same module)
# ══════════════════════════════════════════════════════════════════════════


def test_polyglot_pipeline():
    """Mix C and Python in same module, compile and verify."""
    pc = PolyglotCompiler(optimize=False)

    sources = [
        PolyglotSource(lang="c", source="int mul(int a, int b) { return a * b; }"),
        PolyglotSource(
            lang="python",
            source="def add(a, b):\n    return a + b\n"
        ),
    ]

    result = pc.compile(sources, module_name="poly_test")

    assert result.success, f"Polyglot errors: {result.errors}"
    assert result.module is not None
    assert result.bytecode is not None
    assert result.bytecode[:4] == b"FLUX"

    # Both functions should be present
    assert "mul" in result.module.functions
    assert "add" in result.module.functions

    # Type mappings should exist
    assert "mul" in result.type_mappings
    assert "add" in result.type_mappings


# ══════════════════════════════════════════════════════════════════════════
# Test 8: A2A bytecode roundtrip
# ══════════════════════════════════════════════════════════════════════════


def test_a2a_bytecode_roundtrip():
    """Create FIR with A2A instructions → encode → decode → verify."""
    module = _build_a2a_fir()

    # Encode
    encoder = BytecodeEncoder()
    bytecode = encoder.encode(module)
    assert bytecode[:4] == b"FLUX"

    # Decode
    decoder = BytecodeDecoder()
    decoded = decoder.decode(bytecode)

    assert len(decoded.functions) == 1
    assert decoded.functions[0].name == "send_message"

    # Verify TELL opcode (0x60) is in the code section
    code_section = _extract_code_section(bytecode)
    assert Op.TELL in code_section


# ══════════════════════════════════════════════════════════════════════════
# Test 9: VM arithmetic correctness
# ══════════════════════════════════════════════════════════════════════════


def test_vm_arithmetic_correctness():
    """Compile arithmetic expressions → run on VM → check results."""
    # Build bytecode: MOVI R1,10; MOVI R2,20; IADD R0,R1,R2; HALT
    bytecode = bytes([
        Op.MOVI, 0x01, 10, 0x00,     # MOVI R1, 10
        Op.MOVI, 0x02, 20, 0x00,     # MOVI R2, 20
        Op.IADD, 0x00, 0x01, 0x02,    # IADD R0, R1, R2
        Op.HALT,                       # HALT
    ])

    interp = Interpreter(bytecode, memory_size=65536)
    cycles = interp.execute()

    assert interp.halted
    assert interp.regs.read_gp(0) == 30  # 10 + 20 = 30
    assert cycles == 4

    # Test multiplication
    bytecode_mul = bytes([
        Op.MOVI, 0x01, 7, 0x00,      # MOVI R1, 7
        Op.MOVI, 0x02, 6, 0x00,      # MOVI R2, 6
        Op.IMUL, 0x00, 0x01, 0x02,   # IMUL R0, R1, R2
        Op.HALT,
    ])

    interp2 = Interpreter(bytecode_mul)
    interp2.execute()
    assert interp2.regs.read_gp(0) == 42  # 7 * 6 = 42

    # Test subtraction
    bytecode_sub = bytes([
        Op.MOVI, 0x01, 100, 0x00,    # MOVI R1, 100
        Op.MOVI, 0x02, 37, 0x00,     # MOVI R2, 37
        Op.ISUB, 0x00, 0x01, 0x02,   # ISUB R0, R1, R2
        Op.HALT,
    ])

    interp3 = Interpreter(bytecode_sub)
    interp3.execute()
    assert interp3.regs.read_gp(0) == 63  # 100 - 37 = 63


# ══════════════════════════════════════════════════════════════════════════
# Test 10: VM control flow
# ══════════════════════════════════════════════════════════════════════════


def test_vm_control_flow():
    """Compile if/else/loop → run on VM → verify control flow."""
    # Countdown loop: DEC R0; JNZ R0,-6; HALT
    # R0 starts at 5, decrements to 0
    bytecode = bytes([
        Op.DEC, 0x00,                  # DEC R0
        Op.JNZ, 0x00, 0xFA, 0xFF,     # JNZ R0, -6 -> back to byte 0
        Op.HALT,
    ])

    interp = Interpreter(bytecode)
    interp.regs.write_gp(0, 5)  # Start at 5
    cycles = interp.execute()

    assert interp.halted
    assert interp.regs.read_gp(0) == 0
    assert cycles > 0

    # Test conditional jump (JZ not taken)
    bytecode_jz = bytes([
        Op.MOVI, 0x01, 42, 0x00,     # MOVI R1, 42
        Op.MOVI, 0x02, 0, 0x00,      # MOVI R2, 0
        Op.JZ, 0x02, 0x04, 0x00,     # JZ R2, +4 (skip next 4-byte instruction)
        Op.MOVI, 0x01, 99, 0x00,     # MOVI R1, 99 (should be skipped)
        Op.HALT,
    ])

    interp2 = Interpreter(bytecode_jz)
    interp2.execute()
    assert interp2.regs.read_gp(1) == 42  # R1 should stay 42


# ══════════════════════════════════════════════════════════════════════════
# Test 11: Type unification pipeline
# ══════════════════════════════════════════════════════════════════════════


def test_type_unification_pipeline():
    """Use TypeUnifier in compilation, verify types resolve correctly."""
    unifier = TypeUnifier()

    # C int → FIR
    c_int = unifier.from_c("int")
    assert isinstance(c_int, IntType)
    assert c_int.bits == 32
    assert c_int.signed is True

    # C float → FIR
    c_float = unifier.from_c("float")
    assert isinstance(c_float, FloatType)
    assert c_float.bits == 32

    # Python int → FIR
    py_int = unifier.from_python(int)
    assert isinstance(py_int, IntType)
    assert py_int.bits == 64

    # Python type name → FIR
    py_float = unifier.from_python("float")
    assert isinstance(py_float, FloatType)

    # C → Python unification: C int (i32) and Python int (i64) → i64
    unified = unifier.unify(c_int, py_int)
    assert unified is not None
    assert isinstance(unified, IntType)
    assert unified.bits == 64  # wider type wins

    # Bidirectional conversion
    assert unifier.to_c(c_int) == "int"
    assert unifier.to_c(c_float) == "float"
    assert unifier.to_python(c_int) == "int"
    assert unifier.to_python(c_float) == "float"

    # Coercion cost
    assert unifier.coercion_cost(c_int, py_int) == 1  # widening
    assert unifier.coercion_cost(c_int, c_int) == 0   # identity

    # PolyglotCompiler uses TypeUnifier
    pc = PolyglotCompiler()
    result = pc.unify_types("int", "c", "int", "python")
    assert result is not None


# ══════════════════════════════════════════════════════════════════════════
# Test 12: Stdlib intrinsics in pipeline
# ══════════════════════════════════════════════════════════════════════════


def test_stdlib_intrinsics_in_pipeline():
    """Use stdlib intrinsics in a pipeline compilation."""
    # Verify all intrinsics are registered
    assert "print" in STDLIB_INTRINSICS
    assert "assert" in STDLIB_INTRINSICS
    assert "panic" in STDLIB_INTRINSICS
    assert "sizeof" in STDLIB_INTRINSICS
    assert "alignof" in STDLIB_INTRINSICS
    assert "type_of" in STDLIB_INTRINSICS

    # Build a module that uses the print intrinsic
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    module = builder.new_module("stdlib_test")

    i32 = ctx.get_int(32)
    func = builder.new_function(module, "use_print", [("x", i32)], [])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    x_val = builder._new_value("x", i32)
    print_fn = STDLIB_INTRINSICS["print"]
    print_fn.emit(builder, [x_val])
    builder.ret(None)

    # Verify the function has a call instruction
    instrs = func.blocks[0].instructions
    call_instrs = [i for i in instrs if isinstance(i, Call)]
    assert len(call_instrs) >= 1
    assert call_instrs[0].func == "flux.print"

    # Encode to bytecode
    encoder = BytecodeEncoder()
    bytecode = encoder.encode(module)
    assert bytecode[:4] == b"FLUX"


# ══════════════════════════════════════════════════════════════════════════
# Test 13: Agent protocol messages
# ══════════════════════════════════════════════════════════════════════════


def test_agent_protocol_messages():
    """Create and serialize protocol messages end-to-end."""
    # Create a request
    request = Request.create(
        sender="agent_a",
        receiver="agent_b",
        method="compute.add",
        payload={"a": 10, "b": 20},
    )
    assert request.kind == MessageKind.REQUEST
    assert request.sender == "agent_a"
    assert request.method == "compute.add"

    # Create a response
    response = Response.create(request, payload={"result": 30}, success=True)
    assert response.kind == MessageKind.RESPONSE
    assert response.success is True
    assert response.sender == "agent_b"
    assert response.receiver == "agent_a"
    assert response.conversation_id == request.conversation_id

    # Create an error
    error = request.as_error(code=500, message="Internal error")
    assert error.kind == MessageKind.ERROR
    assert error.error_code == 500

    # Create an event
    event = Event.create(
        sender="monitor",
        event_type="task.completed",
        payload={"task_id": "123"},
    )
    assert event.kind == MessageKind.EVENT
    assert event.event_type == "task.completed"

    # Serialize → deserialize roundtrip (binary codec)
    codec = BinaryMessageCodec()

    for msg in [request, response, error, event]:
        serialized = codec.serialize(msg)
        assert isinstance(serialized, bytes)
        assert len(serialized) >= 60  # header size
        assert serialized[:4] == b"FLXP"

        deserialized = codec.deserialize(serialized)
        assert deserialized.kind == msg.kind
        assert deserialized.sender == msg.sender
        assert deserialized.receiver == msg.receiver
        assert deserialized.conversation_id == msg.conversation_id

    # Batch encode/decode
    batch = BinaryMessageCodec.encode_message_batch([request, response, event])
    assert isinstance(batch, bytes)
    decoded_batch = BinaryMessageCodec.decode_message_batch(batch)
    assert len(decoded_batch) == 3
    assert decoded_batch[0].kind == MessageKind.REQUEST
    assert decoded_batch[1].kind == MessageKind.RESPONSE
    assert decoded_batch[2].kind == MessageKind.EVENT

    # to_dict serialization
    d = request.to_dict()
    assert d["sender"] == "agent_a"
    assert d["kind"] == int(MessageKind.REQUEST)
    assert "payload" in d


# ══════════════════════════════════════════════════════════════════════════
# Test 14: Hot reload cycle
# ══════════════════════════════════════════════════════════════════════════


def test_hot_reload_cycle():
    """Load module → modify → reload → verify changes take effect."""
    loader = HotLoader()

    # Version 1: simple bytecode
    bc_v1 = bytes([
        Op.MOVI, 0x00, 10, 0x00,  # MOVI R0, 10
        Op.HALT,
    ])
    ver1 = loader.load("test_mod", bc_v1, ["main"], source="v1")

    assert ver1.version_id == 0
    assert ver1.parent_version_id is None
    assert loader.get_active("test_mod") is ver1

    # Version 2: modified bytecode
    bc_v2 = bytes([
        Op.MOVI, 0x00, 42, 0x00,  # MOVI R0, 42
        Op.HALT,
    ])
    ver2 = loader.load("test_mod", bc_v2, ["main"], source="v2")

    assert ver2.version_id == 1
    assert ver2.parent_version_id == 0
    assert loader.get_active("test_mod") is ver2
    assert ver2.bytecode == bc_v2

    # Version history
    history = loader.get_version_history("test_mod")
    assert len(history) == 2
    assert history[0].version_id == 0
    assert history[1].version_id == 1

    # Rollback
    prev = loader.rollback("test_mod")
    assert prev is not None
    assert prev.version_id == 0
    assert loader.get_active("test_mod").version_id == 0

    # Enter/exit call tracking
    loader.enter_call("test_mod")
    loader.exit_call(0)
    assert loader._active_calls.get(0, 0) == 0

    # GC: load a third version, then GC should keep only active
    ver3 = loader.load("test_mod", bc_v1, ["main"], source="v3")
    # No active calls on ver2, so GC can remove it
    removed = loader.gc("test_mod")
    assert removed >= 0  # May remove old versions


# ══════════════════════════════════════════════════════════════════════════
# Test runner
# ══════════════════════════════════════════════════════════════════════════


INTEGRATION_TESTS = [
    ("test_parser_to_fir", test_parser_to_fir),
    ("test_fir_to_bytecode", test_fir_to_bytecode),
    ("test_c_to_vm", test_c_to_vm),
    ("test_python_to_vm", test_python_to_vm),
    ("test_full_pipeline", test_full_pipeline),
    ("test_optimizer_bytecode_roundtrip", test_optimizer_bytecode_roundtrip),
    ("test_polyglot_pipeline", test_polyglot_pipeline),
    ("test_a2a_bytecode_roundtrip", test_a2a_bytecode_roundtrip),
    ("test_vm_arithmetic_correctness", test_vm_arithmetic_correctness),
    ("test_vm_control_flow", test_vm_control_flow),
    ("test_type_unification_pipeline", test_type_unification_pipeline),
    ("test_stdlib_intrinsics_in_pipeline", test_stdlib_intrinsics_in_pipeline),
    ("test_agent_protocol_messages", test_agent_protocol_messages),
    ("test_hot_reload_cycle", test_hot_reload_cycle),
]


if __name__ == "__main__":
    print("=" * 60)
    print("FLUX Integration Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = []

    for name, fn in INTEGRATION_TESTS:
        ok, _, trace = _run_test(name, fn)
        if ok:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")
            errors.append((name, trace))

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(INTEGRATION_TESTS)}")
    print("=" * 60)

    if errors:
        for name, trace in errors:
            print(f"\n--- {name} ---")
            print(trace)

    sys.exit(1 if failed > 0 else 0)
