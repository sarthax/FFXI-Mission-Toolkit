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
        b.gm(getattr(scenario, "pos", POS), settle=8); b.tool("event_trace", clear=True); time.sleep(4)
        if not getattr(scenario, "notrainer", False):
            r = b.tool("talk_to_npc", npcId=NPC)
            check("trainer event starts", r.get("started") is True, r)
            time.sleep(2); b.tool("event_trace", clear=True)
        scenario.run(b)
        errs = [l for l in open(MAPLOG, errors="replace").read()[log0:].splitlines() if "[Error]" in l and ("choco" in l.lower() or "luautils" in l)]
        check("no Lua/chocobo errors in map log", not errs, errs[:2])
    finally:
        try: b.close(); crashed = b.p.returncode != 0
        except Exception: pass
        getattr(scenario, "done", lambda: None)()
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

class ChococardBroke(Chococard):
    # under 300 gil: no card, no charge, chocobo kept
    def seed(self):
        super().seed(); q(f"update char_inventory set quantity=299 where charid={CHAR} and itemid=65535 and location=0")
    def run(self, b):
        b.tool("event_update", option=239); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(2)
        check("no chococard when short of gil", q(f"select count(*) from char_inventory where charid={CHAR} and itemid in (2339,2342)")[0][0] == 0)
        gil = q(f"select quantity from char_inventory where charid={CHAR} and itemid=65535 and location=0")[0][0]
        check("no gil charged", gil == 299, gil)

class ChococardFullBag(Chococard):
    # no free slot: no card, no charge (capacity set to the used slot count; restored afterwards)
    def seed(self):
        super().seed()
        self.cap = q(f"select inventory from char_storage where charid={CHAR}")[0][0]
        used = q(f"select count(*) from char_inventory where charid={CHAR} and location=0")[0][0]
        q(f"update char_storage set inventory={used - 1} where charid={CHAR}")   # row 0 is gil, which takes no slot
    def run(self, b):
        b.tool("event_update", option=239); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(2)
        check("no chococard with a full bag", q(f"select count(*) from char_inventory where charid={CHAR} and itemid in (2339,2342)")[0][0] == 0)
        gil = q(f"select quantity from char_inventory where charid={CHAR} and itemid=65535 and location=0")[0][0]
        check("no gil charged with a full bag", gil == 1000, gil)
    def done(self):
        q(f"update char_storage set inventory={self.cap} where charid={CHAR}")

class ChococardMale(Chococard):
    # male bird: item 2339 (exdata bytes for a male card have no capture yet, so only the item/charge are asserted)
    def seed(self):
        super().seed(); q(f"update char_chocobos set sex=0 where charid={CHAR}")
    def run(self, b):
        b.tool("event_update", option=239); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(2)
        rows = q(f"select itemid, extra from char_inventory where charid={CHAR} and itemid in (2339,2342)")
        check("male bird gets chococard 2339", [r[0] for r in rows] == [2339], rows and [r[0] for r in rows])
        if rows: print("INFO male card exdata", bytes(rows[0][1]).hex(" ").upper())
        gil = q(f"select quantity from char_inventory where charid={CHAR} and itemid=65535 and location=0")[0][0]
        check("300 gil charged", gil == 700, gil)
        q(f"delete from char_inventory where charid={CHAR} and itemid=2339")

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

class Naming:
    # option 0xFF: first index bits 8-17, last index bits 18-27 into the fixed name table (6='II', 7='IV', 30 chars max)
    def seed(self):
        seed(4, 30); q(f"update char_chocobos set first_name='Chocobo', last_name='Chocobo', created=created where charid={CHAR}")
    def run(self, b):
        b.tool("event_update", option=0xFF | (6 << 8) | (7 << 18)); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        n = q(f"select first_name, last_name from char_chocobos where charid={CHAR}")[0]
        check("name II IV saved", tuple(n) == ("II", "IV"), n)
        b.tool("event_update", option=0xFF | (9999 << 8) | (7 << 18)); time.sleep(1)
        n = q(f"select first_name, last_name from char_chocobos where charid={CHAR}")[0]
        check("unknown index rejected", tuple(n) == ("II", "IV"), n)

