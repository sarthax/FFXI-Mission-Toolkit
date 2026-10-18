#!/usr/bin/env python3
"""Optional decoder smoke test against synthetic packed .text."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.binary.code_evidence import decode_window
from test_client_pol1_unpack import make_pe


def main():
    # Two NOPs and RET, encoded as literal POL1 bytes.
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "client.dll"
        path.write_bytes(make_pe(b"\xe0\x90\x90\xc3", 3))
        result = decode_window(path, 0x1000, window=3, max_instructions=3)
        if result["status"] == "DECODER_UNAVAILABLE":
            print("optional x86 decoder unavailable: SKIP")
            return
        assert [r["mnemonic"] for r in result["instructions"]] == ["nop", "nop", "ret"]
        assert [r["rva"] for r in result["instructions"]] == [0x1000, 0x1001, 0x1002]
        for rva, window in ((0x0fff, 3), (0x1000, 513)):
            try:
                decode_window(path, rva, window=window)
            except ValueError:
                pass
            else:
                raise AssertionError("accepted invalid RVA/window")
    print("optional x86 decode self-test: PASS")


if __name__ == "__main__":
    main()
