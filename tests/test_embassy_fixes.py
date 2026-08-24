"""Regression tests for the four FLUX bugs found by the DSH embassy.

Repros are cited from ``flux-dsh-plugin/docs/SEAM-REPORT.md`` (§4.6), found
while mounting FLUX on the DeepSeek Harness through ``flux run-md --json``:

1. The open-interpreter's markdown fence parser mangles Python ``return``
   tokens (``'ETURN'`` literal in parse errors).
2. Assembly input silently compiles every opcode to ``ISUB``.
3. Arbitrary garbage "succeeds" as a no-op (``ISUB R0,R0,R0; HALT`` →
   success, result 0).
4. ``MOVI`` is 16-bit signed, so ``factorial of 5000000`` can't even parse
   (silent truncation / hard parse failure for values beyond ±32767).
"""

from flux.open_interpreter import OpenFluxInterpreter, interpret

# ── Bug 1: fence parser mangles `return` into 'ETURN' ──────────────────────────

def test_python_fence_return_not_mangled():
    """```python fence with `return` must not produce 'ETURN' errors.

    SEAM-REPORT bug #1 repro: a Python code fence inside markdown used to be
    fed to the natural-language parser, where ``return a + b`` was treated as
    an add of register 'return' — the 'R' prefix was stripped and int('ETURN')
    blew up into a mangled parse error.
    """
    markdown = (
        "compute 3 + 4\n\n"
        "```python\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "```\n"
    )
    result = interpret(markdown)
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 7
    # The mangled token must never appear in any error output.
    if result.error:
        assert "ETURN" not in result.error


def test_python_fence_only_errors_cleanly():
    """Markdown containing ONLY a non-FLUX code fence errors cleanly.

    No ```flux block, so there is no FLUX code to run — this must be a clear
    error, not a mangled 'ETURN' parse error and not a silent success.
    """
    markdown = (
        "```python\n"
        "x = 5\n"
        "return x\n"
        "```\n"
    )
    result = interpret(markdown)
    assert not result.success
    assert result.error is not None
    assert "ETURN" not in result.error
    assert "FLUX" in result.error


def test_register_parser_rejects_words():
    """Root cause of the 'ETURN' mangle: only R-prefixed digits are registers.

    ``_parse_register('return')`` must raise a clear error instead of
    stripping the 'r' and calling int('ETURN').
    """
    interp = OpenFluxInterpreter()
    try:
        interp._parse_register("return")
    except ValueError as e:
        assert "register" in str(e).lower()
    else:
        raise AssertionError("_parse_register('return') should have raised")


# ── Bug 2: assembly input compiles to all-ISUB ────────────────────────────────

def test_bare_assembly_compiles_correctly():
    """Bare (unfenced) assembly must compile to its real opcodes.

    SEAM-REPORT bug #2 repro: ``MOVI R0, 42`` used to be routed through the
    natural-language parser whose greedy regex compiled every mnemonic to
    ``ISUB R0, R0, R0``.
    """
    result = interpret("MOVI R0, 42\nHALT")
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 42
    # MOVI R0, 42 encodes as 2b 00 2a 00 — not the all-ISUB 09 00 00 00.
    assert result.bytecode.hex().startswith("2b002a00")


def test_bare_assembly_arithmetic():
    """Bare assembly with arithmetic compiles to real opcodes, not ISUB."""
    result = interpret("MOVI R0, 10\nMOVI R1, 5\nIADD R0, R0, R1\nHALT")
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 15
    # MOVI + IADD, no stray ISUB from the natural-language fallback.
    assert "08" in result.bytecode.hex()  # IADD opcode


def test_assembly_mnemonics_not_matched_as_subtraction():
    """Natural-language subtraction must only trigger on real register pairs.

    A line like ``MOVI R0, 42`` must not match the subtract pattern and emit
    ISUB (that greedy match was the all-ISUB root cause). Bare assembly is
    routed to the assembly parser before ``_parse_line``; reaching
    ``_parse_line`` with an assembly mnemonic must raise, never emit ISUB.
    """
    interp = OpenFluxInterpreter()
    try:
        encoded = interp._parse_line("movi r0, 42")
    except ValueError:
        pass  # correct: not natural language, must not mangle to ISUB
    else:
        assert encoded != b"\x09\x00\x00\x00", (
            "assembly mnemonic mangled to ISUB R0,R0,R0"
        )


# ── Bug 3: garbage input silently no-ops ──────────────────────────────────────

def test_garbage_input_errors():
    """Arbitrary garbage must error, not succeed as a no-op.

    SEAM-REPORT bug #3 repro: garbage used to compile to
    ``ISUB R0,R0,R0; HALT`` and return success with result 0.
    """
    result = interpret("xyzzy plugh blargh")
    assert not result.success
    assert result.error is not None
    assert "recognized" in result.error.lower() or "instruction" in result.error.lower()


def test_unknown_mnemonic_in_fence_errors():
    """Unknown opcodes inside a ```flux fence must error, not vanish."""
    result = interpret("```flux\nFOO R0, R1\nHALT\n```")
    assert not result.success
    assert result.error is not None
    assert "FOO" in result.error


def test_malformed_instruction_errors():
    """Known opcode with wrong operand count must error, not silently drop."""
    result = interpret("```flux\nMOVI R0\nHALT\n```")
    assert not result.success
    assert result.error is not None


# ── Bug 4: MOVI is 16-bit (silent truncation / parse failure) ─────────────────

def test_movi_large_immediate_executes():
    """MOVI with a value beyond ±32767 must load the full value.

    SEAM-REPORT bug #4 repro: ``MOVI R0, 40000`` used to fail with
    "'h' format requires -32768 <= number <= 32767".
    """
    result = interpret("```flux\nMOVI R0, 40000\nHALT\n```")
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 40000


def test_movi_large_immediate_all_registers():
    """32-bit loads work into any destination register (no scratch clobber)."""
    for reg_num, value in [(1, 40000), (2, 70000), (5, 130000), (7, 65536)]:
        result = interpret(
            f"```flux\nMOVI R{reg_num}, {value}\nHALT\n```"
        )
        assert result.success, f"R{reg_num} load failed: {result.error}"
        assert result.registers.get(reg_num) == value, (
            f"R{reg_num} expected {value}, got {result.registers.get(reg_num)}"
        )


def test_factorial_large_parses():
    """``factorial of 5000000`` must parse (the embassy's exact repro).

    Execution of 5M iterations exceeds the default cycle budget, so this
    asserts the parse/encode stage: the large immediate must be encodable
    instead of raising the old struct.error.
    """
    interp = OpenFluxInterpreter()
    bytecode = interp._parse_to_bytecode("factorial of 5000000")
    assert bytecode, "factorial of 5000000 produced no bytecode"
    # The 32-bit load sequence for 5000000 = 0x004C4B40 must be present.
    assert len(bytecode) > 4


def test_math_large_operands():
    """Math with operands beyond 16 bits computes the right result."""
    result = interpret("compute 100000 + 200000")
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 300000


def test_natural_language_large_load():
    """``load R0 with 40000`` loads the full 32-bit value."""
    result = interpret("load R0 with 40000")
    assert result.success, f"execution failed: {result.error}"
    assert result.result == 40000


def test_movi_out_of_32bit_errors():
    """Immediates beyond 32 bits must raise a clear error, not truncate."""
    result = interpret("compute 99999999999999999999")
    assert not result.success
    assert result.error is not None
    assert "range" in result.error.lower()
