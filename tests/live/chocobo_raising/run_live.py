"""Live headless scenarios for the DSP Chocobo Raising port (branch feature/chocobo-raising-core).

Not collected by pytest (needs running DSConnect/DSSearch/DSGame servers, the XiHeadless MCP client and
a leased pool character). Run:  py -3 run_live.py day_report [days] | retirement
Env: XI_PROTO=dsp XI_HOST=127.0.0.1 XI_CLIENTVER=30170905_5 DOTNET_EnableWriteXorExecute=0 XIBOT_NAVMESH_DIR=...
Exit code 0 = every assertion passed. Evidence per slice: docs/slices/chocobo-raising-core/TEST_PLAN.md (DSP repo).
"""
import os, re, sys, time

HEADLESS = os.environ.get("XIHEADLESS_DIR", "D:/Claude/FFXI-Tools/headless-research/xiheadless-dsp-chocobo")
DSP = os.environ.get("DSP_RUN_TREE", "D:/Claude/dsp-branches")
# pool account -> charid; ACCOUNT env picks one so scenarios can run in parallel (one account per stream)
POOL_CHARS = {"xitest03": 21831, "xitest04": 21832, "xitest05": 21833, "xitest06": 21834, "xitest07": 21836, "xitest08": 21837}
ACCOUNT = os.environ.get("ACCOUNT", "xitest03"); CHAR = POOL_CHARS[ACCOUNT]
# trainer -> (npc id, !pos, zone, chocobo location); csid sets: Pulonono {741,742,745,748}, Hantileon {817,823,826,831}, Zopago {508,509,512,515}
TRAINERS = {"pulonono": (17764419, "!pos 129 -5.35 -117 241", 241, 3),
            "hantileon": (17719570, "!pos -2.7 -0.1 -103 230", 230, 1),
            "zopago": (17735824, "!pos 51.7 0.874 -107 234", 234, 2)}
TRAINER = os.environ.get("TRAINER", "pulonono")
NPC, POS, ZONE, LOC = TRAINERS[TRAINER]
MAPLOG = DSP + "/log/map-server.log"
sys.path.insert(0, HEADLESS + "/tools")
os.chdir(HEADLESS)
import mysql.connector
from char_pool import Pool
from mcp_client import McpBot

pw = re.search(r"mysql_password:\s*(.*)", open(DSP + "/conf/map_darkstar.conf").read()).group(1).strip()
db = mysql.connector.connect(host="127.0.0.1", user="root", password=pw, database="dspdb_fresh", autocommit=True)
def q(s):
    c = db.cursor(); c.execute(s); return c.fetchall()

failures = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
    if not ok: failures.append(name)

def seed(stage, days):
    if q(f"select count(*) from char_chocobos where charid={CHAR}")[0][0] == 0:   # baseline yellow chocobo
        q(f"insert into char_chocobos (charid,first_name,last_name,sex,last_update_age,stage,location,color,strength,"
          f"endurance,discernment,receptivity,affection,energy,satisfaction,conditions,ability1,ability2,personality,"
          f"weather_preference,hunger,care_plan,held_item) values ({CHAR},'Test','Bird',0,1,{stage},{LOC},0,10,10,10,10,10,100,50,0,0,0,0,0,255,0,0)")
    q(f"update char_chocobos set stage={stage},last_update_age=1,hunger=255,energy=100,conditions=0,locked_plan=0,"
      f"location={LOC},created=now()-interval ({days}*86400-100) second where charid={CHAR}")
    q(f"update chars set pos_zone={ZONE},pos_prevzone=0,pos_rot=0,pos_x=129,pos_y=-6.35,pos_z=-117 where charid={CHAR}")

