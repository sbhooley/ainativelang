"""
OpenFang Channel Adapter

Maps OpenFang's channel/topic system to AINL tool calls, enabling
AINL graphs to publish/subscribe to OpenFang channels seamlessly.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass
import asyncio
import json
from pathlib import Path


@dataclass
class Channel:
    """Represents an OpenFang communication channel."""
    name: str
    topic: str
    qos: int = 0  # quality of service level
    retention: Optional[float] = None  # retention period in seconds


class OpenFangChannelAdapter:
    """Adapter that bridges OpenFang channels to AINL tool calls."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._channels: Dict[str, Channel] = {}
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._initialize_default_channels()

    def _initialize_default_channels(self) -> None:
        """Set up standard OpenFang channels."""
        defaults = [
            Channel("ainl_control", "ainl/control", qos=2),
            Channel("ainl_metrics", "ainl/metrics", qos=1),
            Channel("ainl_alerts", "ainl/alerts", qos=2),
            Channel("openfang_events", "openfang/events", qos=0),
        ]
        for ch in defaults:
            self._channels[ch.name] = ch

    def register_channel(self, channel: Channel) -> None:
        """Register a new channel with the adapter."""
        self._channels[channel.name] = channel

    async def publish(self, channel_name: str, message: Dict[str, Any]) -> bool:
        """Publish a message to an OpenFang channel (called from AINL tool)."""
        if channel_name not in self._channels:
            return False
        # In a real implementation, this would send to OpenFang's router
        # For now, log to file or trigger subscriptions
        await self._deliver_to_subscribers(channel_name, message)
        return True

    def subscribe(self, channel_name: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Subscribe to messages on a channel (external OpenFang components can register)."""
        if channel_name not in self._subscriptions:
            self._subscriptions[channel_name] = []
        self._subscriptions[channel_name].append(callback)

    async def _deliver_to_subscribers(self, channel_name: str, message: Dict[str, Any]) -> None:
        """Deliver a message to all subscribers of a channel."""
        subs = self._subscriptions.get(channel_name, [])
        await asyncio.gather(*[sub(message) for sub in subs], return_exceptions=True)

    def to_ainl_tool_spec(self) -> Dict[str, Any]:
        """Generate an AINL tool specification for channel operations."""
        return {
            "tool": "openfang_channel",
            "description": "Publish/subscribe to OpenFang channels",
            "inputs": {
                "action": "string - 'publish' or 'subscribe'",
                "channel": "string - channel name",
                "message": "object - payload (for publish)",
                "callback": "string - AINL graph node ID to invoke on message (for subscribe)",
            },
            "outputs": {
                "success": "boolean",
                "message_id": "string (if published)",
            },
        }