class ForcedName:
    # an unnamed chocobo that grows past adult 2 is named by the trainer: random 5-8 letter first name, empty last name
    def seed(self):
        seed(1, 66); q(f"update char_chocobos set stage=5, last_update_age=61, created=created where charid={CHAR}"); q(f"update char_chocobos set first_name='Chocobo', last_name='Chocobo', created=created where charid={CHAR}")
    def run(self, b):
        for opt in (504, 246) * 20:   # record count varies with the random care days, so stop once the trainer has named it
            b.tool("event_update", option=opt); time.sleep(0.7)
            if opt == 246 and q(f"select first_name from char_chocobos where charid={CHAR}")[0][0] != "Chocobo": break
        b.tool("event_select", selection=0); time.sleep(3)
        f, l = q(f"select first_name, last_name from char_chocobos where charid={CHAR}")[0]
        check("trainer picked a first name", f != "Chocobo" and 5 <= len(f) <= 8 and l == "", (f, l, q(f"select stage,last_update_age,created from char_chocobos where charid={CHAR}")))

class Walk:
    # options 10994/11250/11506 (cmd 242, arg 42/43/44): energy drops by the captured cost, walk refused when short of energy
    COSTS = {10994: (23, 30), 11250: (31, 40), 11506: (38, 48)}
    def seed(self): seed(4, 30); q(f"update char_chocobos set energy=100, held_item=0 where charid={CHAR}")
    def run(self, b):
        for opt, (lo, hi) in self.COSTS.items():
            q(f"update char_chocobos set energy=100, held_item=0 where charid={CHAR}")
            b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
            r = b.tool("event_update", option=opt); time.sleep(1)
            b.tool("event_select", selection=0); time.sleep(2)
            e = q(f"select energy from char_chocobos where charid={CHAR}")[0][0]
            check(f"walk {opt} cost {lo}-{hi}", lo <= 100 - e <= hi, f"energy={e} reply={r}")
        q(f"update char_chocobos set energy=10 where charid={CHAR}")
        b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
        b.tool("event_update", option=10994); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        e = q(f"select energy from char_chocobos where charid={CHAR}")[0][0]
        check("walk refused when short of energy", e == 10, e)

class Watch:
    # option 12530 (cmd 242 arg 48): costs 3-4 energy, hands over the held item (pebble 17296) and clears it
    def seed(self):
        seed(4, 30); q(f"update char_chocobos set energy=100, held_item=17296 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid=17296")
    def run(self, b):
        b.tool("event_update", option=12530); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        e, h = q(f"select energy, held_item from char_chocobos where charid={CHAR}")[0]
        n = q(f"select coalesce(sum(quantity),0) from char_inventory where charid={CHAR} and itemid=17296")[0][0]
        check("watch over cost 3-4", 96 <= e <= 97, e)
        check("held item cleared", h == 0, h)
        check("item handed over", n == 1, n)

