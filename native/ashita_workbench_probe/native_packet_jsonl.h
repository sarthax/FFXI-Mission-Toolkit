// SDK-independent canonical JSONL serialization for passive packet observations.
#pragma once
#include "passive_packet_queue.h"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>

namespace wb {
inline bool ValidCaptureId(std::string_view id) {
    if (id.empty() || id.size() > 128) return false;
    for (unsigned char ch : id) if (ch < 32 || ch == 127 || ch == '"' || ch == '\\') return false;
    return true;
}
inline std::string HexPacket(const std::vector<uint8_t>& bytes) {
    constexpr char digits[] = "0123456789ABCDEF";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (uint8_t byte : bytes) { out += digits[byte >> 4]; out += digits[byte & 15]; }
    return out;
}
inline std::string SerializePacket(const PacketObservation& packet,
                                   std::string_view client, std::string_view session,
                                   bool injected = false, bool blocked = false,
                                   uint64_t dropped_before = 0) {
    if (!ValidCaptureId(client) || !ValidCaptureId(session) ||
        packet.sequence == 0 || packet.observed_ns == 0 ||
        packet.raw.empty() || packet.raw.size() > 4096)
        throw std::invalid_argument("invalid native packet envelope");
    // Only the verified original callback should supply injection/block flags.
    return "{\\\"schema_version\\\":1,\\\"client_id\\\":\\\"" + std::string(client) +
           "\\",\\\"session_id\\\":\\\"" + std::string(session) +
           "\\",\\\"sequence\\\":" + std::to_string(packet.sequence) +
           ",\\\"observed_at_ns\\\":" + std::to_string(packet.observed_ns) +
           ",\\\"direction\\\":\\\"" + (packet.direction == PacketDirection::Incoming ? "incoming" : "outgoing") +
           "\\",\\\"opcode\\\":" + std::to_string(packet.opcode) +
           ",\\\"raw_hex\\\":\\\"" + HexPacket(packet.raw) +
           "\\",\\\"is_injected\\\":" + (injected ? "true" : "false") +
           ",\\\"is_blocked\\\":" + (blocked ? "true" : "false") +
           ",\\\"dropped_before\\\":" + std::to_string(dropped_before) + "}\\n";
}
} // namespace wb
