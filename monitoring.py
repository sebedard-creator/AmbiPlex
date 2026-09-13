import asyncio
from collections import deque


class MonitorMailbox:
    """Keep events in order and at most one pending LED preview per browser."""

    def __init__(self):
        self._events = deque()
        self._monitoring = None
        self._ready = asyncio.Event()

    async def put(self, data):
        if data.get("type") == "monitoring":
            self._monitoring = data
        else:
            self._events.append(data)
        self._ready.set()

    async def get(self):
        await self._ready.wait()
        if self._events:
            data = self._events.popleft()
        else:
            data, self._monitoring = self._monitoring, None
        if not self._events and self._monitoring is None:
            self._ready.clear()
        return data
