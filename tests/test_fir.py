"""FIR Core Tests — comprehensive tests for the FLUX Intermediate Representation."""

import sys
import traceback

sys.path.insert(0, "src")

from flux.fir.types import (
    TypeContext, IntType, FloatType, BoolType, UnitType, StringType,
    RefType, ArrayType, VectorType, FuncType, StructType, EnumType,
    RegionType, CapabilityType, AgentType, TrustType,
)
from flux.fir.values import Value
from flux.fir.instructions import (
    IAdd, FAdd, Call, Return, Jump, Branch,
    Tell, Ask, Store, GetField, is_terminator,
    Alloca,
)
from flux.fir.blocks import FIRModule, FIRFunction, FIRBlock
from flux.fir.builder import FIRBuilder
from flux.fir.validator import FIRValidator
from flux.fir.printer import print_fir


passed = 0
failed = 0


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}")
        traceback.print_exc()


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────

def test_type_context_interning():
    """Same type params return the same (identity-equal) object."""
    ctx = TypeContext()
    a = ctx.get_int(32, signed=True)
    b = ctx.get_int(32, signed=True)
    assert a is b, "IntType(32, signed=True) should be interned"

    c = ctx.get_int(32, signed=False)
    assert a is not c, "Signed vs unsigned should differ"

    d = ctx.get_float(64)
    e = ctx.get_float(64)
    assert d is e, "FloatType(64) should be interned"

    f = ctx.get_ref(a)
    g = ctx.get_ref(a)
    assert f is g, "RefType should be interned"

    # Different element types → different ref
    h = ctx.get_ref(c)
    assert f is not h, "RefType with different elements should differ"


def test_type_context_types():
    """All type constructors work and produce correct types."""
    ctx = TypeContext()

    # Primitives
    assert isinstance(ctx.get_int(64, False), IntType)
    assert isinstance(ctx.get_float(32), FloatType)
    assert isinstance(ctx.get_bool(), BoolType)
    assert isinstance(ctx.get_unit(), UnitType)
    assert isinstance(ctx.get_string(), StringType)

    # Composites
    i32 = ctx.get_int(32)
    assert isinstance(ctx.get_ref(i32), RefType)
    assert isinstance(ctx.get_array(i32, 10), ArrayType)
    assert isinstance(ctx.get_vector(i32, 4), VectorType)
    assert isinstance(ctx.get_func((i32,), (i32,)), FuncType)

    # Struct
    s = ctx.get_struct("Vec3", (("x", i32), ("y", i32), ("z", i32)))
    assert isinstance(s, StructType)
    assert s.name == "Vec3"
    assert len(s.fields) == 3

    # Enum
    e = ctx.get_enum("Option", (("Some", i32), ("None", None)))
    assert isinstance(e, EnumType)
    assert e.name == "Option"
    assert len(e.variants) == 2

    # Domain-specific
    assert isinstance(ctx.get_region("heap"), RegionType)
    assert isinstance(ctx.get_capability("read", "file"), CapabilityType)
    assert isinstance(ctx.get_agent(), AgentType)
    assert isinstance(ctx.get_trust(), TrustType)

    # Class-level shorthands
    assert TypeContext.i32.bits == 32
    assert TypeContext.i32.signed is True
    assert TypeContext.f32.bits == 32


def test_builder_simple_function():
    """Build a simple add(a: i32, b: i32) -> i32 function."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    i32 = ctx.get_int(32)

    mod = builder.new_module("test")
    func = builder.new_function(mod, "add", [("a", i32), ("b", i32)], [i32])

    entry = builder.new_block(func, "entry", [("a", i32), ("b", i32)])
    builder.set_block(entry)

    # Create parameter values
    a_val = Value(id=0, name="a", type=i32)
    b_val = Value(id=1, name="b", type=i32)

    result = builder.iadd(a_val, b_val)
    assert result is not None
    assert result.type == i32

    builder.ret(result)

    # Verify structure
    assert len(func.blocks) == 1
    assert len(entry.instructions) == 2  # iadd + return
    assert isinstance(entry.instructions[0], IAdd)
    assert isinstance(entry.instructions[1], Return)

    # Verify module
    assert "add" in mod.functions


def test_builder_control_flow():
    """Build an if/else with branch and jump."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    i32 = ctx.get_int(32)
    bool_t = ctx.get_bool()

    mod = builder.new_module("test")
    func = builder.new_function(mod, "max", [("a", i32), ("b", i32)], [i32])

    a_val = Value(id=0, name="a", type=i32)
    b_val = Value(id=1, name="b", type=i32)
    cmp = Value(id=2, name="cmp", type=bool_t)

    entry = builder.new_block(func, "entry", [("a", i32), ("b", i32)])
    then_blk = builder.new_block(func, "then", [("a", i32)])
    else_blk = builder.new_block(func, "else", [("b", i32)])
    merge = builder.new_block(func, "merge", [("result", i32)])

    # entry: branch cmp, then, else
    builder.set_block(entry)
    builder.branch(cmp, "then", "else", [a_val, b_val])

    # then: jump merge(a)
    builder.set_block(then_blk)
    builder.jump("merge", [a_val])

    # else: jump merge(b)
    builder.set_block(else_blk)
    builder.jump("merge", [b_val])

    # merge: return result
    merge_result = Value(id=3, name="result", type=i32)
    builder.set_block(merge)
    builder.ret(merge_result)

    # Verify
    assert len(func.blocks) == 4
    assert isinstance(entry.terminator, Branch)
    assert isinstance(then_blk.terminator, Jump)
    assert isinstance(else_blk.terminator, Jump)
    assert isinstance(merge.terminator, Return)


