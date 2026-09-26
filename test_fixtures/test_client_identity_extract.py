#!/usr/bin/env python3
"""Regression for installed-client identity snapshot extraction."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile

from workbench.client.identity_extract import (
    ZoneExportRequest,
    dat_id_for_zone,
    extract_client_identity_snapshot,
)
from workbench.client.identity_snapshot import read_manifest


def main() -> None:
    assert dat_id_for_zone(0) == 6420
    assert dat_id_for_zone(255) == 6675
    assert dat_id_for_zone(256) == 85590

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        client = root / "client"
        client.mkdir()
        (client / "FTABLE.DAT").write_bytes(b"ftable-old-client")
        (client / "VTABLE.DAT").write_bytes(b"vtable-old-client")
        tinkerer = root / "xi-tinkerer-cli.exe"
        tinkerer.write_bytes(b"placeholder")

        calls = []
        def fake_runner(argv, capture_output, text):
            calls.append(argv)
            output = Path(argv[-1])
            dat_id = int(argv[argv.index("--dat-id") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                "entries:\n"
                f"  10: 'Dialog for dat {dat_id}'\n"
                "  11: 'Second line'\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        result = extract_client_identity_snapshot(
            client_root=client,
            output_dir=root / "snapshot",
            snapshot_id="client:30191204_1",
            zones=[
                ZoneExportRequest(87, "NORTH_GUSTABERG_S"),
                ZoneExportRequest(83, "Rolanberry_Fields"),
            ],
            xi_tinkerer=tinkerer,
            build="30191204_1",
            runner=fake_runner,
        )

        assert len(calls) == 2, calls
        assert result.build == "30191204_1", result
        assert len(result.resources) == 4, result.resources
        assert not result.failures, result.failures
        assert len(result.client_fingerprint) == 64, result.client_fingerprint

        manifest = read_manifest(Path(result.manifest_path))
        assert manifest.snapshot_id == "client:30191204_1", manifest
        assert manifest.metadata["client_fingerprint"] == result.client_fingerprint
        assert len(manifest.files) == 4, manifest.files
        dialog_rows = [x for x in manifest.files if x["kind"] == "DIALOG"]
        assert {x["zone_id"] for x in dialog_rows} == {83, 87}, dialog_rows

    print("installed client identity extraction self-test: PASS")


if __name__ == "__main__":
    main()
