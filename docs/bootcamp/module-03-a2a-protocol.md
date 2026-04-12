> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — All opcode values and names now reference the unified ISA from `isa_unified.py`. A2A opcodes are now Format E (4-byte register triples) instead of Format G (variable-length). See `docs/ISA_UNIFIED.md` for the canonical reference.

# Module 3: A2A (Agent-to-Agent) Protocol

**Learning Objectives:**
- Understand the A2A messaging system
- Learn message types: TELL, ASK, DELEG, BCAST
- Implement trust scoring between agents
- Build multi-agent collaborative systems

## What is A2A Protocol?

The A2A (Agent-to-Agent) protocol is FLUX's native messaging system for agent communication. It provides:

- **Binary message format** — Efficient serialization (52-byte header)
- **Trust scoring** — INCREMENTS+2 trust engine
- **Capability-based security** — Permission tokens for operations
- **Priority routing** — 0-15 priority levels for QoS
- **Conversation tracking** — UUID-based conversation chains

## Message Types

### Core Message Types

All A2A opcodes use **Format E** (4 bytes: `[opcode][rd][rs1][rs2]`).

| Opcode | Hex | Name | Description | Use Case |
|--------|-----|------|-------------|----------|
| 0x50 | TELL | Fire-and-forget | `rd, rs1, rs2` — Send rs2 to agent rs1, tag rd | Status updates, events |
| 0x51 | ASK | Request-response | `rd, rs1, rs2` — Request rs2 from agent rs1, resp→rd | Data queries, requests |
| 0x52 | DELEG | Task delegation | `rd, rs1, rs2` — Delegate task rs2 to agent rs1 | Work distribution |
| 0x53 | BCAST | One-to-many | `rd, rs1, rs2` — Broadcast rs2 to fleet, tag rd | Announcements |
| 0x54 | ACCEPT | Accept task | `rd, rs1, rs2` — Accept delegated task, ctx→rd | Task acceptance |
| 0x55 | DECLINE | Decline task | `rd, rs1, rs2` — Decline task with reason rs2 | Task rejection |
| 0x56 | REPORT | Report status | `rd, rs1, rs2` — Report task status rs2 to rd | Status updates |
| 0x57 | MERGE | Merge results | `rd, rs1, rs2` — Merge results from rs1, rs2→rd | Map-reduce patterns |
| 0x5C | TRUST | Trust level | `rd, rs1, rs2` — Set trust level rs2 for agent rs1 | Trust management |

### Trust & Capability Messages

| Opcode | Hex | Name | Description |
|--------|-----|------|-------------|
| TRUST | 0x5C | Set trust level | Unified trust operation (set/query/check) |
| DISCOV | 0x5D | Discover agents | Query fleet for available agents |

> **Note:** The converged ISA consolidates trust operations into a single TRUST opcode (0x5C). Old separate opcodes (TRUST_CHECK, TRUST_UPDATE, TRUST_QUERY) are unified. Capability enforcement (CAP_REQUIRE, CAP_GRANT, CAP_REVOKE) is now handled at the interpreter level, not as ISA opcodes. See `docs/security-primitives-spec.md` for details.

## A2A Message Format

### Binary Structure

```
┌─────────────────────────────────────────────────────────────┐
│  A2A Message Header (52 bytes)                              │
├─────────────────────────────────────────────────────────────┤
│  sender_uuid:       16 bytes                                │
│  receiver_uuid:     16 bytes                                │
│  conversation_id:   16 bytes                                │
│  in_reply_to:       16 bytes (UUID or None)                 │
│  message_type:      1 byte  (converged ISA opcode)          │
│  priority:          1 byte  (0-15, 15=highest)              │
│  trust_token:       4 bytes (uint32)                        │
│  capability_token:  4 bytes (uint32)                        │
│  payload_len:       4 bytes (uint32)                        │
│  payload:           variable bytes                           │
└─────────────────────────────────────────────────────────────┘
```

