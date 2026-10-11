"""Compile and exercise the SDK-independent native packet queue when C++ compiler exists."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_passive_native_packet_queue(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++ compiler unavailable; native queue must also be built on Windows")
    root = Path(__file__).resolve().parents[1]
    include = root / "native" / "ashita_workbench_probe"
    source = tmp_path / "packet_queue_test.cpp"
    source.write_text(r"""
#include "passive_packet_queue.h"
#include <cassert>
#include <cstdint>
int main() {
    wb::PassivePacketQueue queue(2, 4);
    const uint8_t raw[4] = {1, 2, 3, 4};
    assert(!queue.Offer(wb::PacketDirection::Incoming, 0x34, raw, 4));
    queue.Start();
    assert(queue.Offer(wb::PacketDirection::Incoming, 0x34, raw, 4));
    assert(queue.Offer(wb::PacketDirection::Outgoing, 0x5d, raw, 4));
    assert(!queue.Offer(wb::PacketDirection::Incoming, 0x34, raw, 4));
    auto health = queue.Health();
    assert(health.accepted == 2 && health.rejected == 1 && health.queued == 2);
    auto records = queue.Drain();
    assert(records.size() == 2 && records[0].sequence == 1 && records[1].sequence == 2);
    assert(records[0].raw.size() == 4 && records[0].raw[3] == 4);
    assert(records[1].direction == wb::PacketDirection::Outgoing);
    assert(!queue.Offer(wb::PacketDirection::Incoming, 0x34, raw, 5));
    queue.Stop();
    assert(!queue.Offer(wb::PacketDirection::Incoming, 0x34, raw, 4));
    assert(queue.Health().oversize_drops == 1);
}
""")
    binary = tmp_path / "packet_queue_test"
    subprocess.run([compiler, "-std=c++20", "-pthread", "-I", str(include), str(source), "-o", str(binary)], check=True, timeout=60)
    subprocess.run([str(binary)], check=True, timeout=15)
