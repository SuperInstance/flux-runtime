"""FLUX Synthesis Demo — shows the system improving itself.

Runnable as: python -m flux.synthesis.demo

This demo:
1. Creates a synthesizer
2. Loads several modules at different nesting levels
3. Runs a workload that exercises the modules
4. Shows the profiler classifying them (COOL/WARM/HOT/HEAT)
5. Runs the evolution engine for a few generations
6. Shows that modules got recompiled to faster languages
7. Shows the fitness score improving
8. Demonstrates hot-reloading a single card without affecting the rest
"""

from __future__ import annotations


def run_demo() -> None:
    """Run the full FLUX synthesis demo."""
    import time
    from flux.synthesis.synthesizer import FluxSynthesizer

    print("=" * 72)
    print("  FLUX SYNTHESIS DEMO — The System That Improves Itself")
    print("=" * 72)
    print()

    # ── Step 1: Create the synthesizer ───────────────────────────────────
    print("Step 1: Creating synthesizer...")
    synth = FluxSynthesizer("audio_processing_app")
    print(f"  Created: {synth}")
    print()

    # ── Step 2: Load modules at different nesting levels ─────────────────
    print("Step 2: Loading modules at different nesting levels...")
    modules = {
        "audio/input": "def read_audio(file): return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]",
        "audio/dsp/filter": "def apply_filter(samples, coeff): return [s * coeff for s in samples]",
        "audio/dsp/reverb": "def add_reverb(samples, decay=0.5): return [s * decay for s in samples]",
        "audio/output/mixer": "def mix_tracks(tracks): return sum(tracks) / len(tracks)",
        "audio/output/encoder": "def encode(samples): return bytes(samples)",
        "utils/logger": "def log(msg): print(msg)",
    }

    for path, source in modules.items():
        card = synth.load_module(path, source, language="python")
        print(f"  Loaded: {path} -> {card.name} (v{card.version})")

    print(f"\n  Module tree:")
    for line in synth.get_module_tree().split("\n"):
        print(f"    {line}")
    print()

    # ── Step 3: Run a workload that exercises the modules ────────────────
    print("Step 3: Running workload to profile modules...")
    print("  Simulating audio processing pipeline...")

    # Simulate execution with varying frequencies (hot/cold paths)
    # The reverb filter is the bottleneck — called most frequently
    synth.record_call("audio_processing_app.audio.dsp.filter", duration_ns=50000, calls=100)
    synth.record_call("audio_processing_app.audio.dsp.reverb", duration_ns=80000, calls=100)
    synth.record_call("audio_processing_app.audio.input", duration_ns=10000, calls=20)
    synth.record_call("audio_processing_app.audio.output.mixer", duration_ns=30000, calls=50)
    synth.record_call("audio_processing_app.audio.output.encoder", duration_ns=20000, calls=30)
    synth.record_call("audio_processing_app.utils.logger", duration_ns=5000, calls=5)

    print(f"  Profiled {synth.profiler.module_count} modules")
    print(f"  Recorded {synth.profiler.sample_count} samples")
    print()

    # ── Step 4: Show profiler classification ─────────────────────────────
    print("Step 4: Profiler heat classification...")
    print(f"  {'Module':<50} {'Heat':<8} {'Calls':>8}")
    print(f"  {'-'*50} {'-'*8} {'-'*8}")

    heatmap = synth.get_heatmap()
    for mod_path, heat in sorted(heatmap.items()):
        calls = synth.profiler.call_counts.get(mod_path, 0)
        indicator = {
            "HEAT": ">> HOT!",
            "HOT": "> warm",
            "WARM": "~ mild",
            "COOL": "  cool",
            "FROZEN": "  ice",
        }.get(heat, "  ???")
        print(f"  {mod_path:<50} {indicator:<8} {calls:>8}")

    print()

    # ── Step 5: Show language recommendations ────────────────────────────
    print("Step 5: Language recommendations...")
    recs = synth.get_recommendations()
    print(f"  {'Module':<50} {'Current':<12} {'Recommended':<12} {'Change?':>8}")
    print(f"  {'-'*50} {'-'*12} {'-'*12} {'-'*8}")

    for path, rec in sorted(recs.items()):
        current = rec.current_language or "python"
        change = "YES" if rec.should_change else ""
        print(f"  {path:<50} {current:<12} {rec.recommended_language:<12} {change:>8}")

    print()

    # ── Step 6: Run evolution ────────────────────────────────────────────
    print("Step 6: Running self-evolution (5 generations)...")
    print()

    initial_fitness = synth.current_fitness
    report = synth.evolve(generations=5)
    final_fitness = synth.current_fitness

    for rec in report.records:
        arrow = "+" if rec.is_improvement else "="
        print(
            f"  Gen {rec.generation}: "
            f"fitness {rec.fitness_after:.4f} "
            f"(delta {rec.fitness_delta:+.4f}) {arrow} "
            f"mutations {rec.mutations_committed}/{rec.mutations_proposed} "
            f"patterns {rec.patterns_found}"
        )

    print()
    print(f"  Initial fitness: {initial_fitness:.4f}")
    print(f"  Final fitness:   {final_fitness:.4f}")
    improvement = final_fitness - initial_fitness
    if improvement > 0 and initial_fitness > 0:
        print(f"  Improvement:     +{improvement:.4f} ({improvement/initial_fitness*100:.1f}%)")
    elif improvement > 0:
        print(f"  Improvement:     +{improvement:.4f} (from baseline)")
    else:
        print(f"  Improvement:     {improvement:.4f}")
    print()

    # ── Step 7: Show language changes after evolution ────────────────────
    print("Step 7: Language assignments after evolution...")
    current_langs = synth.selector.current_languages
    print(f"  {'Module':<50} {'Language':<12}")
    print(f"  {'-'*50} {'-'*12}")

    for path, lang in sorted(current_langs.items()):
        indicator = ">>>" if lang != "python" else "   "
        print(f"  {indicator} {path:<47} {lang:<12}")

    print()

    # ── Step 8: Demonstrate hot-reloading ────────────────────────────────
    print("Step 8: Hot-reloading a single card...")
    card_before = synth.get_module("audio/dsp/filter")
    assert card_before is not None
    old_checksum = card_before.checksum

    result = synth.hot_swap(
        "audio/dsp/filter",
        "def apply_filter(samples, coeff, order=2): return [s * coeff**order for s in samples]",
    )

    print(f"  Swap result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Old checksum: {old_checksum}")
    print(f"  New checksum: {result.new_checksum}")
    print(f"  Cards reloaded: {result.cards_reloaded}")

    # Verify other modules are unaffected
    logger_card = synth.get_module("utils/logger")
    assert logger_card is not None
    print(f"  Logger card version (should be unchanged): {logger_card.version}")
    print()

    # ── Final: Generate system report ────────────────────────────────────
    print("=" * 72)
    print("  FULL SYSTEM REPORT")
    print("=" * 72)
    print()
    print(synth.get_system_report().to_text())


def run() -> None:
    """Public entry point called by ``flux demo``."""
    run_demo()


if __name__ == "__main__":
    run()
