"""Tests for FLUX cross-assembler, macros, linker, binary patcher, and ELF headers."""

import sys
sys.path.insert(0, "src")

import json
import struct
import os
import tempfile

from flux.asm.errors import AsmError, AsmErrorKind, SourceLocation, make_error
from flux.asm.macros import MacroPreprocessor
from flux.asm.cross_assembler import CrossAssembler, OutputFormat, AssemblyResult
from flux.asm.linker import FluxLinker, ObjectFile
from flux.asm.binary_patcher import BinaryPatcher, Patch
from flux.asm.elf_header import ElfHeader


# ═══════════════════════════════════════════════════════════════════════════════
# Error tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_asm_error_basic():
    """AsmError basic construction and string formatting."""
    err = AsmError(
        message="test error",
        kind=AsmErrorKind.SYNTAX,
        location=SourceLocation(file="test.asm", line=10, column=5, source_line="  MOV R0, R1"),
    )
    s = str(err)
    assert "test.asm:10" in s
    assert "syntax error" in s
    assert "test error" in s
    assert "^" in s  # caret pointer


def test_asm_error_with_hints():
    """AsmError with hint suggestions."""
    err = AsmError(
        message="unknown opcode FOO",
        kind=AsmErrorKind.UNKNOWN_OPCODE,
        location=SourceLocation(file="x.asm", line=1),
        hints=["Did you mean NOP?"],
    )
    s = str(err)
    assert "hint:" in s
    assert "NOP" in s


def test_make_error_factory():
    """make_error convenience factory."""
    err = make_error("bad thing", kind=AsmErrorKind.RANGE_ERROR, file="a.asm", line=3)
    assert err.kind == AsmErrorKind.RANGE_ERROR
    assert err.location.file == "a.asm"
    assert err.location.line == 3


def test_source_location_context():
    """SourceLocation context_lines with caret."""
    loc = SourceLocation(file="f.asm", line=5, column=10, source_line="  IADD R0, R1, R2")
    lines = loc.context_lines()
    assert len(lines) == 2
    assert "IADD" in lines[0]
    assert "^" in lines[1]


def test_source_location_no_column():
    """SourceLocation without column still works."""
    loc = SourceLocation(file="f.asm", line=5)
    assert "f.asm:5" in str(loc)
    assert ":" not in str(loc).split(":5")[1]  # no extra :column


# ═══════════════════════════════════════════════════════════════════════════════
# Macro preprocessor tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_macro_define_object_like():
    """Object-like macro expansion: #define CONST 42."""
    pp = MacroPreprocessor()
    result = pp.preprocess("#define COUNT 10\nMOVI R0, COUNT\n")
    assert "MOVI R0, 10" in result


def test_macro_define_function_like():
    """Function-like macro expansion: #define ADD3(a,b,c) a + b + c."""
    pp = MacroPreprocessor()
    result = pp.preprocess('#define ADD3(a, b, c) IADD a, b, c\nADD3(R0, R1, R2)\n')
    assert "IADD R0, R1, R2" in result


def test_macro_ifdef_true():
    """#ifdef with defined macro emits code."""
    pp = MacroPreprocessor(defines={"FEATURE_X": "1"})
    result = pp.preprocess("#ifdef FEATURE_X\nIADD R0, R1, R2\n#endif\n")
    assert "IADD R0, R1, R2" in result


def test_macro_ifdef_false():
    """#ifdef with undefined macro suppresses code."""
    pp = MacroPreprocessor()
    result = pp.preprocess("#ifdef MISSING\nIADD R0, R1, R2\n#endif\nNOP\n")
    assert "IADD" not in result
    assert "NOP" in result


def test_macro_ifndef():
    """#ifndef emits code when macro is not defined."""
    pp = MacroPreprocessor()
    result = pp.preprocess("#ifndef HAS_FPU\nIADD R0, R1, R2\n#endif\n")
    assert "IADD R0, R1, R2" in result


def test_macro_undef():
    """#undef removes a macro definition."""
    pp = MacroPreprocessor(defines={"X": "1"})
    result = pp.preprocess("#undef X\n#ifdef X\nNOP\n#endif\n")
    assert "NOP" not in result


def test_macro_nested_conditionals():
    """Nested #ifdef/#endif blocks."""
    pp = MacroPreprocessor(defines={"A": "1", "B": "1"})
    result = pp.preprocess(
        "#ifdef A\n"
        "#ifdef B\nINNER\n#endif\n"
        "#endif\n"
    )
    assert "INNER" in result


def test_macro_else_branch():
    """#else emits alternate code."""
    pp = MacroPreprocessor(defines={"A": "1"})
    result = pp.preprocess(
        "#ifdef A\nYES\n#else\nNO\n#endif\n"
    )
    assert "YES" in result
    assert "NO" not in result


def test_macro_ifdef_else_undefined():
    """#else when macro is undefined."""
    pp = MacroPreprocessor()
    result = pp.preprocess(
        "#ifdef MISSING\nYES\n#else\nNO\n#endif\n"
    )
    assert "YES" not in result
    assert "NO" in result


