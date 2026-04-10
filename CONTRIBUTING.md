# Contributing to FLUX

Thank you for your interest in FLUX — a self-assembling, self-improving bytecode
runtime designed for agent-first code. This guide will help you get started
contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding Features](#adding-features)
- [Pull Request Checklist](#pull-request-checklist)
- [Community Guidelines](#community-guidelines)

## Getting Started

### Prerequisites

- Python 3.11+ (3.12 recommended)
- [uv](https://docs.astral.sh/uv/) or pip for dependency management
- Git

### Clone and Install

```bash
git clone https://github.com/your-org/flux-repo.git
cd flux-repo

# Install in development mode (editable)
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

### Verify Tests Pass

```bash
pytest tests/ -q

# You should see ~1848 tests pass
```

If all tests pass, your environment is correctly set up.

## Development Workflow

1. **Branch** — Create a feature or fix branch from `main`:

   ```bash
   git checkout main
   git pull
   git checkout -b feat/your-feature-name
   # or: git checkout -b fix/issue-description
   ```

2. **Code** — Make your changes, following the [code style](#code-style) guide.

3. **Test** — Write tests for your changes (see [Testing](#testing)):

   ```bash
   pytest tests/ -q
   pytest tests/your_test_file.py -v    # run a specific file
   pytest -k "test_name_pattern" -v     # run matching tests
   ```

4. **Commit** — Use [Conventional Commits](https://www.conventionalcommits.org/):

   ```
   feat(tiles): add map-reduce tile for parallel collections
   fix(vm): handle ALLOCA overflow edge case
   test(fir): add coverage for struct field access
   docs: update README with new CLI commands
   refactor(optimizer): simplify constant folding pass
   ```

5. **Push & PR** — Push your branch and open a pull request against `main`.

## Code Style

FLUX follows a strict, consistent style across the entire codebase.

### Formatters

- **[ruff](https://docs.astral.sh/ruff/)** — linting and import sorting
- **[black](https://black.readthedocs.io/)** — code formatting (line length 100)

Run the formatters before committing:

```bash
ruff check --fix src/ tests/
black src/ tests/
```

### Data Structures

- Use **frozen dataclasses** (`@dataclass(frozen=True)`) for all IR types,
  value objects, and configuration structs.
- Use mutable dataclasses with `field(default_factory=...)` only for
  containers that must track incremental state (builders, VM state, etc.).

```python
# Good
@dataclass(frozen=True)
class IntType(FIRType):
    bits: int
    signed: bool

# Acceptable when mutability is required
@dataclass
class FIRBlock:
    label: str
    instructions: list[Instruction] = field(default_factory=list)
```

### Type Hints

- All public functions **must** have full type annotations (parameters and
  return types).
- Use `from __future__ import annotations` at the top of every module for
  forward-reference support.
- Prefer `Optional[X]` over `X | None` for clarity in data-heavy code.

```python
from __future__ import annotations
from typing import Optional

def compile_module(source: str, language: str = "python") -> FIRModule:
    ...
```

### Naming

- **Modules/files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Test files**: `test_<module>.py`
- **Test functions**: `test_<description>` or `test_<unit>_<scenario>`

## Testing

FLUX uses **pytest** as its test framework. The project currently has
**1,848 tests** across 30 test files, and we aim for **>90% code coverage**.

### Running Tests

```bash
# Run all tests
pytest tests/ -q

# Run with coverage report
pytest tests/ --cov=flux --cov-report=term-missing

# Run a single test file
pytest tests/test_vm.py -v

# Run tests matching a name pattern
pytest -k "test_mov" -v

# Run only the tests you changed (use with pre-commit hooks)
pytest tests/ --lf       # last-failed
pytest tests/ --sw       # step-wise (stop on first failure)
```

### Writing Tests

- Place tests in `tests/test_<module>.py` matching the source module.
- Use shared fixtures from `tests/conftest.py` when available.
- Each test should be **independent** — no shared mutable state between tests.
- Use descriptive names that explain the expected behavior:

  ```python
  # Good
  def test_mov_copies_source_register_to_destination():
      ...

  # Avoid
  def test_mov():
      ...
  ```

- Test both the **happy path** and **error cases** (invalid inputs, edge cases,
  boundary conditions).

- For VM-level tests, construct raw bytecode bytes directly (see
  `tests/test_vm.py` for encoding patterns).

### Test File Map

| Test File | Covers |
|---|---|
| `test_parser.py` | Source parser |
| `test_fir.py` | FIR intermediate representation |
| `test_bytecode.py` | Bytecode encoder/decoder |
| `test_vm.py` | Micro-VM interpreter |
| `test_vm_complete.py` | Full VM instruction set |
| `test_optimizer.py` | Optimization passes |
| `test_jit.py` | JIT compiler |
| `test_type_unify.py` | Polyglot type unification |
| `test_frontends.py` | C and Python frontends |
| `test_stdlib.py` | Standard library intrinsics |
| `test_a2a.py` | A2A protocol |
| `test_runtime.py` | Agent runtime |
| `test_security.py` | Capabilities & sandbox |
| `test_tiles.py` | Tile system |
| `test_modules.py` | Module hierarchy |
| `test_reload.py` | Hot reload |
| `test_evolution.py` | Self-evolution engine |
| `test_synthesis.py` | Synthesis orchestrator |
| `test_adaptive.py` | Adaptive profiling |
| `test_flywheel.py` | Flywheel subsystem |
| `test_swarm.py` | Swarm orchestration |
| `test_simulation.py` | Simulation & prediction |
| `test_memory.py` | Memory & learning |
| `test_creative.py` | Creative subsystem |
| `test_cost.py` | Cost model |
| `test_schema.py` | Schema generators |
| `test_docs.py` | Self-documentation |
| `test_protocol.py` | Protocol negotiation |
| `test_integration.py` | End-to-end pipelines |
| `test_mega.py` | MEGA conductor |

## Adding Features

### New Tiles

1. Define your tile in `src/flux/tiles/` implementing the `Tile` interface.
2. Register it in `src/flux/tiles/library.py` with the appropriate category.
3. Add tests in `tests/test_tiles.py`.
4. Update the tile schema in `src/flux/schema/tile_schema.py`.

### New Frontends

1. Create a new compiler in `src/flux/frontend/<language>_frontend.py`.
2. Implement `compile_to_fir(source: str) -> FIRModule`.
3. Add tests in `tests/test_frontends.py`.
4. Register the frontend in the polyglot pipeline.

### New Mutation Strategies

1. Add the mutation operator in `src/flux/evolution/mutator.py`.
2. Define a fitness function for the strategy.
3. Add validation logic in `src/flux/evolution/validator.py`.
4. Add tests in `tests/test_evolution.py`.

## Pull Request Checklist

Before submitting a PR, verify the following:

- [ ] All existing tests pass: `pytest tests/ -q`
- [ ] New tests added for the feature/fix
- [ ] Code formatted with `ruff` and `black`
- [ ] No linting warnings: `ruff check src/ tests/`
- [ ] Type annotations complete on public APIs
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] Documentation updated (docstrings, inline comments)
- [ ] `CHANGELOG.md` updated (if user-facing change)
- [ ] PR description clearly explains the change and motivation

## Community Guidelines

- **Be respectful** — Treat all contributors with respect and dignity.
  We are building something ambitious together; diverse perspectives make it
  stronger.

- **Constructive reviews** — Code reviews should be constructive and
  specific. Focus on the code, not the person. Explain *why* a change is
  suggested and offer alternatives when possible.

- **Ask questions** — If something is unclear, ask. There are no stupid
  questions. FLUX has many interconnected subsystems, and onboarding can be
  challenging — we are here to help.

- **Incremental progress** — Prefer small, focused PRs over large
  monolithic changes. This makes review easier and reduces the risk of
  regressions.

- **Stay curious** — FLUX explores novel territory (self-evolving runtimes,
  agent-to-agent protocols, polyglot compilation). Experimentation and bold
  ideas are welcome, even when they don't immediately work out.

For the full community code of conduct, see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
