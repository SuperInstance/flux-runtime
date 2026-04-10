"""
ISA v2 Virtual Machine - Executes 4-byte-aligned bytecode
"""

from typing import List, Optional


class Opcode:
    NOP = 0x00
    MOV = 0x01
    IADD = 0x08
    ISUB = 0x09
    IMUL = 0x0A
    IDIV = 0x0B
    INC = 0x0E
    DEC = 0x0F
    JMP = 0x07
    JNZ = 0x06
    JZ = 0x2E
    PUSH = 0x10
    POP = 0x11
    MOVI = 0x2B
    CMP = 0x2D
    HALT = 0x80


class IsaV2VM:
    """Virtual Machine for ISA v2 with fixed 4-byte instructions"""

    def __init__(self, num_registers: int = 8):
        self.registers: List[int] = [0] * num_registers
        self.stack: List[int] = []
        self.memory: bytearray = bytearray(65536)  # 64KB memory
        self.pc: int = 0  # Program counter (in bytes, must be divisible by 4)
        self.halted: bool = False
        self.zero_flag: bool = False
        self.num_registers = num_registers

    def load_bytecode(self, bytecode: bytes, offset: int = 0):
        """Load bytecode into memory at the specified offset"""
        for i, byte in enumerate(bytecode):
            if offset + i < len(self.memory):
                self.memory[offset + i] = byte

    def fetch_instruction(self) -> bytes:
        """Fetch 4-byte instruction at current PC"""
        if self.pc + 4 > len(self.memory):
            raise IndexError(f"PC out of bounds: {self.pc}")
        instruction = bytes(self.memory[self.pc:self.pc + 4])
        self.pc += 4
        return instruction

    def decode_and_execute(self, instruction: bytes):
        """Decode and execute a 4-byte instruction"""
        if len(instruction) != 4:
            raise ValueError(f"Instruction must be 4 bytes, got {len(instruction)}")

        opcode = instruction[0]
        byte1 = instruction[1]
        byte2 = instruction[2]
        byte3 = instruction[3]

        if opcode == Opcode.NOP:
            pass

        elif opcode == Opcode.HALT:
            self.halted = True

        elif opcode == Opcode.MOVI:
            # [op][rd][imm_lo][imm_hi]
            rd = byte1
            imm = byte2 | (byte3 << 8)
            # Convert to signed 16-bit
            if imm & 0x8000:
                imm -= 0x10000
            self.registers[rd] = imm

        elif opcode == Opcode.MOV:
            # [op][rd][rs][0x00]
            rd = byte1
            rs = byte2
            self.registers[rd] = self.registers[rs]

        elif opcode == Opcode.IADD:
            # [op][rd][rs1][rs2]
            rd = byte1
            rs1 = byte2
            rs2 = byte3
            self.registers[rd] = self.registers[rs1] + self.registers[rs2]

        elif opcode == Opcode.ISUB:
            # [op][rd][rs1][rs2]
            rd = byte1
            rs1 = byte2
            rs2 = byte3
            self.registers[rd] = self.registers[rs1] - self.registers[rs2]

        elif opcode == Opcode.IMUL:
            # [op][rd][rs1][rs2]
            rd = byte1
            rs1 = byte2
            rs2 = byte3
            self.registers[rd] = self.registers[rs1] * self.registers[rs2]

        elif opcode == Opcode.IDIV:
            # [op][rd][rs1][rs2]
            rd = byte1
            rs1 = byte2
            rs2 = byte3
            if self.registers[rs2] == 0:
                raise ZeroDivisionError("Division by zero")
            self.registers[rd] = self.registers[rs1] // self.registers[rs2]

        elif opcode == Opcode.INC:
            # [op][rd][0x00][0x00]
            rd = byte1
            self.registers[rd] += 1

        elif opcode == Opcode.DEC:
            # [op][rd][0x00][0x00]
            rd = byte1
            self.registers[rd] -= 1

        elif opcode == Opcode.CMP:
            # [op][rd][rs1][rs2]
            rd = byte1
            rs1 = byte2
            rs2 = byte3
            result = self.registers[rs1] - self.registers[rs2]
            self.zero_flag = (result == 0)

        elif opcode == Opcode.JNZ:
            # [op][rd][off_lo][off_hi]
            rd = byte1
            offset = byte2 | (byte3 << 8)
            # Convert to signed 16-bit
            if offset & 0x8000:
                offset -= 0x10000
            if self.registers[rd] != 0:
                self.pc += offset

        elif opcode == Opcode.JZ:
            # [op][rd][off_lo][off_hi]
            rd = byte1
            offset = byte2 | (byte3 << 8)
            # Convert to signed 16-bit
            if offset & 0x8000:
                offset -= 0x10000
            if self.registers[rd] == 0:
                self.pc += offset

        elif opcode == Opcode.JMP:
            # [op][0x00][off_lo][off_hi]
            offset = byte2 | (byte3 << 8)
            # Convert to signed 16-bit
            if offset & 0x8000:
                offset -= 0x10000
            self.pc += offset

        elif opcode == Opcode.PUSH:
            # [op][rd][0x00][0x00]
            rd = byte1
            self.stack.append(self.registers[rd])

        elif opcode == Opcode.POP:
            # [op][rd][0x00][0x00]
            rd = byte1
            if not self.stack:
                raise IndexError("Stack underflow")
            self.registers[rd] = self.stack.pop()

        else:
            raise ValueError(f"Unknown opcode: 0x{opcode:02X}")

    def run(self, max_cycles: int = 100000):
        """Run the VM until halted or max cycles reached"""
        cycles = 0
        while not self.halted and cycles < max_cycles:
            instruction = self.fetch_instruction()
            self.decode_and_execute(instruction)
            cycles += 1

        if cycles >= max_cycles:
            raise RuntimeError(f"VM exceeded max cycles ({max_cycles})")

    def reset(self):
        """Reset VM state"""
        self.registers = [0] * self.num_registers
        self.stack = []
        self.pc = 0
        self.halted = False
        self.zero_flag = False

    def get_register(self, index: int) -> int:
        """Get register value"""
        return self.registers[index]

    def set_register(self, index: int, value: int):
        """Set register value"""
        self.registers[index] = value