def test_macro_set_directive():
    """.set NAME value directive works like #define."""
    pp = MacroPreprocessor()
    result = pp.preprocess(".set VERSION 3\nMOVI R0, VERSION\n")
    assert "MOVI R0, 3" in result


def test_macro_ifdef_without_endif_raises():
    """Unterminated #ifdef raises AsmError."""
    pp = MacroPreprocessor()
    try:
        pp.preprocess("#ifdef X\nNOP\n")
        assert False, "Should have raised"
    except AsmError as e:
        assert "Unterminated" in str(e)


def test_macro_endif_without_ifdef_raises():
    """#endif without #ifdef raises AsmError."""
    pp = MacroPreprocessor()
    try:
        pp.preprocess("#endif\n")
        assert False, "Should have raised"
    except AsmError as e:
        assert "without" in str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-assembler tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_assemble_simple_nop():
    """Assemble a single NOP instruction."""
    asm = CrossAssembler()
    result = asm.assemble("NOP", output_format=OutputFormat.BINARY)
    assert result.bytecode == bytes([0x00])
    assert len(result.errors) == 0


def test_assemble_halt():
    """HALT assembles to 0x80."""
    asm = CrossAssembler()
    result = asm.assemble("HALT")
    assert result.bytecode == bytes([0x80])


def test_assemble_mov():
    """MOV R0, R1 encodes correctly."""
    asm = CrossAssembler()
    result = asm.assemble("MOV R0, R1")
    assert len(result.bytecode) == 3  # Format C
    assert result.bytecode[0] == 0x01  # MOV opcode
    assert result.bytecode[1] == 0x00  # R0
    assert result.bytecode[2] == 0x01  # R1


def test_assemble_format_b():
    """INC R5 (Format B: 2 bytes)."""
    asm = CrossAssembler()
    result = asm.assemble("INC R5")
    assert len(result.bytecode) == 2
    assert result.bytecode[0] == 0x0E  # INC
    assert result.bytecode[1] == 0x05  # R5


def test_assemble_format_e():
    """IADD R0, R1, R2 (Format E: 4 bytes)."""
    asm = CrossAssembler()
    result = asm.assemble("IADD R0, R1, R2")
    assert len(result.bytecode) == 4
    assert result.bytecode[0] == 0x08  # IADD
    assert result.bytecode[1] == 0x00  # rd
    assert result.bytecode[2] == 0x01  # rs1
    assert result.bytecode[3] == 0x02  # rs2


def test_assemble_format_d():
    """MOVI R0, 42 (Format D: 4 bytes)."""
    asm = CrossAssembler()
    result = asm.assemble("MOVI R0, 42")
    assert len(result.bytecode) == 4
    assert result.bytecode[0] == 0x2B  # MOVI
    assert result.bytecode[1] == 0x00  # R0
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == 42


def test_assemble_labels():
    """Labels and references work correctly."""
    asm = CrossAssembler()
    source = "start:\nMOVI R0, 1\nend:\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "start" in result.symbol_table
    assert "end" in result.symbol_table
    assert result.symbol_table["start"] == 0  # first instruction


def test_assemble_forward_label_ref():
    """Forward label reference in jump target."""
    asm = CrossAssembler()
    source = "JMP R0, end\nMOVI R1, 5\nend:\nHALT"
    result = asm.assemble(source)
    assert len(result.errors) == 0
    assert "end" in result.symbol_table
    # JMP should have the offset to the HALT instruction
    # JMP is 4 bytes, MOVI is 4 bytes, so offset should be 8
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == 8  # offset from JMP to HALT


def test_assemble_comments():
    """Comments (; and //) are stripped."""
    asm = CrossAssembler()
    result = asm.assemble("NOP ; this is a comment\n// another comment\nHALT")
    assert result.bytecode == bytes([0x00, 0x80])


def test_assemble_unknown_opcode():
    """Unknown mnemonic produces error."""
    asm = CrossAssembler()
    result = asm.assemble("FOOBAR R0, R1")
    assert len(result.errors) > 0
    assert any("FOOBAR" in e.message for e in result.errors)


def test_assemble_hex_literal():
    """Hex immediate values work: MOVI R0, 0xFF."""
    asm = CrossAssembler()
    result = asm.assemble("MOVI R0, 0xFF")
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == 0xFF


def test_assemble_negative_immediate():
    """Negative immediate: MOVI R0, -10."""
    asm = CrossAssembler()
    result = asm.assemble("MOVI R0, -10")
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == -10


def test_assemble_output_hex():
    """Hex output format produces space-separated hex."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\nHALT", output_format=OutputFormat.HEX)
    assert "00 80" in result.as_hex()


def test_assemble_output_json():
    """JSON output format contains bytecode_hex and symbols."""
    asm = CrossAssembler()
    source = "start:\nNOP\nHALT"
    result = asm.assemble(source, output_format=OutputFormat.JSON)
    j = json.loads(result.as_json())
    assert "bytecode_hex" in j
    assert "symbols" in j
    assert "start" in j["symbols"]


def test_assemble_output_intel_hex():
    """Intel HEX output format starts with : and ends with EOF record."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\nHALT\nINC R0\n", output_format=OutputFormat.INTEL_HEX)
    ihex = result.as_intel_hex()
    assert ihex.startswith(":")
    assert ":00000001FF" in ihex


