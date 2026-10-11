// Host-side tests for movement_adapter.h (no Ashita SDK, no game access).
#include "movement_adapter.h"
#include "native_control.h"
#include <cstdio>
#include <cstdlib>
#include <limits>

using namespace wb;

struct FakePort : MovementPort {
    PlayerSnapshot snap;
    double now = 100.0;
    int begin = 0, end = 0, writes = 0, warps = 0;
    Vec3 last_dir, last_write, last_warp;
    const char* warp_fail = nullptr;
    float speed = 5.0f; int speed_writes = 0; bool speed_readable = true;
    FakePort() { snap.valid = true; snap.server_id = 1234; snap.entity_index = 7; snap.zone = 98; snap.pos = {10, 20, 30}; }
    PlayerSnapshot Snapshot() override { return snap; }
    void BeginAutorun(const Vec3& d) override { ++begin; last_dir = d; }
    void EndAutorun() override { ++end; }
    void WriteLocalPosition(uint32_t, const Vec3& p) override { ++writes; last_write = p; snap.pos = p; }
    const char* WriteWarpPosition(uint32_t, const Vec3& p) override {
        if (warp_fail) return warp_fail;
        ++warps; last_warp = p; snap.pos = p; return nullptr;
    }
    bool ReadSpeed(uint32_t, float& v) override { v = speed; return speed_readable; }
    void WriteSpeed(uint32_t, float v) override { speed = v; ++speed_writes; }
    double NowSeconds() override { return now; }
};

static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); ++failures; } } while (0)
static bool denied(const Result& r, const char* why) { return !r.ok && r.reason == why; }

