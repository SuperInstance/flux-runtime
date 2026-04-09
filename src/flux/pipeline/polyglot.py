"""Polyglot compilation pipeline — compile C, Python, or mixed-language source
to unified FIR and bytecode using cross-language type unification."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

from flux.fir.types import TypeContext, FIRType
from flux.fir.blocks import FIRModule
from flux.types.unify import TypeUnifier


@dataclass
class PolyglotSource:
    """A single source unit in the polyglot pipeline.

    Attributes
    ----------
    lang : str
        Source language ("c", "python").
    source : str
        Source code text.
    function_name : str
        Optional override for the function name.
    """

    lang: str
    source: str
    function_name: str = ""


@dataclass
class PolyglotResult:
    """Result of a polyglot compilation.

    Attributes
    ----------
    module : FIRModule
        The unified FIR module containing all compiled functions.
    bytecode : bytes
        The compiled FLUX bytecode.
    type_mappings : dict[str, FIRType]
        Mapping of function name → return type.
    errors : list[str]
        Any errors encountered.
    """

    module: Optional[FIRModule] = None
    bytecode: Optional[bytes] = None
    type_mappings: dict[str, FIRType] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class PolyglotCompiler:
    """Compiles mixed-language sources into a unified FIR module.

    Uses TypeUnifier for cross-language type resolution so that functions
    from different languages can interoperate within a single module.

    Parameters
    ----------
    type_ctx : TypeContext | None
        Shared type context. If None, a new one is created.
    optimize : bool
        Whether to run optimization passes.
    """

    def __init__(
        self,
        type_ctx: Optional[TypeContext] = None,
        optimize: bool = True,
    ) -> None:
        self._ctx = type_ctx or TypeContext()
        self._unifier = TypeUnifier(self._ctx)
        self.optimize = optimize

    @property
    def unifier(self) -> TypeUnifier:
        """Access the type unifier for cross-language type resolution."""
        return self._unifier

    @property
    def type_ctx(self) -> TypeContext:
        """Access the shared type context."""
        return self._ctx

    def compile(
        self,
        sources: list[PolyglotSource],
        module_name: str = "polyglot_module",
    ) -> PolyglotResult:
        """Compile multiple source units into a unified FIR module.

        Parameters
        ----------
        sources : list[PolyglotSource]
            Source units to compile. Each unit is compiled independently,
            then merged into a single module.
        module_name : str
            Name for the output FIR module.

        Returns
        -------
        PolyglotResult with the unified module and bytecode.
        """
        result = PolyglotResult()

        try:
            from flux.fir.builder import FIRBuilder
            from flux.bytecode.encoder import BytecodeEncoder

            # Create the target module
            builder = FIRBuilder(self._ctx)
            target_module = builder.new_module(module_name)

            # Compile each source unit
            for src in sources:
                sub_module = self._compile_one(src)

                if sub_module is None:
                    result.errors.append(
                        f"Failed to compile {src.lang} source"
                    )
                    continue

                # Merge functions into the target module
                for fname, func in sub_module.functions.items():
                    if fname in target_module.functions:
                        result.errors.append(
                            f"Duplicate function name: {fname}"
                        )
                        continue
                    target_module.functions[fname] = func

                    # Track return type mapping
                    if func.sig.returns:
                        result.type_mappings[fname] = func.sig.returns[0]

                # Merge structs
                for sname, stype in sub_module.structs.items():
                    if sname not in target_module.structs:
                        target_module.structs[sname] = stype

            # Optimize
            if self.optimize:
                from flux.optimizer.pipeline import OptimizationPipeline
                pipeline = OptimizationPipeline()
                pipeline.run(target_module)

            result.module = target_module

            # Encode to bytecode
            encoder = BytecodeEncoder()
            result.bytecode = encoder.encode(target_module)

        except Exception as e:
            result.errors.append(f"{type(e).__name__}: {e}")

        return result

    def _compile_one(self, src: PolyglotSource) -> Optional[FIRModule]:
        """Compile a single source unit to FIR."""
        lang = src.lang.lower().strip()

        if lang == "c":
            return self._compile_c(src.source)
        elif lang in ("python", "py"):
            return self._compile_python(src.source)
        else:
            return None

    def _compile_c(self, source: str) -> FIRModule:
        """Compile C source to FIR."""
        from flux.frontend.c_frontend import CFrontendCompiler
        compiler = CFrontendCompiler()
        return compiler.compile(source)

    def _compile_python(self, source: str) -> FIRModule:
        """Compile Python source to FIR."""
        from flux.frontend.python_frontend import PythonFrontendCompiler
        compiler = PythonFrontendCompiler()
        return compiler.compile(source)

    def unify_types(self, type_a: str, lang_a: str, type_b: str, lang_b: str) -> Optional[FIRType]:
        """Unify two types from different languages.

        Parameters
        ----------
        type_a, type_b : str
            Type names in their respective language syntax.
        lang_a, lang_b : str
            Source language identifiers ("c", "python", "rust").

        Returns
        -------
        FIRType if unification succeeds, None otherwise.
        """
        fir_a = self._unifier.map_type(type_a, lang_a)
        fir_b = self._unifier.map_type(type_b, lang_b)
        return self._unifier.unify(fir_a, fir_b)

    def resolve_signature(
        self,
        param_types: list[tuple[str, str]],
        return_type: str,
        source_lang: str = "c",
    ) -> tuple[list[tuple[str, FIRType]], FIRType]:
        """Resolve a function signature from source-language types to FIR types.

        Parameters
        ----------
        param_types : list[tuple[str, str]]
            List of (name, type_string) pairs.
        return_type : str
            Return type string.
        source_lang : str
            Language of the type strings.

        Returns
        -------
        Tuple of (params as (name, FIRType), return FIRType).
        """
        params = []
        for name, type_str in param_types:
            fir_type = self._unifier.map_type(type_str, source_lang)
            params.append((name, fir_type))
        ret = self._unifier.map_type(return_type, source_lang)
        return params, ret