def test_builder_call():
    """Build a function that calls another function."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    i32 = ctx.get_int(32)

    mod = builder.new_module("test")

    # Define the callee
    builder.new_function(mod, "add", [("a", i32), ("b", i32)], [i32])

    # Define the caller
    caller = builder.new_function(mod, "caller", [("x", i32)], [i32])
    entry = builder.new_block(caller, "entry", [("x", i32)])
    builder.set_block(entry)

    x_val = Value(id=0, name="x", type=i32)
    y_val = Value(id=1, name="y", type=i32)

    result = builder.call("add", [x_val, y_val], i32)
    assert result is not None

    builder.ret(result)

    instrs = entry.instructions
    assert len(instrs) == 2
    assert isinstance(instrs[0], Call)
    assert instrs[0].func == "add"
    assert len(instrs[0].args) == 2
    assert isinstance(instrs[1], Return)


def test_builder_a2a():
    """Build A2A Tell and Ask instructions."""
    ctx = TypeContext()
    builder = FIRBuilder(ctx)
    i32 = ctx.get_int(32)
    string_t = ctx.get_string()

    mod = builder.new_module("a2a_test")
    func = builder.new_function(mod, "communicate", [], [i32])
    entry = builder.new_block(func, "entry")
    builder.set_block(entry)

    msg = Value(id=0, name="msg", type=string_t)
    cap = Value(id=1, name="cap", type=i32)
    threshold = Value(id=2, name="thresh", type=i32)

    # Tell
    builder.tell("agent_b", msg, cap)

    # Ask
    response = builder.ask("agent_b", msg, i32, cap)
    assert response is not None
    assert response.type == i32

    # Trust check
    trust_result = builder.trustcheck("agent_b", threshold, cap)
    assert trust_result is not None

    builder.ret(response)

    instrs = entry.instructions
    assert len(instrs) == 4
    assert instrs[0].opcode == "tell"
    assert instrs[1].opcode == "ask"
    assert instrs[2].opcode == "trustcheck"
    assert instrs[3].opcode == "return"


def test_validator_empty_module():
    """An empty module (no functions) should validate cleanly."""
    ctx = TypeContext()
    mod = FIRModule(name="empty", type_ctx=ctx)
    validator = FIRValidator()
    errors = validator.validate_module(mod)
    assert errors == [], f"Empty module should be valid, got: {errors}"


def test_validator_missing_terminator():
    """A block without a terminator should fail validation."""
    ctx = TypeContext()
    i32 = ctx.get_int(32)

    mod = FIRModule(name="bad", type_ctx=ctx)
    func = FIRFunction(
        name="broken",
        sig=ctx.get_func((i32,), (i32,)),
        blocks=[],
    )
    mod.functions["broken"] = func

    # Block with instructions but no terminator
    block = FIRBlock(
        label="entry",
        params=[("x", i32)],
        instructions=[IAdd(
            lhs=Value(id=0, name="x", type=i32),
            rhs=Value(id=1, name="y", type=i32),
        )],
    )
    func.blocks.append(block)

    validator = FIRValidator()
    errors = validator.validate_module(mod)
    assert len(errors) > 0, "Should have errors for missing terminator"
    assert any("no terminator" in e.lower() for e in errors), \
        f"Expected 'no terminator' error, got: {errors}"


def test_struct_type():
    """Struct creation, interning, and field access type info."""
    ctx = TypeContext()
    f32 = ctx.get_float(32)
    i32 = ctx.get_int(32)

    vec4 = ctx.get_struct("Vec4", (
        ("x", f32),
        ("y", f32),
        ("z", f32),
        ("w", f32),
    ))
    assert vec4.name == "Vec4"
    assert len(vec4.fields) == 4
    assert vec4.fields[0] == ("x", f32)
    assert vec4.fields[3] == ("w", f32)

    # Interning: same struct definition returns same object
    vec4_again = ctx.get_struct("Vec4", (
        ("x", f32), ("y", f32), ("z", f32), ("w", f32),
    ))
    assert vec4 is vec4_again, "Structs with same name and fields should be interned"

    # Different struct → different object
    vec3 = ctx.get_struct("Vec3", (("x", f32), ("y", f32), ("z", f32)))
    assert vec4 is not vec3

    # Use in a module
    mod = FIRModule(name="struct_test", type_ctx=ctx)
    mod.structs["Vec4"] = vec4
    assert "Vec4" in mod.structs

    # Build a function that uses getfield
    builder = FIRBuilder(ctx)
    func = builder.new_function(mod, "get_x", [("v", vec4)], [f32])
    entry = builder.new_block(func, "entry", [("v", vec4)])
    builder.set_block(entry)

    v_val = Value(id=0, name="v", type=vec4)
    x_val = builder.getfield(v_val, "x", 0, f32)
    assert x_val is not None
    assert x_val.type == f32

    builder.ret(x_val)

    assert len(entry.instructions) == 2
    assert entry.instructions[0].opcode == "getfield"
    assert entry.instructions[0].field_name == "x"
    assert entry.instructions[0].field_index == 0


def test_is_terminator():
    """is_terminator correctly identifies terminators."""
    i32 = TypeContext.i32
    a = Value(id=0, name="a", type=i32)

    assert is_terminator(Jump("target", []))
    assert is_terminator(Branch(a, "t", "f", []))
    assert is_terminator(Return(a))
    assert is_terminator(Return(None))
    assert is_terminator(type("UnreachableInst", (), {"opcode": "unreachable"})())

    # Non-terminators
    assert not is_terminator(IAdd(a, a))
    assert not is_terminator(Store(a, a))
    assert not is_terminator(Alloca(i32))


def test_printer_simple():
    """The printer produces readable output for a simple module."""
    ctx = TypeContext()
    i32 = ctx.get_int(32)

    mod = FIRModule(name="test", type_ctx=ctx)

    builder = FIRBuilder(ctx)
    func = builder.new_function(mod, "add", [("a", i32), ("b", i32)], [i32])
    entry = builder.new_block(func, "entry", [("a", i32), ("b", i32)])
    builder.set_block(entry)

    a_val = Value(id=0, name="a", type=i32)
    b_val = Value(id=1, name="b", type=i32)
    result = builder.iadd(a_val, b_val)
    builder.ret(result)

    output = print_fir(mod)
    assert 'module "test"' in output
    assert "function add" in output
    assert "entry" in output
    assert "iadd" in output
    assert "return" in output


def test_printer_with_struct():
    """Printer renders struct types correctly."""
    ctx = TypeContext()
    f32 = ctx.get_float(32)

    mod = FIRModule(name="struct_demo", type_ctx=ctx)
    vec3 = ctx.get_struct("Vec3", (("x", f32), ("y", f32), ("z", f32)))
    mod.structs["Vec3"] = vec3

    output = print_fir(mod)
    assert "type Vec3 = struct" in output
    assert "x: f32" in output
    assert "z: f32" in output


def test_type_hashability():
    """All frozen dataclass types are hashable (usable in sets/dicts)."""
    ctx = TypeContext()
    i32 = ctx.get_int(32)
    f32 = ctx.get_float(32)

    types = {
        i32, f32, ctx.get_bool(), ctx.get_unit(), ctx.get_string(),
        ctx.get_ref(i32), ctx.get_array(i32, 8), ctx.get_vector(f32, 4),
        ctx.get_func((i32,), (f32,)), ctx.get_struct("S", (("a", i32),)),
        ctx.get_enum("E", (("A", i32), ("B", None))),
        ctx.get_region("stack"), ctx.get_capability("r", "file"),
        ctx.get_agent(), ctx.get_trust(),
    }
    # All 15 unique types should be in the set
    assert len(types) == 15, f"Expected 15 unique types, got {len(types)}"

    # Verify hash works
    for t in types:
        _ = hash(t)


# ────────────────────────────────────────────────────────────────────────────
# Run all tests
# ────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("FIR Core Test Suite")
print("=" * 60)

run_test("test_type_context_interning", test_type_context_interning)
run_test("test_type_context_types", test_type_context_types)
run_test("test_builder_simple_function", test_builder_simple_function)
run_test("test_builder_control_flow", test_builder_control_flow)
run_test("test_builder_call", test_builder_call)
run_test("test_builder_a2a", test_builder_a2a)
run_test("test_validator_empty_module", test_validator_empty_module)
run_test("test_validator_missing_terminator", test_validator_missing_terminator)
run_test("test_struct_type", test_struct_type)
run_test("test_is_terminator", test_is_terminator)
run_test("test_printer_simple", test_printer_simple)
run_test("test_printer_with_struct", test_printer_with_struct)
run_test("test_type_hashability", test_type_hashability)

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
else:
    print("All FIR tests passed!")
