import pytest
from app.websocket.manager import ConnectionManager

class MockWebsocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        self.messages.append(data)

@pytest.mark.asyncio
async def test_websocket_manager():
    manager = ConnectionManager()
    ws1 = MockWebsocket()
    ws2 = MockWebsocket()

    await manager.connect(ws1, "INT-001")
    await manager.connect(ws2, "INT-002")

    assert ws1.accepted is True
    assert "INT-001" in manager.active_connections

    await manager.broadcast_to_intersection("INT-001", "Hello INT 1")
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 0

    manager.disconnect(ws1, "INT-001")
    assert "INT-001" not in manager.active_connections