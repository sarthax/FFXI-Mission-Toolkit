// Original Mission Toolkit native Ashita v4 load probe.
// Deliberately no game memory access, packet mutations, or network transport.
#include "Ashita.h"
#include <cstring>
#include <cmath>
#include <cstdio>
#include <type_traits>
#include <chrono>
#include <cstdlib>
#include <string>
#include <filesystem>
#include <fstream>
#include <sstream>
#include "movement_adapter.h"
#include "native_control.h"
#include "native_packet_writer.h"
#include <memory>

// Compile-time SDK signature gate only: these methods are never invoked.
using XYZSetter = void (IEntity::*)(uint32_t, float) const;
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionX), XYZSetter>);
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionY), XYZSetter>);
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionZ), XYZSetter>);

// SDK-backed MovementPort. Reads are always fresh; writes only happen when the
// MovementAdapter has already approved a command.
class SdkMovementPort final : public wb::MovementPort {
    IAshitaCore* core_;
public:
    explicit SdkMovementPort(IAshitaCore* core) : core_(core) {}
    wb::PlayerSnapshot Snapshot() override {
        wb::PlayerSnapshot s;
        auto* memory = core_ ? core_->GetMemoryManager() : nullptr;
        auto* party = memory ? memory->GetParty() : nullptr;
        auto* entities = memory ? memory->GetEntity() : nullptr;
        auto* player = memory ? memory->GetPlayer() : nullptr;
        if (!party || !entities || !player || party->GetMemberIsActive(0) == 0 ||
            party->GetMemberServerId(0) == 0 || party->GetMemberZone(0) == 0) return s;
        s.server_id = party->GetMemberServerId(0);
        s.zone = party->GetMemberZone(0);
        s.zoning = player->GetIsZoning() != 0;
        const uint32_t capacity = entities->GetEntityMapSize();
        for (uint32_t i = 1; i < capacity; ++i) {
            if (entities->GetServerId(i) == s.server_id) { s.entity_index = i; break; }
        }
        if (s.entity_index == 0) return s;
        s.pos = {entities->GetLocalPositionX(s.entity_index), entities->GetLocalPositionY(s.entity_index),
                 entities->GetLocalPositionZ(s.entity_index)};
        s.valid = true;
        return s;
    }
    // Experimental: drives the client's own auto-run so the client generates ordinary
    // movement packets that the server validates normally.
    void BeginAutorun(const wb::Vec3& d) override {
        auto* af = core_->GetMemoryManager()->GetAutoFollow();
        if (!af) return;
        af->SetFollowDeltaX(d.x);
        af->SetFollowDeltaY(d.y);
        af->SetFollowDeltaZ(d.z);
        af->SetIsAutoRunning(1);
    }
    void EndAutorun() override {
        auto* mm = core_ ? core_->GetMemoryManager() : nullptr;
        auto* af = mm ? mm->GetAutoFollow() : nullptr;
        if (!af) return;
        af->SetIsAutoRunning(0);
        af->SetFollowDeltaX(0.0f);
        af->SetFollowDeltaY(0.0f);
        af->SetFollowDeltaZ(0.0f);
    }
    // Experimental, client-local only; the server is not told.
    void WriteLocalPosition(uint32_t index, const wb::Vec3& p) override {
        auto* e = core_->GetMemoryManager()->GetEntity();
        e->SetLocalPositionX(index, p.x);
        e->SetLocalPositionY(index, p.y);
        e->SetLocalPositionZ(index, p.z);
    }
    // Experimental (mirrors what Project Tako was observed to do, static analysis only).
    // The entity's WarpPointer points at its model/"editable movement" object; position structs
    // live at +52 and +1476 as {x, height, horiz, 1, roll, yaw, pitch} floats (memory order).
    // SDK axes: X = x, Y = horizontal (server z), Z = height (server y).
    static bool ReadFloats(uintptr_t addr, float* out, int n) {
        __try { for (int i = 0; i < n; ++i) out[i] = reinterpret_cast<const float*>(addr)[i]; return true; }
        __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
    }
    static bool WriteFloats(uintptr_t addr, const float* in, int n) {
        __try { for (int i = 0; i < n; ++i) reinterpret_cast<float*>(addr)[i] = in[i]; return true; }
        __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
    }
    static constexpr uintptr_t kWarpOffsets[2] = {52, 1476};
    // Read-only diagnostic: returns pointer (0 if unavailable) and fills both structs.
    uintptr_t ReadWarp(uint32_t index, float out[2][3], bool ok[2]) {
        auto* e = core_->GetMemoryManager()->GetEntity();
        const uintptr_t wp = e->GetWarpPointer(index);
        ok[0] = ok[1] = false;
        if (wp < 0x10000) return 0;
        for (int i = 0; i < 2; ++i) ok[i] = ReadFloats(wp + kWarpOffsets[i], out[i], 3);
        return wp;
    }
    const char* WriteWarpPosition(uint32_t index, const wb::Vec3& p) override {
        float cur[2][3]; bool ok[2];
        const uintptr_t wp = ReadWarp(index, cur, ok);
        if (!wp) return "warp_pointer_null";
        if (!ok[0] || !ok[1]) return "warp_unreadable";
        auto* e = core_->GetMemoryManager()->GetEntity();
        const float local[3] = {e->GetLocalPositionX(index), e->GetLocalPositionZ(index), e->GetLocalPositionY(index)};
        for (int i = 0; i < 2; ++i) {
            for (int k = 0; k < 3; ++k)
                if (!std::isfinite(cur[i][k]) || std::fabs(cur[i][k] - local[k]) > 2.0f) return "warp_struct_mismatch";
        }
        const float np[3] = {p.x, p.z, p.y};  // memory order: x, height, horiz
        for (int i = 0; i < 2; ++i)
            if (!WriteFloats(wp + kWarpOffsets[i], np, 3)) return "warp_write_failed";
        return nullptr;
    }
    bool ReadSpeed(uint32_t index, float& v) override {
        auto* mm = core_ ? core_->GetMemoryManager() : nullptr;
        auto* e = mm ? mm->GetEntity() : nullptr;
        if (!e) return false;
        v = e->GetMovementSpeed2(index);
        return true;
    }
    void WriteSpeed(uint32_t index, float v) override {
        auto* mm = core_ ? core_->GetMemoryManager() : nullptr;
        auto* e = mm ? mm->GetEntity() : nullptr;
        if (e) e->SetMovementSpeed2(index, v);
    }
    float ReadSpeed1(uint32_t index) {
        auto* mm = core_ ? core_->GetMemoryManager() : nullptr;
        auto* e = mm ? mm->GetEntity() : nullptr;
        return e ? e->GetMovementSpeed(index) : -1.0f;
    }
    double NowSeconds() override {
        using namespace std::chrono;
        return duration<double>(steady_clock::now().time_since_epoch()).count();
    }
};

