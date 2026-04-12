> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — All opcode values and names now reference the unified ISA from `isa_unified.py`. A2A opcodes updated: TELL=0x50, ASK=0x51, DELEG=0x52, BCAST=0x53, ACCEPT=0x54. See `docs/ISA_UNIFIED.md` for the canonical reference.

# Module 6: Multi-Agent Fleet Patterns

**Learning Objectives:**
- Master Captain/Worker coordination pattern
- Implement Scout/Reporter information gathering
- Build consensus and voting systems
- Design specialized agent fleets

## Fleet Architecture Overview

A FLUX fleet is a collection of specialized agents working together:

```
┌─────────────────────────────────────────────────────────┐
│  Fleet Coordinator                                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Captain          │  Scouts        │  Workers     │  │
│  │  (Decision)       │  (Gather)      │  (Execute)   │  │
│  ├──────────────────┼────────────────┼──────────────┤  │
│  │  Policy          │  Sensors       │  Processors  │  │
│  │  Planning        │  Monitors      │  Analyzers   │  │
│  │  Resource Mgmt   │  Reporters     │  Transformers│  │
│  └──────────────────┴────────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Pattern 1: Captain/Worker

### Architecture

```
Captain:                        Workers:
- Task distribution            - Receive tasks
- Result aggregation           - Execute processing
- Decision making              - Return results
- Resource management          - Report status
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
import uuid
from flux.a2a.messages import A2AMessage
from flux.vm.unified_interpreter import Interpreter

# Converged ISA v2 A2A opcode values
DELEG  = 0x52
ACCEPT = 0x54

@dataclass
class WorkerAgent:
    """Worker agent that executes tasks."""
    name: str
    bytecode: bytes
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    interpreter: Interpreter = None
    inbox: List[A2AMessage] = field(default_factory=list)

    def __post_init__(self):
        self.interpreter = Interpreter(self.bytecode, memory_size=4096)

    def execute_task(self, task_data: bytes) -> bytes:
        """Execute a task and return result."""
        # Reset VM
        self.interpreter.reset()

        # Load task data into R0
        import struct
        task_id = struct.unpack("<I", task_data[:4])[0]

        # Execute
        self.interpreter.regs[0] = task_id
        self.interpreter.execute()

        # Return result
        result = self.interpreter.regs[0]
        return struct.pack("<I", result)

    def process_messages(self):
        """Process incoming messages."""
        for msg in self.inbox:
            if msg.message_type == DELEG:   # 0x52
                # Execute task
                result = self.execute_task(msg.payload)

                # Send result back using ACCEPT
                reply = A2AMessage(
                    sender=self.agent_id,
                    receiver=msg.sender,
                    conversation_id=msg.conversation_id,
                    in_reply_to=msg.sender,
                    message_type=ACCEPT,     # 0x54
                    priority=msg.priority,
                    trust_token=msg.trust_token,
                    capability_token=msg.capability_token,
                    payload=result,
                )

                # In real implementation, would send via transport
                print(f"{self.name} executed task, result: {result.hex()}")
        self.inbox.clear()


@dataclass
class CaptainAgent:
    """Captain agent that coordinates workers."""
    name: str
    workers: List[WorkerAgent] = field(default_factory=list)
    pending_tasks: Dict = field(default_factory=dict)
    results: List = field(default_factory=list)

    def add_worker(self, worker: WorkerAgent):
        """Add a worker to the fleet."""
        self.workers.append(worker)

    def delegate_task(self, task_id: int, worker_index: int):
        """Delegate a task to a specific worker."""
        if worker_index >= len(self.workers):
            print(f"Invalid worker index: {worker_index}")
            return

        worker = self.workers[worker_index]
        task_data = struct.pack("<I", task_id)

        msg = A2AMessage(
            sender=uuid.uuid4(),  # Captain's ID
            receiver=worker.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=DELEG,     # 0x52
            priority=7,
            trust_token=750,
            capability_token=200,
            payload=task_data,
        )

        worker.inbox.append(msg)
        self.pending_tasks[task_id] = worker.agent_id

    def collect_results(self) -> List[bytes]:
        """Collect results from all workers."""
        results = []
        for worker in self.workers:
            worker.process_messages()
        return results

    def make_decision(self) -> str:
        """Make decision based on collected results."""
        # Simple decision: if we have results, continue
        if self.results:
            return "CONTINUE"
        else:
            return "WAIT"
```

### Example: Parallel Processing

```python
import struct

# Worker bytecode: double the input value
# ADD R0, R0, R0 (0x20 = ADD in converged ISA)
worker_bytecode = bytearray()
worker_bytecode.extend(struct.pack("<BBBB", 0x20, 0, 0, 0))  # ADD R0, R0, R0
worker_bytecode.extend(bytes([0x00]))                          # HALT (0x00)