class Chick:
    # short walks (cmd 242 arg 42) until a lost chick turns up (var owner/location), then guessing Cahaurme (San d'Oria owner 2, option 1)
    VAR = "ChocoboRaisingLostChick"
    def getvar(self):
        r = q(f"select value from char_vars where charid={CHAR} and varname='{self.VAR}'")
        return r[0][0] if r else 0
    def seed(self):
        seed(4, 30); q(f"delete from char_vars where charid={CHAR} and varname='{self.VAR}'")
        q(f"update char_chocobos set walk_progress=0 where charid={CHAR}")
    def run(self, b):
        found = 0
        for i in range(25):
            q(f"update char_chocobos set energy=100, held_item=0 where charid={CHAR}")
            b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
            b.tool("event_update", option=10994); time.sleep(1)
            b.tool("event_select", selection=0); time.sleep(2)
            v = self.getvar()
            if v & 0xF:
                found = v; break
        check("lost chick found on a short walk", found != 0, f"tries={i + 1} var={found}")
        check("chick owner/location valid", (found & 0xF) in range(1, 9) and (found >> 6) & 3 == LOC, hex(found))
        # guessing needs a San d'Oria chick: force owner 2 (Cahaurme), location 1
        if LOC == 1:
            for owner, expect in ((2, 1), (3, 2)):
                q(f"replace into char_vars (charid,varname,value) values ({CHAR},'{self.VAR}',{owner | (1 << 4) | (1 << 6)})")
                b.tool("event_update", option=250); time.sleep(2); b.gm("!pos 55.7 -8.6 -27 230", settle=6); time.sleep(2)
                r = b.tool("talk_to_npc", npcId=17719300)
                check(f"owner event starts (chick owner {owner})", r.get("started") is True, r)
                time.sleep(1); b.tool("event_update", option=1); time.sleep(1)
                b.tool("event_select", selection=0); time.sleep(2)
                v = self.getvar()
                check(f"guess result {'returned' if expect == 1 else 'wrong owner'}", (v >> 16) & 3 == expect, hex(v))
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='{self.VAR}'")

class ChickGuess:
    # no trainer talk: Cahaurme (San d'Oria owner 2, guess option 1) with a seeded chick; GUESS_OWNER=2 right, 3 wrong
    notrainer = True; pos = "!pos 55.7 -8.6 -27 230"
    OWNER = int(os.environ.get("GUESS_OWNER", "2")); VAR = "ChocoboRaisingLostChick"
    def seed(self):
        seed(4, 30)
        q(f"update chars set pos_zone=230 where charid={CHAR}")
        q(f"replace into char_vars (charid,varname,value) values ({CHAR},'{self.VAR}',{self.OWNER | (1 << 4) | (1 << 6)})")
    def run(self, b):
        r = b.tool("talk_to_npc", npcId=17719300)
        check("owner event starts", r.get("started") is True, r)
        time.sleep(1); b.tool("event_update", option=1); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        v = q(f"select value from char_vars where charid={CHAR} and varname='{self.VAR}'")[0][0]
        expect = 1 if self.OWNER == 2 else 2
        check("guess result", (v >> 16) & 3 == expect, hex(v))
        check("solved bit only when right", ((v >> 18) & 1) == (1 if expect == 1 else 0), hex(v))
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='{self.VAR}'")

class ChickReport:
    # trainer report (Hantileon, csid 852) once a search has ended: opens with the report event, finishing clears the result bits
    VAR = "ChocoboRaisingLostChick"
    def seed(self):
        seed(4, 30); q(f"replace into char_vars (charid,varname,value) values ({CHAR},'{self.VAR}',{1 << 16})")
    def run(self, b):
        r = b.tool("event_trace"); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        v = q(f"select value from char_vars where charid={CHAR} and varname='{self.VAR}'")
        check("report event 852 shown and result cleared", TRAINER == "hantileon" and (not v or (v[0][0] >> 16) & 3 == 0), v)
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='{self.VAR}'")

class ChickClerk:
    # stable clerks (CLERK=sandoria|bastok|windurst): the review event opens, with a clue seeded
    notrainer = True
    CL = {"sandoria": (230, 17719599, 846, "!pos -13.2 1.4 -91 230", 1),
          "bastok": (234, 17735846, 534, "!pos 27.7 0.87 -102 234", 2),
          "windurst": (241, 17764441, 761, "!pos 127.7 -5.25 -119 241", 3)}
    ZN, NPCID, CSID, pos, LC = CL[os.environ.get("CLERK", "sandoria")]
    def seed(self):
        seed(4, 30); q(f"update chars set pos_zone={self.ZN} where charid={CHAR}")
        q(f"replace into char_vars (charid,varname,value) values ({CHAR},'ChocoboRaisingLostChick',{2 | (1 << 4) | (self.LC << 6) | (1 << 8 + 4)})")
    def run(self, b):
        r = b.tool("talk_to_npc", npcId=self.NPCID)
        check(f"clerk event {self.CSID} starts", r.get("started") is True and r.get("eventId") == self.CSID, r)
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='ChocoboRaisingLostChick'")

