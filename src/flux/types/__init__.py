"""FLUX Types Module — polyglot type unification and compatibility.

Provides:
- TypeUnifier: maps C/Python/Rust types to FIR types
- Type compatibility checking (are_compatible, coercion_cost, least_upper_bound)
- Generic/polymorphic type support (GenericType, TypeVar, TypeScheme)
"""

from .compat import (
    are_compatible,
    coercion_cost,
    compatibility_report,
    least_upper_bound,
)
from .generic import (
    GenericType,
    TypeScheme,
    TypeVar,
    _collect_free_vars,
    _substitute,
    make_map,
    make_option,
    make_result,
    make_scheme,
    make_vec,
)
from .unify import CoercionRule, TypeUnifier

__all__ = [
    "CoercionRule",
    "GenericType",
    "TypeScheme",
    "TypeUnifier",
    "TypeVar",
    "_collect_free_vars",
    "_substitute",
    "are_compatible",
    "coercion_cost",
    "compatibility_report",
    "least_upper_bound",
    "make_map",
    "make_option",
    "make_result",
    "make_scheme",
    "make_vec",
]
