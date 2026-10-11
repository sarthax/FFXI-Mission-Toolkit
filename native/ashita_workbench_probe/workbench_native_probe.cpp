// Original Mission Toolkit native Ashita v4 load probe.
// Deliberately no game memory access, packet mutations, or network transport.
#include "Ashita.h"
#include <cstring>
#include <cmath>
#include <cstdio>
#include <type_traits>

// Compile-time SDK signature gate only: these methods are never invoked.
using XYZSetter = void (IEntity::*)(uint32_t, float) const;
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionX), XYZSetter>);
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionY), XYZSetter>);
static_assert(std::is_same_v<decltype(&IEntity::SetLocalPositionZ), XYZSetter>);

class WorkbenchNativeProbe final : public IPlugin {
    IAshitaCore* core_ = nullptr;
public:
    const char* GetName() const override { return "WorkbenchNativeProbe"; }
    const char* GetAuthor() const override { return "FFXI Mission Toolkit contributors"; }
    const char* GetDescription() const override { return "Read-only Ashita v4 native compatibility probe"; }
    const char* GetLink() const override { return "https://github.com/sarthax/FFXI-Mission-Toolkit"; }
    double GetVersion() const override { return 0.1; }
    double GetInterfaceVersion() const override { return ASHITA_INTERFACE_VERSION; }
    int32_t GetPriority() const override { return 0; }
    uint32_t GetFlags() const override { return static_cast<uint32_t>(Ashita::PluginFlags::UseCommands); }
    bool Initialize(IAshitaCore* core, ILogManager*, uint32_t) override {
        if (!core) return false;
        core_ = core;
        core_->GetChatManager()->Write(1, false, "[WorkbenchNativeProbe] Loaded: read-only; movement writes unavailable.");
        return true;
    }
    void Release() override { core_ = nullptr; }
    bool HandleCommand(int32_t, const char* command, bool) override {
        if (command == nullptr) return false;
        // Match only the literal command (optionally with trailing spaces).
        constexpr char prefix[] = "/wbprobe";
        if (std::strncmp(command, prefix, sizeof(prefix)-1) != 0) return false;
        const char* rest = command + sizeof(prefix)-1;
        while (*rest == ' ') ++rest;
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
