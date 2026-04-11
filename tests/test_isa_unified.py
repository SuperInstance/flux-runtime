"""Tests for the unified FLUX ISA opcode table."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.bytecode.isa_unified import build_unified_isa, isa_stats, isa_markdown_table


class TestISACompleteness:
    def test_all_256_slots(self):
        ops = build_unified_isa()
        assert len(ops) == 256
    
    def test_no_duplicate_opcodes(self):
        ops = build_unified_isa()
        codes = [o.opcode for o in ops]
        assert len(codes) == len(set(codes)), f"Duplicates: {[c for c in codes if codes.count(c) > 1]}"
    
    def test_sequential_opcodes(self):
        ops = build_unified_isa()
        codes = sorted([o.opcode for o in ops])
        assert codes == list(range(256))
    
    def test_defined_count(self):
        stats = isa_stats(build_unified_isa())
        assert stats["defined"] >= 200
        assert stats["reserved"] <= 56


class TestISACategories:
    def test_system_ops(self):
        ops = build_unified_isa()
        sys_ops = [o for o in ops if o.category == "system" and not o.reserved]
        assert len(sys_ops) >= 10
    
    def test_arithmetic_ops(self):
        ops = build_unified_isa()
        arith = [o for o in ops if o.category == "arithmetic" and not o.reserved]
        assert len(arith) >= 10
    
    def test_float_ops(self):
        ops = build_unified_isa()
        floats = [o for o in ops if o.category == "float" and not o.reserved]
        assert len(floats) >= 6
    
    def test_a2a_ops(self):
        ops = build_unified_isa()
        a2a = [o for o in ops if o.category == "a2a" and not o.reserved]
        assert len(a2a) >= 12
    
    def test_confidence_ops(self):
        ops = build_unified_isa()
        conf = [o for o in ops if o.confidence and not o.reserved]
        assert len(conf) >= 12
    
    def test_viewpoint_ops(self):
        ops = build_unified_isa()
        vp = [o for o in ops if o.category == "viewpoint" and not o.reserved]
        assert len(vp) == 16
    
    def test_sensor_ops(self):
        ops = build_unified_isa()
        sensor = [o for o in ops if o.category == "sensor" and not o.reserved]
        assert len(sensor) >= 10
    
    def test_tensor_ops(self):
        ops = build_unified_isa()
        tensor = [o for o in ops if o.category == "tensor" and not o.reserved]
        assert len(tensor) >= 10
    
    def test_crypto_ops(self):
        ops = build_unified_isa()
        crypto = [o for o in ops if o.category == "crypto" and not o.reserved]
        assert len(crypto) >= 5
    
    def test_vector_ops(self):
        ops = build_unified_isa()
        vec = [o for o in ops if o.category == "vector" and not o.reserved]
        assert len(vec) >= 10


class TestISASources:
    def test_oracle1_contributions(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_source"].get("oracle1", 0) >= 20
    
    def test_jetsonclaw1_contributions(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_source"].get("jetsonclaw1", 0) >= 30
    
    def test_babel_contributions(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_source"].get("babel", 0) == 16
    
    def test_converged_ops(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_source"].get("converged", 0) >= 40
    
    def test_all_sources_represented(self):
        stats = isa_stats(build_unified_isa())
        assert "oracle1" in stats["by_source"]
        assert "jetsonclaw1" in stats["by_source"]
        assert "babel" in stats["by_source"]


class TestISAFormats:
    def test_format_a_ops(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_format"].get("A", 0) >= 10
    
    def test_format_e_dominant(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_format"].get("E", 0) >= 100
    
    def test_format_g_ops(self):
        stats = isa_stats(build_unified_isa())
        assert stats["by_format"].get("G", 0) >= 10


class TestISAMarkdown:
    def test_table_generation(self):
        ops = build_unified_isa()
        md = isa_markdown_table(ops)
        assert "| 0x00 |" in md
        assert "| 0xFF |" in md
        assert "Total:" in md


class TestISAKeyOpcodes:
    def test_stripconf_exists(self):
        ops = build_unified_isa()
        sc = [o for o in ops if o.mnemonic == "STRIPCF"]
        assert len(sc) == 1
        assert sc[0].opcode == 0x17
    
    def test_halt_at_zero(self):
        ops = build_unified_isa()
        assert ops[0].mnemonic == "HALT"
        assert ops[0].opcode == 0x00
    
    def test_illegal_at_ff(self):
        ops = build_unified_isa()
        illegal = [o for o in ops if o.opcode == 0xFF]
        assert illegal[0].mnemonic == "ILLEGAL"
    
    def test_viewpoint_range(self):
        ops = build_unified_isa()
        vp = [o for o in ops if 0x70 <= o.opcode <= 0x7F]
        assert all(o.category == "viewpoint" for o in vp)
        assert all(o.source == "babel" for o in vp)
    
    def test_confidence_range(self):
        ops = build_unified_isa()
        conf = [o for o in ops if 0x60 <= o.opcode <= 0x6F and not o.reserved]
        assert all(o.confidence for o in conf)
