"""Voor alle agent-tests: geen netwerk. Een verbindingspoging faalt hard (geen stille fallback)."""
import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("NETWORK-ATTEMPT: netwerk is niet toegestaan in agent-tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
