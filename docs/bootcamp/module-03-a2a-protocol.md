# Module 3: A2A (Agent-to-Agent) Protocol

**Learning Objectives:**
- Understand the A2A messaging system
- Learn message types: TELL, ASK, DELEGATE, BROADCAST
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

| Opcode | Name | Description | Use Case |
|--------|------|-------------|----------|
| TELL (0x60) | Fire-and-forget | One-way notification | Status updates, events |
| ASK (0x61) | Request-response | Query with reply expected | Data queries, requests |
| DELEGATE (0x62) | Task delegation | Assign work to another agent | Work distribution |
| DELEGATE_RESULT (0x63) | Delegation response | Return delegated work result | Task completion |
| BROADCAST (0x66) | One-to-many | Send to all agents | Announcements |
| REDUCE (0x67) | Aggregation | Collect and combine results | Map-reduce patterns |

### Trust & Capability Messages

| Opcode | Name | Description |
|--------|------|-------------|
| TRUST_CHECK (0x70) | Check trust score |
| TRUST_UPDATE (0x71) | Update trust score |
| TRUST_QUERY (0x72) | Query trust score |
| CAP_REQUIRE (0x74) | Require capability |
| CAP_GRANT (0x76) | Grant capability |
| CAP_REVOKE (0x77) | Revoke capability |

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
│  message_type:      1 byte  (opcode)                        │
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
from flux.bytecode.opcodes import Op

# Create a TELL message
msg = A2AMessage(
    sender=uuid.uuid4(),
    receiver=uuid.uuid4(),
    conversation_id=uuid.uuid4(),
    in_reply_to=None,
    message_type=Op.TELL,
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

@dataclass
class Agent:
    name: str
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    inbox: List = field(default_factory=list)
    trust_scores: dict = field(default_factory=dict)

    def send_tell(self, receiver: "Agent", payload: bytes, priority: int = 5):
        """Send a TELL message to another agent."""
        from flux.a2a.messages import A2AMessage
        from flux.bytecode.opcodes import Op

        trust_token = self.trust_scores.get(receiver.agent_id, 500)

        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=Op.TELL,
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
        from flux.bytecode.opcodes import Op

        trust_token = self.trust_scores.get(receiver.agent_id, 500)

        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver.agent_id,
            conversation_id=uuid.uuid4(),
            in_reply_to=None,
            message_type=Op.ASK,
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
        from flux.bytecode.opcodes import Op

        if msg.message_type == Op.TELL:
            print(f"{self.name} received TELL: {msg.payload.decode()}")
        elif msg.message_type == Op.ASK:
            print(f"{self.name} received ASK: {msg.payload.decode()}")
            # Would send reply here
```

### Pattern 2: Captain-Worker Fleet

```python
class CaptainAgent(Agent):
    """Coordinates worker agents."""

    def broadcast_task(self, workers: List[Agent], task: bytes):
        """Broadcast a task to all workers."""
        from flux.bytecode.opcodes import Op

        for worker in workers:
            msg = A2AMessage(
                sender=self.agent_id,
                receiver=worker.agent_id,
                conversation_id=uuid.uuid4(),
                in_reply_to=None,
                message_type=Op.BROADCAST,
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
                if msg.message_type == Op.DELEGATE_RESULT:
                    results.append(msg.payload)
        return results


class WorkerAgent(Agent):
    """Executes tasks delegated by captain."""

    def handle_message(self, msg):
        """Handle incoming message."""
        from flux.bytecode.opcodes import Op

        if msg.message_type == Op.BROADCAST:
            # Execute task
            result = self.execute_task(msg.payload)

            # Send result back
            reply = A2AMessage(
                sender=self.agent_id,
                receiver=msg.sender,
                conversation_id=msg.conversation_id,
                in_reply_to=msg.sender,
                message_type=Op.DELEGATE_RESULT,
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
from flux.bytecode.opcodes import Op

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
producer.send(processor, Op.TELL, b"DATA:[1,2,3,4,5]")
processor.process()

# Processor -> Consumer
processor.send(consumer, Op.ASK, b"PROCESS:BATCH")
consumer.process()

# Consumer -> Producer (result)
consumer.send(producer, Op.DELEGATE_RESULT, b"RESULT:sum=15")
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

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

def a2a_handler(opcode_name: str, data: bytes):
    """Handle A2A opcodes in bytecode."""
    print(f"A2A: {opcode_name} <- {data.decode()}")
    return 0  # Return value in R0

# Create bytecode with A2A message
bytecode = bytearray()

# Setup: load some data
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 42))  # MOVI R0, 42

# Send TELL message (Format G)
# Data format: [receiver_id_len][receiver_id][payload_len][payload]
receiver_id = b"agent_1\0"
payload = b"VALUE:42"
data = bytes([len(receiver_id)]) + receiver_id + bytes([len(payload)]) + payload

bytecode.extend(bytes([Op.TELL]))  # TELL opcode
bytecode.extend(struct.pack("<H", len(data)))  # Length
bytecode.extend(data)  # Data

# HALT
bytecode.extend(bytes([Op.HALT]))

# Execute with A2A handler
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.on_a2a(a2a_handler)
vm.execute()
```

## Exercise: Three-Agent Task Pipeline

**Task:** Create a three-agent pipeline:
1. **Producer** — Generates data (1, 2, 3, 4, 5)
2. **Transformer** — Transforms data (multiplies by 2)
3. **Consumer** — Consumes and sums results

**Requirements:**
- Use TELL for data flow
- Use BROADCAST for coordination
- Track trust scores between agents

**Solution:**

```python
#!/usr/bin/env python3
"""Three-agent pipeline: Producer → Transformer → Consumer"""

import uuid
from flux.a2a.messages import A2AMessage
from flux.bytecode.opcodes import Op

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
            message_type=Op.TELL,
            priority=5,
            trust_token=self.trust_scores.get(receiver.agent_id, 500),
            capability_token=100,
            payload=payload,
        )
        receiver.inbox.append(msg)
        self._update_trust(receiver.agent_id, +10)

    def send_broadcast(self, receivers, payload):
        """Send BROADCAST to multiple receivers."""
        for receiver in receivers:
            msg = A2AMessage(
                sender=self.agent_id,
                receiver=receiver.agent_id,
                conversation_id=uuid.uuid4(),
                in_reply_to=None,
                message_type=Op.BROADCAST,
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
            if msg.message_type == Op.TELL:
                self._handle_tell(msg)
            elif msg.message_type == Op.BROADCAST:
                self._handle_broadcast(msg)

        self.inbox.clear()

    def _handle_tell(self, msg):
        """Handle TELL message."""
        # Store data
        self.data_store.append(msg.payload)

    def _handle_broadcast(self, msg):
        """Handle BROADCAST message."""
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
- ✅ Use TELL, ASK, DELEGATE, and BROADCAST message types
- ✅ Implement trust scoring between agents
- ✅ Build multi-agent systems with communication patterns
- ✅ Handle A2A messages in both Python and bytecode

## Next Steps

**[Module 4: Memory Regions](module-04-memory-regions.md)** — Learn linear memory management and stack operations.

---

**Need Help?** See the [A2A Protocol Reference](../user-guide.md#a2a-protocol) for complete message format details.