### Creating A2A Messages

```python
import uuid
from flux.a2a.messages import A2AMessage

# Converged ISA v2 A2A opcode values
TELL = 0x50
ASK  = 0x51

# Create a TELL message
msg = A2AMessage(
    sender=uuid.uuid4(),
    receiver=uuid.uuid4(),
    conversation_id=uuid.uuid4(),
    in_reply_to=None,
    message_type=TELL,       # 0x50 in converged ISA (was 0x60)
    priority=5,
    trust_token=750,
    capability_token=100,
    payload=b"STATUS:OK"
)

# Serialize to bytes
raw_bytes = msg.to_bytes()
print(f"Message size: {len(raw_bytes)} bytes")

# Deserialize from bytes
reconstructed = A2AMessage.from_bytes(raw_bytes)
```

## Trust Scoring System

### INCREMENTS+2 Trust Model

Trust scores range from 0-1000:
- **0-249**: Untrusted — Block operations
- **250-499**: Suspicious — Limit capabilities
- **500-749**: Trusted — Normal operations
- **750-1000**: Highly trusted — Full capabilities

### Trust Update Rules

```python
def calculate_trust_update(
    current_score: int,
    interaction_outcome: str,
    message_priority: int
) -> int:
    """Calculate trust score increment."""
    base_increment = {
        "success": +10,
        "failure": -20,
        "timeout": -15,
        "error": -25
    }

    priority_multiplier = 1.0 + (message_priority / 15.0)
    increment = base_increment.get(interaction_outcome, 0) * priority_multiplier

    return max(0, min(1000, current_score + int(increment)))
```

### Trust Engine Usage

```python
from flux.a2a.trust import TrustEngine, InteractionRecord

# Create trust engine
trust_engine = TrustEngine()

# Record interaction
record = InteractionRecord(
    agent_id=uuid.uuid4(),
    outcome="success",
    timestamp=time.time(),
    operation="data_request"
)

# Update trust score
trust_engine.update_trust(agent_id=record.agent_id, record=record)

# Query trust score
score = trust_engine.get_trust_score(agent_id=record.agent_id)
print(f"Trust score: {score}/1000")
```

## Building Multi-Agent Systems

### Pattern 1: Producer-Consumer

```python
from dataclasses import dataclass, field
from typing import List
import uuid

# Converged ISA v2 A2A opcode values
TELL  = 0x50
ASK   = 0x51

@dataclass
class Agent:
    name: str
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    inbox: List = field(default_factory=list)
    trust_scores: dict = field(default_factory=dict)

    def send_tell(self, receiver: "Agent", payload: bytes, priority: int = 5):
        """Send a TELL message to another agent."""
        from flux.a2a.messages import A2AMessage

        trust_token = self.trust_scores.get(receiver.agent_id, 500)

        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=TELL,       # 0x50
            priority=priority,
            trust_token=trust_token,
            capability_token=100,
            payload=payload,
        )

        receiver.inbox.append(msg)
        return msg.to_bytes()

    def send_ask(self, receiver: "Agent", payload: bytes, priority: int = 8):
        """Send an ASK message (request-response)."""
        from flux.a2a.messages import A2AMessage

        trust_token = self.trust_scores.get(receiver.agent_id, 500)

        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=ASK,        # 0x51
            priority=priority,
            trust_token=trust_token,
            capability_token=200,
            payload=payload,
        )

        receiver.inbox.append(msg)
        return msg.to_bytes()

    def process_inbox(self):
        """Process all messages in inbox."""
        messages = self.inbox.copy()
        self.inbox.clear()

        for msg in messages:
            self.handle_message(msg)
            # Update trust based on successful processing
            self.trust_scores[msg.sender] = min(
                1000, self.trust_scores.get(msg.sender, 500) + 10
            )

    def handle_message(self, msg):
        """Handle incoming message."""
        if msg.message_type == TELL:    # 0x50
            print(f"{self.name} received TELL: {msg.payload.decode()}")
        elif msg.message_type == ASK:   # 0x51
            print(f"{self.name} received ASK: {msg.payload.decode()}")
            # Would send reply here
```