def session(scenario):
    pool = Pool(8); a = pool.acquire(only=ACCOUNT); crashed = True; b = None
    log0 = len(open(MAPLOG, errors="replace").read())
    try:
        scenario_seed = scenario.seed
        scenario_seed()
        b = McpBot(a[0], a[1], a[2], tag="live"); b.start(); time.sleep(3)
        b.gm(POS, settle=8); b.tool("event_trace", clear=True); time.sleep(4)
        r = b.tool("talk_to_npc", npcId=NPC)
        check("trainer event starts", r.get("started") is True, r)
        time.sleep(2); b.tool("event_trace", clear=True)
        scenario.run(b)
        errs = [l for l in open(MAPLOG, errors="replace").read()[log0:].splitlines() if "[Error]" in l and ("choco" in l.lower() or "luautils" in l)]
        check("no Lua/chocobo errors in map log", not errs, errs[:2])
    finally:
        try: b.close(); crashed = b.p.returncode != 0
        except Exception: pass
        pool.release(a, crashed)

def size_masked(h):
    """Card exdata with byte 7's size nibble (bits 28-31 = owner race id, Galka 0) cleared; checked separately by size_ok."""
    b = h.split(" "); b[7] = f"{int(b[7], 16) & 0x0F:02X}"; return b
def size_ok(h):
    race = q(f"select race from char_look where charid={CHAR}")[0][0]
    return int(h.split(" ")[7], 16) >> 4 == (0 if race == 8 else race)

class Day:
    def __init__(self, days=6): self.days = days
    def seed(self): seed(1, self.days)
    def run(self, b):
        for opt in (248, 504, 246, 246):
            b.tool("event_update", option=opt); time.sleep(0.7)
        b.tool("event_select", selection=0); time.sleep(3)
        stage = q(f"select stage from char_chocobos where charid={CHAR}")[0][0]
        # seed() makes the bird days-1 days old; thresholds are DSP daysToChick..daysToAdult4 (4,19,29,43,64,129)
        elapsed = self.days - 1
        want = 1 + sum(elapsed >= t for t in (4, 19, 29, 43, 64, 129))
        check(f"{self.days} days -> stage {want}", stage == want, f"stage={stage}")

class Retirement:
    # retiring deletes the row, so keep a copy and put it back afterwards (scenarios stay order-independent)
    def seed(self):
        c = db.cursor(dictionary=True); c.execute(f"select * from char_chocobos where charid={CHAR}")
        self.row = c.fetchone(); seed(4, 3)
        q(f"update char_chocobos set first_name='EirSkd',last_name='O8T18',sex=1,color=0,strength=56,endurance=48,discernment=8,"
          f"receptivity=11,allele1=0,allele2=1,allele3=2,ability1=0,ability2=0,personality=4,weather_preference=0,appearance=0 where charid={CHAR}")
        q(f"delete from char_vars where charid={CHAR} and varname='ChocoRetireItems'")
    def run(self, b):
        for opt in (24672, 244, 40):          # command 96, 244, 40 (San d'Oria capture sequence)
            b.tool("event_update", option=opt); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(3)
        items = {r[0] for r in q(f"select itemid from char_inventory where charid={CHAR} and itemid in (2313,309,310,311,312,313)")}
        check("VCS card 2313 received", 2313 in items, items)
        check("yellow plaque 309 received", 309 in items, items)
        check("chocobo row deleted", q(f"select count(*) from char_chocobos where charid={CHAR}")[0][0] == 0)
        ex = q(f"select extra from char_inventory where charid={CHAR} and itemid=2313")
        got = bytes(ex[0][0]).hex(" ").upper() if ex else ""
        want = "38 30 08 0B 88 00 08 11 00 00 00 00 4F 6B 77 2F 9A 25 9E 90 00 00 00 00"
        mask = size_masked
        check("card exdata matches capture bytes", bool(got) and mask(got) == mask(want), got)
        check("card size nibble = owner race", bool(got) and size_ok(got), got)
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2313,309,310,311,312,313)")
        if self.row:
            cols = ",".join(self.row); vals = ",".join("%s" for _ in self.row)
            c = db.cursor(); c.execute(f"insert into char_chocobos ({cols}) values ({vals})", list(self.row.values()))

