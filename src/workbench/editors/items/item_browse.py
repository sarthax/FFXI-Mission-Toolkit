"""Fast, SQL-only item browsing for the Item Browser page.

Unlike item_edit.search() this never reads the client DAT per row, so it can page through the whole
table. Names for AH categories, jobs, slots and flags come from the editor's own enum tables; weapon
skill names are the SKILLTYPE enum in the server's src/map/entities/battleentity.h.
"""
from workbench.editors.items._db_alias import item_db
from workbench.editors.items import _dat_tools_impl as dat
from workbench.editors.items import item_reference

WEAPON_SKILLS = {
    1: "Hand-to-Hand", 2: "Dagger", 3: "Sword", 4: "Great Sword", 5: "Axe", 6: "Great Axe", 7: "Scythe",
    8: "Polearm", 9: "Katana", 10: "Great Katana", 11: "Club", 12: "Staff", 25: "Archery",
    26: "Marksmanship", 27: "Throwing", 41: "String Instrument", 42: "Wind Instrument",
}
TYPES = ("weapon", "armor", "consumable", "puppet", "furnishing", "general")
SORTS = {"name": "b.name", "id": "b.itemid", "level": "e.level", "dmg": "w.dmg", "delay": "w.delay", "ah": "b.aH"}
_TYPE_SQL = ("case when w.itemId is not null then 'weapon' when e.itemId is not null then 'armor' "
             "when u.itemid is not null then 'consumable' when p.itemid is not null then 'puppet' "
             "when f.itemid is not null then 'furnishing' else 'general' end")
_JOIN = """from item_basic b
    left join item_equipment e on e.itemId=b.itemid
    left join item_weapon w on w.itemId=b.itemid
    left join item_usable u on u.itemid=b.itemid
    left join item_puppet p on p.itemid=b.itemid
    left join item_furnishing f on f.itemid=b.itemid"""


def facets():
    """Option lists for the filter controls, plus per-AH-category item counts."""
    db = item_db(); cu = db.cursor()
    cu.execute("select aH, count(*) from item_basic group by aH")
    counts = {int(a): int(n) for a, n in cu.fetchall() if a is not None}
    db.close()
    return {
        "types": list(TYPES),
        "ah": [{"value": k, "label": v, "count": counts.get(k, 0)} for k, v in sorted(dat.AH_CATEGORY.items())],
        "jobs": [{"value": i, "label": j} for i, j in enumerate(dat.JOBS)],
        "slots": [{"value": i, "label": s} for i, s in enumerate(dat.SLOTS)],
        "skills": [{"value": k, "label": v} for k, v in sorted(WEAPON_SKILLS.items())],
    }


def _like(q):
    q = q.strip().replace("\\", "\\\\").replace("%", "\\%")
    return "%" + q.replace(" ", "_") + "%"


def browse(q="", type_="", ah=-1, job=-1, slot=-1, skill=-1, min_level=-1, max_level=-1,
           rare=False, ex=False, mod=-1, sort="name", desc=False, limit=60, offset=0, ref="", ref_con=None):
    """Page of items matching every given filter, plus the total match count.

    ref: "", matched, drift, ours_only or external_only (needs ref_con, a sqlite connection to the
    toolkit database holding items_external). Every row also gets ref_status when ref_con is given."""
    limit = max(1, min(int(limit), 200)); offset = max(0, int(offset))
    where, params = [], []
    q = (q or "").strip()
    if q:
        if q.isdigit():
            where.append("(b.itemid = %s or b.name like %s)"); params += [int(q), _like(q)]
        else:
            where.append("(b.name like %s or b.sortname like %s)"); params += [_like(q), _like(q)]
    if type_ in TYPES:
        where.append(_TYPE_SQL + " = %s"); params.append(type_)
    if int(ah) >= 0:
        where.append("b.aH = %s"); params.append(int(ah))
    if int(job) >= 0:
        where.append("(e.jobs & %s) <> 0"); params.append(1 << int(job))
    if int(slot) >= 0:
        where.append("(e.slot & %s) <> 0"); params.append(1 << int(slot))
    if int(skill) >= 0:
        where.append("w.skill = %s"); params.append(int(skill))
    if int(min_level) >= 0:
        where.append("e.level >= %s"); params.append(int(min_level))
    if int(max_level) >= 0:
        where.append("e.level <= %s"); params.append(int(max_level))
    if rare:
        where.append("(b.flags & 32768) <> 0")
    if ex:
        where.append("(b.flags & 16384) <> 0")
    if int(mod) >= 0:
        where.append("exists (select 1 from item_mods m where m.itemId=b.itemid and m.modId=%s)"); params.append(int(mod))
    wsql = (" where " + " and ".join(where)) if where else ""
    order = SORTS.get(sort, "b.name") + (" desc" if desc else " asc") + ", b.itemid asc"
    db = item_db(); cu = db.cursor()
    if ref == "external_only" and ref_con is not None:
        cu.execute("select b.name from item_basic b"); names = [r[0] for r in cu.fetchall()]; db.close()
        total, items = item_reference.external_only(ref_con, names, q, limit, offset)
        return {"total": total, "offset": offset, "limit": limit, "items": items}
    filt_ref = ref in ("matched", "drift", "ours_only") and ref_con is not None
    cu.execute("select count(*) " + _JOIN + wsql, tuple(params))
    total = int(cu.fetchone()[0])
    sel = ("select b.itemid, b.name, b.sortname, " + _TYPE_SQL + ", b.aH, b.flags, b.stackSize, e.level, e.jobs, e.slot, "
           "w.skill, w.dmg, w.delay " + _JOIN + wsql + " order by " + order)
    if filt_ref:
        cu.execute(sel, tuple(params))
    else:
        cu.execute(sel + " limit %s offset %s", tuple(params) + (limit, offset))
    rows = cu.fetchall(); db.close()
    items = []
    for iid, name, sortname, typ, aH, flags, stack, level, jobs, slots, wskill, dmg, delay in rows:
        flags = int(flags or 0)
        items.append({
            "itemid": iid, "name": name, "sortname": sortname, "type_name": typ,
            "ah": aH, "ah_name": dat.AH_CATEGORY.get(aH, ""), "level": level,
            "jobs": [j for i, j in enumerate(dat.JOBS) if jobs and (int(jobs) >> i) & 1] if jobs else [],
            "all_jobs": bool(jobs) and int(jobs) == (1 << len(dat.JOBS)) - 1,
            "slots": [s for i, s in enumerate(dat.SLOTS) if slots and (int(slots) >> i) & 1] if slots else [],
            "skill": wskill, "skill_name": WEAPON_SKILLS.get(wskill, "" if wskill is None else "skill %s" % wskill),
            "dmg": dmg, "delay": delay, "stack": stack,
            "rare": bool(flags & 0x8000), "ex": bool(flags & 0x4000),
        })
    if ref_con is not None:
        item_reference.annotate(items, ref_con)
        if filt_ref:
            items = [it for it in items if it["ref_status"] == ref]
            total = len(items); items = items[offset:offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "items": items}