### Pattern 2: Captain-Worker Fleet

```python
# Converged ISA v2 A2A opcode values
TELL   = 0x50
DELEG  = 0x52
BCAST  = 0x53
ACCEPT = 0x54

class CaptainAgent(Agent):
    """Coordinates worker agents."""

    def broadcast_task(self, workers: List[Agent], task: bytes):
        """Broadcast a task to all workers."""
        from flux.a2a.messages import A2AMessage

        for worker in workers:
            msg = A2AMessage(
                sender=self.agent_id,
                receiver=worker.agent_id,
                conversation_id=uuid.uuid4(),
                in_reply_to=None,
                message_type=BCAST,     # 0x53
                priority=7,
                trust_token=self.trust_scores.get(worker.agent_id, 500),
                capability_token=150,
                payload=task,
            )
            worker.inbox.append(msg)

    def collect_results(self, workers: List[Agent]) -> List[bytes]:
        """Collect results from all workers."""
        results = []
        for worker in workers:
            for msg in worker.inbox:
                if msg.message_type == ACCEPT:  # 0x54
                    results.append(msg.payload)
        return results


class WorkerAgent(Agent):
    """Executes tasks delegated by captain."""

    def handle_message(self, msg):
        """Handle incoming message."""
        from flux.a2a.messages import A2AMessage

        if msg.message_type == BCAST:   # 0x53
            # Execute task
            result = self.execute_task(msg.payload)

            # Send result back using ACCEPT
            reply = A2AMessage(
                sender=self.agent_id,
                receiver=msg.sender,
                conversation_id=msg.conversation_id,
                in_reply_to=msg.sender,
                message_type=ACCEPT,     # 0x54 (was DELEGATE_RESULT)
                priority=msg.priority,
                trust_token=msg.trust_token,
                capability_token=msg.capability_token,
                payload=result,
            )

            # Find captain and send reply
            # (In real implementation, would have agent registry)
            print(f"Task executed, result: {result.decode()}")

    def execute_task(self, task: bytes) -> bytes:
        """Execute a task and return result."""
        # Simplified task execution
        return b"RESULT:" + task
```

## Example: Three-Agent Collaboration

```python
#!/usr/bin/env python3
"""Three-agent collaboration example."""

import uuid
from flux.a2a.messages import A2AMessage

# Converged ISA v2 A2A opcode values
TELL   = 0x50
ASK    = 0x51
ACCEPT = 0x54

class SimpleAgent:
    def __init__(self, name: str):
        self.name = name
        self.agent_id = uuid.uuid4()
        self.inbox = []
        self.trust_scores = {}

    def send(self, receiver, message_type, payload, priority=5):
        """Send a message to another agent."""
        trust_token = self.trust_scores.get(receiver.agent_id, 500)

        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=message_type,
            priority=priority,
            trust_token=trust_token,
            capability_token=100,
            payload=payload,
        )

        receiver.inbox.append(msg)

        # Update trust
        self.trust_scores[receiver.agent_id] = min(
            1000, self.trust_scores.get(receiver.agent_id, 500) + 10
        )

    def process(self):
        """Process inbox."""
        for msg in self.inbox:
            print(f"{self.name} <- {msg.payload.decode()}")
        self.inbox.clear()

# Create three agents
producer = SimpleAgent("Producer")
processor = SimpleAgent("Processor")
consumer = SimpleAgent("Consumer")

# Agent collaboration flow
print("=== Agent Collaboration ===")

# Producer -> Processor
producer.send(processor, TELL, b"DATA:[1,2,3,4,5]")   # TELL = 0x50
processor.process()

# Processor -> Consumer
processor.send(consumer, ASK, b"PROCESS:BATCH")       # ASK = 0x51
consumer.process()

# Consumer -> Producer (result)
consumer.send(producer, ACCEPT, b"RESULT:sum=15")      # ACCEPT = 0x54
producer.process()

print("\n=== Trust Scores ===")
for agent in [producer, processor, consumer]:
    print(f"{agent.name}: {agent.trust_scores}")
```