class Chococard:
    # option 239 at the trainer: 300 gil -> chococard (F) 2342 with the capture's exdata; the chocobo stays
    def seed(self):
        seed(4, 3)
        q(f"update char_chocobos set first_name='EirSkd',last_name='O8T18',sex=1,color=0,strength=56,endurance=48,discernment=8,"
          f"receptivity=11,allele1=0,allele2=1,allele3=2,ability1=0,ability2=0,personality=4,weather_preference=0,appearance=0 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2339,2342)")
        q(f"update char_inventory set quantity=1000 where charid={CHAR} and itemid=65535 and location=0")
    def run(self, b):
        b.tool("event_update", option=239); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(2)
        ex = q(f"select extra from char_inventory where charid={CHAR} and itemid=2342")
        got = bytes(ex[0][0]).hex(" ").upper() if ex else ""
        want = "38 30 08 0B 88 00 08 11 00 00 00 00 4F 6B 77 2F 9A 25 9E 90 00 00 00 00"
        mask = size_masked
        check("chococard 2342 exdata matches capture", bool(got) and mask(got) == mask(want), got)
        check("chococard size nibble = owner race", bool(got) and size_ok(got), got)
        gil = q(f"select quantity from char_inventory where charid={CHAR} and itemid=65535 and location=0")[0][0]
        check("300 gil charged", gil == 700, gil)
        check("chocobo kept", q(f"select count(*) from char_chocobos where charid={CHAR}")[0][0] == 1)
        q(f"delete from char_inventory where charid={CHAR} and itemid=2342")

class Feed:
    # trade 2 gysahl greens (4545), option 241: hunger up, greens consumed (capture: reply (10, glow, 0,0,1,rank,0,0))
    def seed(self):
        seed(3, 10); q(f"update char_chocobos set hunger=100 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid=4545")
    def run(self, b):
        b.tool("event_select", selection=0); time.sleep(3)
        b.gm("!additem 4545 2"); time.sleep(2)
        r = b.tool("trade_npc", npcId=NPC, items=[{"itemId": 4545, "qty": 2}]); time.sleep(2)
        b.tool("event_update", option=241); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(3)
        hunger = q(f"select hunger from char_chocobos where charid={CHAR}")[0][0]
        left = q(f"select coalesce(sum(quantity),0) from char_inventory where charid={CHAR} and itemid=4545")[0][0]
        check("feeding raised hunger", hunger > 100, f"hunger={hunger} trade={r}")
        check("gysahl consumed", left == 0, left)

class Menu:
    # options accepted with no Lua error; each is (option, meaning). Reply bytes are not traced by the harness.
    # 215 (intro 3) ends the event, so it must come last
    OPTS = [(208, "check report"), (252, "unknown 252"), (214, "intro 2"), (250, "care menu"),
            (244, "appearance"), (500, "appearance arg"), (251, "condition"), (63220, "244 with args"), (215, "intro 3")]
    def seed(self): seed(4, 30)
    def run(self, b):
        for opt, name in self.OPTS:
            r = b.tool("event_update", option=opt); time.sleep(0.7)
            if isinstance(r, dict) and r.get("error") == "no active event":   # previous option ended the event: reopen, retry once
                b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
                r = b.tool("event_update", option=opt); time.sleep(0.7)
            check(f"option {opt} ({name}) accepted", not (isinstance(r, dict) and r.get("error")), r)
            if isinstance(r, dict) and r.get("stillActive") is False:                # ended by this option (e.g. 250, 215): reopen for the next
                b.tool("talk_to_npc", npcId=NPC); time.sleep(2)

class CarePlan:
    # 0xFE update (852222 = slot 0, length 5, type 1) writes the plan byte length<<4|type (slice 2 evidence 0x51)
    def seed(self):
        seed(4, 30); q(f"update char_chocobos set care_plan=0x70707070 where charid={CHAR}")
    def run(self, b):
        b.tool("event_update", option=852222); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        plan = q(f"select care_plan from char_chocobos where charid={CHAR}")[0][0]
        check("care plan slot 0 = 0x51", (plan >> 24) & 0xFF == 0x51, hex(plan))

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "retirement"
    sc = Day(int(sys.argv[2]) if len(sys.argv) > 2 else 6) if name == "day_report" else Chococard() if name == "chococard" else {"feed": Feed, "menu": Menu, "careplan": CarePlan}.get(name, Retirement)() if name != "retirement" else Retirement()
    session(sc)
    print("RESULT", "FAIL" if failures else "PASS", failures)
    sys.exit(1 if failures else 0)
