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
#include "movement_adapter.h"

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
    double NowSeconds() override {
        using namespace std::chrono;
        return duration<double>(steady_clock::now().time_since_epoch()).count();
    }
};

class WorkbenchNativeProbe final : public IPlugin {
    IAshitaCore* core_ = nullptr;
    SdkMovementPort* port_ = nullptr;
    wb::MovementAdapter* adapter_ = nullptr;
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
        if (tok[0] != "movement") return false;
        if (n == 1 || tok[1] == "status") {
            Say(adapter_->enabled() ? "[WorkbenchNativeProbe] movement=ENABLED (dev mode)" :
                                      "[WorkbenchNativeProbe] movement=DISABLED (default)");
            SayLast();
        } else if (tok[1] == "enable") {
            // Explicit consent token is required: mode then the literal phrase.
            const bool local = n >= 3 && tok[2] == "local";
            const bool autorun = n >= 3 && tok[2] == "autorun";
            if (!(local || autorun) || n != 4 || tok[3] != "DEV-SERVER-ONLY") {
                Say("[WorkbenchNativeProbe] usage: /wbprobe movement enable <autorun|local> DEV-SERVER-ONLY (authorized private DSP/Topaz test server only)");
            } else {
                const auto r = adapter_->Enable(local ? wb::Mode::LocalWrite : wb::Mode::Autorun);
                Say(("[WorkbenchNativeProbe] enable: " + r.reason).c_str());
            }
        } else if (tok[1] == "disable") {
            adapter_->Disable();
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
        adapter_ = new wb::MovementAdapter(*port_);
        core_->GetChatManager()->Write(1, false, "[WorkbenchNativeProbe] Loaded: reads available; movement DISABLED by default.");
        return true;
    }
    void Release() override {
        if (adapter_) { adapter_->Stop("unload"); adapter_->Disable("unload"); }
        delete adapter_; adapter_ = nullptr;
        delete port_; port_ = nullptr;
        core_ = nullptr;
    }
    // SDK default returns false, which makes Ashita refuse to load a UseDirect3D plugin.
    bool Direct3DInitialize(IDirect3DDevice8*) override { return true; }
    void Direct3DPresent(const RECT*, const RECT*, HWND, const RGNDATA*) override {
        if (adapter_) adapter_->Tick();
    }
    bool HandleCommand(int32_t, const char* command, bool) override {
        if (command == nullptr) return false;
        // Match only the literal command (optionally with trailing spaces).
        constexpr char prefix[] = "/wbprobe";
        if (std::strncmp(command, prefix, sizeof(prefix)-1) != 0) return false;
        const char* rest = command + sizeof(prefix)-1;
        while (*rest == ' ') ++rest;
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
            for (uint32_t i = 1; i < capacity; ++i) {
                if (entities->GetServerId(i) == server_id) {
                    index = i;
                    break;
                }
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
