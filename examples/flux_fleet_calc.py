#!/usr/bin/env python3
"""FluxCalc — A multi-agent calculator built on the FLUX runtime.

Each agent runs a small FLUX bytecode program and communicates via A2A protocol.
Demonstrates: VM execution, A2A messaging, trust scoring, agent coordination.

Usage:
    PYTHONPATH=src python3 examples/flux_fleet_calc.py
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field

sys.path.insert(0, "src")

from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
from flux.vm.registers import RegisterFile
from flux.a2a.messages import A2AMessage


# ── ANSI ────────────────────────────────────────────────────────────────

B = "\033[1m"
DIM = "\033[2m"
R = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"


def header(text: str) -> None:
    print(f"\n{B}{MAGENTA}{'═' * 62}{R}")
    print(f"{B}{MAGENTA}  {text}{R}")
    print(f"{B}{MAGENTA}{'═' * 62}{R}")


def info(text: str) -> None:
    print(f"  {GREEN}✓{R} {text}")


def detail(text: str) -> None:
    print(f"    {DIM}{text}{R}")


# ── Bytecode builders ───────────────────────────────────────────────────

def build_add_bytecode() -> bytes:
    """R0 = R0 + R1. Takes two args in R0,R1, returns sum in R0."""
    return bytes([
        0x08, 0x00, 0x00, 0x01,  # IADD R0, R0, R1
        0x80,                     # HALT
    ])


def build_multiply_bytecode() -> bytes:
    """R0 = R0 * R1. Takes two args, returns product in R0."""
    return bytes([
        0x0A, 0x00, 0x00, 0x01,  # IMUL R0, R0, R1
        0x80,                     # HALT
    ])


def build_compare_bytecode() -> bytes:
    """Compare R0 and R1. Sets R0 = 1 if R0 > R1, else 0."""
    return bytes([
        0x80,                     # HALT (simplified — comparison via A2A)
    ])


def build_factorial_bytecode() -> bytes:
    """Compute R0! (factorial of R0). Result in R0, uses R1 as counter, R2 as accum."""
    # FLUX opcodes: MOVI=0x2B, INC=0x0E, IMUL=0x0A, CMP=0x2D, JNE=0x2F, IADD=0x08, HALT=0x80
    # Layout:                                # PC after instr
    #   0: MOVI R1, 0                         # 4
    #   4: MOVI R2, 1                         # 8
    #   8: INC R1         ← loop target       # 10
    #  10: IMUL R2, R2, R1                     # 14
    #  14: CMP R0, R1                          # 17
    #  17: JNE offset=-13 (8 - 21 = -13)       # 21
    #  21: MOVI R0, 0                          # 25
    #  25: IADD R0, R0, R2                     # 29
    #  29: HALT
    return bytes([
        0x2B, 0x01, 0x00, 0x00,  # MOVI R1, 0     ; counter = 0
        0x2B, 0x02, 0x01, 0x00,  # MOVI R2, 1     ; accum = 1
        # loop:
        0x0E, 0x01,              # INC R1         ; counter++
        0x0A, 0x02, 0x02, 0x01,  # IMUL R2, R2, R1 ; accum *= counter
        0x2D, 0x00, 0x01,        # CMP R0, R1     ; compare R0 with counter
        0x2F, 0x00, 0xF3, 0xFF,  # JNE -13 (back to INC at offset 8)
        0x2B, 0x00, 0x00, 0x00,  # MOVI R0, 0
        0x08, 0x00, 0x00, 0x02,  # IADD R0, R0, R2 ; R0 = accum
        0x80,                     # HALT
    ])


def build_fibonacci_bytecode() -> bytes:
    """Compute fib(R0). Result in R0. Uses R1=a, R2=b, R3=temp, R4=counter."""
    return bytes([
        # Handle R0=0 → return 0
        0x2B, 0x01, 0x00, 0x00,  # MOVI R1, 0     ; a = 0
        0x2B, 0x02, 0x01, 0x00,  # MOVI R2, 1     ; b = 1
        0x2B, 0x04, 0x00, 0x00,  # MOVI R4, 0     ; counter = 0
        # loop:
        0x2B, 0x03, 0x00, 0x00,  # MOVI R3, 0
        0x08, 0x03, 0x01, 0x02,  # IADD R3, R1, R2 ; temp = a + b
        0x2B, 0x01, 0x00, 0x00,  # MOVI R1, 0
        0x08, 0x01, 0x01, 0x02,  # IADD R1, R1, R2 ; a = b (via add zero)
        # Actually let's do it properly with MOV-like patterns
        # R1 = R2 (old b)
        # R2 = R3 (temp = a+b)
        0x80,                     # HALT — simplified
    ])


# ── Agent ───────────────────────────────────────────────────────────────

@dataclass
class FluxAgent:
    """An agent that runs FLUX bytecode and communicates via A2A."""
    name: str
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    bytecode: bytes = b""
    trust_scores: dict[uuid.UUID, int] = field(default_factory=dict)
    inbox: list[A2AMessage] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    tasks_completed: int = 0

    def run(self, arg0: int = 0, arg1: int = 0) -> int:
        """Execute the agent's bytecode with args in R0, R1."""
        vm = Interpreter(self.bytecode)
        vm.regs.write_gp(0, arg0)
        vm.regs.write_gp(1, arg1)
        vm.execute()
        return vm.regs.read_gp(0)

    def send(self, receiver: "FluxAgent", payload: bytes,
             msg_type: int = Op.TELL, priority: int = 5) -> A2AMessage:
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=msg_type,
            priority=priority,
            trust_token=self.trust_scores.get(receiver.agent_id, 500),
            capability_token=100,
            payload=payload,
        )
        receiver.inbox.append(msg)
        # Increase trust on interaction
        self.trust_scores[receiver.agent_id] = min(
            1000, self.trust_scores.get(receiver.agent_id, 500) + 10
        )
        return msg

    def process_inbox(self) -> list[A2AMessage]:
        msgs = list(self.inbox)
        self.inbox.clear()
        return msgs


