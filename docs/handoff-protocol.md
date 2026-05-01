# Handoff Protocol Specification

## Overview

The handoff protocol defines how the frontdesk service transfers calls to specialized desk services (faultdesk, billingdesk, etc.) using WebSocket communication. This protocol enables seamless service-to-service handoff while maintaining audio streaming and context transfer.

## Design Goals

1. **Transparent Handoff**: End user experiences no interruption or reconnection
2. **Stateless Desks**: Each desk service receives complete context needed to handle the call
3. **Bidirectional Communication**: Both audio and control messages flow in both directions
4. **Extensible**: Easy to add new desk services without modifying the protocol
5. **Error Handling**: Graceful degradation and fallback mechanisms

## Connection Flow

```
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│   Browser   │          │  Frontdesk  │          │  Faultdesk  │
└──────┬──────┘          └──────┬──────┘          └──────┬──────┘
       │                        │                        │
       │ 1. WS /ws/voice        │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │ 2. audio frames        │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │   (User expresses      │                        │
       │    fault intent)       │                        │
       │                        │                        │
       │                        │ 3. WS /ws/desk         │
       │                        ├───────────────────────>│
       │                        │                        │
       │                        │ 4. handoff_init        │
       │                        ├───────────────────────>│
       │                        │                        │
       │                        │ 5. handoff_ack         │
       │                        │<───────────────────────┤
       │                        │                        │
       │ 6. audio frames        │ 7. audio frames        │
       ├───────────────────────>├───────────────────────>│
       │                        │                        │
       │ 8. audio response      │ 9. audio response      │
       │<───────────────────────┤<───────────────────────┤
       │                        │                        │
       │ (Conversation continues with faultdesk)         │
       │                        │                        │
       │                        │ 10. session_end        │
       │                        │<───────────────────────┤
       │                        │                        │
       │ 11. session_end        │                        │
       │<───────────────────────┤                        │
       │                        │                        │
```

## Message Types

### 1. handoff_init (Frontdesk → Desk)

Initiates the handoff by transferring call context to the desk service.

```json
{
  "type": "handoff_init",
  "call_id": "call_abc123",
  "triage_summary": "インターネットが3日前から繋がらない",
  "caller_attrs": {
    "phone_number": "+81-3-1234-5678",
    "area_code_hint": "03",
    "customer_id": null
  },
  "source_phase": "triage",
  "context": {
    "conversation_length_sec": 45,
    "sentiment": "frustrated",
    "urgency": "high"
  },
  "timestamp": "2026-05-01T03:12:34.567Z"
}
```

**Fields:**
- `call_id`: Unique identifier for this call (UUID format)
- `triage_summary`: Natural language summary of customer's intent
- `caller_attrs`: Known attributes about the caller
- `source_phase`: Phase in frontdesk before handoff (typically "triage")
- `context`: Optional additional context (sentiment, urgency, etc.)
- `timestamp`: ISO 8601 timestamp

### 2. handoff_ack (Desk → Frontdesk)

Acknowledges receipt of handoff and confirms readiness to receive audio.

```json
{
  "type": "handoff_ack",
  "ready": true,
  "desk_session_id": "session_xyz789",
  "message": "Fault desk ready to receive call",
  "timestamp": "2026-05-01T03:12:34.890Z"
}
```

**Fields:**
- `ready`: Boolean indicating if desk is ready
- `desk_session_id`: Session ID created by desk service
- `message`: Optional human-readable status message
- `timestamp`: ISO 8601 timestamp

### 3. audio (Bidirectional)

Carries audio data in both directions.

```json
{
  "type": "audio",
  "audio": "base64_encoded_pcm16_data...",
  "direction": "upstream",
  "timestamp": "2026-05-01T03:12:35.123Z"
}
```

**Fields:**
- `audio`: Base64-encoded PCM16 audio (24kHz, mono)
- `direction`: "upstream" (to desk) or "downstream" (from desk to frontdesk/browser)
- `timestamp`: Optional timestamp

