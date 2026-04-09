"""SystemReport — comprehensive report of the FLUX system state.

Generates human-readable text and JSON-compatible dict reports covering
all subsystems: modules, heatmap, language assignments, tiles,
evolution history, and fitness trends.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .synthesizer import FluxSynthesizer


class SystemReport:
    """Comprehensive report of the FLUX system state.

    Sections:
    1. System Overview (name, generation, total modules, total tiles)
    2. Module Hierarchy (nested tree view)
    3. Heat Map (table of modules with heat levels)
    4. Language Assignments (current vs recommended)
    5. Tile Usage (which tiles are composed, most expensive)
    6. Evolution History (mutations applied, speedups)
    7. Fitness Trend (generation -> score)
    """

    def __init__(self, synth: FluxSynthesizer) -> None:
        self.synth = synth
        self._generated_at = time.time()

    # ── Text Report ───────────────────────────────────────────────────────

    def to_text(self) -> str:
        """Generate a human-readable text report.

        Returns:
            Multi-line string with all report sections.
        """
        sections: list[str] = []

        sections.append("=" * 72)
        sections.append("  FLUX SYSTEM REPORT")
        sections.append("=" * 72)
        sections.append("")

        # 1. System Overview
        sections.append(self._section_overview())

        # 2. Module Hierarchy
        sections.append(self._section_hierarchy())

        # 3. Heat Map
        sections.append(self._section_heatmap())

        # 4. Language Assignments
        sections.append(self._section_languages())

        # 5. Tile Usage
        sections.append(self._section_tiles())

        # 6. Evolution History
        sections.append(self._section_evolution())

        # 7. Fitness Trend
        sections.append(self._section_fitness())

        # Footer
        sections.append("")
        sections.append("-" * 72)
        sections.append(f"  Generated at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._generated_at))}")
        sections.append("=" * 72)

        return "\n".join(sections)

    # ── JSON Report ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Generate a JSON-compatible report.

        Returns:
            Dict with all report data.
        """
        synth = self.synth

        # Heat map
        heatmap = synth.profiler.get_heatmap()

        # Recommendations
        recs = synth.get_recommendations()
        recs_dict = {}
        for path, rec in recs.items():
            recs_dict[path] = {
                "recommended": rec.recommended_language,
                "current": rec.current_language,
                "heat": rec.heat_level.name,
                "speed_score": rec.speed_score,
                "expressiveness_score": rec.expressiveness_score,
                "modularity_score": rec.modularity_score,
                "should_change": rec.should_change,
                "reason": rec.reason,
            }

        # Tiles
        tiles_list = []
        for tile in synth.tile_registry.all_tiles[:20]:  # top 20
            tiles_list.append({
                "name": tile.name,
                "type": tile.tile_type.value,
                "inputs": len(tile.inputs),
                "outputs": len(tile.outputs),
                "cost": tile.cost_estimate,
                "abstraction": tile.abstraction_level,
            })

        # Evolution history
        evo_history = synth.get_evolution_history()
        evolution_records = []
        for gen, fitness in evo_history:
            evolution_records.append({
                "generation": gen,
                "fitness": round(fitness, 4),
            })

        # Bottleneck report
        bottleneck = synth.get_bottleneck_report(5)
        bottleneck_entries = []
        for entry in bottleneck.entries:
            bottleneck_entries.append({
                "module": entry.module_path,
                "calls": entry.call_count,
                "total_ns": entry.total_time_ns,
                "heat": entry.heat_level.name,
                "recommendation": entry.recommendation,
            })

        return {
            "overview": {
                "name": synth.name,
                "generation": synth.generation,
                "fitness": round(synth.current_fitness, 4),
                "modules_loaded": synth.module_count,
                "containers": synth.container_count,
                "tiles_registered": synth.tile_count,
                "profiled_modules": synth.profiler.module_count,
                "samples_recorded": synth.profiler.sample_count,
                "reload_history": len(synth.reloader.history),
            },
            "hierarchy": synth.get_hierarchy(),
            "heatmap": {k: v.name for k, v in heatmap.items()},
            "recommendations": recs_dict,
            "tiles": tiles_list,
            "bottlenecks": bottleneck_entries,
            "evolution_history": evolution_records,
            "generated_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(self._generated_at)
            ),
        }

    # ── Section generators ───────────────────────────────────────────────

    def _section_overview(self) -> str:
        synth = self.synth
        stats = synth.stats()
        lines = [
            "1. SYSTEM OVERVIEW",
            "-" * 72,
            f"  Name:              {stats['name']}",
            f"  Generation:        {stats['generation']}",
            f"  Fitness Score:     {stats['fitness']:.4f}",
            f"  Modules Loaded:    {stats['modules']}",
            f"  Containers:        {stats['containers']}",
            f"  Tiles Registered:  {stats['tiles']}",
            f"  Profiled Modules:  {stats['profiled_modules']}",
            f"  Samples Recorded:  {stats['samples']}",
            f"  Evolution Runs:    {stats['evolution_runs']}",
            f"  Reload Events:     {stats['reload_history']}",
            f"  Uptime:            {stats['uptime_s']:.1f}s",
            "",
        ]
        return "\n".join(lines)

    def _section_hierarchy(self) -> str:
        synth = self.synth
        tree = synth.get_module_tree()
        lines = [
            "2. MODULE HIERARCHY",
            "-" * 72,
            tree,
            "",
        ]
        return "\n".join(lines)

    def _section_heatmap(self) -> str:
        synth = self.synth
        heatmap = synth.get_heatmap()

        if not heatmap:
            return (
                "3. HEAT MAP\n"
                + "-" * 72 + "\n"
                + "  No modules profiled yet. Run a workload first.\n\n"
            )

        lines = [
            "3. HEAT MAP",
            "-" * 72,
            f"  {'Module Path':<40} {'Heat':<8} {'Calls':>8} {'Time (ns)':>12}",
            f"  {'-'*40} {'-'*8} {'-'*8} {'-'*12}",
        ]

        # Sort by heat level (HEAT first)
        heat_order = {"HEAT": 4, "HOT": 3, "WARM": 2, "COOL": 1, "FROZEN": 0}
        sorted_modules = sorted(
            heatmap.keys(),
            key=lambda m: (heat_order.get(heatmap[m], 0), m),
            reverse=True,
        )

        for mod in sorted_modules:
            heat = heatmap[mod]
            calls = synth.profiler.call_counts.get(mod, 0)
            total_ns = synth.profiler.total_time_ns.get(mod, 0)
            lines.append(
                f"  {mod:<40} {heat:<8} {calls:>8} {total_ns:>12,}"
            )

        lines.append("")
        return "\n".join(lines)

    def _section_languages(self) -> str:
        synth = self.synth
        recs = synth.get_recommendations()

        if not recs:
            return (
                "4. LANGUAGE ASSIGNMENTS\n"
                + "-" * 72 + "\n"
                + "  No recommendations yet. Profile modules first.\n\n"
            )

        lines = [
            "4. LANGUAGE ASSIGNMENTS",
            "-" * 72,
            f"  {'Module':<40} {'Current':<12} {'Recommended':<12} {'Change':>7}",
            f"  {'-'*40} {'-'*12} {'-'*12} {'-'*7}",
        ]

        for path, rec in sorted(recs.items()):
            change = "YES" if rec.should_change else ""
            current = rec.current_language or "-"
            lines.append(
                f"  {path:<40} {current:<12} {rec.recommended_language:<12} {change:>7}"
            )

        lines.append("")
        return "\n".join(lines)

    def _section_tiles(self) -> str:
        synth = self.synth
        expensive = synth.tile_registry.most_expensive(10)

        lines = [
            "5. TILE USAGE (Top 10 most expensive)",
            "-" * 72,
            f"  {'Tile Name':<30} {'Type':<10} {'Cost':>8} {'Abs':>4} {'Params':>6}",
            f"  {'-'*30} {'-'*10} {'-'*8} {'-'*4} {'-'*6}",
        ]

        for tile in expensive:
            lines.append(
                f"  {tile.name:<30} {tile.tile_type.value:<10} "
                f"{tile.cost_estimate:>8.2f} {tile.abstraction_level:>4} "
                f"{len(tile.params):>6}"
            )

        lines.append(f"\n  Total tiles registered: {synth.tile_count}")
        lines.append("")
        return "\n".join(lines)

    def _section_evolution(self) -> str:
        synth = self.synth
        history = synth.get_evolution_history()

        if not history:
            return (
                "6. EVOLUTION HISTORY\n"
                + "-" * 72 + "\n"
                + "  No evolution has been run yet.\n\n"
            )

        lines = [
            "6. EVOLUTION HISTORY",
            "-" * 72,
            f"  {'Generation':>10} {'Fitness':>12} {'Delta':>10}",
            f"  {'-'*10} {'-'*12} {'-'*10}",
        ]

        prev_fitness = 0.0
        for gen, fitness in history:
            delta = fitness - prev_fitness
            arrow = "+" if delta > 0 else ""
            lines.append(
                f"  {gen:>10} {fitness:>12.4f} {arrow}{delta:>9.4f}"
            )
            prev_fitness = fitness

        lines.append("")
        return "\n".join(lines)

    def _section_fitness(self) -> str:
        synth = self.synth
        history = synth.get_evolution_history()

        lines = [
            "7. FITNESS TREND",
            "-" * 72,
        ]

        if not history:
            lines.append(f"  Current fitness: {synth.current_fitness:.4f}")
            lines.append("  No trend data yet.")
        else:
            # ASCII chart
            if len(history) > 1:
                fitnesses = [f for _, f in history]
                chart_width = 50
                min_f = min(fitnesses) - 0.01
                max_f = max(fitnesses) + 0.01
                f_range = max_f - min_f if max_f > min_f else 0.01

                chart_lines: list[str] = []
                for gen, fitness in history:
                    bar_len = int((fitness - min_f) / f_range * chart_width)
                    bar = "#" * max(1, bar_len)
                    chart_lines.append(
                        f"  Gen {gen:>3}: {bar} {fitness:.4f}"
                    )

                lines.extend(chart_lines)
            else:
                gen, fitness = history[0]
                lines.append(f"  Gen {gen}: {fitness:.4f}")

            lines.append("")
            lines.append(f"  Current: {synth.current_fitness:.4f}")

            if len(history) >= 2:
                improvement = history[-1][1] - history[0][1]
                lines.append(
                    f"  Total improvement: {improvement:+.4f}"
                )

        lines.append("")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SystemReport({self.synth.name!r}, "
            f"generated={time.strftime('%H:%M:%S', time.localtime(self._generated_at))})"
        )