class WorkbenchNativeProbe final : public IPlugin {
    IAshitaCore* core_ = nullptr;
    SdkMovementPort* port_ = nullptr;
    wb::MovementAdapter* adapter_ = nullptr;
    wb::SpeedOverride* speed_ = nullptr;
    wb::ControlRouter* router_ = nullptr;
    std::filesystem::path dir_;
    wb::PassivePacketQueue packet_queue_{512, 4096};
    std::unique_ptr<wb::PassivePacketWriter> packet_writer_;
    void StopPacketRecording() {
        if (!packet_writer_) return;
        try { packet_writer_->Stop(); Say("[WorkbenchNativeProbe] Packet recording stopped."); }
        catch (const std::exception&) { Say("[WorkbenchNativeProbe] Packet recording incomplete; retain evidence."); }
        packet_writer_.reset();
    }
    void HandlePacketRecorderCommand(const char* cmd) {
        if (std::strcmp(cmd, "capture status") == 0) {
            auto h = packet_queue_.Health();
            const std::string msg = "[WorkbenchNativeProbe] capture enabled=" + std::to_string(h.enabled) +
                " queued=" + std::to_string(h.queued) + " accepted=" + std::to_string(h.accepted) +
                " lost=" + std::to_string(h.rejected) + " written=" +
                std::to_string(packet_writer_ ? packet_writer_->Written() : 0);
            Say(msg.c_str());
        } else if (std::strcmp(cmd, "capture stop") == 0) {
            StopPacketRecording();
        } else if (std::strcmp(cmd, "capture start") == 0) {
            Say("[WorkbenchNativeProbe] Native capture unavailable until Ashita SDK packet callbacks are verified and wired.");
        }
    }
    double next_cmd_ = 0, next_status_ = 0, next_settings_ = 0;
    static int64_t EpochMs() {
        using namespace std::chrono;
        return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
    }
    static bool ReadSmall(const std::filesystem::path& f, std::string& out) {
        std::error_code ec;
        if (!std::filesystem::is_regular_file(f, ec) || std::filesystem::file_size(f, ec) > 8192) return false;
        std::ifstream in(f, std::ios::binary);
        if (!in) return false;
        std::ostringstream ss;
        ss << in.rdbuf();
        out = ss.str();
        return true;
    }
    wb::Settings LoadSettings() {
        std::string txt;
        return ReadSmall(dir_ / "settings.ini", txt) ? wb::ParseSettings(txt) : wb::Settings{};
    }
    void WriteStatus() {
        wb::StatusInfo si;
        si.nonce = router_->nonce();
        si.now_ms = EpochMs();
        si.allow_file_commands = router_->settings().allow_file_commands;
        si.allow_chat_commands = router_->settings().allow_chat_commands;
        si.auto_arm = router_->settings().auto_arm;
        si.enabled = adapter_->enabled();
        si.mode = adapter_->enabled() ? (adapter_->mode() == wb::Mode::Warp ? "warp" : adapter_->mode() == wb::Mode::Autorun ? "autorun" : "local") : "";
        si.snap = port_->Snapshot();
        si.speed_active = speed_->active();
        si.speed_percent = speed_->percent();
        si.speed_raw = si.snap.valid ? port_->ReadSpeed1(si.snap.entity_index) : -1.0f;
        si.last = router_->last();
        si.last_move = adapter_->last().id.empty() ? nullptr : &adapter_->last();
        const auto tmp = dir_ / "status.tmp";
        {
            std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
            if (!out) return;
            out << wb::RenderStatus(si);
        }
        std::error_code ec;
        std::filesystem::rename(tmp, dir_ / "status.txt", ec);
    }
    void PollFiles() {
        const double now = port_->NowSeconds();
        if (now >= next_settings_) {
            next_settings_ = now + 2.0;
            wb::Settings st = LoadSettings();
            const auto& cur = router_->settings();
            st.enable_ttl_seconds = cur.enable_ttl_seconds;  // load-time only
            st.base_speed = cur.base_speed;
            router_->SetSettings(st);
        router_->SetChatSink([this](const std::string& line) { core_->GetChatManager()->QueueCommand(1, line.c_str()); });
        }
        if (now >= next_cmd_) {
            next_cmd_ = now + 0.2;
            std::string txt;
            if (router_->settings().allow_file_commands && ReadSmall(dir_ / "command.txt", txt) &&
                router_->Process(txt, EpochMs())) {
                const auto& o = router_->last();
                Say(("[WorkbenchNativeProbe] toolkit cmd seq=" + std::to_string(o.seq) + (o.ok ? " ok: " : " REJECTED: ") + o.reason).c_str());
                next_status_ = 0;
            }
        }
        if (now >= next_status_) {
            next_status_ = now + 0.5;
            WriteStatus();
        }
    }
    void Say(const char* text) { if (core_) core_->GetChatManager()->Write(1, false, text); }
    void SayAudit(size_t n) {
        const auto& a = adapter_->audit();
        const size_t start = a.size() > n ? a.size() - n : 0;
        for (size_t i = start; i < a.size(); ++i) Say(("[WorkbenchNativeProbe] audit: " + a[i]).c_str());
    }
    void SayLast() {
        const auto& o = adapter_->last();
        if (o.id.empty()) { Say("[WorkbenchNativeProbe] movement: no command yet."); return; }
        char b[320];
        std::snprintf(b, sizeof(b),
            "[WorkbenchNativeProbe] movement id=%s completed=%d reason=%s before=(%.3f,%.3f,%.3f) after=(%.3f,%.3f,%.3f) scope=client_local server_confirmed=NO",
            o.id.c_str(), o.completed ? 1 : 0, o.reason.c_str(), o.before.x, o.before.y, o.before.z,
            o.after.x, o.after.y, o.after.z);
        Say(b);
    }
    // /wbprobe movement ... | /wbprobe move ... | /wbprobe stop. Returns true if handled.
    bool HandleMovement(const char* rest) {
        std::string tok[6];
        int n = 0;
        for (const char* c = rest; *c && n < 6;) {
            while (*c == ' ') ++c;
            const char* b = c;
            while (*c && *c != ' ') ++c;
            if (c > b) tok[n++].assign(b, c - b);
        }
        if (n == 0) return false;
        if (tok[0] == "stop") { adapter_->Stop(); Say("[WorkbenchNativeProbe] STOP issued."); return true; }
        if (tok[0] == "move") {
            if (n != 5) { Say("[WorkbenchNativeProbe] usage: /wbprobe move <id> <dx> <dy> <dz>"); return true; }
            char* end = nullptr;
            wb::Vec3 d;
            d.x = std::strtof(tok[2].c_str(), &end); if (*end) d.x = NAN;
            d.y = std::strtof(tok[3].c_str(), &end); if (*end) d.y = NAN;
            d.z = std::strtof(tok[4].c_str(), &end); if (*end) d.z = NAN;
            const auto r = adapter_->Request(tok[1], d);
            Say(("[WorkbenchNativeProbe] move " + std::string(r.ok ? "accepted: " : "REJECTED: ") + r.reason).c_str());
            return true;
        }
        if (tok[0] == "warp") {  // /wbprobe warp <id> <x> <y> <z>  (server coords, as !logpos prints)
            if (n != 5) { Say("[WorkbenchNativeProbe] usage: /wbprobe warp <id> <x> <y> <z>  (server order: x, y=height, z; as !logpos)"); return true; }
            char* end = nullptr;
            float v[3];
            for (int i = 0; i < 3; ++i) { v[i] = std::strtof(tok[2 + i].c_str(), &end); if (*end) v[i] = NAN; }
            const auto r = adapter_->RequestAbsolute(tok[1], wb::ServerToSdk(v[0], v[1], v[2]));
            Say(("[WorkbenchNativeProbe] warp " + std::string(r.ok ? "accepted: " : "REJECTED: ") + r.reason).c_str());
            if (r.ok) SayLast();
            return true;
        }
        if (tok[0] == "speed") {  // /wbprobe speed <percent>|off|status
            char b[256];
            if (n == 1 || tok[1] == "status") {
                const auto sn = port_->Snapshot();
                std::snprintf(b, sizeof(b), "[WorkbenchNativeProbe] speed: override=%s %.0f%% armed=%d MovementSpeed=%.3f MovementSpeed2=%.3f",
                              speed_->active() ? "ON" : "off", speed_->percent(), adapter_->enabled() ? 1 : 0,
                              sn.valid ? port_->ReadSpeed1(sn.entity_index) : -1.0f, [&] { float f = -1; if (sn.valid) port_->ReadSpeed(sn.entity_index, f); return f; }());
                Say(b);
            } else if (tok[1] == "off") {
                speed_->Off();
                router_->SuppressSpeedConfig();
                Say("[WorkbenchNativeProbe] speed override off (base restored).");
            } else {
                char* end = nullptr;
                const float pct = std::strtof(tok[1].c_str(), &end);
                if (*end || !adapter_->enabled() || !speed_->Set(pct))
                    Say("[WorkbenchNativeProbe] speed REJECTED: needs movement armed and percent 25..400.");
                else Say("[WorkbenchNativeProbe] speed override set; held while armed (re-applied after zoning).");
            }
            return true;
        }
        if (tok[0] == "warpinfo") {  // read-only discovery of the warp structs
            auto* snap = static_cast<SdkMovementPort*>(port_);
            const auto sn = snap->Snapshot();
            if (!sn.valid) { Say("[WorkbenchNativeProbe] warpinfo: state unverified."); return true; }
            float w[2][3]; bool ok[2];
            const uintptr_t wp = snap->ReadWarp(sn.entity_index, w, ok);
            char b[320];
            std::snprintf(b, sizeof(b), "[WorkbenchNativeProbe] warpinfo: ptr=0x%08X local(sdk x,y,z)=(%.3f,%.3f,%.3f)",
                          (unsigned)wp, sn.pos.x, sn.pos.y, sn.pos.z);
            Say(b);
            for (int i = 0; i < 2 && wp; ++i) {
                std::snprintf(b, sizeof(b), "[WorkbenchNativeProbe] warpinfo: +%u %s mem(x,h,horiz)=(%.3f,%.3f,%.3f)",
                              (unsigned)SdkMovementPort::kWarpOffsets[i], ok[i] ? "ok" : "UNREADABLE", w[i][0], w[i][1], w[i][2]);
                Say(b);
            }
            return true;
        }
        if (tok[0] != "movement") return false;
        if (n == 1 || tok[1] == "status") {
            Say(adapter_->enabled() ? "[WorkbenchNativeProbe] movement=ENABLED (dev mode)" :
                                      "[WorkbenchNativeProbe] movement=DISABLED (default)");
            SayLast();
        } else if (tok[1] == "enable") {
            // Explicit consent token is required: mode then the literal phrase.
            const bool local = n >= 3 && tok[2] == "local";
            const bool autorun = n >= 3 && tok[2] == "autorun";
            const bool warp = n >= 3 && tok[2] == "warp";
            if (!(local || autorun || warp) || n != 4 || tok[3] != "DEV-SERVER-ONLY") {
                Say("[WorkbenchNativeProbe] usage: /wbprobe movement enable <autorun|local|warp> DEV-SERVER-ONLY (authorized private DSP/Topaz test server only)");
            } else {
                const auto r = adapter_->Enable(warp ? wb::Mode::Warp : local ? wb::Mode::LocalWrite : wb::Mode::Autorun);
                Say(("[WorkbenchNativeProbe] enable: " + r.reason).c_str());
            }
        } else if (tok[1] == "disable") {
            adapter_->Disable();
            speed_->Off();
            router_->SuppressAutoArm();
            Say("[WorkbenchNativeProbe] movement disabled.");
        } else if (tok[1] == "audit") {
            SayAudit(20);
        } else {
            return false;
        }
        return true;
    }
public:
    const char* GetName() const override { return "WorkbenchNativeProbe"; }
    const char* GetAuthor() const override { return "FFXI Mission Toolkit contributors"; }
    const char* GetDescription() const override { return "Read-only Ashita v4 native compatibility probe"; }
    const char* GetLink() const override { return "https://github.com/sarthax/FFXI-Mission-Toolkit"; }
    double GetVersion() const override { return 0.1; }
    double GetInterfaceVersion() const override { return ASHITA_INTERFACE_VERSION; }
    int32_t GetPriority() const override { return 0; }
    uint32_t GetFlags() const override { return static_cast<uint32_t>(Ashita::PluginFlags::UseCommands) |
                                                          static_cast<uint32_t>(Ashita::PluginFlags::UseDirect3D); }
    bool Initialize(IAshitaCore* core, ILogManager*, uint32_t) override {
        if (!core) return false;
        core_ = core;
        port_ = new SdkMovementPort(core);
        dir_ = std::filesystem::path(core->GetInstallPath()) / "config" / "workbench_native";
        std::error_code ec;
        std::filesystem::create_directories(dir_, ec);
        const wb::Settings st = LoadSettings();
        wb::Limits lim;
        lim.enable_ttl = st.enable_ttl_seconds;
        adapter_ = new wb::MovementAdapter(*port_, lim);
        speed_ = new wb::SpeedOverride(*port_, static_cast<float>(st.base_speed));
        char nonce[32];
        std::snprintf(nonce, sizeof(nonce), "%llx", static_cast<unsigned long long>(EpochMs()) ^ (static_cast<unsigned long long>(GetCurrentProcessId()) << 40));
        router_ = new wb::ControlRouter(*adapter_, *speed_, *port_, nonce);
        router_->SetSettings(st);
        core_->GetChatManager()->Write(1, false, "[WorkbenchNativeProbe] Loaded: reads available; movement DISABLED by default.");
        return true;
    }
    void Release() override {
        StopPacketRecording();
        if (adapter_) { adapter_->Stop("unload"); adapter_->Disable("unload"); }
        if (speed_) speed_->Off();
        if (speed_ && adapter_) speed_->Tick(false);  // restore base speed once before teardown
        delete router_; router_ = nullptr;
        delete speed_; speed_ = nullptr;
        delete adapter_; adapter_ = nullptr;
        delete port_; port_ = nullptr;
        core_ = nullptr;
    }
    // SDK default returns false, which makes Ashita refuse to load a UseDirect3D plugin.
    bool Direct3DInitialize(IDirect3DDevice8*) override { return true; }
    void Direct3DPresent(const RECT*, const RECT*, HWND, const RGNDATA*) override {
        if (adapter_) {
            adapter_->Tick();
            router_->Tick();
            PollFiles();
            if (packet_writer_) {
                try { packet_writer_->Pump(); }
                catch (const std::exception&) { StopPacketRecording(); }
            }
        }
    }
    bool HandleCommand(int32_t, const char* command, bool) override {
        if (command == nullptr) return false;
        // Match only the literal command (optionally with trailing spaces).
        constexpr char prefix[] = "/wbprobe";
        if (std::strncmp(command, prefix, sizeof(prefix)-1) != 0) return false;
        const char* rest = command + sizeof(prefix)-1;
        while (*rest == ' ') ++rest;
        if (std::strcmp(rest, "capture start") == 0 || std::strcmp(rest, "capture stop") == 0 ||
            std::strcmp(rest, "capture status") == 0) {
            HandlePacketRecorderCommand(rest);
            return true;
        }
        if (adapter_ && *rest && HandleMovement(rest)) return true;
        const bool position = std::strcmp(rest, "position") == 0;
        const bool capabilities = std::strcmp(rest, "capabilities") == 0;
        if (*rest != '\0' && !position && !capabilities) return false;
        if (capabilities) {
            if (core_) core_->GetChatManager()->Write(1, false,
                "[WorkbenchNativeProbe] Native XYZ setters declared; writes=disabled; server acceptance=unverified.");
            return true;
        }
        if (position) {
            auto* memory = core_ ? core_->GetMemoryManager() : nullptr;
            auto* party = memory ? memory->GetParty() : nullptr;
            auto* entities = memory ? memory->GetEntity() : nullptr;
            if (!party || !entities || party->GetMemberIsActive(0) == 0 ||
                party->GetMemberServerId(0) == 0 || party->GetMemberZone(0) == 0) {
                if (core_) core_->GetChatManager()->Write(1, false,
                    "[WorkbenchNativeProbe] Position unavailable: no active player.");
                return true;
            }
            const uint32_t server_id = party->GetMemberServerId(0);
            const uint32_t capacity = entities->GetEntityMapSize();
            uint32_t index = 0;
            // The SDK has no id->index lookup, so scan the entity map for the player's server id.
            for (uint32_t i = 1; i < capacity; ++i) {
                if (entities->GetServerId(i) == server_id) { index = i; break; }
            }
            if (index == 0) {
                char detail[256];
                std::snprintf(detail, sizeof(detail),
                    "[WorkbenchNativeProbe] Index unresolved: party_slot=%u server_id=%u mapped=%u map_size=%u",
                    static_cast<unsigned>(party->GetMemberIndex(0)), static_cast<unsigned>(server_id),
                    static_cast<unsigned>(index), static_cast<unsigned>(capacity));
                core_->GetChatManager()->Write(1, false, detail);
                return true;
            }
            const float x = entities->GetLocalPositionX(index);
            const float y = entities->GetLocalPositionY(index);
            const float z = entities->GetLocalPositionZ(index);
            if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
                core_->GetChatManager()->Write(1, false,
                    "[WorkbenchNativeProbe] Position unavailable: nonfinite coordinate.");
                return true;
            }
            char output[256];
            std::snprintf(output, sizeof(output),
                "[WorkbenchNativeProbe] Read-only zone=%u entity=%u XYZ=(%.3f, %.3f, %.3f)",
                static_cast<unsigned>(party->GetMemberZone(0)), static_cast<unsigned>(index),
                static_cast<double>(x), static_cast<double>(y), static_cast<double>(z));
            core_->GetChatManager()->Write(1, false, output);
            return true;
        }
        if (core_ != nullptr)
            core_->GetChatManager()->Write(1, false,
                "[WorkbenchNativeProbe] SDK loaded; read-only; XYZ write=disabled; packet injection=disabled.");
        return true;
    }
};

extern "C" {
__declspec(dllexport) IPlugin* __stdcall expCreatePlugin(const char*) {
    return new WorkbenchNativeProbe();
}
__declspec(dllexport) void __stdcall expDestroyPlugin(void* instance) {
    delete static_cast<WorkbenchNativeProbe*>(instance);
}
__declspec(dllexport) double __stdcall expGetInterfaceVersion() {
    return ASHITA_INTERFACE_VERSION;
}
}
