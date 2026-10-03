from src.workbench.editors.character.packed_transactions import _campaign_edit


def _blob(current=7, completed=()):
    data = bytearray(514)
    data[0:2] = int(current).to_bytes(2, "little")
    for item in completed:
        data[2 + int(item)] = 1
    return bytes(data)


def run():
    for family in ("dsp", "topaz", "lsb"):
        original = _blob(current=7, completed=(1, 511))

        changed, before, after = _campaign_edit(original, family, {"current": 42})
        assert before["current"] == 7
        assert after["current"] == 42
        assert changed[0:2] == (42).to_bytes(2, "little")
        assert changed[2:] == original[2:]

        changed, before, after = _campaign_edit(original, family, {"completed_id": 255, "completed": True})
        assert before["completed"] is False
        assert after["completed"] is True
        assert changed[2 + 255] == 1
        assert changed[: 2 + 255] == original[: 2 + 255]
        assert changed[3 + 255 :] == original[3 + 255 :]

        changed, before, after = _campaign_edit(original, family, {"completed_id": 511, "completed": False})
        assert before["completed"] is True
        assert after["completed"] is False
        assert changed[2 + 511] == 0
        assert changed[: 2 + 511] == original[: 2 + 511]

        try:
            _campaign_edit(original, family, {"completed_id": 512, "completed": True})
        except ValueError as exc:
            assert "0 and 511" in str(exc)
        else:
            raise AssertionError("completion ID 512 must be rejected")

        try:
            _campaign_edit(original, family, {"current": 65536})
        except ValueError as exc:
            assert "0 and 65535" in str(exc)
        else:
            raise AssertionError("current Campaign ID 65536 must be rejected")


if __name__ == "__main__":
    run()
