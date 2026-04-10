"""
Comprehensive tests for ISA v2 - Fixed 4-byte instruction format
"""

import pytest
from flux.isa_v2 import encode_v2, encode_program, Instruction, Opcode, IsaV2VM


class TestEncoder:
    """Test instruction encoding"""

    def test_nop(self):
        """Test NOP encoding"""
        result = encode_v2(Instruction(opcode=Opcode.NOP))
        assert result == bytes([0x00, 0x00, 0x00, 0x00])

    def test_halt(self):
        """Test HALT encoding"""
        result = encode_v2(Instruction(opcode=Opcode.HALT))
        assert result == bytes([0x80, 0x00, 0x00, 0x00])

    def test_mov(self):
        """Test MOV encoding"""
        result = encode_v2(Instruction(opcode=Opcode.MOV, rd=1, rs1=2))
        assert result == bytes([0x01, 0x01, 0x02, 0x00])

    def test_movi_positive(self):
        """Test MOVI with positive immediate"""
        result = encode_v2(Instruction(opcode=Opcode.MOVI, rd=1, imm=42))
        assert result == bytes([0x2B, 0x01, 0x2A, 0x00])

    def test_movi_negative(self):
        """Test MOVI with negative immediate (two's complement)"""
        result = encode_v2(Instruction(opcode=Opcode.MOVI, rd=1, imm=-1))
        # -1 in 16-bit two's complement is 0xFFFF
        assert result == bytes([0x2B, 0x01, 0xFF, 0xFF])

    def test_movi_large(self):
        """Test MOVI with large immediate"""
        result = encode_v2(Instruction(opcode=Opcode.MOVI, rd=2, imm=1000))
        # 1000 = 0x03E8
        assert result == bytes([0x2B, 0x02, 0xE8, 0x03])

    def test_iadd(self):
        """Test IADD encoding"""
        result = encode_v2(Instruction(opcode=Opcode.IADD, rd=1, rs1=2, rs2=3))
        assert result == bytes([0x08, 0x01, 0x02, 0x03])

    def test_isub(self):
        """Test ISUB encoding"""
        result = encode_v2(Instruction(opcode=Opcode.ISUB, rd=1, rs1=2, rs2=3))
        assert result == bytes([0x09, 0x01, 0x02, 0x03])

    def test_imul(self):
        """Test IMUL encoding"""
        result = encode_v2(Instruction(opcode=Opcode.IMUL, rd=1, rs1=2, rs2=3))
        assert result == bytes([0x0A, 0x01, 0x02, 0x03])

    def test_idiv(self):
        """Test IDIV encoding"""
        result = encode_v2(Instruction(opcode=Opcode.IDIV, rd=1, rs1=2, rs2=3))
        assert result == bytes([0x0B, 0x01, 0x02, 0x03])

    def test_inc(self):
        """Test INC encoding"""
        result = encode_v2(Instruction(opcode=Opcode.INC, rd=1))
        assert result == bytes([0x0E, 0x01, 0x00, 0x00])

    def test_dec(self):
        """Test DEC encoding"""
        result = encode_v2(Instruction(opcode=Opcode.DEC, rd=1))
        assert result == bytes([0x0F, 0x01, 0x00, 0x00])

    def test_cmp(self):
        """Test CMP encoding"""
        result = encode_v2(Instruction(opcode=Opcode.CMP, rd=0, rs1=1, rs2=2))
        assert result == bytes([0x2D, 0x00, 0x01, 0x02])

    def test_jz(self):
        """Test JZ encoding"""
        result = encode_v2(Instruction(opcode=Opcode.JZ, rd=1, offset=4))
        assert result == bytes([0x2E, 0x01, 0x04, 0x00])

    def test_jnz(self):
        """Test JNZ encoding"""
        result = encode_v2(Instruction(opcode=Opcode.JNZ, rd=1, offset=4))
        assert result == bytes([0x06, 0x01, 0x04, 0x00])

    def test_jmp(self):
        """Test JMP encoding"""
        result = encode_v2(Instruction(opcode=Opcode.JMP, offset=8))
        assert result == bytes([0x07, 0x00, 0x08, 0x00])

    def test_push(self):
        """Test PUSH encoding"""
        result = encode_v2(Instruction(opcode=Opcode.PUSH, rd=1))
        assert result == bytes([0x10, 0x01, 0x00, 0x00])

    def test_pop(self):
        """Test POP encoding"""
        result = encode_v2(Instruction(opcode=Opcode.POP, rd=1))
        assert result == bytes([0x11, 0x01, 0x00, 0x00])

    def test_encode_program(self):
        """Test encoding a program"""
        instructions = [
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.IADD, rd=3, rs1=1, rs2=2),
            Instruction(opcode=Opcode.HALT),
        ]
        bytecode = encode_program(instructions)
        assert len(bytecode) == 16  # 4 instructions * 4 bytes
        assert bytecode == bytes([
            0x2B, 0x01, 0x0A, 0x00,  # MOVI R1, 10
            0x2B, 0x02, 0x14, 0x00,  # MOVI R2, 20
            0x08, 0x03, 0x01, 0x02,  # IADD R3, R1, R2
            0x80, 0x00, 0x00, 0x00,  # HALT
        ])