# Create fleet
captain = CaptainAgent("MainCaptain")

# Add 5 workers
for i in range(5):
    worker = WorkerAgent(f"Worker{i}", bytes(worker_bytecode))
    captain.add_worker(worker)

# Distribute tasks
print("=== Task Distribution ===")
for i in range(5):
    captain.delegate_task(i * 10, i)  # Task 0, 10, 20, 30, 40
    print(f"Delegated task {i * 10} to Worker{i}")

# Collect results
print("\n=== Result Collection ===")
results = captain.collect_results()

# Make decision
decision = captain.make_decision()
print(f"\nCaptain decision: {decision}")
```

## Pattern 2: Scout/Reporter

### Architecture

```
Scouts:                         Captain:
- Explore environment           - Receive reports
- Gather data                   - Aggregate information
- Report findings               - Update world model
- Monitor conditions            - Trigger actions
```

### Implementation

```python
@dataclass
class ScoutAgent:
    """Scout agent that explores and reports."""
    name: str
    scout_type: str  # "weather", "resource", "enemy", etc.
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    position: tuple = (0, 0)

    def scout(self, timestep: int) -> bytes:
        """Scout the environment and return data."""
        if self.scout_type == "weather":
            # Simulate weather scouting
            import random
            wind = random.randint(0, 30)
            visibility = random.randint(1, 10)
            return struct.pack("<HH", wind, visibility)

        elif self.scout_type == "resource":
            # Simulate resource scouting
            import random
            resources = random.randint(0, 100)
            return struct.pack("<I", resources)

        return b""

    def send_report(self, receiver, report_data: bytes):
        """Send a report to the receiver."""
        # TELL = 0x50 in converged ISA
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=0x50,        # TELL (0x50)
            priority=6,
            trust_token=500,
            capability_token=100,
            payload=report_data,
        )

        # In real implementation, send via transport
        print(f"{self.name} sent report: {report_data.hex()}")


@dataclass
class ReporterAgent:
    """Reporter agent that aggregates scout data."""
    name: str
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    reports: List = field(default_factory=list)

    def receive_report(self, report: bytes, scout_name: str):
        """Receive and process a scout report."""
        self.reports.append({
            "scout": scout_name,
            "data": report,
            "timestamp": time.time()
        })

    def aggregate_reports(self) -> Dict[str, Any]:
        """Aggregate all reports into summary."""
        summary = {
            "total_reports": len(self.reports),
            "latest_data": {}
        }

        for report in self.reports:
            scout = report["scout"]
            data = report["data"]
            summary["latest_data"][scout] = data

        return summary
```

### Example: Environmental Monitoring

```python
import time

# Create scouts
weather_scout = ScoutAgent("WeatherScout", "weather")
resource_scout = ScoutAgent("ResourceScout", "resource")
terrain_scout = ScoutAgent("TerrainScout", "terrain")

# Create reporter
reporter = ReporterAgent("MainReporter")

# Simulate scouting
print("=== Scout Deployment ===")
for timestep in range(3):
    print(f"\nTimestep {timestep}:")

    # Each scout reports
    weather_data = weather_scout.scout(timestep)
    weather_scout.send_report(reporter.agent_id, weather_data)
    reporter.receive_report(weather_data, weather_scout.name)

    resource_data = resource_scout.scout(timestep)
    resource_scout.send_report(reporter.agent_id, resource_data)
    reporter.receive_report(resource_data, resource_scout.name)

    time.sleep(0.1)  # Simulate delay

# Aggregate reports
print("\n=== Report Aggregation ===")
summary = reporter.aggregate_reports()
print(f"Total reports: {summary['total_reports']}")
print(f"Latest data: {summary['latest_data']}")
```

## Pattern 3: Consensus and Voting

### Architecture

```
Agents:                         Coordinator:
- Receive proposal              - Broadcast proposal
- Evaluate and vote             - Collect votes
- Send vote                     - Determine consensus
- Await consensus               - Broadcast result
```

### Implementation

```python
from enum import Enum
from typing import Callable

class Vote(Enum):
    YES = 1
    NO = 0
    ABSTAIN = -1

@dataclass
class ConsensusAgent:
    """Agent that participates in consensus."""
    name: str
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    voting_strategy: Callable = None

    def evaluate_proposal(self, proposal: bytes) -> Vote:
        """Evaluate a proposal and return vote."""
        if self.voting_strategy:
            return self.voting_strategy(proposal)
        else:
            # Default: random vote
            import random
            return random.choice(list(Vote))

    def cast_vote(self, coordinator, proposal_id: int, vote: Vote):
        """Cast vote for a proposal."""
        # ASK = 0x51 in converged ISA
        vote_data = struct.pack("<Ii", proposal_id, vote.value)
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=coordinator,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=0x51,        # ASK (0x51)
            priority=8,              # High priority for voting
            trust_token=700,
            capability_token=200,
            payload=vote_data,
        )

        print(f"{self.name} cast vote: {vote.name}")