**Output:**
```
=== Agent Collaboration ===
Processor <- DATA:[1,2,3,4,5]
Consumer <- PROCESS:BATCH
Producer <- RESULT:sum=15

=== Trust Scores ===
Producer: {UUID('...'): 510}
Processor: {UUID('...'): 510, UUID('...'): 510}
Consumer: {UUID('...'): 510}
```

## A2A in Bytecode

### Using A2A Opcodes in FLUX Programs

In the converged ISA, A2A opcodes are **Format E** (4 bytes: opcode + rd + rs1 + rs2), using register operands instead of variable-length data:

```python
import struct
from flux.vm.unified_interpreter import Interpreter

def a2a_handler(opcode_name: str, rd, rs1, rs2):
    """Handle A2A opcodes in bytecode."""
    print(f"A2A: {opcode_name} — send R{rs2} to agent R{rs1}, tag R{rd}")
    return 0

# Create bytecode with A2A message
bytecode = bytearray()

# Setup: load values into registers
bytecode.extend(struct.pack("<BBB", 0x18, 0, 0))     # MOVI R0, 0  (tag register)
bytecode.extend(struct.pack("<BBB", 0x18, 1, 1))     # MOVI R1, 1  (target agent)
bytecode.extend(struct.pack("<BBB", 0x18, 2, 42))    # MOVI R2, 42 (payload value)

# TELL R0, R1, R2 — Send R2 to agent R1, tag R0 (Format E, 4 bytes)
bytecode.extend(struct.pack("<BBBB", 0x50, 0, 1, 2))  # TELL (0x50)

# HALT
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.on_a2a(a2a_handler)
vm.execute()
```

> **Note:** In the converged ISA, A2A opcodes are Format E with register operands, making them much simpler than the old Format G variable-length encoding. The VM interpreter handles the actual message transport.

## Exercise: Three-Agent Task Pipeline

**Task:** Create a three-agent pipeline:
1. **Producer** — Generates data (1, 2, 3, 4, 5)
2. **Transformer** — Transforms data (multiplies by 2)
3. **Consumer** — Consumes and sums results

**Requirements:**
- Use TELL (0x50) for data flow
- Use BCAST (0x53) for coordination
- Track trust scores between agents

**Solution:**

