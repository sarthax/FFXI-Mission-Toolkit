#!/usr/bin/env python3
"""Synthetic POL1 reference candidate test; values are not semantic xrefs."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.binary.address_candidates import address_candidates
from test_client_pol1_unpack import make_pe

def main():
    # Six literal bytes: raw 32-bit RVA 0x1234 then two padding bytes
    encoded = b"\xfc\x34\x12\x00\x00\x90\x90"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "synthetic.dll"
        p.write_bytes(make_pe(encoded, 6))
        result = address_candidates(p, 0x1234)
        assert result["status"] == "CANDIDATES", result
        assert result["matches"][0]["kind"] == "rva32"
        assert result["matches"][0]["match_rva"] == 0x1000
        assert address_candidates(p, 0x9999)["status"] == "UNKNOWN"
        for target in (-1, 0x100000000):
            try:
                address_candidates(p, target)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid target accepted")
    print("unpacked address candidate self-test: PASS")

if __name__ == "__main__":
    main()