class Story:
    # care action 50 (option 13042) then story 4 (option 1074, impatient -> gallop). LSB-guess numbers: needs discernment 64, 25% learn.
    def seed(self):
        seed(4, 30); q(f"update char_chocobos set energy=100, discernment=10, ability1=0, ability2=0 where charid={CHAR}")
    def tell(self, b):
        b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
        b.tool("event_update", option=13042); time.sleep(1)
        b.tool("event_update", option=1074); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        return q(f"select energy, discernment, ability1 from char_chocobos where charid={CHAR}")[0]
    def run(self, b):
        b.gm("!addkeyitem 837", settle=3)
        e, d, a = self.tell(b)
        check("story costs 11-14 energy", 86 <= e <= 89 or e > 89, (e, d, a))  # a refund can follow a lucky learn
        check("discernment +1 per telling, no ability below 64", d == 11 and a == 0, (e, d, a))
        q(f"update char_chocobos set discernment=200 where charid={CHAR}")
        for i in range(40):
            q(f"update char_chocobos set energy=100 where charid={CHAR}")
            b.gm("!addkeyitem 837", settle=2)
            e, d, a = self.tell(b)
            if a == 1: break
        check("gallop learned within 40 tellings (25% each)", a == 1, f"tries={i + 1} discernment={d}")
    def done(self):
        q(f"update char_chocobos set discernment=10, ability1=0, ability2=0 where charid={CHAR}")

class Whistle:
    # Chocobo Whistle quest (Hantileon only: San d'Oria raiser, so the quest starts at SEARCH). Growth to adult 1 starts it,
    # walks search (command 88, arg = walk length), the wrong length answers "not here", the right one gives the Handkerchief,
    # Hantileon scene 830 + option 222 hands over the whistle (item 15533). All reply shapes are LSB, no capture.
    VARS = ("ChocoboWhistleProg", "ChocoboWhistleHidingWalk")
    def seed(self):
        seed(3, 30); q(f"update char_chocobos set energy=100, held_item=0, created=created where charid={CHAR}")   # adolescent, old enough to grow up
        q(f"delete from char_vars where charid={CHAR} and varname in ('ChocoboWhistleProg','ChocoboWhistleHidingWalk')")
        q(f"delete from char_inventory where charid={CHAR} and itemid=15533")
    def prog(self):
        r = q(f"select value from char_vars where charid={CHAR} and varname='ChocoboWhistleProg'")
        return r[0][0] if r else 0
    def walk(self, b, opt, search):
        q(f"update char_chocobos set energy=100, created=created where charid={CHAR}")
        b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
        b.tool("event_update", option=opt); time.sleep(1)
        if search is not None:
            b.tool("event_update", option=88 + 256 * search); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
    def run(self, b):
        check("growth to adult 1 starts the quest at SEARCH (2)", self.prog() == 2, (self.prog(), q(f"select stage,last_update_age,unix_timestamp()-unix_timestamp(created) from char_chocobos where charid={CHAR}")))
        q(f"insert into char_vars (charid,varname,value) values ({CHAR},'ChocoboWhistleHidingWalk',1) on duplicate key update value=1")
        self.walk(b, 11506, 3)   # long walk, handkerchief hides on the short one
        check("wrong walk length finds nothing", self.prog() == 2 and not b.tool("key_items", id=809).get("owned", False), self.prog())
        self.walk(b, 10994, 1)   # short walk
        check("right walk length finds the Handkerchief (FOUND 3)", self.prog() == 3, self.prog())
        check("Handkerchief key item 809 held", b.tool("key_items", id=809).get("owned") is True, b.tool("key_items", id=809))
        r = b.tool("talk_to_npc", npcId=NPC)
        check("Hantileon starts scene 830", r.get("eventId") == 830, r); time.sleep(2)
        b.tool("event_select", selection=222); time.sleep(3)
        n = q(f"select coalesce(sum(quantity),0) from char_inventory where charid={CHAR} and itemid=15533")[0][0]
        check("quest DONE (4) and whistle handed over", self.prog() == 4 and n == 1, (self.prog(), n))
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname in ('ChocoboWhistleProg','ChocoboWhistleHidingWalk')")
        q(f"delete from char_inventory where charid={CHAR} and itemid=15533")

