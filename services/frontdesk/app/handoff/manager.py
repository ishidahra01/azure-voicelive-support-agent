"""
Handoff manager.

Manages handoff from frontdesk to desk services, including WebSocket
connection management and audio stream bridging.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import websockets
from fastapi import WebSocket
from voiceshared.ws_protocol.handoff import (
    HandoffAckMessage,
    HandoffInitMessage,
    parse_handoff_message,
)

from .registry import desk_registry

logger = logging.getLogger(__name__)


class HandoffManager:
    """
    Manages handoff to desk services.

    Connects to desk WebSocket, sends handoff_init, bridges audio streams.
    """

    def __init__(self, call_id: str, browser_ws: WebSocket):
        self.call_id = call_id
        self.browser_ws = browser_ws
        self.desk_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.active = False
        self.desk_session_id: Optional[str] = None
        self._upstream_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def initiate_handoff(
        self,
        desk_name: str,
        triage_summary: str,
        caller_attrs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Initiate handoff to a desk service.

        Args:
            desk_name: Name of desk to hand off to
            triage_summary: Summary from triage phase
            caller_attrs: Caller attributes

        Returns:
            True if handoff successful, False otherwise
        """
        try:
            # Get desk URL from registry
            desk_url = desk_registry.get_desk_url(desk_name)
            if not desk_url:
                logger.error(f"No URL found for desk: {desk_name}")
                return False

            logger.info(f"Initiating handoff to {desk_name} for call {self.call_id}")

            # Connect to desk WebSocket
            try:
                self.desk_ws = await websockets.connect(desk_url)
                logger.info(f"Connected to desk {desk_name}")
            except Exception as e:
                logger.error(f"Failed to connect to desk {desk_name}: {e}")
                return False

            # Send handoff_init message
            handoff_init = HandoffInitMessage(
                call_id=self.call_id,
                triage_summary=triage_summary,
                caller_attrs=caller_attrs or {},
                source_phase="triage",
                timestamp=datetime.utcnow(),
            )

            await self.desk_ws.send(handoff_init.model_dump_json())
            logger.info(f"Sent handoff_init to {desk_name}")

            # Wait for handoff_ack
            try:
                response = await asyncio.wait_for(self.desk_ws.recv(), timeout=5.0)
                ack_data = json.loads(response)
                ack_msg = parse_handoff_message(ack_data)

                if isinstance(ack_msg, HandoffAckMessage) and ack_msg.ready:
                    self.desk_session_id = ack_msg.desk_session_id
                    self.active = True
                    logger.info(f"Handoff acknowledged by {desk_name}")

                    # Send handoff status to browser
                    await self.browser_ws.send_json(
                        {
                            "type": "handoff_status",
                            "status": "connected",
                            "target_desk": desk_name,
                            "message": f"Connected to {desk_name}",
                        }
                    )

                    # Start audio bridging
                    asyncio.create_task(self._bridge_audio())

                    return True
                else:
                    logger.error(f"Handoff not ready from {desk_name}")
                    return False

            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for handoff_ack from {desk_name}")
                return False

        except Exception as e:
            logger.error(f"Error during handoff to {desk_name}: {e}", exc_info=True)
            return False

    async def _bridge_audio(self):
        """Bridge audio between browser and desk."""
        if not self.desk_ws:
            return

        logger.info(f"Starting audio bridge for call {self.call_id}")

        try:
            # Create tasks for bidirectional audio streaming
            upstream_task = asyncio.create_task(self._bridge_upstream())
            downstream_task = asyncio.create_task(self._bridge_downstream())

            # Wait for either task to complete (or fail)
            done, pending = await asyncio.wait(
                [upstream_task, downstream_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel remaining task
            for task in pending:
                task.cancel()

            logger.info(f"Audio bridge ended for call {self.call_id}")

        except Exception as e:
            logger.error(f"Error in audio bridge: {e}", exc_info=True)

    async def _bridge_upstream(self):
        """Bridge audio/control from browser to desk (upstream)."""
        if not self.desk_ws:
            return

        logger.debug("Upstream bridge started")

        while self.active and self.desk_ws:
            message = await self._upstream_queue.get()
            try:
                await self.desk_ws.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Desk connection closed for call {self.call_id}")
                self.active = False
                break
            except Exception as e:
                logger.error(f"Error forwarding upstream message: {e}", exc_info=True)

    async def forward_from_browser(self, message: Dict[str, Any]) -> None:
        """Queue a browser-originated message to be forwarded to desk."""
        if not self.active:
            return

        msg_type = message.get("type")
        if msg_type not in {"audio", "control"}:
            return

        await self._upstream_queue.put(message)

    async def _bridge_downstream(self):
        """Bridge audio and messages from desk to browser (downstream)."""
        if not self.desk_ws:
            return

        logger.debug("Downstream bridge started")

        try:
            async for message in self.desk_ws:
                try:
                    # Parse message from desk
                    if isinstance(message, str):
                        data = json.loads(message)

                        # Forward relevant messages to browser
                        msg_type = data.get("type")

                        if msg_type in [
                            "audio",
                            "transcript",
                            "phase_changed",
                            "slots_snapshot",
                            "tool_call",
                            "session_end",
                        ]:
                            await self.browser_ws.send_json(data)

                        # Handle session_end
                        if msg_type == "session_end":
                            logger.info(f"Desk ended session for call {self.call_id}")
                            self.active = False
                            break

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from desk: {message}")
                except Exception as e:
                    logger.error(f"Error processing desk message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Desk connection closed for call {self.call_id}")
            self.active = False
        except Exception as e:
            logger.error(f"Error in downstream bridge: {e}", exc_info=True)
            self.active = False

    async def close(self):
        """Close the handoff and desk connection."""
        self.active = False

        if self.desk_ws:
            try:
                await self.desk_ws.close()
                logger.info(f"Closed desk connection for call {self.call_id}")
            except Exception as e:
                logger.error(f"Error closing desk connection: {e}")

            self.desk_ws = None
