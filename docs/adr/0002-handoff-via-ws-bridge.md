# ADR 0002: Handoff via WebSocket Bridge

## Status
Accepted

## Context
When frontdesk routes a call to a specialized desk (faultdesk), we need to transfer the audio stream and context without disconnecting the end user.

Options considered:
1. **Disconnect and Reconnect**: Browser disconnects from frontdesk, connects to faultdesk
2. **HTTP Redirect**: Use HTTP 301/302 to redirect WebSocket connection
3. **WebSocket Bridge**: Frontdesk maintains browser connection, bridges to faultdesk
4. **Session Transfer**: Transfer Voice Live session state between services

## Decision
We implement **WebSocket bridging** where frontdesk maintains the browser connection and establishes a secondary connection to faultdesk, relaying audio and control messages bidirectionally.

## Rationale

### Why WebSocket Bridge:
1. **Transparent to User**: Browser never disconnects; no audible interruption
2. **Simple Browser Client**: No complex reconnection logic needed in frontend
3. **Controlled Handoff**: Frontdesk orchestrates handoff, can implement retry/fallback
4. **Context Transfer**: Frontdesk sends structured handoff message with context
5. **Monitoring**: Frontdesk can monitor handoff success and intervene if needed

### How It Works:

```
Browser                 Frontdesk                 Faultdesk
  │                        │                        │
  │─────audio frames──────>│                        │
  │                        │                        │
  │                        │ (route_to_fault_desk   │
  │                        │  tool called)          │
  │                        │                        │
  │                        │──WS connect /ws/desk──>│
  │                        │                        │
  │                        │──handoff_init────────>│
  │                        │                        │
  │                        │<─handoff_ack───────────│
  │                        │                        │
  │─────audio frames──────>│─────audio frames─────>│
  │<────audio frames───────│<────audio frames──────│
  │                        │                        │
```

### Implementation Approach:

```python
class HandoffBridge:
    def __init__(self, browser_ws: WebSocket, desk_ws: WebSocket):
        self.browser_ws = browser_ws
        self.desk_ws = desk_ws
        self.active = True

    async def bridge_audio(self):
        async def upstream():
            # Browser → Desk
            async for message in self.browser_ws:
                if message["type"] == "audio":
                    await self.desk_ws.send_json({
                        "type": "audio",
                        "audio": message["audio"],
                        "direction": "upstream"
                    })

        async def downstream():
            # Desk → Browser
            async for message in self.desk_ws:
                if message["type"] == "audio":
                    await self.browser_ws.send_json({
                        "type": "audio",
                        "audio": message["audio"]
                    })

        await asyncio.gather(upstream(), downstream())
```

## Consequences

### Positive:
- **Zero User Impact**: No disconnection or re-authentication
- **Flexible Routing**: Can route to different desks dynamically
- **Fallback Capability**: If desk unavailable, can return to frontdesk
- **Simplified Client**: Browser client remains simple
- **Audit Trail**: Frontdesk logs all handoffs

### Negative:
- **Extra Hop**: Adds latency (Browser → Frontdesk → Faultdesk)
- **Frontdesk Load**: Frontdesk must relay all audio frames
- **Connection Management**: Frontdesk manages two WebSocket connections
- **Error Handling**: Must handle desk disconnection gracefully

### Trade-offs Accepted:

**Latency Overhead**:
- Acceptable: Typical WS relay adds ~10-20ms
- Audio frame size: 40ms chunks, so 10ms << frame duration
- User won't perceive difference

**Frontdesk Resource Usage**:
- Acceptable: Audio relay is lightweight (no processing)
- Frontdesk can handle 100+ concurrent bridges on single instance
- Horizontal scaling available if needed

## Alternatives Considered

### 1. Disconnect and Reconnect
**Rejected because**:
- Poor user experience (audible gap)
- Complex error recovery if reconnection fails
- Browser must handle multiple WebSocket URLs
- State synchronization becomes complex

### 2. HTTP Redirect
**Rejected because**:
- WebSocket doesn't support HTTP redirects after upgrade
- Would require disconnect/reconnect anyway
- No standard WebSocket redirect mechanism

### 3. Session Transfer
**Rejected because**:
- Voice Live sessions are not transferable between services
- Would require complex state serialization
- Potential for state corruption
- Doesn't eliminate the need for new connection

## Implementation Checklist
- [x] Define handoff protocol messages
- [ ] Implement HandoffBridge class in frontdesk
- [ ] Implement bidirectional audio relay
- [ ] Handle desk connection failures
- [ ] Implement desk unavailable fallback
- [ ] Monitor and log handoff metrics
- [ ] Test latency impact
- [ ] Test concurrent handoffs

## Monitoring

Key metrics to track:
- Handoff latency (initiation to first audio frame)
- Audio frame relay latency
- Handoff success rate
- Desk connection failures
- Concurrent bridge count

Target SLOs:
- Handoff initiation: < 500ms
- Per-frame relay overhead: < 20ms
- Success rate: > 99%

## Future Enhancements
- **Direct Connection Option**: For production, consider allowing browser to connect directly to desk after initial handoff
- **Multi-Hop Routing**: Support routing through multiple desks (e.g., frontdesk → triage desk → specialist desk)
- **Load Balancing**: Frontdesk can load-balance across multiple faultdesk instances

## References
- [WebSocket RFC 6455](https://tools.ietf.org/html/rfc6455)
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [Voice Live API Best Practices](https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio-quickstart)