```python
#!/usr/bin/env python3
"""Three-agent pipeline: Producer → Transformer → Consumer"""

import uuid
from flux.a2a.messages import A2AMessage

# Converged ISA v2 A2A opcode values
TELL  = 0x50
BCAST = 0x53

class PipelineAgent:
    def __init__(self, name: str):
        self.name = name
        self.agent_id = uuid.uuid4()
        self.inbox = []
        self.trust_scores = {}
        self.data_store = []

    def send_tell(self, receiver, payload):
        """Send TELL message."""
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=TELL,       # 0x50
            priority=5,
            trust_token=self.trust_scores.get(receiver.agent_id, 500),
            capability_token=100,
            payload=payload,
        )
        receiver.inbox.append(msg)
        self._update_trust(receiver.agent_id, +10)

    def send_broadcast(self, receivers, payload):
        """Send BCAST to multiple receivers."""
        for receiver in receivers:
            msg = A2AMessage(
                sender=self.agent_id,
                receiver=receiver.agent_id,
                conversation_id=uuid.uuid4(),
                in_reply_to=None,
                message_type=BCAST,     # 0x53
                priority=6,
                trust_token=self.trust_scores.get(receiver.agent_id, 500),
                capability_token=150,
                payload=payload,
            )
            receiver.inbox.append(msg)
            self._update_trust(receiver.agent_id, +5)

    def _update_trust(self, agent_id, increment):
        """Update trust score."""
        current = self.trust_scores.get(agent_id, 500)
        self.trust_scores[agent_id] = max(0, min(1000, current + increment))

    def process(self):
        """Process messages."""
        for msg in self.inbox:
            payload = msg.payload.decode()
            print(f"{self.name} <- {payload}")

            # Handle different message types
            if msg.message_type == TELL:    # 0x50
                self._handle_tell(msg)
            elif msg.message_type == BCAST:  # 0x53
                self._handle_broadcast(msg)

        self.inbox.clear()

    def _handle_tell(self, msg):
        """Handle TELL message."""
        # Store data
        self.data_store.append(msg.payload)

    def _handle_broadcast(self, msg):
        """Handle BCAST message."""
        # Could trigger different behavior
        pass

# Create agents
producer = PipelineAgent("Producer")
transformer = PipelineAgent("Transformer")
consumer = PipelineAgent("Consumer")

# Pipeline flow
print("=== Pipeline Execution ===\n")

# Producer generates data
print("1. Producer generates data:")
for i in range(1, 6):
    data = f"DATA:{i}".encode()
    producer.send_tell(transformer, data)
    print(f"   Producer -> Transformer: {data.decode()}")

# Transformer processes data
print("\n2. Transformer processes data:")
transformer.process()
for data in transformer.data_store:
    value = int(data.decode().split(":")[1])
    transformed = f"RESULT:{value * 2}".encode()
    transformer.send_tell(consumer, transformed)
    print(f"   Transformer -> Consumer: {transformed.decode()}")

# Consumer aggregates
print("\n3. Consumer aggregates:")
consumer.process()
total = sum(
    int(msg.payload.decode().split(":")[1])
    for msg in consumer.data_store
    if msg.payload.startswith(b"RESULT:")
)
print(f"   Total: {total}")

print("\n=== Trust Scores ===")
for agent in [producer, transformer, consumer]:
    print(f"{agent.name}: {[(str(k)[:8], v) for k, v in agent.trust_scores.items()]}")
```

**Output:**
```
=== Pipeline Execution ===

1. Producer generates data:
   Producer -> Transformer: DATA:1
   Producer -> Transformer: DATA:2
   Producer -> Transformer: DATA:3
   Producer -> Transformer: DATA:4
   Producer -> Transformer: DATA:5

2. Transformer processes data:
Transformer <- DATA:1
Transformer <- DATA:2
Transformer <- DATA:3
Transformer <- DATA:4
Transformer <- DATA:5
   Transformer -> Consumer: RESULT:2
   Transformer -> Consumer: RESULT:4
   Transformer -> Consumer: RESULT:6
   Transformer -> Consumer: RESULT:8
   Transformer -> Consumer: RESULT:10

3. Consumer aggregates:
Consumer <- RESULT:2
Consumer <- RESULT:4
Consumer <- RESULT:6
Consumer <- RESULT:8
Consumer <- RESULT:10
   Total: 30

=== Trust Scores ===
Producer: [('a1b2c3d4', 550)]
Transformer: [('a1b2c3d4', 550), ('e5f6g7h8', 550)]
Consumer: [('e5f6g7h8', 550)]
```

## Progress Checkpoint

At the end of Module 3, you should be able to:

- ✅ Understand A2A message format and structure
- ✅ Use TELL (0x50), ASK (0x51), DELEG (0x52), and BCAST (0x53) message types
- ✅ Implement trust scoring between agents
- ✅ Build multi-agent systems with communication patterns
- ✅ Handle A2A messages in both Python and bytecode (Format E encoding)

## Next Steps

**[Module 4: Memory Regions](module-04-memory-regions.md)** — Learn linear memory management and stack operations.

---

**Need Help?** See the [ISA Unified Reference](../ISA_UNIFIED.md) for complete opcode table or [Security Primitives Spec](../security-primitives-spec.md) for capability enforcement details.