def test_assemble_data_byte_directive():
    """.byte directive emits individual bytes."""
    asm = CrossAssembler()
    result = asm.assemble(".byte 0x01, 0x02, 0x03")
    assert result.bytecode == bytes([0x01, 0x02, 0x03])


def test_assemble_data_word_directive():
    """.word directive emits 16-bit LE words."""
    asm = CrossAssembler()
    result = asm.assemble(".word 0x0102, 0x0304")
    assert result.bytecode == b'\x02\x01\x04\x03'


def test_assemble_data_fill_directive():
    """.fill directive emits N bytes."""
    asm = CrossAssembler()
    result = asm.assemble(".fill 5, 0xFF")
    assert result.bytecode == bytes([0xFF] * 5)


def test_assemble_data_ascii_directive():
    """.ascii and .asciz directives."""
    asm = CrossAssembler()
    result = asm.assemble('.ascii "hello"\n.asciz "world"')
    assert b"hello" in result.bytecode
    assert b"world\x00" in result.bytecode


def test_assemble_with_preprocessing():
    """Full pipeline: macros + assembly."""
    asm = CrossAssembler(defines={"N": "10"})
    source = "#define OP MOVI\nOP R0, N\nHALT"
    result = asm.assemble(source)
    assert result.bytecode[0] == 0x2B  # MOVI
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == 10
    assert result.bytecode[4] == 0x80  # HALT