@dataclass
class ConsensusCoordinator:
    """Coordinates consensus among agents."""
    name: str
    agents: List[ConsensusAgent] = field(default_factory=list)
    proposals: Dict = field(default_factory=dict)
    votes: Dict = field(default_factory=dict)

    def add_agent(self, agent: ConsensusAgent):
        """Add an agent to the consensus group."""
        self.agents.append(agent)

    def propose(self, proposal: bytes) -> int:
        """Propose a decision to the group."""
        proposal_id = len(self.proposals)
        self.proposals[proposal_id] = {
            "data": proposal,
            "status": "PENDING"
        }
        self.votes[proposal_id] = {}

        print(f"\n=== Proposal {proposal_id} ===")
        print(f"Proposal: {proposal.decode()}")

        # Broadcast proposal
        for agent in self.agents:
            vote = agent.evaluate_proposal(proposal)
            agent.cast_vote(self.agent_id, proposal_id, vote)
            self.votes[proposal_id][agent.name] = vote

        return proposal_id

    def tally_votes(self, proposal_id: int) -> Dict[str, int]:
        """Tally votes for a proposal."""
        if proposal_id not in self.votes:
            return {}

        votes = self.votes[proposal_id]
        tally = {
            "YES": sum(1 for v in votes.values() if v == Vote.YES),
            "NO": sum(1 for v in votes.values() if v == Vote.NO),
            "ABSTAIN": sum(1 for v in votes.values() if v == Vote.ABSTAIN),
            "TOTAL": len(votes)
        }

        return tally

    def determine_consensus(self, proposal_id: int) -> bool:
        """Determine if consensus is reached."""
        tally = self.tally_votes(proposal_id)

        print(f"\nVote tally:")
        print(f"  YES:     {tally['YES']}")
        print(f"  NO:      {tally['NO']}")
        print(f"  ABSTAIN: {tally['ABSTAIN']}")

        # Simple majority: YES > NO
        consensus = tally['YES'] > tally['NO']

        if consensus:
            print(f"✓ Consensus reached: YES")
            self.proposals[proposal_id]["status"] = "ACCEPTED"
        else:
            print(f"✗ Consensus not reached")
            self.proposals[proposal_id]["status"] = "REJECTED"

        return consensus
```

### Example: Group Decision

```python
import struct

# Create voting strategies
def conservative_vote(proposal: bytes) -> Vote:
    """Conservative voting strategy."""
    value = struct.unpack("<I", proposal)[0]
    return Vote.YES if value < 50 else Vote.NO

def liberal_vote(proposal: bytes) -> Vote:
    """Liberal voting strategy."""
    value = struct.unpack("<I", proposal)[0]
    return Vote.YES if value < 80 else Vote.NO

def random_vote(proposal: bytes) -> Vote:
    """Random voting strategy."""
    import random
    return random.choice([Vote.YES, Vote.NO])

# Create agents
coordinator = ConsensusCoordinator("Coordinator")
coordinator.agent_id = uuid.uuid4()

agent1 = ConsensusAgent("Agent1", voting_strategy=conservative_vote)
agent2 = ConsensusAgent("Agent2", voting_strategy=liberal_vote)
agent3 = ConsensusAgent("Agent3", voting_strategy=random_vote)

# Add agents to coordinator
coordinator.add_agent(agent1)
coordinator.add_agent(agent2)
coordinator.add_agent(agent3)

# Propose decisions
proposals = [
    struct.pack("<I", 30),   # Low value - should pass
    struct.pack("<I", 60),   # Medium value - depends
    struct.pack("<I", 90),   # High value - should fail
]

for i, proposal in enumerate(proposals):
    proposal_id = coordinator.propose(proposal)
    consensus = coordinator.determine_consensus(proposal_id)
    print(f"Result: {consensus}")
