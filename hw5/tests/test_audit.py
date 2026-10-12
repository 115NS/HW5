"""The audit trail is append-only and tamper-evident."""

import json

import pytest

from backend.audit import AuditTamperedError, AuditTrail


def make(tmp_path, n=3):
    trail = AuditTrail(tmp_path / "audit_trail.json")
    for i in range(n):
        trail.append(action="tool_call", run_id="r1", ticket_id=101, agent="inventory", step=i, tool={"name": "check_stock"})
    return trail


def test_append_builds_a_valid_chain(tmp_path):
    trail = make(tmp_path)
    entries = json.loads(trail.path.read_text())
    assert [e["seq"] for e in entries] == [0, 1, 2]
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert trail.verify() == (True, [])


def test_edit_is_detected_and_blocks_further_appends(tmp_path):
    trail = make(tmp_path)
    entries = json.loads(trail.path.read_text())
    entries[1]["agent"] = "boss"
    trail.path.write_text(json.dumps(entries))
    ok, problems = trail.verify()
    assert not ok and "entry 1: hash mismatch" in problems[0]
    with pytest.raises(AuditTamperedError):
        trail.append(action="error", run_id="r1", ticket_id=101, agent="boss")


def test_deletion_is_detected(tmp_path):
    trail = make(tmp_path)
    entries = json.loads(trail.path.read_text())
    del entries[1]
    trail.path.write_text(json.dumps(entries))
    assert trail.verify()[0] is False


def test_none_fields_are_omitted(tmp_path):
    trail = AuditTrail(tmp_path / "a.json")
    e = trail.append(action="run_start", run_id="r", ticket_id=None, agent=None, error=None, approval_status="pending_human_approval")
    assert "error" not in e and e["approval_status"] == "pending_human_approval"
