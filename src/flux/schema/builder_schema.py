"""Builder Schema — guides for extending FLUX and open research questions.

This module provides machine-readable documentation that tells future AI agents
(and human developers) exactly how to extend and improve the FLUX system.
"""

from __future__ import annotations
from typing import Any


FLUX_BUILDER_SCHEMA: dict[str, dict[str, Any]] = {
    "how_to_add_a_tile": {
        "description": "Create a new composable computation tile",
        "steps": [
            "1. Create a Tile instance in flux/tiles/library.py (or a new file)",
            "2. Choose a TileType: COMPUTE, MEMORY, CONTROL, A2A, EFFECT, or TRANSFORM",
            "3. Define input TilePorts with FIR types (e.g., TilePort('data', PortDirection.INPUT, i32))",
            "4. Define output TilePorts with FIR types",
            "5. Define parameters with defaults (e.g., params={'fn': '_my_fn'})",
            "6. Implement fir_blueprint(builder, inputs, params) -> dict[str, Value]",
            "   - Use builder.call(), builder.getelem(), builder.setelem(), etc.",
            "   - Return dict mapping output port names to FIR Values",
            "7. Set cost_estimate (relative: NOP=0.0, gather=1.0, broadcast=15.0)",
            "8. Set abstraction_level (0-10: 0=raw opcodes, 10=very high-level)",
            "9. Add tags (set of strings for searchability)",
            "10. Append to ALL_BUILTIN_TILES list",
            "11. Add tests in tests/test_tiles.py (create instance, test to_fir, test ports)",
        ],
        "example": (
            "from flux.tiles.tile import Tile, TileType\n"
            "from flux.tiles.ports import TilePort, PortDirection\n"
            "\n"
            "my_tile = Tile(\n"
            "    name='double',\n"
            "    tile_type=TileType.COMPUTE,\n"
            "    inputs=[TilePort('x', PortDirection.INPUT, i32)],\n"
            "    outputs=[TilePort('result', PortDirection.OUTPUT, i32)],\n"
            "    fir_blueprint=lambda b, inp, p: {'result': b.iadd(inp['x'], inp['x'])},\n"
            "    cost_estimate=0.5,\n"
            "    abstraction_level=3,\n"
            "    tags={'compute', 'arithmetic', 'double'},\n"
            ")\n"
        ),
        "constraints": [
            "All ports must use FIR types from flux.fir.types (e.g., IntType, FloatType, BoolType)",
            "fir_blueprint must use the provided FIRBuilder, not create its own",
            "Cost estimate must be relative to other tiles (NOP=0.0, VADD=2.0, BROADCAST=15.0)",
            "Tile names must be unique across the registry",
            "fir_blueprint must return a dict with output port names as keys",
        ],
        "files_to_modify": [
            "src/flux/tiles/library.py",
            "tests/test_tiles.py",
        ],
    },

    "how_to_add_an_opcode": {
        "description": "Add a new bytecode instruction to the FLUX VM",
        "steps": [
            "1. Add to Op enum in src/flux/bytecode/opcodes.py with next available value",
            "2. Choose encoding format:",
            "   - Format A (1 byte): no operands (e.g., NOP, HALT)",
            "   - Format B (2 bytes): single register (e.g., INC, NEG)",
            "   - Format C (3 bytes): two registers rd, rs (e.g., IADD, MOV)",
            "   - Format D (4 bytes): register + 16-bit immediate (e.g., JMP, MOVI)",
            "   - Format E (4 bytes): three registers rd, rs1, rs2 (e.g., VFMA)",
            "   - Format G (variable): length-prefixed payload (e.g., TELL, BROADCAST)",
            "3. Add opcode to the appropriate FORMAT_X frozenset",
            "4. Add handler in src/flux/vm/interpreter.py _step() method",
            "5. Add encoder support in src/flux/bytecode/encoder.py _encode_instruction()",
            "6. Decoder support is automatic via format detection",
            "7. Add test for encode/decode/execute roundtrip in tests/test_bytecode.py",
            "8. Update this schema if the opcode is in a new category",
        ],
        "example": (
            "# opcodes.py\n"
            "XOR3 = 0x58  # Next available after STORE8\n"
            "\n"
            "# Add to FORMAT_E\n"
            "FORMAT_E = frozenset({Op.VFMA, Op.XOR3})\n"
            "\n"
            "# interpreter.py _step():\n"
            "elif op == Op.XOR3:\n"
            "    rd = self._read_reg(self._fetch_u8())\n"
            "    rs1 = self._read_reg(self._fetch_u8())\n"
            "    rs2 = self._read_reg(self._fetch_u8())\n"
            "    self._write_reg(rd, rs1 ^ rs2 ^ rs2)  # example\n"
        ),
        "constraints": [
            "Opcodes must be in the Op IntEnum with unique values",
            "Register indices must be < 64 (masked with 0x3F)",
            "Format G opcodes require explicit encoder and decoder support",
            "New opcodes must have get_format() return the correct format letter",
            "All opcodes should have instruction_size() return correct byte count (-1 for Format G)",
        ],
        "files_to_modify": [
            "src/flux/bytecode/opcodes.py",
            "src/flux/vm/interpreter.py",
            "src/flux/bytecode/encoder.py",
            "tests/test_bytecode.py",
            "tests/test_vm.py",
        ],
    },

    "how_to_add_a_language_frontend": {
        "description": "Add support for a new programming language",
        "steps": [
            "1. Create src/flux/frontend/{lang}_frontend.py",
            "2. Implement parse(source: str) -> list of AST-like nodes",
            "   - Can use Python's ast module, regex, or a custom parser",
            "3. Implement to_fir(nodes, builder: FIRBuilder) -> FIRModule",
            "   - Map language constructs to FIR instructions",
            "   - Variables -> SSA values via builder",
            "   - Functions -> FIRFunction with blocks",
            "   - Control flow -> branch/jump/ret instructions",
            "4. Add type mappings to src/flux/types/unify.py TypeUnifier",
            "   - Map language types to FIR types (to_fir, from_fir)",
            "5. Register language profile in src/flux/adaptive/selector.py",
            "   - Create LanguageProfile with 7 tiers (speed, expressiveness, etc.)",
            "6. Register compiler in CompilerBridge (src/flux/adaptive/compiler_bridge.py)",
            "7. Add tests covering parse, FIR emission, and type mapping",
        ],
        "example": (
            "# rust_frontend.py\n"
            "def parse(source: str) -> list:\n"
            "    # Parse Rust source into AST nodes\n"
            "    ...\n"
            "\n"
            "def to_fir(nodes, builder):\n"
            "    module = builder.new_module('rust_module')\n"
            "    for node in nodes:\n"
            "        _emit_node(builder, module, node)\n"
            "    return module\n"
        ),
        "constraints": [
            "All types must map to FIR types (IntType, FloatType, BoolType, etc.)",
            "Functions must produce FIRFunctions with proper signatures",
            "Control flow must use FIR branch/jump/ret (not Python exceptions)",
            "Language profiles must have all 7 tiers scored 1-10",
            "Frontend must handle at least basic arithmetic, functions, and control flow",
        ],
        "files_to_modify": [
            "src/flux/frontend/{lang}_frontend.py",
            "src/flux/types/unify.py",
            "src/flux/adaptive/selector.py",
            "src/flux/adaptive/compiler_bridge.py",
            "tests/test_frontends.py",
        ],
    },

    "how_to_add_an_evolution_strategy": {
        "description": "Add a new self-improvement strategy for the evolution engine",
        "steps": [
            "1. Add to MutationStrategy enum in src/flux/evolution/genome.py",
            "2. Implement propose logic in SystemMutator.propose_mutations()",
            "   - src/flux/evolution/mutator.py",
            "   - Create MutationProposal with estimated_risk and estimated_speedup",
            "3. Implement apply logic in SystemMutator.apply_mutation()",
            "   - Modify the genome copy according to the strategy",
            "4. Add to bandit arms in src/flux/memory/bandit.py MutationBandit",
            "   - Each strategy gets a Thompson Sampling arm",
            "5. Add to knowledge base condition patterns in src/flux/flywheel/knowledge.py",
            "6. Add tests: proposal generation, application, rollback",
        ],
        "example": (
            "# genome.py\n"
            "class MutationStrategy(Enum):\n"
            "    RECOMPILE_LANGUAGE = 'recompile_language'\n"
            "    ...\n"
            "    CONST_PROPAGATE = 'const_propagate'  # NEW\n"
            "\n"
            "# mutator.py\n"
            "if strategy == MutationStrategy.CONST_PROPAGATE:\n"
            "    proposal = MutationProposal(\n"
            "        strategy=strategy,\n"
            "        target=target,\n"
            "        description=f'Propagate constants in {target}',\n"
            "        estimated_speedup=1.1,\n"
            "        estimated_risk=0.1,\n"
            "    )\n"
        ),
        "constraints": [
            "All strategies must be in MutationStrategy enum",
            "Proposals must include estimated_risk and estimated_speedup",
            "Apply must work on a genome copy (never mutate in-place)",
            "Rollback must be possible (genome has deep copy support)",
            "Risk tolerance filter must be respected",
        ],
        "files_to_modify": [
            "src/flux/evolution/genome.py",
            "src/flux/evolution/mutator.py",
            "src/flux/memory/bandit.py",
            "src/flux/flywheel/knowledge.py",
            "tests/test_evolution.py",
        ],
    },

    "how_to_add_a_module_granularity": {
        "description": "Add a new nesting level to the fractal module hierarchy",
        "steps": [
            "1. Add to Granularity enum in src/flux/modules/granularity.py",
            "2. Set reload_cost (1-10, higher = more expensive to reload)",
            "3. Set isolation (1-10, higher = more isolated from siblings)",
            "4. Set typical_size (approximate number of cards at this level)",
            "5. Update FractalReloader.reload_strategy() if needed",
            "   - src/flux/modules/reloader.py",
            "   - The strategy uses card counts to recommend granularity",
            "6. Update should_reload_to() if new level changes the hierarchy",
            "7. Add tests in tests/test_modules.py",
        ],
        "example": (
            "# granularity.py\n"
            "class Granularity(Enum):\n"
            "    TRAIN = 0\n"
            "    ...\n"
            "    CARD = 7\n"
            "    ATOM = 8  # NEW: even finer than CARD\n"
            "\n"
            "# In GranularityMeta or lookup table:\n"
            "# ATOM: reload_cost=1, isolation=10, typical_size=1\n"
        ),
        "constraints": [
            "Granularity levels must be ordered (higher = finer granularity)",
            "reload_cost must be monotonically decreasing (finer = cheaper)",
            "isolation must be monotonically increasing (finer = more isolated)",
            "typical_size should decrease with granularity level",
            "The 8 existing levels go from TRAIN (0) to CARD (7)",
        ],
        "files_to_modify": [
            "src/flux/modules/granularity.py",
            "src/flux/modules/reloader.py",
            "tests/test_modules.py",
        ],
    },
}


