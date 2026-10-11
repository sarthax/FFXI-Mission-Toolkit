// Toolkit <-> native plugin control channel: SDK-independent parsing, gating and routing.
//
// Transport is small key=value text files under <Ashita>/config/workbench_native/:
//   settings.ini  admin-owned opt-in (nothing is accepted unless allow_file_commands=1)
//   command.txt   written atomically by the Toolkit (one command, monotonically increasing seq)
//   status.txt    written by the plugin (~2 Hz): nonce, armed state, position, last result
// Every command still goes through MovementAdapter/SpeedOverride, so all limits, binding and
// fail-closed behaviour are identical to the in-game /wbprobe commands.
#pragma once
#include "movement_adapter.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <sstream>
#include <string>

namespace wb {

using KV = std::map<std::string, std::string>;

inline std::string Trim(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && (s[b] == ' ' || s[b] == '\t' || s[b] == '\r' || s[b] == '\n')) ++b;
    while (e > b && (s[e - 1] == ' ' || s[e - 1] == '\t' || s[e - 1] == '\r' || s[e - 1] == '\n')) --e;
    return s.substr(b, e - b);
}

// Lines of key=value; '#' / ';' comment lines; later keys win; sizes bounded.
inline KV ParseKV(const std::string& text) {
    KV out;
    if (text.size() > 8192) return out;
    std::istringstream in(text);
    std::string line;
    int n = 0;
    while (std::getline(in, line) && ++n <= 64) {
        line = Trim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        const size_t eq = line.find('=');
        if (eq == std::string::npos || eq == 0) continue;
        const std::string k = Trim(line.substr(0, eq));
        std::string v = Trim(line.substr(eq + 1));
        const size_t cm = v.find(" ;");  // trailing comment
        if (cm != std::string::npos) v = Trim(v.substr(0, cm));
        if (k.size() <= 32 && v.size() <= 128) out[k] = v;
    }
    return out;
}

inline bool ParseDouble(const KV& kv, const char* key, double& out) {
    const auto it = kv.find(key);
    if (it == kv.end() || it->second.empty()) return false;
    char* end = nullptr;
    const double v = std::strtod(it->second.c_str(), &end);
    if (*end != '\0' || !std::isfinite(v)) return false;
    out = v;
    return true;
}
inline std::string Get(const KV& kv, const char* key) {
    const auto it = kv.find(key);
    return it == kv.end() ? std::string() : it->second;
}

// Server axis order is what !logpos prints: (x, y = height, z = horizontal).
// SDK axis order (zone 98 live evidence) is (x, horizontal, height).  Convert in ONE place.
inline Vec3 ServerToSdk(float x, float y, float z) { return {x, z, y}; }
inline Vec3 SdkToServer(const Vec3& s) { return {s.x, s.z, s.y}; }

struct Settings {
    bool allow_file_commands = false;   // master switch for the Toolkit channel
    std::string auto_arm;               // "", "warp", "autorun", "local": arm automatically at load/zone
    double enable_ttl_seconds = 120.0;  // 0 = never expires
    double speed_percent = 0.0;         // >0: hold this speed override once armed
    double base_speed = SpeedOverride::kBase;
};

inline Settings ParseSettings(const std::string& text) {
    const KV kv = ParseKV(text);
    Settings s;
    double v = 0;
    const std::string allow = Get(kv, "allow_file_commands");
    s.allow_file_commands = allow == "1" || allow == "true";
    const std::string arm = Get(kv, "auto_arm");
    if (arm == "warp" || arm == "autorun" || arm == "local") s.auto_arm = arm;
    if (ParseDouble(kv, "enable_ttl_seconds", v) && v >= 0 && v <= 86400) s.enable_ttl_seconds = v;
    if (ParseDouble(kv, "speed_percent", v) && (v == 0 || (v >= 25 && v <= 400))) s.speed_percent = v;
    if (ParseDouble(kv, "base_speed", v) && v > 0.5 && v < 50) s.base_speed = v;
    return s;
}