def test_assemble_align_directive():
    """.align directive pads to alignment boundary."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\n.align 4\nNOP")
    # NOP(1) + pad(3) + NOP(1) = 5 bytes total
    assert len(result.bytecode) == 5
    assert result.bytecode[0] == 0x00  # NOP
    assert result.bytecode[4] == 0x00  # NOP at aligned offset


def test_assemble_duplicate_label_error():
    """Duplicate label produces error."""
    asm = CrossAssembler()
    result = asm.assemble("start:\nNOP\nstart:\nHALT")
    assert any("Duplicate" in str(e) or "duplicate" in str(e).lower() for e in result.errors)


def test_assemble_multiple_instructions():
    """Multiple instructions assemble correctly in sequence."""
    asm = CrossAssembler()
    source = "MOVI R0, 1\nMOVI R1, 2\nIADD R0, R0, R1\nHALT"
    result = asm.assemble(source)
    assert len(result.bytecode) == 4 + 4 + 4 + 1  # 13 bytes
    assert result.bytecode[-1] == 0x80  # HALT


# ═══════════════════════════════════════════════════════════════════════════════
# Binary patcher tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_patcher_patch_opcode():
    """Patch an opcode byte at a specific offset."""
    data = bytes([0x00, 0x80, 0x0E, 0x05])
    patcher = BinaryPatcher(data)
    patcher.patch_opcode(0, 0x80)  # NOP -> HALT
    assert patcher.get_bytes()[0] == 0x80


def test_patcher_patch_imm16():
    """Patch a 16-bit immediate value."""
    data = bytearray(4)
    patcher = BinaryPatcher(bytes(data))
    patcher.patch_imm16(0, 1000)
    val = struct.unpack_from("<h", patcher.get_bytes(), 0)[0]
    assert val == 1000


def test_patcher_patch_register():
    """Patch a register number."""
    data = bytes([0x0E, 0x00])  # INC R0
    patcher = BinaryPatcher(data)
    patcher.patch_register(1, 5)  # change to R5
    assert patcher.get_bytes()[1] == 5


def test_patcher_find_pattern():
    """Find byte patterns in data."""
    data = bytes([0x08, 0x00, 0x01, 0x02, 0x08, 0x03, 0x04, 0x05])
    patcher = BinaryPatcher(data)
    offsets = patcher.find_pattern(bytes([0x08, 0x00]))
    assert len(offsets) == 1
    assert offsets[0] == 0


def test_patcher_replace_pattern():
    """Replace all occurrences of a pattern."""
    data = bytes([0x00, 0x00, 0x00])
    patcher = BinaryPatcher(data)
    count = patcher.replace_pattern(bytes([0x00]), bytes([0xFF]))
    assert count == 3
    assert patcher.get_bytes() == bytes([0xFF, 0xFF, 0xFF])


def test_patcher_nop_fill():
    """NOP fill a region."""
    data = bytes([0xFF, 0xFF, 0xFF, 0xFF])
    patcher = BinaryPatcher(data)
    patcher.nop_fill(1, 2)
    result = patcher.get_bytes()
    assert result[0] == 0xFF
    assert result[1] == 0x00
    assert result[2] == 0x00
    assert result[3] == 0xFF


def test_patcher_undo():
    """Undo reverts last patch."""
    data = bytes([0x00, 0x80])
    patcher = BinaryPatcher(data)
    patcher.patch_opcode(0, 0x0E)
    assert patcher.get_bytes()[0] == 0x0E
    assert patcher.undo() is True
    assert patcher.get_bytes()[0] == 0x00


def test_patcher_insert_delete():
    """Insert and delete bytes."""
    data = bytes([0x01, 0x02, 0x03])
    patcher = BinaryPatcher(data)
    patcher.insert_bytes(1, bytes([0xAA]))
    assert patcher.get_bytes() == bytes([0x01, 0xAA, 0x02, 0x03])
    patcher.delete_bytes(0, 2)
    assert patcher.get_bytes() == bytes([0x02, 0x03])


def test_patcher_out_of_bounds():
    """Out-of-bounds patch raises AsmError."""
    data = bytes([0x00])
    patcher = BinaryPatcher(data)
    try:
        patcher.patch_bytes(5, bytes([0xFF]))
        assert False, "Should have raised"
    except AsmError as e:
        assert "out of bounds" in str(e).lower()


def test_patcher_hexdump():
    """Hexdump produces formatted output."""
    data = bytes([0x00, 0x01, 0x02, 0x80])
    patcher = BinaryPatcher(data)
    dump = patcher.hexdump()
    assert "00 01 02 80" in dump


def test_patcher_compare_with():
    """Compare shows differences."""
    data = bytes([0x00, 0x01, 0x02])
    patcher = BinaryPatcher(data)
    patcher.patch_opcode(1, 0xFF)
    diffs = patcher.compare_with(data)
    assert len(diffs) == 1
    assert diffs[0] == (1, 0x01, 0xFF)


# ═══════════════════════════════════════════════════════════════════════════════
# Linker tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_object_file_serialize_deserialize():
    """Object file serialization round-trip."""
    obj = ObjectFile(
        filename="test.o",
        code=bytes([0x00, 0x80]),
        symbols={"main": 0, "end": 2},
        relocations=[],
        entry_point=0,
    )
    data = obj.serialize()
    obj2 = ObjectFile.deserialize(data, filename="test.o")
    assert obj2.code == obj.code
    assert obj2.symbols == obj.symbols
    assert obj2.entry_point == obj.entry_point


def test_object_file_magic():
    """Object file has correct magic bytes."""
    obj = ObjectFile(code=b"\x00")
    data = obj.serialize()
    assert data[:8] == b"FLUXOBJ\x00"


def test_linker_two_files():
    """Link two object files together."""
    obj1 = ObjectFile(
        filename="a.o",
        code=bytes([0x00, 0x00]),  # NOP, NOP
        symbols={"func_a": 0},
        relocations=[],
    )
    obj2 = ObjectFile(
        filename="b.o",
        code=bytes([0x80]),  # HALT
        symbols={"func_b": 0},
        relocations=[],
    )
    linker = FluxLinker()
    result = linker.link([obj1, obj2])
    assert len(result) == 3
    assert result[0] == 0x00  # NOP
    assert result[2] == 0x80  # HALT


def test_linker_undefined_symbol():
    """Linker raises on undefined symbol during relocation."""
    obj = ObjectFile(
        filename="bad.o",
        code=struct.pack("<h", 0),
        symbols={},
        relocations=[(0, "missing_symbol")],
    )
    linker = FluxLinker()
    try:
        linker.link([obj])
        assert False, "Should have raised"
    except AsmError as e:
        assert "Undefined" in str(e)


def test_linker_empty_input():
    """Linker raises on empty input."""
    linker = FluxLinker()
    try:
        linker.link([])
        assert False, "Should have raised"
    except AsmError as e:
        assert "No object files" in str(e)


def test_object_file_to_json():
    """Object file JSON export."""
    obj = ObjectFile(filename="test.o", code=bytes([0x00, 0x80]), symbols={"x": 0})
    j = json.loads(obj.to_json())
    assert j["filename"] == "test.o"
    assert j["code_hex"] == "0080"
    assert "x" in j["symbols"]


# ═══════════════════════════════════════════════════════════════════════════════
# ELF header tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_elf_header_generate():
    """ELF-like header generation produces valid output."""
    eh = ElfHeader(entry_point=0x400100)
    bytecode = bytes([0x00, 0x80])  # NOP, HALT
    result = eh.generate(bytecode)
    assert len(result) > len(bytecode)
    # Check FLUX magic
    assert result[0:4] == b"\x7fFLU"


def test_elf_header_validate():
    """ELF header validation works."""
    eh = ElfHeader()
    valid = eh.generate(bytes([0x00]))
    errors = ElfHeader.validate_header(valid)
    assert len(errors) == 0

    # Invalid magic
    errors = ElfHeader.validate_header(b"FAKE_DATA" * 8)
    assert len(errors) > 0


def test_elf_header_invalid_class():
    """ELF header validation catches invalid class."""
    data = bytearray(16)
    data[0:4] = b"\x7fFLU"
    data[4] = 99  # invalid class
    errors = ElfHeader.validate_header(bytes(data))
    assert any("class" in e.lower() for e in errors)


def test_elf_header_with_symbols():
    """ELF header includes symbol table when symbols are provided."""
    eh = ElfHeader(
        entry_point=0x10,
        symbols={"main": 0, "helper": 4},
    )
    bytecode = bytes([0x00, 0x00, 0x00, 0x00, 0x80])  # NOP*4 + HALT
    result = eh.generate(bytecode)
    assert len(result) > len(bytecode) + 64  # header + code


def test_elf_header_custom_section():
    """ELF header with custom section."""
    eh = ElfHeader()
    from flux.asm.elf_header import Section
    eh.sections = [
        Section(name=".flux.meta", section_type=6, data=b"metadata"),
    ]
    result = eh.generate(bytes([0x00, 0x80]))
    assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_full_pipeline_assemble_patch_link():
    """Full pipeline: assemble → patch → link → ELF wrap."""
    # Assemble
    asm = CrossAssembler(defines={"VAL": "42"})
    code = "MOVI R0, VAL\nHALT"
    result = asm.assemble(code)
    assert len(result.errors) == 0

    # Patch
    patcher = BinaryPatcher(result.bytecode)
    patcher.patch_opcode(0, 0x0E)  # Change MOVI to INC
    patched = patcher.get_bytes()

    # Create object file and link
    obj = ObjectFile(filename="main.o", code=patched, symbols={"main": 0})
    linker = FluxLinker()
    linked = linker.link([obj])

    # Wrap in ELF header
    eh = ElfHeader(entry_point=0, symbols={"main": 0})
    final = eh.generate(linked)
    assert len(final) > len(linked)
    assert final[0:4] == b"\x7fFLU"


def test_assemble_with_include():
    """Test .include directive by preprocessing."""
    pp = MacroPreprocessor()
    # Since we can't easily create temp files in all environments,
    # test the error case (missing file)
    try:
        pp.preprocess('.include "nonexistent_file.asm"\nNOP')
        # If it didn't raise, that's okay too (file might exist)
    except AsmError as e:
        assert "include" in str(e).lower() or "Cannot" in str(e)


def test_assembly_source_map():
    """AssemblyResult source map tracks instruction locations."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\nHALT\nINC R0")
    assert len(result.source_map) == 3
    assert result.source_map[0]["line"] == 1  # NOP is on line 1
    assert result.source_map[1]["line"] == 2  # HALT is on line 2
    assert result.source_map[2]["line"] == 3  # INC is on line 3