int main() {
    const float nan = std::numeric_limits<float>::quiet_NaN();
    {   // disabled by default
        FakePort p; MovementAdapter a(p);
        CHECK(!a.enabled());
        CHECK(denied(a.Request("a", {1, 0, 0}), "disabled"));
        CHECK(p.begin == 0 && p.writes == 0);
    }
    {   // enable fails closed when state unverified / zoning
        FakePort p; MovementAdapter a(p);
        p.snap.valid = false; CHECK(denied(a.Enable(Mode::Autorun), "state_unverified"));
        p.snap.valid = true; p.snap.zoning = true; CHECK(denied(a.Enable(Mode::Autorun), "state_unverified"));
        CHECK(!a.enabled());
    }
    {   // validation
        FakePort p; MovementAdapter a(p); CHECK(a.Enable(Mode::Autorun).ok);
        CHECK(denied(a.Request("", {1, 0, 0}), "invalid_id"));
        CHECK(denied(a.Request("n", {nan, 0, 0}), "nonfinite_delta"));
        CHECK(denied(a.Request("inf", {std::numeric_limits<float>::infinity(), 0, 0}), "nonfinite_delta"));
        CHECK(denied(a.Request("big", {3.5f, 0, 0}), "exceeds_max_step"));
        CHECK(denied(a.Request("tiny", {0.01f, 0, 0}), "delta_too_small"));
        CHECK(denied(a.Request("vert", {0, 0, 1}), "vertical_unsupported_in_autorun"));
        CHECK(p.begin == 0);
    }
    {   // identity / zone / zoning / staleness
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        p.snap.server_id = 99; CHECK(denied(a.Request("w", {1, 0, 0}), "wrong_character"));
        p.snap.server_id = 1234; p.snap.zone = 5; CHECK(denied(a.Request("z", {1, 0, 0}), "wrong_zone"));
        p.snap.zone = 98; p.snap.zoning = true; CHECK(denied(a.Request("zg", {1, 0, 0}), "zoning"));
        p.snap.zoning = false; p.snap.valid = false; CHECK(denied(a.Request("v", {1, 0, 0}), "state_unverified"));
        p.snap.valid = true; p.snap.pos.x = nan; CHECK(denied(a.Request("np", {1, 0, 0}), "nonfinite_position"));
        CHECK(p.begin == 0);
    }
    {   // autorun happy path, rate limit, duplicate, busy
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        CHECK(a.Request("m1", {2, 0, 0}).ok);
        CHECK(p.begin == 1 && a.active());
        CHECK(denied(a.Request("m2", {1, 0, 0}), "busy"));
        p.snap.pos.x = 11; a.Tick(); CHECK(a.active());
        p.snap.pos.x = 11.8f; a.Tick();
        CHECK(!a.active() && a.last().completed && a.last().reason == "arrived" && p.end >= 1);
        CHECK(!a.last().server_confirmed);
        CHECK(denied(a.Request("m3", {1, 0, 0}), "rate_limited"));
        p.now += 2.0;
        CHECK(denied(a.Request("m1", {1, 0, 0}), "duplicate_id"));
        CHECK(a.Request("m3", {1, 0, 0}).ok);
    }
    {   // slope: height change must not defeat arrival
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        a.Request("sl", {0, 2, 0}); p.snap.pos = {10, 21.8f, 31.5f}; a.Tick();
        CHECK(a.last().reason == "arrived");
    }
    {   // stop, overshoot, timeout, state lost
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        a.Request("s1", {2, 0, 0}); a.Stop();
        CHECK(!a.active() && a.last().reason == "operator_stop" && !a.last().completed && p.end >= 1);
        p.now += 2; a.Request("o1", {1, 0, 0}); p.snap.pos.x = 14; a.Tick();
        CHECK(a.last().reason == "overshoot" && !a.active());
        p.now += 2; p.snap.pos = {10, 20, 30}; a.Request("t1", {2, 0, 0}); p.now += 5; a.Tick();
        CHECK(a.last().reason == "timeout");
        p.now += 2; p.snap.pos = {10, 20, 30}; a.Request("l1", {2, 0, 0}); p.snap.zoning = true; a.Tick();
        CHECK(a.last().reason == "state_lost" && !a.active());
    }
    {   // stop works even with unverifiable state
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        a.Request("x", {1, 0, 0}); p.snap.valid = false; a.Stop();
        CHECK(!a.active() && p.end >= 1);
    }
    {   // local write mode is bounded and reported as client-local only
        FakePort p; MovementAdapter a(p); a.Enable(Mode::LocalWrite);
        CHECK(a.Request("w1", {1, 0, 0}).ok);
        CHECK(p.writes == 1 && p.last_write.x == 11.0f && p.begin == 0);
        CHECK(a.last().completed && !a.last().server_confirmed);
        p.now += 2; CHECK(denied(a.Request("w2", {10, 0, 0}), "exceeds_max_step"));
        CHECK(p.writes == 1);
    }
    {   // warp mode: bounded, allows vertical, client-local report only, fails closed
        FakePort p; MovementAdapter a(p); CHECK(a.Enable(Mode::Warp).ok);
        CHECK(a.Request("p1", {0, 0, 1}).ok);
        CHECK(p.warps == 1 && p.last_warp.z == 31.0f && p.writes == 0 && p.begin == 0);
        CHECK(a.last().completed && a.last().reason == "warp_written" && !a.last().server_confirmed);
        p.now += 2; CHECK(a.Request("p2", {500, 0, 0}).ok);          // no distance cap in warp mode
        CHECK(p.warps == 2 && p.last_warp.x == 510.0f);
        p.now += 2; CHECK(denied(a.Request("pb", {5000, 0, 0}), "target_out_of_bounds"));
        p.now += 2; CHECK(denied(a.RequestAbsolute("pn", {nan, 0, 0}), "nonfinite_target"));
        p.now += 2; CHECK(a.Request("pr0", {1, 0, 0}).ok);
        p.now += 0.1; CHECK(denied(a.Request("pr", {1, 0, 0}), "rate_limited"));
        p.now += 2; p.snap.pos = {10, 20, 30};
        CHECK(a.RequestAbsolute("abs1", {-300, 400, 50}).ok);
        CHECK(p.warps == 4 && p.last_warp.x == -300.0f && p.last_warp.y == 400.0f && p.last_warp.z == 50.0f);
        p.now += 2; CHECK(denied(a.RequestAbsolute("abs2", {-300, 400, 50}), "delta_too_small"));
        p.now += 2; p.snap.zone = 5; CHECK(denied(a.RequestAbsolute("abs3", {1, 1, 1}), "wrong_zone"));
        p.snap.zone = 98;
        p.warp_fail = "warp_pointer_null";
        CHECK(a.Request("p3", {1, 0, 0}).ok);
        CHECK(!a.last().completed && a.last().reason == "warp_pointer_null" && p.warps == 4 && !a.active());
    }
    {   // absolute requests need warp mode; relative modes keep the 3-yalm cap
        FakePort p; MovementAdapter a(p); a.Enable(Mode::LocalWrite);
        CHECK(denied(a.RequestAbsolute("x", {11, 20, 30}), "absolute_requires_warp_mode"));
        CHECK(denied(a.Request("big", {10, 0, 0}), "exceeds_max_step"));
    }
    {   // ttl <= 0 never expires (admin opt-in); rebinding after zone change
        FakePort p; Limits l; l.enable_ttl = 0; MovementAdapter a(p, l); a.Enable(Mode::Warp);
        p.now += 100000; CHECK(a.Request("t", {1, 0, 0}).ok);
        p.snap.zone = 5; p.now += 2; CHECK(denied(a.Request("z", {1, 0, 0}), "wrong_zone"));
        CHECK(a.bound_zone() == 98 && a.Enable(Mode::Warp).ok && a.bound_zone() == 5);
        p.now += 2; CHECK(a.Request("z2", {1, 0, 0}).ok);
    }
    {   // speed override: gated by armed state, holds across resets, restores once
        FakePort p; SpeedOverride sp(p);
        CHECK(!sp.Set(10) && !sp.Set(401) && !sp.Set(nan) && !sp.active());
        CHECK(sp.Set(120));
        sp.Tick(false); p.now += 1; sp.Tick(false);          // not armed -> never writes
        CHECK(p.speed_writes == 0 && !sp.active());
        CHECK(sp.Set(120));
        p.now += 1; sp.Tick(true); CHECK(p.speed == 6.0f && p.speed_writes == 1);
        p.now += 1; sp.Tick(true); CHECK(p.speed_writes == 1);   // already correct
        p.speed = 5.0f; p.now += 1; sp.Tick(true); CHECK(p.speed == 6.0f && p.speed_writes == 2);  // zone reset
        p.snap.zoning = true; p.speed = 5.0f; p.now += 1; sp.Tick(true); CHECK(p.speed == 5.0f);   // no writes while zoning
        p.snap.zoning = false;
        p.now += 1; sp.Tick(false);                           // disarmed -> restore base once
        CHECK(p.speed == 5.0f && !sp.active());
        const int w = p.speed_writes; p.now += 1; sp.Tick(false); CHECK(p.speed_writes == w);
        p.speed_readable = false; CHECK(sp.Set(150)); p.now += 1; sp.Tick(true); CHECK(p.speed == 5.0f);
    }
    {   // enable TTL expiry
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        p.now += 121; CHECK(denied(a.Request("e", {1, 0, 0}), "enable_expired"));
        CHECK(!a.enabled());
        a.Enable(Mode::Autorun); p.now += 121; a.Tick(); CHECK(!a.enabled());
    }
    {   // disable mid-run cancels
        FakePort p; MovementAdapter a(p); a.Enable(Mode::Autorun);
        a.Request("d", {2, 0, 0}); a.Disable();
        CHECK(!a.active() && !a.enabled() && a.last().reason == "disabled");
    }
    {   // control channel: opt-in, nonce, staleness, replay, consent, routing
        FakePort p; Limits l; l.enable_ttl = 0; MovementAdapter a(p, l); SpeedOverride sp(p);
        ControlRouter r(a, sp, p, "N1");
        constexpr int64_t t = 1000000;
        auto cmd = [&](int seq, const char* body, int64_t ts = 1000000, const char* nonce = "N1") {
            char b[256];
            std::snprintf(b, sizeof b, "seq=%d\nnonce=%s\nts_ms=%lld\n%s\n", seq, nonce, static_cast<long long>(ts), body);
            return std::string(b);
        };
        CHECK(!r.Process(cmd(1, "cmd=stop"), t));                       // channel off by default
        r.SetSettings(ParseSettings("allow_file_commands=1\nspeed_percent=120\n"));
        CHECK(r.Process(cmd(1, "cmd=stop", t, "BAD"), t) && r.last().reason == "nonce_mismatch");
        CHECK(!r.Process(cmd(1, "cmd=stop"), t));                       // seq consumed even when rejected
        CHECK(r.Process(cmd(2, "cmd=stop", t - 20000), t) && r.last().reason == "stale_command");
        CHECK(r.Process(cmd(3, "cmd=enable\nmode=warp"), t) && r.last().reason == "consent_required" && !a.enabled());
        CHECK(r.Process(cmd(4, "cmd=enable\nmode=bogus\nconsent=DEV-SERVER-ONLY"), t) && r.last().reason == "invalid_mode");
        CHECK(r.Process(cmd(5, "cmd=enable\nmode=warp\nconsent=DEV-SERVER-ONLY"), t) && r.last().ok && a.enabled());
        CHECK(!r.Process(cmd(5, "cmd=disable"), t) && a.enabled());     // replay ignored
        // server order x,y(height),z -> SDK (x, z, y)
        CHECK(r.Process(cmd(6, "cmd=warp_to\nid=w\nx=100\ny=-5\nz=200"), t) && r.last().ok);
        CHECK(p.last_warp.x == 100.0f && p.last_warp.y == 200.0f && p.last_warp.z == -5.0f);
        p.now += 2;
        CHECK(r.Process(cmd(7, "cmd=warp_to\nx=nan\ny=0\nz=0"), t) && r.last().reason == "invalid_target");
        CHECK(r.Process(cmd(8, "cmd=warp_to\nx=9999\ny=0\nz=0"), t) && !r.last().ok && r.last().reason == "target_out_of_bounds");
        p.now += 2;
        r.Tick(); CHECK(sp.active());                                   // configured speed hold engages once armed
        p.now += 1; r.Tick(); CHECK(p.speed == 6.0f);
        CHECK(r.Process(cmd(9, "cmd=speed_off"), t));
        p.now += 1; r.Tick(); CHECK(p.speed == 5.0f && !sp.active());
        p.now += 2; r.Tick(); CHECK(!sp.active());                      // explicit off is not re-armed by config
        CHECK(r.Process(cmd(10, "cmd=speed\nvalue=10"), t) && r.last().reason == "invalid_speed");
        CHECK(r.Process(cmd(11, "cmd=disable"), t) && !a.enabled());
        const Settings s = ParseSettings("allow_file_commands=1\nenable_ttl_seconds=0\nauto_arm=warp\nspeed_percent=900\n");
        CHECK(s.auto_arm == "warp" && s.enable_ttl_seconds == 0 && s.speed_percent == 0);
        CHECK(!ParseSettings("allow_file_commands=0").allow_file_commands && !ParseSettings("garbage").allow_file_commands);
        // auto_arm: arms, rebinds on zone change, but not after an operator disable
        FakePort p2; MovementAdapter a2(p2); SpeedOverride sp2(p2); ControlRouter r2(a2, sp2, p2, "N2");
        r2.SetSettings(s);
        r2.Tick(); CHECK(a2.enabled() && a2.bound_zone() == 98);
        p2.snap.zone = 5; p2.now += 2; r2.Tick(); CHECK(a2.bound_zone() == 5);
        a2.Disable(); r2.SuppressAutoArm(); p2.now += 2; r2.Tick(); CHECK(!a2.enabled());
        const Vec3 sv = SdkToServer(ServerToSdk(1, 2, 3)); CHECK(sv.x == 1 && sv.y == 2 && sv.z == 3);
        StatusInfo si; si.nonce = "N1"; si.snap = p.snap;
        CHECK(RenderStatus(si).find("server_confirmed=NO") != std::string::npos);
    }
    if (failures == 0) std::puts("movement_adapter_test: ALL PASSED");
    return failures ? 1 : 0;
}