def give(itemid, extra=None):
    """Insert an inventory item (before login: the server reads inventory at login) with optional exdata bytes."""
    slot = q(f"select coalesce(max(slot),0)+1 from char_inventory where charid={CHAR} and location=0")[0][0]
    c = db.cursor()
    c.execute("insert into char_inventory (charid,location,slot,itemid,quantity,bazaar,signature,extra) values (%s,0,%s,%s,1,0,'',%s)",
              (CHAR, slot, itemid, bytes(extra) if extra else bytes(24)))

BREED_VARS = "('ChocoBreedEggItem','ChocoBreedEggGenes','ChocoBreedEggReady')"
FINBARR = 17776821

def card(sire, dna, ability=0, rcp=0):
    word = dna[0] + dna[1] * 8 + dna[2] * 64 + ability * 512
    return [10, 10, 10, rcp] + list(word.to_bytes(4, "little")) + [0] * 16

PLAN = int(os.environ.get("PLAN", "1")); FULLBAG = os.environ.get("FULLBAG") == "1"
EGG = {1: 2319, 2: 2318, 3: 2318, 4: 2317}[PLAN]

class BreedTicket:
    # Finbarr event 10108 menu: option 1 (Gourmet) buys the 3500 gil ticket with plan byte 1 and signature "PlanA". LSB-only.
    notrainer = True; pos = "!pos -50 8.2 98 244"
    def seed(self):
        seed(4, 30); q(f"update chars set pos_zone=244 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2344,2339,2342,2317,2318,2319)")
        q(f"delete from char_vars where charid={CHAR} and varname in {BREED_VARS}")
        q(f"update char_inventory set quantity=5000 where charid={CHAR} and itemid=65535 and location=0")
    def run(self, b):
        r = b.tool("talk_to_npc", npcId=FINBARR)
        check("Finbarr starts menu event 10108", r.get("eventId") == 10108, r); time.sleep(2)
        b.tool("event_select", selection=PLAN); time.sleep(3)
        ex = q(f"select extra from char_inventory where charid={CHAR} and itemid=2344")
        got = bytes(ex[0][0]).hex(" ").upper() if ex else ""
        check(f"ticket 2344 with plan {PLAN} and an encoded signature", bool(ex) and bytes(ex[0][0])[0] == PLAN and any(bytes(ex[0][0])[12:24]), got)  # signature is the encoded name, not ASCII
        gil = q(f"select quantity from char_inventory where charid={CHAR} and itemid=65535 and location=0")[0][0]
        check("3500 gil charged", gil == 1500, gil)
    def done(self):
        q(f"delete from char_inventory where charid={CHAR} and itemid=2344")

