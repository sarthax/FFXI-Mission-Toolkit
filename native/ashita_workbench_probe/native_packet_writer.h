// SDK-independent native recording consumer. Invoke Pump only off packet callbacks.
#pragma once
#include "native_packet_jsonl.h"
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
namespace wb {
class PassivePacketWriter {
    PassivePacketQueue& queue_;
    std::filesystem::path path_;
    std::ofstream stream_;
    std::string client_, session_;
    uint64_t written_ = 0;
    bool faulted_ = false;
public:
    PassivePacketWriter(PassivePacketQueue& queue, std::filesystem::path path,
                        std::string client, std::string session)
        : queue_(queue), path_(std::move(path)),
          client_(std::move(client)), session_(std::move(session)) {
        if (!ValidCaptureId(client_) || !ValidCaptureId(session_))
            throw std::invalid_argument("invalid native recording identity");
        // Refuse existing evidence. Do not create an empty file until explicitly started.
    }
    void Start() {
        if (stream_.is_open() || faulted_) throw std::logic_error("recording already started or faulted");
        if (std::filesystem::exists(path_)) throw std::runtime_error("recording destination exists");
        if (!path_.parent_path().empty()) std::filesystem::create_directories(path_.parent_path());
        stream_.open(path_, std::ios::out | std::ios::binary | std::ios::trunc);
        if (!stream_) { faulted_ = true; throw std::runtime_error("recording open failed"); }
        queue_.Start();
    }
    size_t Pump(size_t limit = 256) {
        if (!stream_.is_open() || faulted_) throw std::logic_error("recording unavailable");
        // This first writer version fails closed on any loss rather than silently
        // publishing a falsely complete session with missing packets.
        if (queue_.Health().rejected != 0) {
            faulted_ = true;
            queue_.Stop();
            throw std::runtime_error("packet queue loss detected; session incomplete");
        }
        auto packets = queue_.Drain(limit);
        try {
            for (const auto& packet : packets) {
                stream_ << SerializePacket(packet, client_, session_);
                stream_.flush();
                if (!stream_) throw std::runtime_error("native recording write failed");
                ++written_;
            }
        } catch (...) {
            faulted_ = true;
            queue_.Stop();
            throw;
        }
        return packets.size();
    }
    void Stop() {
        queue_.Stop();
        if (queue_.Health().rejected != 0) faulted_ = true;
        if (stream_.is_open() && !faulted_) {
            while (queue_.Health().queued) Pump();
        }
        if (stream_.is_open()) {
            stream_.flush();
            if (!stream_) faulted_ = true;
            stream_.close();
        }
        if (faulted_) throw std::runtime_error("native recording incomplete; retain evidence");
    }
    uint64_t Written() const { return written_; }
    bool Faulted() const { return faulted_; }
};
} // namespace wb