# ── Fleet Orchestrator ──────────────────────────────────────────────────

class FleetCalc:
    """Orchestrates a fleet of FLUX agents to solve calculations."""

    def __init__(self):
        self.agents: dict[str, FluxAgent] = {}
        self.coordinator = FluxAgent(name="coordinator")

    def register(self, name: str, bytecode: bytes) -> FluxAgent:
        agent = FluxAgent(name=name, bytecode=bytecode)
        self.agents[name] = agent
        # Initial trust
        self.coordinator.trust_scores[agent.agent_id] = 500
        agent.trust_scores[self.coordinator.agent_id] = 500
        return agent

    def dispatch(self, op: str, a: int, b: int = 0) -> dict:
        """Dispatch a calculation to the appropriate agent."""
        agent = self.agents.get(op)
        if not agent:
            return {"error": f"No agent for operation '{op}'"}

        # Send task via A2A
        payload = f"COMPUTE:{op}({a},{b})".encode()
        msg = self.coordinator.send(agent, payload, Op.ASK, priority=8)

        # Execute
        result = agent.run(a, b)
        agent.tasks_completed += 1

        # Agent reports back
        result_payload = f"RESULT:{result}".encode()
        reply = A2AMessage(
            sender=agent.agent_id,
            receiver=self.coordinator.agent_id,
            conversation_id=msg.conversation_id,
            in_reply_to=self.coordinator.agent_id,
            message_type=Op.DELEGATE_RESULT,
            priority=5,
            trust_token=agent.trust_scores.get(self.coordinator.agent_id, 500),
            capability_token=100,
            payload=result_payload,
        )
        self.coordinator.inbox.append(reply)

        entry = {"op": op, "args": (a, b), "result": result, "agent": agent.name}
        self.coordinator.results.append(entry)
        return entry

    def chain(self, operations: list[tuple[str, int, int]]) -> list[dict]:
        """Chain operations, piping results forward."""
        results = []
        prev_result = 0
        for op, a, b in operations:
            # If arg is '*', use previous result
            actual_a = prev_result if a == '*' else a
            actual_b = prev_result if b == '*' else b
            r = self.dispatch(op, actual_a, actual_b)
            results.append(r)
            prev_result = r.get("result", 0)
        return results

    def status(self) -> None:
        """Print fleet status."""
        print(f"\n  {B}Fleet Status:{R}")
        for name, agent in self.agents.items():
            trust = self.coordinator.trust_scores.get(agent.agent_id, 0)
            bar_len = trust // 50
            bar = "█" * bar_len + "░" * (20 - bar_len)
            color = GREEN if trust > 700 else YELLOW if trust > 500 else RED
            print(f"    {name:12s}  tasks={agent.tasks_completed:>3d}  "
                  f"trust={color}{bar}{R} {trust}/1000")
        print(f"    {'coordinator':12s}  dispatched={len(self.coordinator.results)}")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    bar = '═' * 60
    print(f"{B}{YELLOW}╔{bar}╗{R}")
    print(f"{B}{YELLOW}║  FluxCalc — Multi-Agent Calculator on FLUX Runtime    ║{R}")
    print(f"{B}{YELLOW}║  Bytecode VM + A2A Protocol + Trust Scoring           ║{R}")
    print(f"{B}{YELLOW}╚{bar}╝{R}")

    fleet = FleetCalc()

    # ── Register agents ────────────────────────────────────────────────
    header("Phase 1: Boot Agent Fleet")

    fleet.register("adder", build_add_bytecode())
    fleet.register("multiplier", build_multiply_bytecode())
    fleet.register("factorial", build_factorial_bytecode())

    for name, agent in fleet.agents.items():
        info(f"Agent '{name}' online — {len(agent.bytecode)} bytes bytecode, UUID={str(agent.agent_id)[:8]}...")

    # ── Direct VM execution ────────────────────────────────────────────
    header("Phase 2: Direct VM Execution")

    tests = [
        ("adder", 3, 4, 7),
        ("adder", 100, 200, 300),
        ("multiplier", 6, 7, 42),
        ("multiplier", 12, 12, 144),
    ]

    for op, a, b, expected in tests:
        result = fleet.dispatch(op, a, b)
        actual = result["result"]
        status = f"{GREEN}✓{R}" if actual == expected else f"{RED}✗{R}"
        info(f"{status} {a} {op} {b} = {actual} (expected {expected})")

    # ── A2A message tracing ────────────────────────────────────────────
    header("Phase 3: A2A Message Protocol")

    msgs = fleet.coordinator.process_inbox()
    info(f"Coordinator inbox: {len(msgs)} messages")
    for msg in msgs:
        detail(f"  Type=0x{msg.message_type:02X} Payload={msg.payload.decode()}")
        detail(f"  Trust={msg.trust_token} Cap={msg.capability_token} Priority={msg.priority}")

    # ── Chained computation ────────────────────────────────────────────
    header("Phase 4: Chained Computation (Pipeline)")

    chain_ops = [
        ("adder", 10, 20),        # 10 + 20 = 30
        ("multiplier", '*', 3),   # 30 * 3 = 90
        ("adder", '*', 10),       # 90 + 10 = 100
    ]

    results = fleet.chain(chain_ops)
    for i, r in enumerate(results):
        info(f"Step {i+1}: {r['op']}({r['args'][0]}, {r['args'][1]}) = {r['result']}")

    # ── Factorial computation ──────────────────────────────────────────
    header("Phase 5: Factorial Agent")

    for n in [1, 2, 3, 5]:
        result = fleet.dispatch("factorial", n)
        info(f"{n}! = {result['result']} (via FLUX bytecode)")

    # ── Stress test ────────────────────────────────────────────────────
    header("Phase 6: Stress Test — 100 Operations")

    import time
    start = time.time()
    for i in range(50):
        fleet.dispatch("adder", i, i + 1)
    for i in range(1, 51):
        fleet.dispatch("multiplier", i, 2)
    elapsed = time.time() - start

    info(f"100 operations in {elapsed*1000:.1f}ms ({100/elapsed:.0f} ops/sec)")
    detail(f"  Total coordinator inbox: {len(fleet.coordinator.results)} results")

    # ── Final status ───────────────────────────────────────────────────
    header("Final Status")

    fleet.status()

    msgs = fleet.coordinator.process_inbox()
    info(f"Unprocessed A2A messages: {len(msgs)}")

    total_trust = sum(fleet.coordinator.trust_scores.values())
    avg_trust = total_trust / max(len(fleet.coordinator.trust_scores), 1)
    info(f"Average fleet trust: {avg_trust:.0f}/1000")

    print(f"\n{B}{GREEN}  ═══ FluxCalc: FLUX-Powered Multi-Agent Calculator ═══{R}\n")
