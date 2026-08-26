from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from erasemap.bank_control_plane import SyntheticBankControlPlane
from erasemap.cli import main
from erasemap.synthetic_bank_control_plane import (
    make_control_plane_server,
    render_control_plane_html,
    write_control_plane_demo,
)


def test_dashboard_has_live_connector_contract_and_scope(tmp_path: Path) -> None:
    plane = SyntheticBankControlPlane()
    rendered = render_control_plane_html(plane.manifest())

    assert "LOCAL API CONNECTED" in rendered
    assert "512 synthetic clients" in rendered
    assert "SYNTHETIC · NO REAL DATA" in rendered
    assert "production integration requires organization approval" in rendered
    assert "Exact plan / dry run" in rendered
    assert "Evidence event log" in rendered

    output = tmp_path / "control-plane"
    manifest = write_control_plane_demo(output)
    assert manifest["registered_artifact_count"] == 3072
    assert (output / "index.html").is_file()
    assert (output / "README.txt").is_file()


def test_server_exposes_customers_and_ordered_action_api() -> None:
    plane = SyntheticBankControlPlane()
    server = make_control_plane_server(plane, port=0)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    customer = plane.demo_customer_id
    try:
        with urlopen(f"{base}/api/overview") as response:
            overview = json.loads(response.read())
        assert overview["customer_count"] == 512

        with urlopen(f"{base}/api/customers?query=KZ-DEMO-042") as response:
            customers = json.loads(response.read())["customers"]
        assert customers[0]["customer_id"] == customer

        request = Request(
            f"{base}/api/customers/{customer}/actions/create-request", method="POST"
        )
        with urlopen(request) as response:
            payload = json.loads(response.read())
        assert payload["stage"] == "REQUESTED"
        assert payload["verdict"]["status"] == "INCOMPLETE"
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_control_plane_generate_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "control-plane"
    assert main(
        [
            "bank-control-plane",
            "generate",
            "--output",
            str(output),
            "--customers",
            "512",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["status"] == "READY"
    assert response["customer_count"] == 512
    assert (output / "index.html").is_file()