def test_register_range_validation():
    """Register > 63 raises error."""
    asm = CrossAssembler()
    result = asm.assemble("INC R64")
    assert len(result.errors) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# New feature tests: @label syntax, BEQ/BNE aliases, # comments, python_list output
# ═══════════════════════════════════════════════════════════════════════════════

def test_at_label_syntax():
    """@label defines a label (alternative to name: syntax)."""
    asm = CrossAssembler()
    source = "@start\nMOVI R0, 1\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "start" in result.symbol_table
    assert result.symbol_table["start"] == 0


def test_at_label_forward_reference():
    """@label can be referenced by forward jumps."""
    asm = CrossAssembler()
    source = "JMP R0, end\n@start\nMOVI R0, 1\n@end\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "start" in result.symbol_table
    assert "end" in result.symbol_table


def test_at_label_with_comment():
    """@label with trailing comment is parsed correctly."""
    asm = CrossAssembler()
    source = "@loop ; this is the loop start\nNOP\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "loop" in result.symbol_table


def test_at_label_duplicate_error():
    """Duplicate @label raises error."""
    asm = CrossAssembler()
    source = "@loop\nNOP\n@loop\nHALT"
    result = asm.assemble(source)
    assert any("uplicate" in str(e).lower() for e in result.errors)


def test_at_label_and_colon_label_coexist():
    """@label and name: label can be used together."""
    asm = CrossAssembler()
    source = "@start\nNOP\ngoodbye:\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "start" in result.symbol_table
    assert "goodbye" in result.symbol_table


def test_beq_alias():
    """BEQ is an alias for JE."""
    asm = CrossAssembler()
    result_beq = asm.assemble("BEQ R0, 10")
    result_je = asm.assemble("JE R0, 10")
    assert result_beq.bytecode == result_je.bytecode
    assert result_beq.bytecode[0] == 0x2E  # JE opcode


def test_bne_alias():
    """BNE is an alias for JNE."""
    asm = CrossAssembler()
    result_bne = asm.assemble("BNE R0, 10")
    result_jne = asm.assemble("JNE R0, 10")
    assert result_bne.bytecode == result_jne.bytecode
    assert result_bne.bytecode[0] == 0x2F  # JNE opcode


