// Host-side tests for movement_adapter.h (no Ashita SDK, no game access).
#include "movement_adapter.h"
#include <cstdio>
#include <cstdlib>
#include <limits>

using namespace wb;

struct FakePort : MovementPort {
    PlayerSnapshot snap;
    double now = 100.0;
    int begin = 0, end = 0, writes = 0;
    Vec3 last_dir, last_write;
    FakePort() { snap.valid = true; snap.server_id = 1234; snap.entity_index = 7; snap.zone = 98; snap.pos = {10, 20, 30}; }
    PlayerSnapshot Snapshot() override { return snap; }
    void BeginAutorun(const Vec3& d) override { ++begin; last_dir = d; }
    void EndAutorun() override { ++end; }
    void WriteLocalPosition(uint32_t, const Vec3& p) override { ++writes; last_write = p; snap.pos = p; }
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
    if (failures == 0) std::puts("movement_adapter_test: ALL PASSED");
    return failures ? 1 : 0;
}
