"""ELF-like header generation for FLUX executables.

Generates a minimal ELF-like executable header that wraps FLUX bytecode,
providing metadata, section information, and entry point for the runtime loader.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Optional, BinaryIO

from .errors import AsmError, AsmErrorKind


# FLUX ELF constants
FLUX_MAGIC = b"\x7fFLUX"
FLUX_CLASS_64 = 2
FLUX_CLASS_32 = 1
FLUX_DATA_LE = 1
FLUX_VERSION_CURRENT = 1
FLUX_OS_NONE = 0

# Section types
SHT_NULL = 0
SHT_CODE = 1
SHT_DATA = 2
SHT_SYMBOL_TABLE = 3
SHT_STRING_TABLE = 4
SHT_RELOCATION = 5
SHT_NOTE = 6

# Section flags
SHF_EXEC = 0x1
SHF_WRITE = 0x2
SHF_READ = 0x4

# Header sizes
ELF64_HEADER_SIZE = 64
ELF64_SECTION_HEADER_SIZE = 64

# Program header types
PT_LOAD = 1
PT_FLUX_CODE = 0x70000001  # Custom type for FLUX bytecode segment
PT_FLUX_INFO = 0x70000002  # Custom type for FLUX metadata segment


@dataclass
class Section:
    """An ELF-like section."""
    name: str
    section_type: int
    flags: int = SHF_READ
    data: bytes = b""
    alignment: int = 1
    info: int = 0


@dataclass
class ProgramHeader:
    """An ELF-like program header (segment)."""
    segment_type: int
    flags: int = 0x5  # PF_R | PF_X
    offset: int = 0
    virtual_addr: int = 0
    physical_addr: int = 0
    file_size: int = 0
    mem_size: int = 0
    alignment: int = 0x1000


@dataclass
class ElfHeader:
    """Generates ELF-like headers for FLUX executables.

    The header format is inspired by ELF64 but simplified for FLUX's needs.
    It includes magic bytes, section table, program headers, and metadata.
    """

    # Configuration
    entry_point: int = 0
    base_address: int = 0x400000
    machine: int = 0xF100  # FLUX architecture
    flags: int = 0
    is_64bit: bool = True

    # Sections
    sections: list[Section] = field(default_factory=list)
    program_headers: list[ProgramHeader] = field(default_factory=list)

    # Symbol table
    symbols: dict[str, int] = field(default_factory=dict)

    # Metadata
    build_timestamp: Optional[float] = None
    source_filename: str = ""
    linker_version: str = "1.0"

    def generate(self, bytecode: bytes) -> bytes:
        """Generate a complete ELF-like executable from FLUX bytecode.

        Layout:
          [ELF Header 64B]
          [Program Headers]
          [Section Data]
          [Section Header Table]

        Args:
            bytecode: Raw FLUX bytecode.

        Returns:
            Complete executable binary.
        """
        # Build default sections
        code_section = Section(
            name=".flux.code",
            section_type=SHT_CODE,
            flags=SHF_READ | SHF_EXEC,
            data=bytecode,
            alignment=16,
        )
        data_section = Section(
            name=".flux.data",
            section_type=SHT_DATA,
            flags=SHF_READ | SHF_WRITE,
            data=b"",
            alignment=8,
        )
        null_section = Section(name="", section_type=SHT_NULL)

        # Build string table section
        all_section_names = [s.name for s in [null_section, code_section, data_section] + self.sections]
        strtab_data = self._build_string_table(all_section_names)
        strtab_section = Section(
            name=".shstrtab",
            section_type=SHT_STRING_TABLE,
            data=strtab_data,
            alignment=1,
        )

        # Build symbol table if we have symbols
        symtab_section = Section(
            name=".symtab",
            section_type=SHT_SYMBOL_TABLE,
            data=self._build_symbol_table(bytecode),
            alignment=8,
            info=len(self.symbols),
        )

        all_sections = [null_section, code_section, data_section, strtab_section, symtab_section]
        all_sections.extend(self.sections)

        # Compute layout
        n_sections = len(all_sections)
        n_phdrs = max(1, len(self.program_headers))

        header_size = ELF64_HEADER_SIZE
        phdr_offset = header_size
        phdr_size = 56  # Elf64_Phdr size
        section_data_start = phdr_offset + n_phdrs * phdr_size

        # Align section data start
        section_data_start = (section_data_start + 15) & ~15

        # Compute section offsets and sizes
        current_offset = section_data_start
        section_offsets = []
        for section in all_sections:
            if section.data:
                # Align to section alignment
                current_offset = (current_offset + section.alignment - 1) & ~(section.alignment - 1)
            section_offsets.append(current_offset)
            if section.data:
                current_offset += len(section.data)

        # Section header table offset
        shdr_offset = (current_offset + 15) & ~15
        shdr_size = ELF64_SECTION_HEADER_SIZE

        # Build program headers
        if not self.program_headers:
            code_phdr = ProgramHeader(
                segment_type=PT_LOAD,
                flags=0x5,
                offset=section_offsets[1],
                virtual_addr=self.base_address + section_offsets[1],
                physical_addr=self.base_address + section_offsets[1],
                file_size=len(bytecode),
                mem_size=len(bytecode),
                alignment=16,
            )
            self.program_headers = [code_phdr]

        # Build ELF header
        timestamp = self.build_timestamp or time.time()
        elf_header = self._build_elf_header(
            n_phdrs=n_phdrs,
            n_sections=n_sections,
            shdr_offset=shdr_offset,
            timestamp=timestamp,
        )

        # Assemble the file
        output = bytearray()

        # 1. ELF header
        output.extend(elf_header)
        output.extend(b'\x00' * (phdr_offset - len(output)))

        # 2. Program headers
        for phdr in self.program_headers:
            output.extend(self._build_program_header(phdr))

        # 3. Pad to section data start
        output.extend(b'\x00' * (section_data_start - len(output)))

        # 4. Section data
        for i, section in enumerate(all_sections):
            if section.data:
                # Pad to alignment
                pad = section_offsets[i] - len(output)
                if pad > 0:
                    output.extend(b'\x00' * pad)
                output.extend(section.data)

        # 5. Pad to section header table
        output.extend(b'\x00' * (shdr_offset - len(output)))

        # 6. Section header table
        for i, section in enumerate(all_sections):
            output.extend(self._build_section_header(
                section, section_offsets[i], shdr_offset, strtab_section,
                all_section_names,
            ))

        return bytes(output)

    def _build_elf_header(self, n_phdrs: int, n_sections: int,
                          shdr_offset: int, timestamp: float) -> bytes:
        """Build the ELF64-like file header."""
        ident = bytearray(16)
        ident[0:4] = FLUX_MAGIC
        ident[4] = FLUX_CLASS_64 if self.is_64bit else FLUX_CLASS_32
        ident[5] = FLUX_DATA_LE
        ident[6] = FLUX_VERSION_CURRENT
        ident[7] = 0  # ELFOSABI_NONE
        # ident[8:16] = padding (zeros)

        header = bytearray(64)
        header[0:16] = ident

        struct.pack_into("<H", header, 16, 2)  # ET_EXEC
        struct.pack_into("<H", header, 18, self.machine & 0xFFFF)
        struct.pack_into("<I", header, 20, FLUX_VERSION_CURRENT)
        struct.pack_into("<Q", header, 24, self.entry_point)
        struct.pack_into("<Q", header, 32, ELF64_HEADER_SIZE)  # phdr offset
        struct.pack_into("<Q", header, 40, shdr_offset)  # shdr offset
        struct.pack_into("<I", header, 48, self.flags)
        struct.pack_into("<H", header, 52, ELF64_HEADER_SIZE)
        struct.pack_into("<H", header, 54, 56)  # phdr entry size
        struct.pack_into("<H", header, 56, n_phdrs)
        struct.pack_into("<H", header, 58, ELF64_SECTION_HEADER_SIZE)
        struct.pack_into("<H", header, 60, n_sections)
        struct.pack_into("<H", header, 62, 4)  # shndx of .shstrtab (index 4 in our layout)

        return bytes(header)

    def _build_program_header(self, phdr: ProgramHeader) -> bytes:
        """Build a single program header entry (56 bytes)."""
        data = bytearray(56)
        struct.pack_into("<I", data, 0, phdr.segment_type)
        struct.pack_into("<I", data, 4, phdr.flags)
        struct.pack_into("<Q", data, 8, phdr.offset)
        struct.pack_into("<Q", data, 16, phdr.virtual_addr)
        struct.pack_into("<Q", data, 24, phdr.physical_addr)
        struct.pack_into("<Q", data, 32, phdr.file_size)
        struct.pack_into("<Q", data, 40, phdr.mem_size)
        struct.pack_into("<Q", data, 48, phdr.alignment)
        return bytes(data)

    def _build_section_header(self, section: Section, offset: int,
                               shdr_offset: int, strtab: Section,
                               all_names: list[str]) -> bytes:
        """Build a single section header entry (64 bytes)."""
        data = bytearray(64)

        # Name index in string table
        name_idx = 0
        current_pos = 0
        for name in all_names:
            if name == section.name:
                name_idx = current_pos
                break
            current_pos += len(name) + 1  # null-terminated

        struct.pack_into("<I", data, 0, name_idx)
        struct.pack_into("<I", data, 4, section.section_type)
        struct.pack_into("<Q", data, 8, section.flags)
        struct.pack_into("<Q", data, 16, self.base_address + offset if section.data else 0)
        struct.pack_into("<Q", data, 24, offset)
        struct.pack_into("<Q", data, 32, len(section.data))
        struct.pack_into("<I", data, 40, 0)  # link (to symtab/strtab)
        struct.pack_into("<I", data, 44, section.info)
        struct.pack_into("<Q", data, 48, section.alignment)
        struct.pack_into("<Q", data, 56, 0)  # entry size

        return bytes(data)

    def _build_string_table(self, names: list[str]) -> bytes:
        """Build a string table for section names."""
        table = bytearray(b'\x00')  # Start with null byte
        for name in names:
            table.extend(name.encode("utf-8"))
            table.append(0x00)
        return bytes(table)

    def _build_symbol_table(self, bytecode: bytes) -> bytes:
        """Build a minimal symbol table.

        Each entry: name_offset:u32 + value:u64 + size:u64 + info:u8 + other:u8 + section_idx:u16
        Total: 24 bytes per entry
        """
        # Build string table for symbol names
        sym_names = bytearray(b'\x00')  # null for null symbol
        sym_entries = bytearray()

        # Null symbol (first entry)
        sym_entries.extend(struct.pack("<I", 0))  # name offset
        sym_entries.extend(struct.pack("<Q", 0))  # value
        sym_entries.extend(struct.pack("<Q", 0))  # size
        sym_entries.extend(struct.pack("<BBH", 0, 0, 0))  # info, other, section

        for name, value in self.symbols.items():
            name_offset = len(sym_names)
            sym_names.extend(name.encode("utf-8"))
            sym_names.append(0x00)

            sym_entries.extend(struct.pack("<I", name_offset))
            sym_entries.extend(struct.pack("<Q", value))
            sym_entries.extend(struct.pack("<Q", 0))  # size unknown
            sym_entries.extend(struct.pack("<BBH", 1, 0, 1))  # STB_GLOBAL, STT_FUNC, section 1

        return bytes(sym_entries) + bytes(sym_names)

    @staticmethod
    def validate_header(data: bytes) -> list[str]:
        """Validate that data starts with a valid FLUX ELF header.

        Returns:
            List of error strings (empty = valid).
        """
        errors = []
        if len(data) < 16:
            errors.append(f"Header too short: {len(data)} bytes")
            return errors

        magic = data[0:4]
        if magic != b"\x7fFLU":
            errors.append(f"Invalid magic: {magic!r} (expected \\x7fFLU)")
            return errors

        if data[4] not in (1, 2):
            errors.append(f"Invalid class: {data[4]} (expected 1=32-bit or 2=64-bit)")

        if data[5] != 1:
            errors.append(f"Invalid data encoding: {data[5]} (expected 1=LE)")

        return errors
