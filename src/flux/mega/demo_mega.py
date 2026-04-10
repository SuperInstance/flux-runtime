"""Mega demo — exercises every subsystem in FLUX.

Run this to verify the entire system works as one cohesive machine:

    python -m flux.mega.demo_mega
"""

from __future__ import annotations

import tempfile
import os

from flux.mega.conductor import GrandConductor
from flux.swarm.agent import AgentRole


def run_mega_demo() -> str:
    """Run the mega demo — exercises every subsystem in FLUX.

    Returns:
        The full system report as a string.
    """
    # Use a temp workspace so we don't pollute the project dir
    with tempfile.TemporaryDirectory() as tmpdir:
        conductor = GrandConductor("mega_demo", workspace=tmpdir)

        # 1. Load modules
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.load("math/multiply", "def mul(a, b): return a * b", "python")
        conductor.load("math/divide", "def div(a, b): return a / b", "python")

        # 2. Run workload
        def workload():
            return 42

        result = conductor.run(workload)
        assert result.success, f"Workload failed: {result.error}"

        # 3. Profile some modules for richer data
        conductor.synthesizer.record_call("mega_demo.math.add", duration_ns=500, calls=10)
        conductor.synthesizer.record_call("mega_demo.math.multiply", duration_ns=200, calls=5)
        conductor.synthesizer.record_call("mega_demo.math.divide", duration_ns=1000, calls=2)

        # 4. Assess
        assessment = conductor.assess()

        # 5. Predict
        prediction = conductor.predict("recompile math/add")
        assert prediction is not None

        # 6. Simulate
        sim = conductor.simulate("fuse add+mul")
        assert sim is not None

        # 7. Spawn agents
        conductor.spawn_agent("worker_1", AgentRole.SPECIALIST_COMPUTE)
        conductor.spawn_agent("worker_2", AgentRole.SPECIALIST_EXPLORER)
        assert conductor.swarm.agent_count == 2

        # 8. Message passing
        success = conductor.send_message(
            "worker_1", "worker_2",
            {"type": "request", "data": "hello"},
        )
        assert success, "Message delivery failed"

        # 9. Memory
        conductor.remember("last_run", str(result.result))
        recalled = conductor.recall("last_run")
        assert recalled == "42", f"Memory recall failed: got {recalled!r}"

        # 10. Sonify
        music = conductor.sonify(workload)
        assert len(music) > 0, "Sonification produced no events"

        # 11. Bandit strategy selection
        strategy = conductor.bandit.select()
        assert strategy is not None

        # 12. Generate docs
        doc_dir = os.path.join(tmpdir, "docs")
        doc_count = conductor.generate_docs(doc_dir)
        assert doc_count > 0, "Doc generation failed"

        # 13. Full report
        report = conductor.full_report()

        return report


if __name__ == "__main__":
    report = run_mega_demo()
    print(report)