def get_builder_schema() -> dict[str, dict[str, Any]]:
    """Return the full builder extension schema."""
    return FLUX_BUILDER_SCHEMA


def get_open_questions() -> list[dict[str, Any]]:
    """Open research questions for future builders.

    These represent fundamental questions about the FLUX architecture
    that remain unanswered and could guide future research and development.
    """
    return [
        {
            "id": "Q1",
            "question": "Can the system achieve fixed-point optimization?",
            "detail": (
                "When the evolution engine optimizes the optimizer, "
                "and the improved optimizer optimizes the system, "
                "does the process converge to a fixed point? "
                "Or does it oscillate? This relates to Kleene's "
                "fixed-point theorem in lattice theory."
            ),
            "difficulty": "hard",
            "area": "theory",
        },
        {
            "id": "Q2",
            "question": "What is the Godelian limit of self-improvement?",
            "detail": (
                "A system cannot prove all truths about itself "
                "(Godel's incompleteness theorem). How does this "
                "constrain the self-evolution engine? Can the system "
                "recognize when it has reached a fundamental limit?"
            ),
            "difficulty": "very_hard",
            "area": "theory",
        },
        {
            "id": "Q3",
            "question": "Can agents develop culture (persistent shared patterns)?",
            "detail": (
                "When agents communicate through the A2A protocol, "
                "can stable cultural norms emerge? This requires "
                "persistent shared state across agent generations "
                "and selection pressure for cooperation."
            ),
            "difficulty": "medium",
            "area": "multi_agent",
        },
        {
            "id": "Q4",
            "question": "Is there a fundamental tension between creativity and efficiency?",
            "detail": (
                "Maximum expressiveness (Python) vs maximum speed "
                "(C+SIMD) represent opposite ends of a spectrum. "
                "Can the adaptive selector find a Pareto-optimal "
                "balance, or must it always sacrifice one for the other?"
            ),
            "difficulty": "medium",
            "area": "design",
        },
        {
            "id": "Q5",
            "question": "What is the optimal tile composition for a given problem domain?",
            "detail": (
                "With 34+ tiles and combinatorial DAG composition, "
                "the search space for optimal tile graphs is enormous. "
                "Can the evolution engine discover domain-specific "
                "tile compositions that outperform hand-crafted ones?"
            ),
            "difficulty": "hard",
            "area": "optimization",
        },
        {
            "id": "Q6",
            "question": "How do you validate that a self-improving system hasn't introduced subtle bugs?",
            "detail": (
                "Behavioral equivalence testing is undecidable in general "
                "(Rice's theorem). The correctness validator can only "
                "check a finite set of test cases. Can the digital twin "
                "simulation provide probabilistic correctness guarantees?"
            ),
            "difficulty": "very_hard",
            "area": "verification",
        },
        {
            "id": "Q7",
            "question": "Can the system generalize improvements across different workloads?",
            "detail": (
                "Transfer learning for code optimization: an improvement "
                "discovered for workload A may or may not help workload B. "
                "What determines transferability? Can the knowledge base "
                "learn when to generalize vs. when to specialize?"
            ),
            "difficulty": "hard",
            "area": "learning",
        },
        {
            "id": "Q8",
            "question": "What is the minimum viable bootstrap set for self-hosting?",
            "detail": (
                "How much of FLUX needs to be working before FLUX can "
                "compile FLUX? The parser, FIR, bytecode encoder, and VM "
                "form a natural bootstrap chain. Can the tile system "
                "express the compiler itself?"
            ),
            "difficulty": "medium",
            "area": "bootstrap",
        },
        {
            "id": "Q9",
            "question": "How should the system handle conflicting optimization goals?",
            "detail": (
                "Speed vs energy vs modularity vs correctness — "
                "multi-objective tradeoffs. The fitness function uses "
                "fixed weights (0.4/0.3/0.3). Should these be adaptive? "
                "Can the decision oracle find Pareto fronts?"
            ),
            "difficulty": "medium",
            "area": "design",
        },
        {
            "id": "Q10",
            "question": "Can digital twin predictions be made arbitrarily accurate?",
            "detail": (
                "What is the theoretical limit of simulation fidelity? "
                "The digital twin runs a shadow copy of the system, but "
                "the shadow has finite resources. There are fundamental "
                "limits related to computational irreducibility "
                "(Wolfram) and chaotic systems."
            ),
            "difficulty": "hard",
            "area": "simulation",
        },
    ]
