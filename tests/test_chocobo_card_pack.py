"""Offline check: DSP chocobo_raising_day.lua packCard() reproduces the 24 card bytes of the San d'Oria retire
capture (Raguza 2021-12-04, 0x020 packet for item 2313). Needs lupa and the DSP worktree; skipped otherwise."""
import os, pathlib, pytest
lupa = pytest.importorskip("lupa")
SRC = pathlib.Path(os.environ.get("DSP_CHOCOBO_LUA", "dsp-checkout/scripts/globals/chocobo_raising_day.lua"))
pytestmark = pytest.mark.skipif(not SRC.exists(), reason="DSP chocobo script not available")

CAPTURE = "38 30 08 0B 88 00 08 11 00 00 00 00 4F 6B 77 2F 9A 25 9E 90 00 00 00 00"
BIT = """bit={}
function bit.band(a,b) local r,m=0,1 a=a%4294967296 b=b%4294967296 while a>0 and b>0 do if a%2==1 and b%2==1 then r=r+m end a=(a-a%2)/2 b=(b-b%2)/2 m=m*2 end return r end
function bit.rshift(a,n) return math.floor((a%4294967296)/2^n) end"""

def _pack(saved_lua, race):
    L = lupa.LuaRuntime(unpack_returned_tuples=True); L.execute(BIT)
    src = SRC.read_text(encoding="latin-1")
    L.execute("CR={}\n" + src[src.index("local APPEARANCE_TALONS"):src.index("local OWED_VAR")] +
              "\nfunction pack(s,r) local t=CR.packCard(s,r) local o={} for k=1,#t do o[k]=string.format('%02X',t[k]) end return table.concat(o,' ') end")
    return L.eval("pack")(L.eval(saved_lua), race)

SAVED = ("{strength=56,endurance=48,discernment=8,receptivity=11,allele1=0,allele2=1,allele3=2,ability1=0,ability2=0,"
         "personality=4,weather_preference=0,sex=1,color=0,appearance=0,first_name='EirSkd',last_name='O8T18'}")

def test_card_matches_capture():
    assert _pack(SAVED, 1) == CAPTURE

def test_galka_size_is_zero():
    assert _pack(SAVED, 8).split()[7] == "01"   # size 0 -> top nibble 0, gender bit 24 still set

def test_unnamed_uses_chocobo():
    assert _pack(SAVED.replace("'EirSkd'", "'Chocobo'").replace("'O8T18'", "'Chocobo'"), 1)[36:41] != CAPTURE[36:41]