**Audio Format:**
- Encoding: PCM16 (16-bit signed integer)
- Sample Rate: 24000 Hz
- Channels: 1 (mono)
- Frame Size: Typically 20-60ms chunks

### 4. control (Bidirectional)

Control messages for managing the call state.

```json
{
  "type": "control",
  "action": "pause",
  "params": {
    "reason": "user_requested"
  }
}
```

**Actions:**
- `pause`: Temporarily pause audio processing
- `resume`: Resume audio processing
- `end`: End the call
- `mute`: Mute microphone
- `unmute`: Unmute microphone

### 5. transcript (Desk → Frontdesk → Browser)

Transcript of conversation for display.

```json
{
  "type": "transcript",
  "role": "assistant",
  "text": "かしこまりました。お客様のお名前を教えていただけますか？",
  "is_final": true,
  "timestamp": "2026-05-01T03:12:36.456Z"
}
```

### 6. phase_changed (Desk → Frontdesk → Browser)

Notification of phase transition in desk service.

```json
{
  "type": "phase_changed",
  "from": "identity",
  "to": "interview",
  "trigger": "tool:verify_identity",
  "timestamp": "2026-05-01T03:13:45.789Z"
}
```

### 7. slots_snapshot (Desk → Frontdesk → Browser)

Current state of all slots in the active phase.

```json
{
  "type": "slots_snapshot",
  "phase": "interview",
  "slots": [
    {
      "name": "fault_symptom",
      "status": "filled",
      "value": "ネット不通",
      "required": true
    },
    {
      "name": "fault_started_at",
      "status": "pending",
      "required": true
    },
    {
      "name": "indoor_env",
      "status": "pending",
      "required": true
    }
  ],
  "timestamp": "2026-05-01T03:14:12.345Z"
}
```

### 8. tool_call (Desk → Frontdesk → Browser)

Notification of tool execution (for UI display and logging).

```json
{
  "type": "tool_call",
  "tool_name": "verify_identity",
  "arguments": {
    "customer_id": "12345678",
    "name": "山田太郎"
  },
  "call_id": "call_tool_001",
  "status": "completed",
  "result": {
    "verified": true,
    "customer_record": {...}
  },
  "timestamp": "2026-05-01T03:13:30.123Z"
}
```

### 9. session_end (Desk → Frontdesk)

Indicates the desk service has completed handling the call.

```json
{
  "type": "session_end",
  "reason": "normal",
  "message": "Call completed successfully",
  "return_to_frontdesk": false,
  "timestamp": "2026-05-01T03:20:15.678Z"
}
```

**Reasons:**
- `normal`: Call completed successfully
- `error`: Error occurred during processing
- `escalate`: Customer needs to be escalated to human operator
- `timeout`: Session timed out

**Fields:**
- `return_to_frontdesk`: If true, control should return to frontdesk (for escalation scenarios)

### 10. error (Bidirectional)

Error notification.

```json
{
  "type": "error",
  "code": "DESK_UNAVAILABLE",
  "message": "Fault desk service is temporarily unavailable",
  "details": {
    "retry_after": 30
  },
  "timestamp": "2026-05-01T03:12:40.123Z"
}
```

## State Machine

### Frontdesk States

```
┌─────────────────────┐
│  INITIAL (Triage)   │
└──────────┬──────────┘
           │
           │ route_to_*_desk() tool called
           ▼
┌─────────────────────┐
│  HANDOFF_INITIATED  │
└──────────┬──────────┘
           │
           │ Connect to desk WS
           ▼
┌─────────────────────┐
│  HANDOFF_CONNECTING │
└──────────┬──────────┘
           │
           │ handoff_init sent
           ▼
┌─────────────────────┐
│  HANDOFF_PENDING    │
└──────────┬──────────┘
           │
           │ handoff_ack received
           ▼
┌─────────────────────┐
│  HANDOFF_ACTIVE     │ (Bridging audio)
└──────────┬──────────┘
           │
           │ session_end received
           ▼
┌─────────────────────┐
│  CALL_COMPLETE      │
└─────────────────────┘
```

