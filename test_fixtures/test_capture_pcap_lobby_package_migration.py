#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.captures import pcap_ingest as canonical_pcap
from workbench.captures import lobby_ingest as canonical_lobby
from workbench.captures import integrity, raw_packet_ingest
from workbench.core.services import pcap_ingest as legacy_pcap
from workbench.core.services import lobby_ingest as legacy_lobby


def main() -> None:
    assert legacy_pcap is canonical_pcap
    assert legacy_lobby is canonical_lobby
    assert canonical_pcap.capture_integrity is integrity
    assert canonical_pcap.raw_packet_ingest is raw_packet_ingest
    assert canonical_pcap.lobby_ingest is canonical_lobby
    assert canonical_pcap.sniff_pcap_format(b"\xd4\xc3\xb2\xa1" + b"\x00" * 20) == "pcap"
    assert canonical_pcap.sniff_pcap_format(b"\x0a\x0d\x0d\x0a" + b"\x00" * 8) == "pcapng"
    assert canonical_lobby.validate_packet(b"").get("valid") is False

    code = "from workbench.captures import pcap_ingest, lobby_ingest; assert pcap_ingest.lobby_ingest is lobby_ingest"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)


if __name__ == "__main__":
    main()
