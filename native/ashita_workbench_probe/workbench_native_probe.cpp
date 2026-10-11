// Original Mission Toolkit native Ashita v4 load probe.
// Deliberately no game memory access, packet mutations, or network transport.
#include "Ashita.h"
#include <cstring>

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
        if (*rest != '\0') return false;
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
