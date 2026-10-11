// Mission Toolkit native movement adapter: SDK-independent policy + state machine.
//
// All game access goes through MovementPort so every safeguard can be unit
// tested on the host with a fake port (see movement_adapter_test.cpp).  The
// adapter is DISABLED by default, fails closed whenever state cannot be
// verified, and never reports server acceptance: the strongest claim it can
// make is "client-local".  Server confirmation is the Toolkit's job (compare
// against server-observed coordinates).
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <string>

namespace wb {

struct Vec3 { float x = 0, y = 0, z = 0; };

inline bool finite3(const Vec3& v) { return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z); }
// Ground-plane distance. Live test 2026-10-11 (zone 98): SDK X/Y are the horizontal plane
// (SDK Y == server z) and SDK Z is height (== server y), so autorun legs are judged on X/Y only.
inline float dist2(const Vec3& a, const Vec3& b) {
    const float dx = a.x - b.x, dy = a.y - b.y;
    return std::sqrt(dx * dx + dy * dy);
}
inline float dist3(const Vec3& a, const Vec3& b) {
    const float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

struct PlayerSnapshot {
    bool valid = false;        // player active + entity index resolved
    uint32_t server_id = 0;
    uint32_t entity_index = 0;
    uint32_t zone = 0;
    bool zoning = false;
    Vec3 pos;
};

// Native SDK access boundary.
class MovementPort {
public:
    virtual ~MovementPort() = default;
    virtual PlayerSnapshot Snapshot() = 0;                    // fresh read each call
    virtual void BeginAutorun(const Vec3& direction) = 0;     // autofollow delta + IsAutoRunning=1
    virtual void EndAutorun() = 0;                            // IsAutoRunning=0, deltas zeroed
    virtual void WriteLocalPosition(uint32_t entity_index, const Vec3& pos) = 0;  // experimental
    virtual double NowSeconds() = 0;                          // monotonic
};

enum class Mode { Autorun, LocalWrite };

struct Limits {
    float max_step = 3.0f;          // yalms, total displacement per command
    float arrive_radius = 0.35f;
    double min_interval = 1.0;      // seconds between accepted commands
    double enable_ttl = 120.0;      // auto-disable after this long
    double autorun_timeout = 4.0;   // hard stop for an autorun leg
};

struct Result {
    bool ok = false;
    std::string reason;
};

struct Outcome {
    std::string id;
    Mode mode = Mode::Autorun;
    Vec3 before, target, after;
    bool completed = false;
    std::string reason;
    // Always false here: native code cannot observe server acceptance.
    bool server_confirmed = false;
};

class MovementAdapter {
public:
    explicit MovementAdapter(MovementPort& port, Limits limits = {}) : port_(port), lim_(limits) {}

    bool enabled() const { return enabled_; }
    bool active() const { return active_; }
    const Outcome& last() const { return last_; }
    const std::deque<std::string>& audit() const { return audit_; }

    // Explicit development-mode enablement; binds the session to one character+zone.
    Result Enable(Mode mode) {
        const auto s = port_.Snapshot();
        if (!s.valid || s.zoning || s.zone == 0 || s.server_id == 0) return Deny("enable", "state_unverified");
        enabled_ = true;
        mode_ = mode;
        bound_server_id_ = s.server_id;
        bound_zone_ = s.zone;
        enabled_at_ = port_.NowSeconds();
        last_accept_ = -1e18;
        seen_ids_.clear();
        Log("enable mode=%s server_id=%u zone=%u", ModeName(mode), s.server_id, s.zone);
        return {true, "enabled"};
    }

    void Disable(const char* why = "operator") {
        if (active_) Finish(false, "disabled");
        if (enabled_) Log("disable reason=%s", why);
        enabled_ = false;
    }

    // Immediate, unconditional stop. Never depends on telemetry validity.
    void Stop(const char* why = "operator_stop") {
        port_.EndAutorun();
        if (active_) Finish(false, why);
        else Log("stop (idle) reason=%s", why);
    }

    Result Request(const std::string& id, const Vec3& delta) {
        if (!enabled_) return Deny(id, "disabled");
        if (id.empty() || id.size() > 64) return Deny(id, "invalid_id");
        if (seen_ids_.count(id)) return Deny(id, "duplicate_id");
        if (!finite3(delta)) return Deny(id, "nonfinite_delta");
        const float mag = std::sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z);
        if (mag < 0.05f) return Deny(id, "delta_too_small");
        if (mag > lim_.max_step) return Deny(id, "exceeds_max_step");
        if (mode_ == Mode::Autorun && std::fabs(delta.z) > 0.05f) return Deny(id, "vertical_unsupported_in_autorun");
        const double now = port_.NowSeconds();
        if (now - enabled_at_ > lim_.enable_ttl) { enabled_ = false; return Deny(id, "enable_expired"); }
        if (active_) return Deny(id, "busy");
        if (now - last_accept_ < lim_.min_interval) return Deny(id, "rate_limited");
        const auto s = port_.Snapshot();
        if (!s.valid) return Deny(id, "state_unverified");
        if (s.zoning) return Deny(id, "zoning");
        if (s.server_id != bound_server_id_) return Deny(id, "wrong_character");
        if (s.zone != bound_zone_) return Deny(id, "wrong_zone");
        if (!finite3(s.pos)) return Deny(id, "nonfinite_position");

        seen_ids_.insert(id);
        last_accept_ = now;
        cur_ = Outcome{};
        cur_.id = id;
        cur_.mode = mode_;
        cur_.before = s.pos;
        cur_.target = {s.pos.x + delta.x, s.pos.y + delta.y, s.pos.z + delta.z};
        entity_index_ = s.entity_index;
        started_ = now;
        active_ = true;
        Log("accept id=%s mode=%s delta=(%.2f,%.2f,%.2f) from=(%.3f,%.3f,%.3f)", id.c_str(), ModeName(mode_),
            delta.x, delta.y, delta.z, s.pos.x, s.pos.y, s.pos.z);
        if (mode_ == Mode::LocalWrite) {
            port_.WriteLocalPosition(entity_index_, cur_.target);
            Finish(true, "local_write_applied");
        } else {
            port_.BeginAutorun(delta);
        }
        return {true, "accepted"};
    }

    // Call every frame.
    void Tick() {
        if (enabled_ && port_.NowSeconds() - enabled_at_ > lim_.enable_ttl) Disable("ttl");
        if (!active_ || mode_ != Mode::Autorun) return;
        const auto s = port_.Snapshot();
        if (!s.valid || s.zoning || s.server_id != bound_server_id_ || s.zone != bound_zone_ || !finite3(s.pos)) {
            port_.EndAutorun();
            Finish(false, "state_lost");
            return;
        }
        const float d = dist2(s.pos, cur_.target);
        const float travelled = dist2(s.pos, cur_.before);
        const float planned = dist2(cur_.target, cur_.before);
        if (d <= lim_.arrive_radius) { port_.EndAutorun(); cur_.after = s.pos; Finish(true, "arrived"); return; }
        if (travelled > planned + lim_.arrive_radius) { port_.EndAutorun(); cur_.after = s.pos; Finish(false, "overshoot"); return; }
        if (port_.NowSeconds() - started_ > lim_.autorun_timeout) { port_.EndAutorun(); cur_.after = s.pos; Finish(false, "timeout"); }
    }

private:
    static const char* ModeName(Mode m) { return m == Mode::Autorun ? "autorun" : "local_write"; }

    Result Deny(const std::string& id, const char* reason) {
        Log("deny id=%s reason=%s", id.c_str(), reason);
        return {false, reason};
    }

    void Finish(bool completed, const char* reason) {
        const auto s = port_.Snapshot();
        if (s.valid && finite3(s.pos)) cur_.after = s.pos;
        cur_.completed = completed;
        cur_.reason = reason;
        cur_.server_confirmed = false;
        last_ = cur_;
        active_ = false;
        Log("finish id=%s completed=%d reason=%s before=(%.3f,%.3f,%.3f) after=(%.3f,%.3f,%.3f) scope=client_local server=unverified",
            cur_.id.c_str(), completed ? 1 : 0, reason, cur_.before.x, cur_.before.y, cur_.before.z,
            cur_.after.x, cur_.after.y, cur_.after.z);
    }

    template <typename... A> void Log(const char* fmt, A... a) {
        char buf[320];
        std::snprintf(buf, sizeof(buf), fmt, a...);
        audit_.push_back(buf);
        if (audit_.size() > 200) audit_.pop_front();
    }

    // minimal set to avoid <set> overhead concerns; ids are short
    struct IdSet {
        std::deque<std::string> v;
        void clear() { v.clear(); }
        bool count(const std::string& s) const { for (auto& x : v) if (x == s) return true; return false; }
        void insert(const std::string& s) { v.push_back(s); if (v.size() > 256) v.pop_front(); }
    };

    MovementPort& port_;
    Limits lim_;
    bool enabled_ = false, active_ = false;
    Mode mode_ = Mode::Autorun;
    uint32_t bound_server_id_ = 0, bound_zone_ = 0, entity_index_ = 0;
    double enabled_at_ = 0, last_accept_ = -1e18, started_ = 0;
    Outcome cur_, last_;
    IdSet seen_ids_;
    std::deque<std::string> audit_;
};

}  // namespace wb