inline bool ModeFromName(const std::string& n, Mode& m) {
    if (n == "warp") { m = Mode::Warp; return true; }
    if (n == "autorun") { m = Mode::Autorun; return true; }
    if (n == "local") { m = Mode::LocalWrite; return true; }
    return false;
}

struct CommandOutcome {
    bool ok = false;
    std::string reason;
    std::string id;
    uint64_t seq = 0;
};

// Executes Toolkit commands. `now_ms` is wall-clock epoch milliseconds.
class ControlRouter {
public:
    ControlRouter(MovementAdapter& adapter, SpeedOverride& speed, MovementPort& port, std::string nonce)
        : adapter_(adapter), speed_(speed), port_(port), nonce_(std::move(nonce)) {}

    void SetSettings(const Settings& s) { settings_ = s; }
    const Settings& settings() const { return settings_; }
    const std::string& nonce() const { return nonce_; }
    const CommandOutcome& last() const { return last_; }
    uint64_t last_seq() const { return last_seq_; }

    // Operator typed `movement disable`: stop auto-arming until the plugin is reloaded.
    void SuppressAutoArm() { auto_suppressed_ = true; }
    void SuppressSpeedConfig() { speed_suppressed_ = true; }

    // Process raw command.txt text. Returns true when a new command was consumed (outcome in last()).
    bool Process(const std::string& text, int64_t now_ms) {
        if (!settings_.allow_file_commands) return false;
        const KV kv = ParseKV(text);
        double seq_d = 0, ts = 0;
        if (!ParseDouble(kv, "seq", seq_d) || seq_d < 1 || seq_d > 9e15) return false;
        const uint64_t seq = static_cast<uint64_t>(seq_d);
        if (seq <= last_seq_) return false;   // already handled (or replayed)
        last_seq_ = seq;                      // consume even if rejected: no retries of stale commands
        CommandOutcome o;
        o.seq = seq;
        o.id = Get(kv, "id");
        const std::string cmd = Get(kv, "cmd");
        if (Get(kv, "nonce") != nonce_) { o.reason = "nonce_mismatch"; return Finish(o); }
        if (!ParseDouble(kv, "ts_ms", ts) || std::fabs(static_cast<double>(now_ms) - ts) > 15000.0) {
            o.reason = "stale_command"; return Finish(o);
        }
        if (cmd == "stop") {
            adapter_.Stop("toolkit_stop");
            o.ok = true; o.reason = "stopped";
        } else if (cmd == "disable") {
            adapter_.Disable("toolkit");
            speed_.Off();
            auto_suppressed_ = true;
            o.ok = true; o.reason = "disabled";
        } else if (cmd == "enable") {
            Mode m;
            if (Get(kv, "consent") != "DEV-SERVER-ONLY") o.reason = "consent_required";
            else if (!ModeFromName(Get(kv, "mode"), m)) o.reason = "invalid_mode";
            else {
                const auto r = adapter_.Enable(m);
                auto_suppressed_ = false;
                o.ok = r.ok; o.reason = r.reason;
            }
        } else if (cmd == "warp_to") {
            double x, y, z;
            if (!ParseDouble(kv, "x", x) || !ParseDouble(kv, "y", y) || !ParseDouble(kv, "z", z)) {
                o.reason = "invalid_target";
            } else {
                const Vec3 sdk = ServerToSdk(static_cast<float>(x), static_cast<float>(y), static_cast<float>(z));
                const auto r = adapter_.RequestAbsolute(o.id.empty() ? "toolkit" + std::to_string(seq) : o.id, sdk);
                o.ok = r.ok;
                o.reason = r.reason;
                if (r.ok) {  // warp is synchronous: report the written/failed outcome
                    o.ok = adapter_.last().completed;
                    o.reason = adapter_.last().reason;
                }
            }
        } else if (cmd == "speed") {
            double pct;
            if (!ParseDouble(kv, "value", pct) || !speed_.Set(static_cast<float>(pct))) o.reason = "invalid_speed";
            else if (!adapter_.enabled()) { speed_.Off(); o.reason = "not_armed"; }
            else { o.ok = true; o.reason = "speed_set"; }
        } else if (cmd == "speed_off") {
            speed_.Off();
            speed_suppressed_ = true;
            o.ok = true; o.reason = "speed_off";
        } else {
            o.reason = "unknown_command";
        }
        return Finish(o);
    }

