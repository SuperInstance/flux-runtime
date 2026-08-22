"""FLUX Agent Communication Protocol — typed messages, channels, and agent discovery.

This package provides a higher-level protocol layer on top of the binary
A2A message format.  It introduces:

- **Typed message envelopes** (Request, Response, Event, Error) with
  structured payloads and metadata.
- **Communication channels** (DirectChannel, BroadcastChannel, TopicChannel)
  for different message routing patterns.
- **Agent registry** for service discovery and capability-based routing.
- **Capability negotiation** and trust handshaking for secure agent interaction.
- **Message serialization** to/from bytecode-compatible binary format.
"""

from .channel import (
    BroadcastChannel,
    Channel,
    DirectChannel,
    TopicChannel,
)
from .message import (
    Error,
    Event,
    MessageEnvelope,
    MessageId,
    MessageKind,
    Request,
    Response,
)
from .negotiation import (
    CapabilityOffer,
    NegotiationState,
    Negotiator,
    TrustHandshake,
)
from .registry import (
    AgentDescriptor,
    AgentRegistry,
    CapabilityDescriptor,
)
from .serialization import (
    BinaryMessageCodec,
    MessageSerializer,
)

__all__ = [
    # Messages
    "MessageKind", "MessageEnvelope", "Request", "Response", "Event", "Error",
    "MessageId",
    # Channels
    "Channel", "DirectChannel", "BroadcastChannel", "TopicChannel",
    # Registry
    "AgentDescriptor", "CapabilityDescriptor", "AgentRegistry",
    # Negotiation
    "NegotiationState", "CapabilityOffer", "TrustHandshake", "Negotiator",
    # Serialization
    "MessageSerializer", "BinaryMessageCodec",
]