### Desk States

```
┌─────────────────────┐
│  WAITING            │
└──────────┬──────────┘
           │
           │ WS connection + handoff_init received
           ▼
┌─────────────────────┐
│  INITIALIZING       │
└──────────┬──────────┘
           │
           │ Create Voice Live session
           ▼
┌─────────────────────┐
│  READY              │
└──────────┬──────────┘
           │
           │ Send handoff_ack
           ▼
┌─────────────────────┐
│  ACTIVE             │ (Processing call)
└──────────┬──────────┘
           │
           │ Call ends or escalates
           ▼
┌─────────────────────┐
│  CLOSING            │
└──────────┬──────────┘
           │
           │ Send session_end
           ▼
┌─────────────────────┐
│  CLOSED             │
└─────────────────────┘
```

## Error Handling

### Desk Unavailable

If desk service is unavailable:

```python
# Frontdesk response
{
  "type": "error",
  "code": "DESK_UNAVAILABLE",
  "message": "申し訳ございません。現在システムが混み合っております。",
  "details": {"desk": "faultdesk"}
}

# Then either:
# 1. Retry after delay
# 2. Route to alternative desk
# 3. Escalate to human operator
```

### Handoff Timeout

If `handoff_ack` not received within 5 seconds:

```python
# Frontdesk closes WS to desk
# Returns to triage agent
# Informs user: "申し訳ございません。接続に失敗しました。もう一度お試しください。"
```

### Mid-Call Disconnection

If desk service disconnects during call:

```python
# Frontdesk detects WS close
# Recreates triage session
# Informs user: "接続が切断されました。最初からやり直させていただけますか？"
```

## Performance Considerations

### Latency Targets

- Handoff initiation → handoff_ack: < 500ms
- Audio frame transmission: < 100ms per frame
- Phase change notification: < 200ms

### Throughput

- Audio frame size: 20-60ms chunks (typical 40ms = 1920 bytes PCM16)
- Frame rate: ~25 frames/second for 40ms chunks
- Bandwidth: ~384 kbps (24kHz × 16-bit × 1 channel)

### Scalability

- Desk services should be horizontally scalable
- Each desk instance handles multiple concurrent calls
- Load balancer distributes handoffs across instances

## Security

### Authentication

- Desk services require API key or mutual TLS for WS connections
- Frontdesk authenticates before handoff_init

### Data Privacy

- Audio data encrypted in transit (WSS)
- PII in caller_attrs should be minimal
- Full customer data retrieved by desk service using caller_attrs hints

### Audit Trail

- All handoff messages logged with call_id
- Enables replay and debugging
- Retention policy: 90 days

## Testing

### Unit Tests

- Message serialization/deserialization
- State machine transitions
- Error handling paths

### Integration Tests

- Full handoff flow: frontdesk → faultdesk
- Audio streaming continuity
- Error recovery scenarios

### Load Tests

- Multiple concurrent handoffs
- Desk service capacity limits
- Network partition handling

## Implementation Checklist

- [ ] Define message schemas (Pydantic models)
- [ ] Implement frontdesk handoff manager
- [ ] Implement desk handoff receiver
- [x] Audio bridge implementation (upstream: browser → frontdesk → desk via /ws/voice audio frames)
- [ ] State machine for both sides
- [ ] Error handling and retry logic
- [ ] Logging and monitoring
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation

## Example Implementation

See:
- `services/frontdesk/app/handoff/manager.py` - Frontdesk handoff manager
- `services/faultdesk/app/handoff/inbound.py` - Desk handoff receiver
- `packages/voiceshared/ws_protocol/handoff.py` - Message definitions