class BreedDate:
    # trade ticket + both cards: the date plays (10102), the egg is laid for the next JST midnight; once due, Finbarr hands over a bred egg
    notrainer = True; pos = "!pos -50 8.2 98 244"
    def seed(self):
        seed(4, 30); q(f"update chars set pos_zone=244 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2344,2339,2342,2317,2318,2319)")
        q(f"delete from char_vars where charid={CHAR} and varname in {BREED_VARS}")
        give(2344, [PLAN] + [0] * 11 + list(b"Plan" + bytes([64 + PLAN])) + [0] * 7)
        give(2339, card([1, 1, 1], [1, 1, 1], 5, 64)); give(2342, card([1, 1, 1], [1, 1, 1], 5, 64))
    def v(self, n):
        r = q(f"select value from char_vars where charid={CHAR} and varname='{n}'"); return r[0][0] if r else 0
    def run(self, b):
        r = b.tool("trade_npc", npcId=FINBARR, items=[{"itemId": 2344, "qty": 1}, {"itemId": 2339, "qty": 1}, {"itemId": 2342, "qty": 1}]); time.sleep(2)
        check("trade accepted", r.get("ok") is True, r)
        b.tool("event_select", selection=0); time.sleep(3)
        check(f"egg pending: plan {PLAN} lays item {EGG}", self.v("ChocoBreedEggItem") == EGG, self.v("ChocoBreedEggItem"))
        check("ticket and cards consumed", q(f"select count(*) from char_inventory where charid={CHAR} and itemid in (2344,2339,2342)")[0][0] == 0)
        # parents are all dna 1 (plan 2 = Sports): offspring genes are 1 unless a 5% mutation hit
        g = self.v("ChocoBreedEggGenes")
        check(f"gene word has plan {PLAN - 1} in bits 14-15", (g >> 14) & 3 == PLAN - 1, hex(g))
        r = b.tool("talk_to_npc", npcId=FINBARR)
        check("before midnight Finbarr says wait (10105)", r.get("eventId") == 10105, r); time.sleep(2); b.tool("event_select", selection=0); time.sleep(1)
        q(f"update char_vars set value=1 where charid={CHAR} and varname='ChocoBreedEggReady'")
        r = b.tool("talk_to_npc", npcId=FINBARR)
        check("when due Finbarr lays the egg (10107)", r.get("eventId") == 10107, r); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(3)
        ex = q(f"select extra from char_inventory where charid={CHAR} and itemid={EGG}")
        check(f"bred egg {EGG} received with IsBred bit", bool(ex) and ex[0][0][3] & 0x80 == 0x80, ex)
        check("pending egg cleared", self.v("ChocoBreedEggItem") == 0)
    def done(self):
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2344,2339,2342,2317,2318,2319,16448)")
        q(f"delete from char_vars where charid={CHAR} and varname in {BREED_VARS}")

class BreedFullBag:
    # a bred egg is due but the bag is full: Finbarr must not lose it (egg stays pending, nothing added)
    notrainer = True; pos = "!pos -50 8.2 98 244"
    def seed(self):
        seed(4, 30); q(f"update chars set pos_zone=244 where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2344,2339,2342,2317,2318,2319,16448)")
        q(f"delete from char_vars where charid={CHAR} and varname in {BREED_VARS}")
        cap = q(f"select inventory from char_storage where charid={CHAR}")[0][0]
        used = q(f"select count(*) from char_inventory where charid={CHAR} and location=0 and itemid<>65535")[0][0]
        for _ in range(cap - used): give(16448)
        for n, v in (("ChocoBreedEggItem", 2319), ("ChocoBreedEggGenes", 0xa49), ("ChocoBreedEggReady", 1)):
            q(f"replace into char_vars (charid,varname,value) values ({CHAR},'{n}',{v})")
    def run(self, b):
        r = b.tool("talk_to_npc", npcId=FINBARR); time.sleep(2)
        b.tool("event_select", selection=0); time.sleep(3)
        pend = q(f"select value from char_vars where charid={CHAR} and varname='ChocoBreedEggItem'")
        check("full bag: egg stays pending", bool(pend) and pend[0][0] == 2319, pend)
        check("full bag: no egg added", not q(f"select 1 from char_inventory where charid={CHAR} and itemid=2319"))
    def done(self):
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2319,16448)")
        q(f"delete from char_vars where charid={CHAR} and varname in {BREED_VARS}")

