"""FLUX Migrate — Convert existing source code to FLUX.MD format.

Provides the FluxMigrator class for converting Python, C, and JavaScript
source files into structured FLUX.MD documents ready for the FLUX pipeline.
"""

from flux.migrate.migrator import FluxMigrator
from flux.migrate.report import MigrationReport, MigratedFile

__all__ = ["FluxMigrator", "MigrationReport", "MigratedFile"]