class TestVM:
    """Test VM execution"""

    def test_vm_init(self):
        """Test VM initialization"""
        vm = IsaV2VM()
        assert len(vm.registers) == 8
        assert vm.pc == 0
        assert not vm.halted
        assert len(vm.stack) == 0

    def test_movi_execution(self):
        """Test MOVI instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=42),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 42

    def test_mov_execution(self):
        """Test MOV instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=100),
            Instruction(opcode=Opcode.MOV, rd=2, rs1=1),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 100
        assert vm.get_register(2) == 100

    def test_iadd_execution(self):
        """Test IADD instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.IADD, rd=3, rs1=1, rs2=2),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(3) == 30

    def test_isub_execution(self):
        """Test ISUB instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=50),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.ISUB, rd=3, rs1=1, rs2=2),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(3) == 30

    def test_imul_execution(self):
        """Test IMUL instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=6),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=7),
            Instruction(opcode=Opcode.IMUL, rd=3, rs1=1, rs2=2),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(3) == 42

    def test_idiv_execution(self):
        """Test IDIV instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=100),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=5),
            Instruction(opcode=Opcode.IDIV, rd=3, rs1=1, rs2=2),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(3) == 20

    def test_inc_dec_execution(self):
        """Test INC and DEC instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),
            Instruction(opcode=Opcode.INC, rd=1),
            Instruction(opcode=Opcode.INC, rd=1),
            Instruction(opcode=Opcode.DEC, rd=1),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 11

    def test_push_pop_execution(self):
        """Test PUSH and POP instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=100),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=200),
            Instruction(opcode=Opcode.PUSH, rd=1),
            Instruction(opcode=Opcode.PUSH, rd=2),
            Instruction(opcode=Opcode.POP, rd=3),
            Instruction(opcode=Opcode.POP, rd=4),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(3) == 200  # Pop should get last pushed value
        assert vm.get_register(4) == 100  # Pop should get first pushed value

    def test_jmp_execution(self):
        """Test JMP instruction execution"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),
            Instruction(opcode=Opcode.JMP, offset=4),  # Skip next instruction
            Instruction(opcode=Opcode.MOVI, rd=1, imm=999),  # This should be skipped
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 10  # Should remain 10
        assert vm.get_register(2) == 20

    def test_jz_execution_taken(self):
        """Test JZ when condition is true (branch taken)"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=0),
            Instruction(opcode=Opcode.JZ, rd=1, offset=4),  # Branch if R1 == 0
            Instruction(opcode=Opcode.MOVI, rd=1, imm=999),  # This should be skipped
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 0  # Should remain 0
        assert vm.get_register(2) == 20

    def test_jz_execution_not_taken(self):
        """Test JZ when condition is false (branch not taken)"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=5),
            Instruction(opcode=Opcode.JZ, rd=1, offset=4),  # Branch if R1 == 0
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),  # This should execute
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 10

    def test_jnz_execution_taken(self):
        """Test JNZ when condition is true (branch taken)"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=5),
            Instruction(opcode=Opcode.JNZ, rd=1, offset=4),  # Branch if R1 != 0
            Instruction(opcode=Opcode.MOVI, rd=1, imm=999),  # This should be skipped
            Instruction(opcode=Opcode.MOVI, rd=2, imm=20),
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 5  # Should remain 5
        assert vm.get_register(2) == 20

    def test_jnz_execution_not_taken(self):
        """Test JNZ when condition is false (branch not taken)"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=0),
            Instruction(opcode=Opcode.JNZ, rd=1, offset=4),  # Branch if R1 != 0
            Instruction(opcode=Opcode.MOVI, rd=1, imm=10),  # This should execute
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 10


class TestPrograms:
    """Test complete programs"""

    def test_sum_program(self):
        """Test program that sums 1+2+3+4+5"""
        vm = IsaV2VM()
        # R1 = 0 (sum), R2 = 5 (counter)
        # Loop: add R2 to R1, decrement R2, if R2 != 0 jump back
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=0),   # sum = 0
            Instruction(opcode=Opcode.MOVI, rd=2, imm=5),   # i = 5
            # loop_start:
            Instruction(opcode=Opcode.IADD, rd=1, rs1=1, rs2=2),  # sum += i
            Instruction(opcode=Opcode.DEC, rd=2),          # i--
            Instruction(opcode=Opcode.JNZ, rd=2, offset=-12),     # if i != 0, jump back (offset is from PC after fetch)
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 15  # 5+4+3+2+1 = 15

    def test_factorial_5(self):
        """Test program that computes 5! = 120"""
        vm = IsaV2VM()
        # R1 = 1 (result), R2 = 5 (counter)
        # Loop: multiply R1 by R2, decrement R2, if R2 != 0 jump back
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=1),   # result = 1
            Instruction(opcode=Opcode.MOVI, rd=2, imm=5),   # n = 5
            # loop_start:
            Instruction(opcode=Opcode.IMUL, rd=1, rs1=1, rs2=2),  # result *= n
            Instruction(opcode=Opcode.DEC, rd=2),          # n--
            Instruction(opcode=Opcode.JNZ, rd=2, offset=-12),     # if n != 0, jump back (offset is from PC after fetch)
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 120  # 5! = 120

    def test_factorial_0(self):
        """Test program that computes 0! = 1"""
        vm = IsaV2VM()
        # R1 = 1 (result), R2 = 0 (counter)
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=1),   # result = 1
            Instruction(opcode=Opcode.MOVI, rd=2, imm=0),   # n = 0
            Instruction(opcode=Opcode.JZ, rd=2, offset=12),        # if n == 0, skip to HALT
            # loop_start (not executed for n=0):
            Instruction(opcode=Opcode.IMUL, rd=1, rs1=1, rs2=2),  # result *= n
            Instruction(opcode=Opcode.DEC, rd=2),                # n--
            Instruction(opcode=Opcode.JNZ, rd=2, offset=-12),     # if n != 0, jump back
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 1  # 0! = 1

    def test_fibonacci_10(self):
        """Test program that computes 10th Fibonacci number (55)"""
        vm = IsaV2VM()
        # R1 = 0 (fib_0), R2 = 1 (fib_1), R3 = 9 (counter)
        # Loop: R4 = R1 + R2, R1 = R2, R2 = R4, decrement R3, jump if R3 != 0
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=0),   # a = 0
            Instruction(opcode=Opcode.MOVI, rd=2, imm=1),   # b = 1
            Instruction(opcode=Opcode.MOVI, rd=3, imm=9),   # count = 9 (we need 9 iterations)
            # loop_start:
            Instruction(opcode=Opcode.IADD, rd=4, rs1=1, rs2=2),  # c = a + b
            Instruction(opcode=Opcode.MOV, rd=1, rs1=2),          # a = b
            Instruction(opcode=Opcode.MOV, rd=2, rs1=4),          # b = c
            Instruction(opcode=Opcode.DEC, rd=3),                # count--
            Instruction(opcode=Opcode.JNZ, rd=3, offset=-20),     # if count != 0, jump back (offset is from PC after fetch)
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(2) == 55  # 10th Fibonacci number

    def test_arithmetic_expression(self):
        """Test program that computes (5 + 3) * 2 - 4 = 12"""
        vm = IsaV2VM()
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=5),   # R1 = 5
            Instruction(opcode=Opcode.MOVI, rd=2, imm=3),   # R2 = 3
            Instruction(opcode=Opcode.MOVI, rd=3, imm=2),   # R3 = 2
            Instruction(opcode=Opcode.MOVI, rd=4, imm=4),   # R4 = 4
            Instruction(opcode=Opcode.IADD, rd=5, rs1=1, rs2=2),  # R5 = R1 + R2 = 8
            Instruction(opcode=Opcode.IMUL, rd=5, rs1=5, rs2=3),  # R5 = R5 * R3 = 16
            Instruction(opcode=Opcode.ISUB, rd=5, rs1=5, rs2=4),  # R5 = R5 - R4 = 12
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(5) == 12

    def test_stack_operations(self):
        """Test program that uses stack for swap operation"""
        vm = IsaV2VM()
        # Swap R1 and R2 using stack
        bytecode = encode_program([
            Instruction(opcode=Opcode.MOVI, rd=1, imm=100),
            Instruction(opcode=Opcode.MOVI, rd=2, imm=200),
            Instruction(opcode=Opcode.PUSH, rd=1),  # Push R1
            Instruction(opcode=Opcode.PUSH, rd=2),  # Push R2
            Instruction(opcode=Opcode.POP, rd=1),   # Pop R1 (gets R2's value)
            Instruction(opcode=Opcode.POP, rd=2),   # Pop R2 (gets R1's value)
            Instruction(opcode=Opcode.HALT),
        ])
        vm.load_bytecode(bytecode)
        vm.run()
        assert vm.get_register(1) == 200
        assert vm.get_register(2) == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
