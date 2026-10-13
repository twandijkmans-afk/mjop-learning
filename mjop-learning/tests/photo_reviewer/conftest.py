"""Voor alle Photo Reviewer-tests: geen netwerk (een verbindingspoging faalt hard) en geen echte providerconfiguratie."""
import os
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("NETWORK-ATTEMPT: netwerk is niet toegestaan in Photo Reviewer-tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MJOP_PHOTO_EXTERNAL_CONSENT_ID", raising=False)
