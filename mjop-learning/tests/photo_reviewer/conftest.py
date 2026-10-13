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


AUTH_KEY = "test-only-human-approver-key-0123456789abcdef"


@pytest.fixture
def approved_gate(monkeypatch, tmp_path):
    """Alleen voor tests: provider tijdelijk APPROVED, sleutel en tweede sleutel gezet, tijdelijk grootboek buiten de repository.
    Geeft het grootboek terug. In productie staat de provider op NOT_APPROVED."""
    import vision_budget_ledger as L
    from agent.photo import safety_gate as G
    monkeypatch.setitem(G.PROVIDER_APPROVALS, "anthropic", {"status": "APPROVED", "reason": "alleen test"})
    monkeypatch.setenv(G.ENV_AUTH_KEY, AUTH_KEY)
    monkeypatch.setenv("MJOP_PHOTO_EXTERNAL_CONSENT_ID", "PCON-00001")
    d = tmp_path / "ledger"
    d.mkdir(mode=0o700)
    return L.FileBudgetLedger(str(d))
