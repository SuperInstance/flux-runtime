---
title: A2A Agent Handshake Protocol
version: 1.0
description: Demonstrating agent-to-agent communication through the FLUX A2A protocol
---

# Agent-to-Agent Handshake — The A2A Protocol in Action

FLUX isn't just a compiler — it's a **multi-agent runtime**. Agents communicate
through the A2A (Agent-to-Agent) protocol, a binary message format with trust
gating, capability verification, and priority-based delivery.

This document demonstrates a complete handshake between two agents:
- **Agent A** (Producer) — sends a computation request
- **Agent B** (Worker) — processes the request and replies

## The A2A Message Header

Every A2A message starts with a 52-byte binary header:

```
Offset  Size   Field
  0       16   sender_uuid        (128-bit UUID)
 16       16   receiver_uuid      (128-bit UUID)
 32        8   conversation_id    (compact 64-bit)
 40        1   message_type       (uint8, 0x60-0x7B)
 41        1   priority           (uint8, 0-15)
 42        4   trust_token        (uint32 LE)
 46        4   capability_token   (uint32 LE)
 50        2   in_reply_to        (uint16 LE, 0 = None)
 52      var   payload            (arbitrary bytes)
```

## Agent A: The Producer

Agent A is a C program that prepares data and sends it to Agent B:

```c
int prepare_request(int x, int y) {
    int data = x * 100 + y;
    return data;
}

int main() {
    int request = prepare_request(42, 7);
    return request;
}
```

### What Agent A does:

1. Prepares computation data: `42 * 100 + 7 = 4207`
2. Constructs an A2A message with `message_type = 0x62` (DELEGATE)
3. Sends to Agent B via the local transport
4. Waits for a reply

## Agent B: The Worker

Agent B receives the request, processes it, and replies:

```python
def process(data):
    x = data // 100
    y = data - x * 100
    result = x + y
    return result

def main():
    data = 4207
    result = process(data)
    return result
```

### What Agent B does:

1. Receives the DELEGATE message from Agent A
2. Parses the payload: `x = 42`, `y = 7`
3. Computes: `42 + 7 = 49`
4. Constructs a reply with `message_type = 0x63` (DELEGATE_RESULT)
5. Sends back to Agent A

## The Handshake Sequence

```
  Agent A                          Agent B
    │                                 │
    │  ─── DELEGATE(4207) ──────────>│
    │     msg_type: 0x62              │
    │     priority: 5                 │
    │     trust_token: 0x00001000     │
    │                                 │
    │                          [parse x=42, y=7]
    │                          [compute 42+7=49]
    │                                 │
    │  <── DELEGATE_RESULT(49) ──────│
    │     msg_type: 0x63              │
    │     in_reply_to: 0x0001         │
    │     trust_token: 0x00001000     │
    │                                 │
    [result = 49]                     │
    │                                 │
```

## A2A Opcodes in the FLUX ISA

These opcodes are embedded in bytecode and executed by the VM:

| Opcode  | Name              | Direction       | Purpose |
|---------|-------------------|-----------------|---------|
| 0x60    | TELL              | One-way         | Fire-and-forget message |
| 0x61    | ASK               | Request-reply   | Question with expected answer |
| 0x62    | DELEGATE          | Task assignment | Assign work to another agent |
| 0x63    | DELEGATE_RESULT   | Response        | Return delegated work result |
| 0x64    | REPORT_STATUS     | Status update   | Periodic heartbeat/status |
| 0x65    | REQUEST_OVERRIDE  | Override        | Request another agent yield |
| 0x66    | BROADCAST         | One-to-many     | Send to all registered agents |
| 0x67    | REDUCE            | Aggregation     | Collect and reduce results |
| 0x68    | DECLARE_INTENT    | Declaration     | Announce planned action |
| 0x69    | ASSERT_GOAL       | Goal assertion  | State a goal to achieve |
| 0x6A    | VERIFY_OUTCOME    | Verification    | Check if outcome matches goal |
| 0x6B    | EXPLAIN_FAILURE   | Error report    | Explain why something failed |
| 0x6C    | SET_PRIORITY      | Priority change | Adjust message priority |
| 0x78    | BARRIER           | Synchronization | Wait for all agents to arrive |
| 0x79    | SYNC_CLOCK        | Time sync       | Synchronize agent clocks |
| 0x7B    | EMERGENCY_STOP    | Emergency       | Immediate halt all agents |

## Trust Engine: INCREMENTS+2

Every message carries a `trust_token`. The trust engine computes a
six-dimensional trust score:

| Dimension    | Weight | Method |
|-------------|--------|--------|
| History     | 0.30   | EMA of success/failure |
| Capability  | 0.25   | Capability match score |
| Latency     | 0.20   | Inverse linear (10ms→1.0) |
| Consistency | 0.15   | 1 - coefficient of variation |
| Determinism | 0.05   | Behavioral consistency |
| Audit       | 0.05   | Record existence check |

Trust decays over time:
```
composite *= max(0, 1 - 0.01 * elapsed / 3600)
```

Default trust threshold for message delivery: **0.3**.

## Trust-Gated Delivery

The coordinator checks trust before delivering:

```python
def send_message(sender, receiver, msg_type, payload, priority):
    trust = compute_trust(sender, receiver)
    if trust >= TRUST_THRESHOLD:
        deliver(sender, receiver, msg_type, payload)
        record_interaction(sender, receiver, success=True)
    else:
        record_interaction(sender, receiver, success=False)
        return False  # blocked
```

## Running the Example

```bash
cd /home/z/my-project/flux-py
PYTHONPATH=src python3 -c "
from flux.pipeline.e2e import FluxPipeline
from flux.pipeline.debug import disassemble_bytecode
import pathlib

md = pathlib.Path('examples/04_agent_handshake.md').read_text()
pipeline = FluxPipeline()
result = pipeline.run(md, lang='md')

print(f'Success: {result.success}')
print(f'Cycles: {result.cycles}')
print(f'Bytecode: {len(result.bytecode)} bytes')
"
```

For a full A2A demo with actual agent communication, see `03_a2a_agents.py`.
