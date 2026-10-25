"""Live headless scenarios for the DSP Chocobo Raising port (branch feature/chocobo-raising-core).

Not collected by pytest (needs running DSConnect/DSSearch/DSGame servers, the XiHeadless MCP client and
a leased pool character). Run:  py -3 run_live.py day_report [days] | retirement
Env: XI_PROTO=dsp XI_HOST=127.0.0.1 XI_CLIENTVER=30170905_5 DOTNET_EnableWriteXorExecute=0 XIBOT_NAVMESH_DIR=...
Exit code 0 = every assertion passed. Evidence per slice: docs/slices/chocobo-raising-core/TEST_PLAN.md (DSP repo).
"""
import os, re, sys, time

HEADLESS = os.environ.get("XIHEADLESS_DIR", "D:/Claude/FFXI-Tools/headless-research/xiheadless-dsp-chocobo")
DSP = os.environ.get("DSP_RUN_TREE", "D:/Claude/dsp-branches")
CHAR, ACCOUNT = 21831, "xitest03"
PULONONO, POS = 17764419, "!pos 129 -5.35 -117 241"   # Windurst Woods trainer, csid set {741,742,745,748}
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
          f"weather_preference,hunger,care_plan,held_item) values ({CHAR},'Test','Bird',0,1,{stage},3,0,10,10,10,10,10,100,50,0,0,0,0,0,255,0,0)")
    q(f"update char_chocobos set stage={stage},last_update_age=1,hunger=255,energy=100,conditions=0,locked_plan=0,"
      f"location=3,created=now()-interval ({days}*86400-100) second where charid={CHAR}")
    q(f"update chars set pos_zone=241,pos_prevzone=240,pos_rot=0,pos_x=129,pos_y=-6.35,pos_z=-117 where charid={CHAR}")

def session(scenario):
    pool = Pool(8); a = pool.acquire(only=ACCOUNT); crashed = True; b = None
    try:
        scenario_seed = scenario.seed
        scenario_seed()
        b = McpBot(a[0], a[1], a[2], tag="live"); b.start(); time.sleep(3)
        b.gm(POS, settle=8); b.tool("event_trace", clear=True); time.sleep(4)
        r = b.tool("talk_to_npc", npcId=PULONONO)
        check("trainer event starts", r.get("started") is True, r)
        time.sleep(2); b.tool("event_trace", clear=True)
        scenario.run(b)
    finally:
        try: b.close(); crashed = b.p.returncode != 0
        except Exception: pass
        pool.release(a, crashed)

class Day:
    def __init__(self, days=6): self.days = days
    def seed(self): seed(1, self.days)
    def run(self, b):
        for opt in (248, 504, 246, 246):
            b.tool("event_update", option=opt); time.sleep(0.7)
        b.tool("event_select", selection=0); time.sleep(3)
        stage = q(f"select stage from char_chocobos where charid={CHAR}")[0][0]
        want = 2 if self.days < 30 else 4
        check(f"{self.days} days -> stage {want}", stage == want, f"stage={stage}")

class Retirement:
    # retiring deletes the row, so keep a copy and put it back afterwards (scenarios stay order-independent)
    def seed(self):
        c = db.cursor(dictionary=True); c.execute(f"select * from char_chocobos where charid={CHAR}")
        self.row = c.fetchone(); seed(4, 3); q(f"delete from char_vars where charid={CHAR} and varname='ChocoRetireItems'")
    def run(self, b):
        for opt in (24672, 244, 40):          # command 96, 244, 40 (San d'Oria capture sequence)
            b.tool("event_update", option=opt); time.sleep(1)
        b.tool("event_select", selection=0); time.sleep(3)
        items = {r[0] for r in q(f"select itemid from char_inventory where charid={CHAR} and itemid in (2313,309,310,311,312,313)")}
        check("VCS card 2313 received", 2313 in items, items)
        check("yellow plaque 309 received", 309 in items, items)
        check("chocobo row deleted", q(f"select count(*) from char_chocobos where charid={CHAR}")[0][0] == 0)
        q(f"delete from char_inventory where charid={CHAR} and itemid in (2313,309,310,311,312,313)")
        if self.row:
            cols = ",".join(self.row); vals = ",".join("%s" for _ in self.row)
            c = db.cursor(); c.execute(f"insert into char_chocobos ({cols}) values ({vals})", list(self.row.values()))

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "retirement"
    sc = Day(int(sys.argv[2]) if len(sys.argv) > 2 else 6) if name == "day_report" else Retirement()
    session(sc)
    print("RESULT", "FAIL" if failures else "PASS", failures)
    sys.exit(1 if failures else 0)