    // Called every frame. Arms per settings (default: never) and re-binds after zoning.
    void Tick() {
        const double now = port_.NowSeconds();
        if (now >= next_arm_) {
            next_arm_ = now + 1.0;
            Mode m;
            if (!auto_suppressed_ && ModeFromName(settings_.auto_arm, m) && !adapter_.active()) {
                const auto s = port_.Snapshot();
                if (s.valid && !s.zoning &&
                    (!adapter_.enabled() || s.zone != adapter_.bound_zone() || s.server_id != adapter_.bound_server_id())) {
                    adapter_.Enable(m);
                }
            }
            if (settings_.speed_percent > 0 && !speed_.active() && adapter_.enabled() && !speed_suppressed_)
                speed_.Set(static_cast<float>(settings_.speed_percent));
        }
        speed_.Tick(adapter_.enabled());
    }

private:
    bool Finish(CommandOutcome& o) { last_ = o; return true; }

    MovementAdapter& adapter_;
    SpeedOverride& speed_;
    MovementPort& port_;
    std::string nonce_;
    Settings settings_;
    CommandOutcome last_;
    uint64_t last_seq_ = 0;
    bool auto_suppressed_ = false, speed_suppressed_ = false;
    double next_arm_ = -1e18;
};

struct StatusInfo {
    std::string nonce;
    int64_t now_ms = 0;
    bool allow_file_commands = false;
    bool enabled = false;
    std::string mode;
    PlayerSnapshot snap;
    bool speed_active = false;
    float speed_percent = 0;
    float speed_raw = -1;
    std::string auto_arm;
    CommandOutcome last;
    const Outcome* last_move = nullptr;
};

inline std::string RenderStatus(const StatusInfo& s) {
    char b[1024];
    const Vec3 sv = SdkToServer(s.snap.pos);
    std::snprintf(b, sizeof(b),
        "version=1\nupdated_ms=%lld\nnonce=%s\nallow_file_commands=%d\nauto_arm=%s\nenabled=%d\nmode=%s\n"
        "player_valid=%d\nzone=%u\nserver_id=%u\nzoning=%d\npos_x=%.3f\npos_y=%.3f\npos_z=%.3f\n"
        "speed_active=%d\nspeed_percent=%.1f\nspeed_raw=%.3f\n"
        "last_seq=%llu\nlast_id=%s\nlast_ok=%d\nlast_reason=%s\nlast_scope=client_local\nserver_confirmed=NO\n",
        static_cast<long long>(s.now_ms), s.nonce.c_str(), s.allow_file_commands ? 1 : 0, s.auto_arm.c_str(),
        s.enabled ? 1 : 0, s.mode.c_str(), s.snap.valid ? 1 : 0, s.snap.zone, s.snap.server_id, s.snap.zoning ? 1 : 0,
        sv.x, sv.y, sv.z, s.speed_active ? 1 : 0, s.speed_percent, s.speed_raw,
        static_cast<unsigned long long>(s.last.seq), s.last.id.c_str(), s.last.ok ? 1 : 0, s.last.reason.c_str());
    std::string out = b;
    if (s.last_move) {
        const Vec3 a = SdkToServer(s.last_move->before), c = SdkToServer(s.last_move->after);
        std::snprintf(b, sizeof(b), "move_id=%s\nmove_completed=%d\nmove_reason=%s\n"
            "move_before=%.3f,%.3f,%.3f\nmove_after=%.3f,%.3f,%.3f\n",
            s.last_move->id.c_str(), s.last_move->completed ? 1 : 0, s.last_move->reason.c_str(),
            a.x, a.y, a.z, c.x, c.y, c.z);
        out += b;
    }
    return out;
}

}  // namespace wb