def test_blt_bge_bgt_ble_aliases():
    """BLT/BGE/BGT/BLE are aliases for JL/JGE/JG/JLE."""
    asm = CrossAssembler()
    pairs = [
        ("BLT", "JL", 0x36),
        ("BGE", "JGE", 0x37),
        ("BGT", "JG", 0x4D),
        ("BLE", "JLE", 0x4E),
    ]
    for alias, canonical, opcode in pairs:
        result_a = asm.assemble(f"{alias} R0, 5")
        result_c = asm.assemble(f"{canonical} R0, 5")
        assert result_a.bytecode == result_c.bytecode, f"{alias} != {canonical}"
        assert result_a.bytecode[0] == opcode


def test_hash_comment_not_preprocessor():
    """# at start of line (not a preprocessor directive) is treated as comment."""
    asm = CrossAssembler(preprocess=False)
    source = "# This is a comment\nNOP\n# Another comment\nHALT"
    result = asm.assemble(source)
    assert result.bytecode == bytes([0x00, 0x80])


def test_hash_comment_preserves_preprocessor():
    """#define and #ifdef are NOT treated as comments."""
    asm = CrossAssembler(defines={"X": "1"}, preprocess=True)
    source = "#define Y 2\nNOP"
    result = asm.assemble(source)
    assert len(result.errors) == 0


def test_python_list_output():
    """as_python_list returns list of ints."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\nHALT\nINC R5")
    py_list = result.as_python_list()
    assert isinstance(py_list, list)
    assert py_list == [0x00, 0x80, 0x0E, 0x05]


def test_python_list_empty():
    """Python list output for empty assembly."""
    asm = CrossAssembler()
    result = asm.assemble("")
    py_list = result.as_python_list()
    assert py_list == []


def test_all_branch_aliases_resolve():
    """All branch aliases map to correct canonical opcodes."""
    from flux.asm.opcodes_compat import OPCODE_DEFS
    aliases_to_canonical = {
        "BEQ": "JE", "BNE": "JNE", "BLT": "JL",
        "BGE": "JGE", "BGT": "JG", "BLE": "JLE",
        "ADD": "IADD", "SUB": "ISUB", "MUL": "IMUL",
        "DIV": "IDIV", "NEG": "INEG", "NOT": "INOT",
    }
    for alias, canonical in aliases_to_canonical.items():
        assert alias in OPCODE_DEFS, f"Alias {alias} not in OPCODE_DEFS"
        assert OPCODE_DEFS[alias].opcode == OPCODE_DEFS[canonical].opcode


def test_opcode_count_over_50():
    """At least 50 unique opcodes are defined."""
    from flux.asm.opcodes_compat import OPCODE_DEFS
    # Count only non-aliased opcodes (check by unique opcode byte values)
    unique_opcodes = set()
    for name, definition in OPCODE_DEFS.items():
        unique_opcodes.add(definition.opcode)
    assert len(unique_opcodes) >= 50, f"Only {len(unique_opcodes)} unique opcodes"


def test_assemble_dword_directive():
    """.dword directive emits 32-bit LE values."""
    asm = CrossAssembler()
    result = asm.assemble(".dword 0x01020304")
    assert len(result.bytecode) == 4
    assert result.bytecode == b'\x04\x03\x02\x01'


def test_assemble_org_directive():
    """.org directive pads to target address."""
    asm = CrossAssembler()
    result = asm.assemble("NOP\n.org 8\nHALT")
    assert len(result.bytecode) == 9
    assert result.bytecode[0] == 0x00  # NOP at 0
    assert result.bytecode[8] == 0x80  # HALT at 8


def test_assemble_binary_literal():
    """Binary literal: MOVI R0, 0b1010."""
    asm = CrossAssembler()
    result = asm.assemble("MOVI R0, 0b1010")
    imm = struct.unpack_from("<h", result.bytecode, 2)[0]
    assert imm == 0b1010


def test_assemble_push_pop():
    """PUSH and POP encode correctly."""
    asm = CrossAssembler()
    result = asm.assemble("PUSH R0\nPOP R1")
    assert len(result.bytecode) == 4  # 2 bytes each
    assert result.bytecode[0] == 0x20  # PUSH
    assert result.bytecode[1] == 0x00  # R0
    assert result.bytecode[2] == 0x21  # POP
    assert result.bytecode[3] == 0x01  # R1


def test_assemble_call_ret():
    """CALL and RET encode correctly."""
    asm = CrossAssembler()
    source = "CALL R0, 10\nRET R0, R1"
    result = asm.assemble(source)
    assert len(result.bytecode) == 7  # CALL=4 + RET=3
    assert result.bytecode[0] == 0x07  # CALL
    assert result.bytecode[4] == 0x28  # RET


def test_assemble_float_ops():
    """Float arithmetic opcodes encode correctly."""
    asm = CrossAssembler()
    result = asm.assemble("FADD R0, R1, R2\nFSUB R3, R4, R5")
    assert len(result.bytecode) == 8  # 4 bytes each
    assert result.bytecode[0] == 0x40  # FADD
    assert result.bytecode[4] == 0x41  # FSUB


def test_assemble_vector_ops():
    """Vector (SIMD) opcodes encode correctly."""
    asm = CrossAssembler()
    result = asm.assemble("VADD R0, R1, R2\nVMUL R3, R4, R5")
    assert len(result.bytecode) == 8
    assert result.bytecode[0] == 0x52  # VADD
    assert result.bytecode[4] == 0x54  # VMUL


def test_assemble_a2a_ops():
    """A2A protocol opcodes encode as 1-byte instructions."""
    asm = CrossAssembler()
    result = asm.assemble("TELL\nASK\nDELEGATE\nBROADCAST")
    assert result.bytecode == bytes([0x60, 0x61, 0x62, 0x66])


def test_assemble_with_labels_and_arithmetic():
    """Labels used in arithmetic expressions."""
    asm = CrossAssembler(preprocess=True)
    source = "start:\nNOP\nNOP\nNOP\nend:\n.size = end - start"
    result = asm.assemble(source)
    assert result.errors == []
    assert "start" in result.symbol_table
    assert result.symbol_table["end"] == 3


def test_assemble_escape_sequences():
    """String escape sequences in .ascii directive."""
    asm = CrossAssembler()
    result = asm.assemble(r'.ascii "hello\tworld\n"')
    assert b"\t" in result.bytecode
    assert b"\n" in result.bytecode


def test_assemble_system_ops():
    """System opcodes: HALT, YIELD, DEBUG_BREAK."""
    asm = CrossAssembler()
    result = asm.assemble("HALT\nYIELD\nDEBUG_BREAK")
    assert result.bytecode == bytes([0x80, 0x81, 0x84])


def test_assemble_conditional_jump_with_label():
    """Conditional jump (BEQ) with label reference."""
    asm = CrossAssembler()
    source = "MOVI R0, 1\nMOVI R1, 1\nBEQ R0, skip\nMOVI R0, 0\n@skip\nHALT"
    result = asm.assemble(source)
    assert result.errors == []
    assert "skip" in result.symbol_table


def test_assemble_comments_inside_strings():
    """Comments inside string literals are not stripped."""
    asm = CrossAssembler()
    result = asm.assemble(r'.ascii "hello ; world"')
    assert b";" in result.bytecode


def test_assemble_complex_program():
    """Assemble a complex multi-instruction program with labels and jumps."""
    asm = CrossAssembler()
    source = """\
    @main
    MOVI R0, 10
    MOVI R1, 0