class BreedHatch:
    notrainer = True
    # a bred egg (dna 2,2,2, ability 5, Gourmet) handed to the trainer: the chocobo keeps the genes and ability, strength gets the +8 plan seed
    def seed(self):
        q(f"delete from char_chocobos where charid={CHAR}")
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2319)")
        give(2319, list((2 + 16 + 128 + 5 * 512 + (1 << 31)).to_bytes(4, "little")) + [0] * 20)
        q(f"update chars set pos_zone={ZONE},pos_x=129,pos_y=-6.35,pos_z=-117 where charid={CHAR}")
    def run(self, b):
        r = b.tool("trade_npc", npcId=NPC, items=[{"itemId": 2319, "qty": 1}]); time.sleep(2)
        b.tool("event_select", selection=252); time.sleep(3)
        row = q(f"select allele1,allele2,allele3,ability1,strength from char_chocobos where charid={CHAR}")
        check("bred genes, ability and +8 strength kept", bool(row) and row[0] == (2, 2, 2, 5, 8), row)
    def done(self):
        q(f"delete from char_chocobos where charid={CHAR}")

class Compete:
    # care action 52 (option 13554): refused until the rivals are met, 27-34 energy, wins counted in walk_progress bits 12-13, key item 841 on the third win (50% chance is an LSB guess)
    def seed(self):
        seed(4, 30); q(f"update char_chocobos set energy=100, affection=10, walk_progress=0, created=created where charid={CHAR}")
    def go(self, b):
        b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
        b.tool("event_update", option=13554); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        return q(f"select energy, affection, walk_progress from char_chocobos where charid={CHAR}")[0]
    def run(self, b):
        e, a, w = self.go(b)
        check("compete refused before the rivals are met", e >= 95 and (w >> 12) & 3 == 0, (e, a, w))  # the talk can roll a day over (small energy/affection drift)
        q(f"update char_chocobos set walk_progress=256, energy=100, created=created where charid={CHAR}")
        e, a, w = self.go(b)
        check("compete costs 27-34 energy and adds affection", 64 <= e <= 73 and a >= 1, (e, a, w))
        q(f"update char_chocobos set energy=10, created=created where charid={CHAR}")
        e, a, w = self.go(b)
        check("compete refused when short of energy", e == 10, (e, a, w))
        for i in range(30):
            q(f"update char_chocobos set energy=100, created=created where charid={CHAR}")
            e, a, w = self.go(b)
            if (w >> 12) & 3 == 3: break
        check("three wins reached within 30 tries", (w >> 12) & 3 == 3, (i + 1, w))
        check("rivals meeting count kept", (w >> 8) & 3 == 1, w)
        k = b.tool("key_items", id=841)
        check("third win teaches the happy story (841)", k.get("owned") is True, k)
    def done(self):
        q(f"update char_chocobos set walk_progress=0, affection=10, created=created where charid={CHAR}")

class Dietmund:
    # long walk (option 11506) meets Dietmund once after Save My Son is complete; sets ChocoboMetDietmund and never again
    def seed(self):
        seed(5, 60); q(f"update char_chocobos set receptivity=255, walk_progress=0, created=created where charid={CHAR}")
        q(f"delete from char_vars where charid={CHAR} and varname='ChocoboMetDietmund'")
    def walk(self, b):
        q(f"update char_chocobos set energy=100, held_item=0, created=created where charid={CHAR}")
        b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
        b.tool("event_update", option=11506); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(2)
        return q(f"select value from char_vars where charid={CHAR} and varname='ChocoboMetDietmund'")
    def run(self, b):
        for i in range(12):
            if self.walk(b): break
        check("not met before Save My Son is complete", not self.walk(b))
        b.gm("!completequest jeuno save_my_son", settle=3)
        for i in range(40):
            met = self.walk(b)
            if met: break
        check("Dietmund met on a long walk after the quest", bool(met), i + 1)
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='ChocoboMetDietmund'")

