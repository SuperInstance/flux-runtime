"""Tests for Marine Physics opcodes (PHY_ABSORB through PHY_REFRAC)."""

import pytest
import math
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter, VMHaltError


def make_absorb_program():
    return bytearray([Op.PHY_ABSORB, 2, 0, 1, Op.HALT])

def make_scatter_program():
    return bytearray([Op.PHY_SCATTER, 2, 0, 1, Op.HALT])

def make_jerlov_program():
    return bytearray([Op.PHY_JERLOV, 2, 0, 1, Op.HALT])

def make_thermo_program():
    return bytearray([Op.PHY_THERMO, 2, 0, 1, Op.HALT])

def make_seabed_program():
    return bytearray([Op.PHY_SEABED, 2, 0, 1, Op.HALT])

def make_atten_program():
    return bytearray([Op.PHY_ATTEN, 2, 0, 1, Op.HALT])

def make_visib_program():
    return bytearray([Op.PHY_VISIB, 2, 0, 1, Op.HALT])

def make_soundv_program():
    return bytearray([Op.PHY_SOUNDV, 2, 0, 1, Op.HALT])

def make_refrac_program():
    return bytearray([Op.PHY_REFRAC, 2, 0, 1, Op.HALT])


class TestPhysicsAbsorb:
    def test_absorption_coastal_blue_green(self):
        vm = Interpreter(make_absorb_program())
        vm.regs.write_fp(0, 480.0)
        vm.regs.write_fp(1, 0.0)
        vm.execute()
        result = vm.regs.read_fp(2)
        assert 0.1 < result < 5.0, f"Absorption out of range: {result}"

    def test_absorption_oceanic_clear(self):
        code = make_absorb_program()
        vm = Interpreter(code)
        vm.regs.write_fp(0, 420.0)
        vm.regs.write_fp(1, 1.0)
        vm.execute()
        oceanic = vm.regs.read_fp(2)

        vm2 = Interpreter(code)
        vm2.regs.write_fp(0, 420.0)
        vm2.regs.write_fp(1, 0.0)
        vm2.execute()
        coastal = vm2.regs.read_fp(2)

        assert oceanic < coastal, f"Oceanic ({oceanic}) should be < Coastal ({coastal})"


class TestPhysicsScatter:
    def test_scatter_decreases_with_depth(self):
        code = make_scatter_program()
        vm = Interpreter(code)
        vm.regs.write_fp(0, 480.0)
        vm.regs.write_fp(1, 5.0)
        vm.execute()
        shallow = vm.regs.read_fp(2)

        vm2 = Interpreter(code)
        vm2.regs.write_fp(0, 480.0)
        vm2.regs.write_fp(1, 80.0)
        vm2.execute()
        deep = vm2.regs.read_fp(2)

        assert deep < shallow, f"Deep ({deep}) should be < shallow ({shallow})"


class TestPhysicsJerlov:
    def test_high_chlorophyll_is_coastal(self):
        vm = Interpreter(make_jerlov_program())
        vm.regs.write_fp(0, 10.0)
        vm.regs.write_fp(1, 15.0)
        vm.execute()
        assert vm.regs.read_fp(2) == 0.0


class TestPhysicsThermo:
    def test_thermocline_nonzero(self):
        code = make_thermo_program()
        vm = Interpreter(code)
        vm.regs.write_fp(0, 15.0)
        vm.regs.write_fp(1, 0.0)
        vm.execute()
        result = abs(vm.regs.read_fp(2))
        assert result > 0.0, "Summer thermocline should be non-zero"


class TestPhysicsSeabed:
    def test_rock_reflects_more_than_mud(self):
        code = make_seabed_program()
        vm = Interpreter(code)
        vm.regs.write_fp(0, 30.0)
        vm.regs.write_fp(1, 3.0)
        vm.execute()
        rock = vm.regs.read_fp(2)

        vm2 = Interpreter(code)
        vm2.regs.write_fp(0, 30.0)
        vm2.regs.write_fp(1, 0.0)
        vm2.execute()
        mud = vm2.regs.read_fp(2)

        assert rock > mud, f"Rock ({rock}) should reflect more than mud ({mud})"


class TestPhysicsAttenVisib:
    def test_attenuation_sum(self):
        vm = Interpreter(make_atten_program())
        vm.regs.write_fp(0, 0.5)
        vm.regs.write_fp(1, 0.3)
        vm.execute()
        assert vm.regs.read_fp(2) == pytest.approx(0.8)

    def test_visibility_inverse(self):
        code = make_visib_program()
        vm = Interpreter(code)
        vm.regs.write_fp(0, 0.01)
        vm.regs.write_fp(1, 30.0)
        vm.execute()
        clear = vm.regs.read_fp(2)

        vm2 = Interpreter(code)
        vm2.regs.write_fp(0, 1.0)
        vm2.regs.write_fp(1, 30.0)
        vm2.execute()
        murky = vm2.regs.read_fp(2)

        assert murky < clear, f"Murky ({murky}) should be less than clear ({clear})"


class TestPhysicsSoundSpeed:
    def test_sound_speed_reasonable(self):
        vm = Interpreter(make_soundv_program())
        vm.regs.write_fp(0, 15.0)
        vm.regs.write_fp(1, 35.0)
        vm.execute()
        speed = vm.regs.read_fp(2)
        assert 1400 < speed < 1600, f"Sound speed out of range: {speed}"


class TestPhysicsRefrac:
    def test_refraction_bends_toward_normal(self):
        vm = Interpreter(make_refrac_program())
        vm.regs.write_fp(0, math.radians(30))
        vm.regs.write_fp(1, 1.1)
        vm.execute()
        angle = vm.regs.read_fp(2)
        assert angle < math.radians(30)
