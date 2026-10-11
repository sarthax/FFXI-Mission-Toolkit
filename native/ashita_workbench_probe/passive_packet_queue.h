// SDK-independent passive packet observation queue. No disk I/O or packet mutation in Offer().
#pragma once
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace wb {
enum class PacketDirection { Incoming, Outgoing };
struct PacketObservation {
    PacketDirection direction{};
    uint16_t opcode{};
    uint64_t sequence{};
    uint64_t observed_ns{};
    std::vector<uint8_t> raw;
};
struct PacketQueueHealth {
    uint64_t accepted = 0;
    uint64_t consumed = 0;
    uint64_t rejected = 0;
    uint64_t contention_drops = 0;
    uint64_t oversize_drops = 0;
    size_t queued = 0;
    bool enabled = false;
};
class PassivePacketQueue {
    mutable std::mutex mutex_;
    std::deque<PacketObservation> queue_;
    const size_t capacity_;
    const size_t max_packet_bytes_;
    std::atomic<uint64_t> contention_drops_{0};
    bool enabled_ = false;
    uint64_t next_sequence_ = 1;
    PacketQueueHealth counters_;
public:
    explicit PassivePacketQueue(size_t capacity = 512, size_t max_packet_bytes = 8192)
        : capacity_(std::max<size_t>(1, capacity)), max_packet_bytes_(std::max<size_t>(1, max_packet_bytes)) {}
    // Caller must stop capture before changing sessions. Stop intentionally clears queued
    // data only when discard=true; normally the consumer drains after Stop().
    void Start() { std::lock_guard<std::mutex> lock(mutex_); enabled_ = true; }
    void Stop() { std::lock_guard<std::mutex> lock(mutex_); enabled_ = false; }
    bool Offer(PacketDirection direction, uint16_t opcode, const void* data, size_t length) {
        // Never wait for disk or a contended consumer on the Ashita callback thread.
        std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
        if (!lock.owns_lock()) { contention_drops_.fetch_add(1, std::memory_order_relaxed); return false; }
        if (!enabled_) return false;
        if (!data || length == 0 || length > max_packet_bytes_) {
            ++counters_.rejected;
            ++counters_.oversize_drops;
            return false;
        }
        if (queue_.size() >= capacity_) { ++counters_.rejected; return false; }
        PacketObservation entry;
        entry.direction = direction;
        entry.opcode = opcode;
        entry.sequence = next_sequence_++;
        entry.observed_ns = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
        entry.raw.resize(length);
        std::memcpy(entry.raw.data(), data, length); // callback buffer lifetime ends on return
        queue_.push_back(std::move(entry));
        ++counters_.accepted;
        return true;
    }
    std::vector<PacketObservation> Drain(size_t limit = 256) {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<PacketObservation> result;
        const size_t n = std::min(limit, queue_.size());
        result.reserve(n);
        for (size_t i = 0; i < n; ++i) {
            result.push_back(std::move(queue_.front()));
            queue_.pop_front();
        }
        counters_.consumed += n;
        return result;
    }
    PacketQueueHealth Health() const {
        std::lock_guard<std::mutex> lock(mutex_);
        auto value = counters_;
        value.contention_drops = contention_drops_.load(std::memory_order_relaxed);
        value.rejected += value.contention_drops;
        value.queued = queue_.size();
        value.enabled = enabled_;
        return value;
    }
};
} // namespace wb
