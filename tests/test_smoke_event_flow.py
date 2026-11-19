from __future__ import annotations

from scripts.smoke_test import run_smoke


def test_full_event_flow_smoke_with_fictitious_data(tmp_path):
    checks = run_smoke(tmp_path, block_network=True)
    assert any("MODO TESTE" in item for item in checks)
    assert any("Backup manual" in item for item in checks)
    assert any("Auditoria offline" in item for item in checks)
    assert len(checks) >= 10
