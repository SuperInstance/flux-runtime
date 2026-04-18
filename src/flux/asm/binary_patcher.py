"""Binary patching utilities for FLUX bytecode.

Provides utilities for patching raw bytecode at specific offsets,
finding patterns, and applying patches.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional, Union

from .errors import AsmError, AsmErrorKind


@dataclass
class Patch:
    """A single binary patch to apply."""
    offset: int
    data: bytes
    description: str = ""


@dataclass
class PatchResult:
    """Result of applying a patch."""
    success: bool
    patched_data: bytes = b""
    applied_patches: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BinaryPatcher:
    """Utilities for patching FLUX bytecode.

    Features:
        - Patch bytes at specific offsets
        - Replace opcode at offset
        - Patch immediate values (8-bit, 16-bit, 32-bit)
        - Find byte patterns
        - Replace patterns
        - Undo/redo support via patch history
    """

    def __init__(self, data: bytes):
        self.original_data = data
        self.data = bytearray(data)
        self._patch_history: list[bytearray] = []

    @property
    def size(self) -> int:
        """Current size of the data."""
        return len(self.data)

    def patch_bytes(self, offset: int, patch_data: bytes, description: str = "") -> None:
        """Patch raw bytes at a specific offset.

        Args:
            offset: Byte offset to start patching.
            patch_data: Bytes to write.
            description: Human-readable description of the patch.

        Raises:
            AsmError: If the patch is out of bounds.
        """
        if offset < 0 or offset + len(patch_data) > len(self.data):
            raise AsmError(
                message=f"Patch at offset {offset} (size {len(patch_data)}) "
                        f"out of bounds (data size {len(self.data)})",
                kind=AsmErrorKind.PATCH_ERROR,
            )
        self._save_state()
        self.data[offset:offset + len(patch_data)] = patch_data

    def patch_opcode(self, offset: int, new_opcode: int, description: str = "") -> None:
        """Replace the opcode byte at the given offset."""
        self.patch_bytes(offset, bytes([new_opcode & 0xFF]),
                         description or f"Replace opcode at 0x{offset:04x}")

    def patch_imm8(self, offset: int, value: int, description: str = "") -> None:
        """Patch an 8-bit immediate value at the given offset."""
        if value < 0 or value > 255:
            raise AsmError(
                message=f"Imm8 value {value} out of range [0, 255]",
                kind=AsmErrorKind.RANGE_ERROR,
            )
        self.patch_bytes(offset, bytes([value & 0xFF]),
                         description or f"Patch imm8={value} at 0x{offset:04x}")

    def patch_imm16(self, offset: int, value: int, description: str = "",
                    signed: bool = True) -> None:
        """Patch a 16-bit immediate value at the given offset (little-endian)."""
        if signed and (value < -32768 or value > 32767):
            raise AsmError(
                message=f"Imm16 value {value} out of range [-32768, 32767]",
                kind=AsmErrorKind.RANGE_ERROR,
            )
        fmt = "<h" if signed else "<H"
        self._save_state()
        struct.pack_into(fmt, self.data, offset, value)

    def patch_imm32(self, offset: int, value: int, description: str = "",
                    signed: bool = True) -> None:
        """Patch a 32-bit immediate value at the given offset (little-endian)."""
        fmt = "<i" if signed else "<I"
        self._save_state()
        struct.pack_into(fmt, self.data, offset, value)

    def patch_register(self, offset: int, reg: int, description: str = "") -> None:
        """Patch a register number at the given offset."""
        if reg < 0 or reg > 63:
            raise AsmError(
                message=f"Register {reg} out of range [0, 63]",
                kind=AsmErrorKind.RANGE_ERROR,
            )
        self.patch_bytes(offset, bytes([reg & 0xFF]),
                         description or f"Patch register={reg} at 0x{offset:04x}")

    def find_pattern(self, pattern: bytes, start: int = 0) -> list[int]:
        """Find all occurrences of a byte pattern.

        Returns:
            List of offsets where the pattern was found.
        """
        offsets = []
        data = bytes(self.data)
        pos = start
        while pos <= len(data) - len(pattern):
            idx = data.find(pattern, pos)
            if idx == -1:
                break
            offsets.append(idx)
            pos = idx + 1
        return offsets

    def replace_pattern(self, old_pattern: bytes, new_pattern: bytes) -> int:
        """Replace all occurrences of a pattern.

        Returns:
            Number of replacements made.
        """
        count = 0
        pos = 0
        while pos <= len(self.data) - len(old_pattern):
            idx = bytes(self.data).find(old_pattern, pos)
            if idx == -1:
                break
            self._save_state()
            self.data[idx:idx + len(old_pattern)] = new_pattern
            count += 1
            pos = idx + len(new_pattern)
        return count

    def insert_bytes(self, offset: int, data: bytes) -> None:
        """Insert bytes at the given offset (shifts everything after)."""
        if offset < 0 or offset > len(self.data):
            raise AsmError(
                message=f"Insert offset {offset} out of bounds",
                kind=AsmErrorKind.PATCH_ERROR,
            )
        self._save_state()
        self.data[offset:offset] = data

    def delete_bytes(self, offset: int, length: int) -> None:
        """Delete bytes at the given offset."""
        if offset < 0 or offset + length > len(self.data):
            raise AsmError(
                message=f"Delete at offset {offset} (length {length}) out of bounds",
                kind=AsmErrorKind.PATCH_ERROR,
            )
        self._save_state()
        del self.data[offset:offset + length]

    def nop_fill(self, offset: int, length: int) -> None:
        """Fill a region with NOP (0x00) bytes."""
        if offset < 0 or offset + length > len(self.data):
            raise AsmError(
                message=f"NOP fill at offset {offset} (length {length}) out of bounds",
                kind=AsmErrorKind.PATCH_ERROR,
            )
        self._save_state()
        for i in range(length):
            self.data[offset + i] = 0x00  # NOP

    def compare_with(self, other: bytes) -> list[tuple[int, int, int]]:
        """Compare current data with another byte sequence.

        Returns:
            List of (offset, old_byte, new_byte) for differing bytes.
        """
        differences = []
        min_len = min(len(self.data), len(other))
        for i in range(min_len):
            if self.data[i] != other[i]:
                differences.append((i, other[i], self.data[i]))
        # Check length difference
        if len(self.data) != len(other):
            differences.append((min_len, len(other), len(self.data)))
        return differences

    def undo(self) -> bool:
        """Undo the last patch operation.

        Returns:
            True if undo was successful, False if no history.
        """
        if not self._patch_history:
            return False
        self.data = self._patch_history.pop()
        return True

    def redo_stack_clear(self) -> None:
        """Clear the undo history."""
        self._patch_history.clear()

    def get_bytes(self) -> bytes:
        """Get the current patched data."""
        return bytes(self.data)

    def hexdump(self, start: int = 0, length: Optional[int] = None) -> str:
        """Generate a hexdump of the data."""
        if length is None:
            length = len(self.data) - start
        end = min(start + length, len(self.data))
        lines = []
        for i in range(start, end, 16):
            chunk = self.data[i:min(i + 16, end)]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08x}  {hex_part:<48s}  |{ascii_part}|")
        return "\n".join(lines)

    def _save_state(self) -> None:
        """Save current state for undo."""
        self._patch_history.append(bytearray(self.data))
        # Limit history to 100 entries
        if len(self._patch_history) > 100:
            self._patch_history.pop(0)


def create_patch(offset: int, data: bytes, description: str = "") -> Patch:
    """Convenience factory for creating Patch objects."""
    return Patch(offset=offset, data=data, description=description)