class GmCommand:
    # !chocobo GM command: field/meeting/wins/condition setters, age shift (created moves back N days), var set
    notrainer = True
    def seed(self):
        seed(5, 60); q(f"update char_chocobos set walk_progress=0,conditions=0,created=created where charid={CHAR}")
    def run(self, b):
        g = lambda c: b.gm(c, settle=3)
        row = lambda: q(f"select stage,energy,walk_progress,conditions,unix_timestamp(created) from char_chocobos where charid={CHAR}")[0]
        t0 = row()[4]
        g("!chocobo info")
        g("!chocobo set energy 42"); check("set energy", row()[1] == 42, row())
        g("!chocobo meet 5 1"); check("meet rivals 1", (row()[2] // 4**4) % 4 == 1, row())
        g("!chocobo wins 2"); check("wins 2", (row()[2] >> 12) % 4 == 2, row())
        g("!chocobo cond 3 1"); check("cond bit 3 set", row()[3] & 8 == 8, row())
        g("!chocobo cond 3 0"); check("cond bit 3 cleared", row()[3] & 8 == 0, row())
        g("!chocobo age 2"); check("age shifts birthday back 2 days", abs((t0 - row()[4]) - 2 * 86400) < 5, row())
        g("!chocobo var dietmund 1"); check("var set", q(f"select value from char_vars where charid={CHAR} and varname='ChocoboMetDietmund'")[0][0] == 1)
    def done(self):
        q(f"delete from char_vars where charid={CHAR} and varname='ChocoboMetDietmund'")

class CareMenu:
    # NEEDS a temporary line in CR.handleCareMenu: player:setVar('ChocoboCareMaskDbg', mask) (the harness cannot see 0x05C replies); not in the committed Lua
    # option 243 answers the care menu mask (captured masks): chick 0x7FFFFFEA, adolescent 0x7FFFFFC8 (C0 with rivals met), adult 0x7FFFFF88 (80 with rivals met)
    CASES = [(2, 0, 0x7FFFFFEA), (3, 0, 0x7FFFFFC8), (3, 256, 0x7FFFFFC0), (4, 0, 0x7FFFFF88), (4, 256, 0x7FFFFF80)]
    def seed(self): seed(4, 30)
    def run(self, b):
        for stage, wp, want in self.CASES:
            q(f"update char_chocobos set stage={stage}, walk_progress={wp}, energy=100, conditions=0, created=created where charid={CHAR}")
            b.tool("talk_to_npc", npcId=NPC); time.sleep(2)
            b.tool("event_trace", clear=True)
            r = b.tool("event_update", option=243); time.sleep(1)
            got = (q(f"select value from char_vars where charid={CHAR} and varname='ChocoboCareMaskDbg'") or [(None,)])[0][0]
            b.tool("event_select", selection=0); time.sleep(2)
            check(f"stage {stage} rivals {wp} mask {want:#x}", got == want, got)
    def done(self):
        q(f"update char_chocobos set walk_progress=0, created=created where charid={CHAR}")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "retirement"
    sc = Day(int(sys.argv[2]) if len(sys.argv) > 2 else 6) if name == "day_report" else Chococard() if name == "chococard" else {"chococard_broke": ChococardBroke, "chococard_fullbag": ChococardFullBag, "chococard_male": ChococardMale, "feed": Feed, "menu": Menu, "careplan": CarePlan, "walk": Walk, "chick": Chick, "chick_report": ChickReport, "chick_clerk": ChickClerk, "chick_guess": ChickGuess, "watch": Watch, "story": Story, "whistle": Whistle, "breed_ticket": BreedTicket, "breed_date": BreedDate, "breed_fullbag": BreedFullBag, "breed_hatch": BreedHatch, "compete": Compete, "dietmund": Dietmund, "care_menu": CareMenu, "gm": GmCommand, "naming": Naming, "forced_name": ForcedName}.get(name, Retirement)() if name != "retirement" else Retirement()
    session(sc)
    print("RESULT", "FAIL" if failures else "PASS", failures)
    sys.exit(1 if failures else 0)