```

## Pattern 4: Specialized Fleet

### Example: Fishing Fleet (from flux_fleet_sim.py)

```python
@dataclass
class FleetSimulator:
    """Complete fleet with specialized agents."""
    agents: Dict[str, Agent] = field(default_factory=dict)

    def __post_init__(self):
        # Navigator agent: handles direction
        navigator_bytecode = bytes([
            0x20, 0x00, 0x00, 0x01,  # ADD R0, R0, R1 (converged ISA)
            # ... navigation logic ...
            0x02,                     # RET (0x02, Format A)
        ])
        self.agents["navigator"] = Agent("Navigator", navigator_bytecode)

        # Weather scout: monitors conditions
        weather_bytecode = bytes([
            # ... weather monitoring logic ...
            0x02,                     # RET (0x02)
        ])
        self.agents["weather_scout"] = Agent("WeatherScout", weather_bytecode)

        # Fish finder: locates targets
        finder_bytecode = bytes([
            # ... fish finding logic ...
            0x02,                     # RET (0x02)
        ])
        self.agents["fish_finder"] = Agent("FishFinder", finder_bytecode)

        # Supply manager: tracks resources
        supply_bytecode = bytes([
            # ... supply tracking logic ...
            0x02,                     # RET (0x02)
        ])
        self.agents["supply_manager"] = Agent("SupplyManager", supply_bytecode)

        # Captain: makes decisions
        captain_bytecode = bytes([
            # ... decision logic ...
            0x02,                     # RET (0x02)
        ])
        self.agents["captain"] = Agent("Captain", captain_bytecode)

    def run_timestep(self, timestep: int):
        """Execute one timestep of fleet operation."""
        # 1. Captain broadcasts mission params
        captain = self.agents["captain"]
        for name, agent in self.agents.items():
            if name != "captain":
                # Broadcast mission
                pass

        # 2. Weather scout reports conditions
        weather_scout = self.agents["weather_scout"]
        weather_data = weather_scout.run({0: timestep})

        # 3. Navigator adjusts heading
        navigator = self.agents["navigator"]
        new_heading = navigator.run({0: 45, 1: -5})

        # 4. Fish finder locates targets
        fish_finder = self.agents["fish_finder"]
        catch_probability = fish_finder.run({0: 200, 1: 60})

        # 5. Supply manager checks resources
        supply_manager = self.agents["supply_manager"]
        supply_status = supply_manager.run({0: 100, 1: 80, 2: 90})

        # 6. Captain makes decision
        decision = captain.run({
            0: 100,  # fuel
            1: 0,    # catch
            2: 8,    # weather score
            3: supply_status
        })

        return {
            "heading": new_heading,
            "catch_prob": catch_probability,
            "decision": decision
        }
```

## Exercise: Build a 5-Agent Fleet

**Task:** Create a fleet with 5 specialized agents:
1. **Coordinator** — Orchestrates fleet
2. **Collector** — Gathers input data
3. **Processor** — Processes data
4. **Analyzer** — Analyzes results
5. **Reporter** — Reports findings

**Requirements:**
- Use BCAST (0x53) for coordination
- Use DELEG (0x52) for task distribution
- Implement trust scoring
- Show fleet execution for 3 timesteps

**Solution Framework:**

```python
# Create 5 agents with specific bytecode
fleet = FleetSimulator()

# Add specialized agents
fleet.add_agent(CoordinatorAgent("Coordinator"))
fleet.add_agent(CollectorAgent("Collector"))
fleet.add_agent(ProcessorAgent("Processor"))
fleet.add_agent(AnalyzerAgent("Analyzer"))
fleet.add_agent(ReporterAgent("Reporter"))

# Run simulation
for timestep in range(3):
    print(f"\n=== Timestep {timestep} ===")
    result = fleet.run_timestep(timestep)
    print(f"Result: {result}")
```

## Progress Checkpoint

At the end of Module 6, you should be able to:

- ✅ Implement Captain/Worker coordination pattern
- ✅ Build Scout/Reporter information gathering systems
- ✅ Create consensus and voting mechanisms
- ✅ Design specialized agent fleets
- ✅ Coordinate multi-agent workflows

## Bootcamp Completion

🎉 **Congratulations!** You've completed the FLUX Agent Bootcamp!

You are now equipped to:
- Write FLUX bytecode programs using the converged ISA v2
- Implement control flow and functions
- Build multi-agent systems with A2A messaging
- Manage memory regions and stack operations
- Compile C code to FLUX bytecode
- Design and deploy agent fleets

### Next Steps

- **[ISA Unified Reference](../ISA_UNIFIED.md)** — Complete converged ISA v2 opcode table
- **[User Guide](../user-guide.md)** — Complete API reference
- **[Developer Guide](../developer-guide.md)** — Architecture and contribution
- **[Agent Training Guide](../agent-training/README.md)** — Specialized guide for AI agents

### Build Something Amazing!

Join the FLUX community and share your creations:
- GitHub: [https://github.com/SuperInstance/flux-runtime](https://github.com/SuperInstance/flux-runtime)
- Examples: See `examples/` directory for inspiration

---

**Happy agent building!** 🚀