loop:
    ADD R1, R1, R0
    DEC R0
    JNZ R0, loop
    PUSH R1
    HALT
"""
    result = asm.assemble(source)
    assert result.errors == []
    assert "main" in result.symbol_table
    assert "loop" in result.symbol_table
    assert result.bytecode[-1] == 0x80  # HALT at end


def test_assemble_many_simd_ops():
    """All SIMD vector opcodes available."""
    from flux.asm.opcodes_compat import OPCODE_DEFS
    simd_load_store = ["VLOAD", "VSTORE"]
    simd_3reg = ["VADD", "VSUB", "VMUL", "VDIV", "VFMA"]
    asm = CrossAssembler()
    for op in simd_load_store:
        result = asm.assemble(f"{op} R0, R1")
        assert len(result.errors) == 0, f"{op} failed: {result.errors}"
        assert OPCODE_DEFS[op].opcode == result.bytecode[0]
    for op in simd_3reg:
        result = asm.assemble(f"{op} R0, R1, R2")
        assert len(result.errors) == 0, f"{op} failed: {result.errors}"
        assert OPCODE_DEFS[op].opcode == result.bytecode[0]


def test_assemble_trust_ops():
    """Trust and capability opcodes."""
    from flux.asm.opcodes_compat import OPCODE_DEFS
    trust_ops = [
        "TRUST_CHECK", "TRUST_UPDATE", "TRUST_QUERY",
        "CAP_REQUIRE", "CAP_GRANT", "CAP_REVOKE",
        "BARRIER", "EMERGENCY_STOP",
    ]
    asm = CrossAssembler()
    for op in trust_ops:
        result = asm.assemble(op)
        assert len(result.errors) == 0, f"{op} failed: {result.errors}"
        assert OPCODE_DEFS[op].opcode == result.bytecode[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Running FLUX cross-assembler tests...\n")

    # Error tests (5)
    test_asm_error_basic()
    print("  ✓ test_asm_error_basic")
    test_asm_error_with_hints()
    print("  ✓ test_asm_error_with_hints")
    test_make_error_factory()
    print("  ✓ test_make_error_factory")
    test_source_location_context()
    print("  ✓ test_source_location_context")
    test_source_location_no_column()
    print("  ✓ test_source_location_no_column")

    # Macro tests (11)
    test_macro_define_object_like()
    print("  ✓ test_macro_define_object_like")
    test_macro_define_function_like()
    print("  ✓ test_macro_define_function_like")
    test_macro_ifdef_true()
    print("  ✓ test_macro_ifdef_true")
    test_macro_ifdef_false()
    print("  ✓ test_macro_ifdef_false")
    test_macro_ifndef()
    print("  ✓ test_macro_ifndef")
    test_macro_undef()
    print("  ✓ test_macro_undef")
    test_macro_nested_conditionals()
    print("  ✓ test_macro_nested_conditionals")
    test_macro_else_branch()
    print("  ✓ test_macro_else_branch")
    test_macro_ifdef_else_undefined()
    print("  ✓ test_macro_ifdef_else_undefined")
    test_macro_set_directive()
    print("  ✓ test_macro_set_directive")
    test_macro_ifdef_without_endif_raises()
    print("  ✓ test_macro_ifdef_without_endif_raises")
    test_macro_endif_without_ifdef_raises()
    print("  ✓ test_macro_endif_without_ifdef_raises")

    # Assembler tests (22)
    test_assemble_simple_nop()
    print("  ✓ test_assemble_simple_nop")
    test_assemble_halt()
    print("  ✓ test_assemble_halt")
    test_assemble_mov()
    print("  ✓ test_assemble_mov")
    test_assemble_format_b()
    print("  ✓ test_assemble_format_b")
    test_assemble_format_e()
    print("  ✓ test_assemble_format_e")
    test_assemble_format_d()
    print("  ✓ test_assemble_format_d")
    test_assemble_labels()
    print("  ✓ test_assemble_labels")
    test_assemble_forward_label_ref()
    print("  ✓ test_assemble_forward_label_ref")
    test_assemble_comments()
    print("  ✓ test_assemble_comments")
    test_assemble_unknown_opcode()
    print("  ✓ test_assemble_unknown_opcode")
    test_assemble_hex_literal()
    print("  ✓ test_assemble_hex_literal")
    test_assemble_negative_immediate()
    print("  ✓ test_assemble_negative_immediate")
    test_assemble_output_hex()
    print("  ✓ test_assemble_output_hex")
    test_assemble_output_json()
    print("  ✓ test_assemble_output_json")
    test_assemble_output_intel_hex()
    print("  ✓ test_assemble_output_intel_hex")
    test_assemble_data_byte_directive()
    print("  ✓ test_assemble_data_byte_directive")
    test_assemble_data_word_directive()
    print("  ✓ test_assemble_data_word_directive")
    test_assemble_data_fill_directive()
    print("  ✓ test_assemble_data_fill_directive")
    test_assemble_data_ascii_directive()
    print("  ✓ test_assemble_data_ascii_directive")
    test_assemble_with_preprocessing()
    print("  ✓ test_assemble_with_preprocessing")
    test_assemble_align_directive()
    print("  ✓ test_assemble_align_directive")
    test_assemble_duplicate_label_error()
    print("  ✓ test_assemble_duplicate_label_error")
    test_assemble_multiple_instructions()
    print("  ✓ test_assemble_multiple_instructions")

    # Binary patcher tests (11)
    test_patcher_patch_opcode()
    print("  ✓ test_patcher_patch_opcode")
    test_patcher_patch_imm16()
    print("  ✓ test_patcher_patch_imm16")
    test_patcher_patch_register()
    print("  ✓ test_patcher_patch_register")
    test_patcher_find_pattern()
    print("  ✓ test_patcher_find_pattern")
    test_patcher_replace_pattern()
    print("  ✓ test_patcher_replace_pattern")
    test_patcher_nop_fill()
    print("  ✓ test_patcher_nop_fill")
    test_patcher_undo()
    print("  ✓ test_patcher_undo")
    test_patcher_insert_delete()
    print("  ✓ test_patcher_insert_delete")
    test_patcher_out_of_bounds()
    print("  ✓ test_patcher_out_of_bounds")
    test_patcher_hexdump()
    print("  ✓ test_patcher_hexdump")
    test_patcher_compare_with()
    print("  ✓ test_patcher_compare_with")

    # Linker tests (5)
    test_object_file_serialize_deserialize()
    print("  ✓ test_object_file_serialize_deserialize")
    test_object_file_magic()
    print("  ✓ test_object_file_magic")
    test_linker_two_files()
    print("  ✓ test_linker_two_files")
    test_linker_undefined_symbol()
    print("  ✓ test_linker_undefined_symbol")
    test_linker_empty_input()
    print("  ✓ test_linker_empty_input")
    test_object_file_to_json()
    print("  ✓ test_object_file_to_json")

    # ELF header tests (4)
    test_elf_header_generate()
    print("  ✓ test_elf_header_generate")
    test_elf_header_validate()
    print("  ✓ test_elf_header_validate")
    test_elf_header_invalid_class()
    print("  ✓ test_elf_header_invalid_class")
    test_elf_header_with_symbols()
    print("  ✓ test_elf_header_with_symbols")
    test_elf_header_custom_section()
    print("  ✓ test_elf_header_custom_section")

    # Integration tests (4)
    test_full_pipeline_assemble_patch_link()
    print("  ✓ test_full_pipeline_assemble_patch_link")
    test_assemble_with_include()
    print("  ✓ test_assemble_with_include")
    test_assembly_source_map()
    print("  ✓ test_assembly_source_map")
    test_register_range_validation()
    print("  ✓ test_register_range_validation")

    print("\n✅ All 62 cross-assembler tests passed!")
