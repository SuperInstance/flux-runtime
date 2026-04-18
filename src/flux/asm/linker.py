"""FLUX Linker — combines multiple object files into executables.

Supports:
  - Combining multiple .o (object) files
  - Symbol resolution across files
  - Relocation of labels and references
  - Export/import symbol tables
  - Entry point specification
"""

from __future__ import annotations

import struct
import json
from dataclasses import dataclass, field
from typing import Optional, BinaryIO

from .errors import AsmError, AsmErrorKind, SourceLocation


@dataclass
class ObjectFile:
    """Represents a single object file for linking.

    Layout:
      magic: b'FLUXOBJ' (8 bytes)
      header_size: uint32 LE (4 bytes)
      code_size: uint32 LE (4 bytes)
      n_symbols: uint32 LE (4 bytes)
      n_relocations: uint32 LE (4 bytes)
      entry_point: uint32 LE (4 bytes) — 0xFFFFFFFF if none
      [code: code_size bytes]
      [symbols: n_symbols * (name_len:u16 + name + value:u32)]
      [relocations: n_relocations * (offset:u32 + sym_name_len:u16 + sym_name)]
    """
    filename: str = "<unknown>"
    code: bytes = b""
    symbols: dict[str, int] = field(default_factory=dict)
    relocations: list[tuple[int, str]] = field(default_factory=list)  # (offset, symbol_name)
    entry_point: int = 0xFFFFFFFF

    @staticmethod
    def MAGIC() -> bytes:
        return b"FLUXOBJ\x00"  # 8 bytes, null-padded for struct alignment

    HEADER_FORMAT = "<8sIIIII"  # magic(8) + header_size(4) + code_size(4) + n_symbols(4) + n_relocs(4) + entry(4)
    HEADER_SIZE = 28

    def serialize(self) -> bytes:
        """Serialize this object file to bytes."""
        buf = bytearray()

        # Header
        header = struct.pack(
            self.HEADER_FORMAT,
            self.MAGIC(), self.HEADER_SIZE,
            len(self.code), len(self.symbols),
            len(self.relocations), self.entry_point,
        )
        buf.extend(header)

        # Code section
        buf.extend(self.code)

        # Symbols
        for name, value in self.symbols.items():
            name_bytes = name.encode("utf-8")
            buf.extend(struct.pack("<H", len(name_bytes)))
            buf.extend(name_bytes)
            buf.extend(struct.pack("<I", value))

        # Relocations
        for offset, sym_name in self.relocations:
            name_bytes = sym_name.encode("utf-8")
            buf.extend(struct.pack("<I", offset))
            buf.extend(struct.pack("<H", len(name_bytes)))
            buf.extend(name_bytes)

        return bytes(buf)

    @classmethod
    def deserialize(cls, data: bytes, filename: str = "<unknown>") -> "ObjectFile":
        """Deserialize bytes into an ObjectFile."""
        if len(data) < cls.HEADER_SIZE:
            raise AsmError(
                message=f"Object file too short: {len(data)} bytes",
                kind=AsmErrorKind.LINKER_ERROR,
            )

        magic, header_size, code_size, n_symbols, n_relocs, entry_point = struct.unpack_from(
            cls.HEADER_FORMAT, data, 0,
        )

        if magic != cls.MAGIC():
            raise AsmError(
                message=f"Invalid object file magic: {magic!r}",
                kind=AsmErrorKind.LINKER_ERROR,
            )

        pos = header_size

        # Code
        code = data[pos:pos + code_size]
        pos += code_size

        # Symbols
        symbols: dict[str, int] = {}
        for _ in range(n_symbols):
            name_len = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            name = data[pos:pos + name_len].decode("utf-8")
            pos += name_len
            value = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            symbols[name] = value

        # Relocations
        relocations: list[tuple[int, str]] = []
        for _ in range(n_relocs):
            offset = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            name_len = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            sym_name = data[pos:pos + name_len].decode("utf-8")
            pos += name_len
            relocations.append((offset, sym_name))

        return cls(
            filename=filename,
            code=code,
            symbols=symbols,
            relocations=relocations,
            entry_point=entry_point,
        )

    def to_json(self) -> str:
        """Export object file as JSON."""
        return json.dumps({
            "filename": self.filename,
            "code_hex": self.code.hex(),
            "symbols": self.symbols,
            "relocations": [{"offset": off, "symbol": sym} for off, sym in self.relocations],
            "entry_point": self.entry_point,
        }, indent=2)


class FluxLinker:
    """Links multiple ObjectFiles into a single executable.

    Features:
      - Symbol resolution across all input files
      - Relocation patching
      - Entry point selection
      - Symbol conflict detection
    """

    def __init__(self, entry_symbol: Optional[str] = None):
        self.entry_symbol = entry_symbol
        self.errors: list[AsmError] = []
        self.warnings: list[str] = []

    def link(self, objects: list[ObjectFile]) -> bytes:
        """Link multiple object files into a single executable.

        Returns:
            Linked executable bytes.

        Raises:
            AsmError: If linking fails.
        """
        self.errors = []
        self.warnings = []

        if not objects:
            raise AsmError(
                message="No object files to link",
                kind=AsmErrorKind.LINKER_ERROR,
            )

        # Resolve symbols across all objects
        global_symbols: dict[str, int] = {}
        code_offset = 0
        code_sections: list[bytes] = []
        all_relocations: list[tuple[int, int, str]] = []  # (global_offset, local_offset, symbol)

        for obj in objects:
            # Check for duplicate symbols
            for sym_name, sym_value in obj.symbols.items():
                if sym_name in global_symbols:
                    self.warnings.append(
                        f"Symbol '{sym_name}' redefined in {obj.filename} "
                        f"(previously defined at offset {global_symbols[sym_name]})"
                    )
                global_symbols[sym_name] = sym_value + code_offset

            # Track relocations
            for reloc_offset, reloc_sym in obj.relocations:
                all_relocations.append((code_offset, reloc_offset, reloc_sym))

            code_sections.append(obj.code)
            code_offset += len(obj.code)

        # Combine code
        linked_code = bytearray()
        for section in code_sections:
            linked_code.extend(section)

        # Apply relocations
        for base_offset, local_offset, symbol_name in all_relocations:
            if symbol_name not in global_symbols:
                raise AsmError(
                    message=f"Undefined symbol during linking: {symbol_name}",
                    kind=AsmErrorKind.LINKER_ERROR,
                    hints=["Check that all required object files are included."],
                )

            target_addr = global_symbols[symbol_name]
            abs_offset = base_offset + local_offset

            if abs_offset + 2 > len(linked_code):
                raise AsmError(
                    message=f"Relocation at offset {abs_offset} out of bounds",
                    kind=AsmErrorKind.LINKER_ERROR,
                )

            # Patch as little-endian i16 relative offset
            current_addr = abs_offset
            rel_offset = target_addr - current_addr
            struct.pack_into("<h", linked_code, abs_offset, rel_offset)

        return bytes(linked_code)

    def link_files(self, paths: list[str]) -> bytes:
        """Link object files from file paths."""
        objects = []
        for path in paths:
            try:
                with open(path, "rb") as f:
                    data = f.read()
                obj = ObjectFile.deserialize(data, filename=path)
                objects.append(obj)
            except IOError as e:
                raise AsmError(
                    message=f"Cannot read object file '{path}': {e}",
                    kind=AsmErrorKind.IO_ERROR,
                ) from e
        return self.link(objects)
