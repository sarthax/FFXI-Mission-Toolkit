"""Item editing layer: every write to the live item_* tables goes through here so it is
  1. backed up first (data/item_backups/*.json: full previous rows, restorable),
  2. journalled as annotated SQL (data/item_edit_log.sql: `-- comment` + the exact statement).
Mirrors zone_edit.py's conventions exactly, but for item_basic/item_equipment/item_weapon/
item_usable/item_puppet/item_furnishing instead of mob_spawn_points/npc_list.

Client DAT edits (the level requirement the real client itself enforces, not just the server's
permission check) are a SEPARATE step handled by item_dat_tools.py -- update_item()/create_item()
below call into it so both sides move together, per the project's "level requirement is dual
authority" research finding.
"""
import json
import time
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

import item_dat_tools as dat
from workbench.devtools.spatial import active_zone_plot as zone_plot
from workbench.editors.items._db_alias import item_db as _item_db

DATA = Path(__file__).parent / "data"
BACKUPS = DATA / "item_backups"
LOG = DATA / "item_edit_log.sql"

TABLES = {  # table -> primary key columns (all six real item_* tables, per C:\topaz\sql\*.sql)
    "item_basic":      ["itemid"],
    "item_equipment":  ["itemId"],
    "item_weapon":     ["itemId"],
    "item_usable":     ["itemid"],
    "item_puppet":     ["itemid"],
    "item_furnishing": ["itemid"],
}
# Which of the six tables a given item_basic.flags/type combination actually has a row in --
# item_basic always exists; the rest are conditional on item_type (mirrors item_dat_tools.TYPE_NAME).
TYPE_TABLES = {
    0: [],                       # general -- item_basic only
    1: ["item_usable"],          # consumable
    3: ["item_equipment"],       # armor
    4: ["item_equipment", "item_weapon"],  # weapon
    5: ["item_puppet"],
    6: ["item_furnishing"],
}

# Bitmasked columns, so the UI can render checkboxes instead of asking the user to know the
# schema. Only columns with a CONFIRMED bit mapping (verified against C:\topaz source or
# item_dat_tools' own vendored tables) are listed here -- per project rule, never invent a
# schema. {table: {column: [(bit_value, label), ...]}}
# item_basic.flags as the server itself reads it: ITEM_FLAG in src/map/items/item.h (identical in
# the DSP and Topaz trees). item_dat_tools.ITEM_FLAGS uses different names for the same bits, so the
# server column is labelled from the server's own enum.
SERVER_ITEM_FLAGS = dict(dat.ITEM_FLAGS)

BITMASK_SCHEMAS = {
    "item_basic": {
        "flags": sorted(SERVER_ITEM_FLAGS.items()),
    },
    "item_equipment": {
        "jobs": [(1 << i, job) for i, job in enumerate(dat.JOBS)],
        "slot": [(1 << i, name) for i, name in enumerate(dat.SLOTS)],
    },
    "item_usable": {
        "validTargets": sorted(dat.VALID_TARGETS.items()),
    },
}

# Single-value enum columns -- rendered as a dropdown, NOT checkboxes, since only one value can
# ever be true at once (unlike the flag bitmasks above where several bits combine).
# item_basic.aH: which Auction House submenu the item appears under (0 = not sellable at AH).
# item_furnishing.moghancement: confirmed via charentity.cpp's UpdateMoghancement()
# (`switch (m_moghancementID)`, single-value equality) to be a real enum, NOT a bitmask, despite
# its value range superficially looking bitmask-shaped -- see item_dat_tools.MOGHANCEMENT comment.
ENUM_SCHEMAS = {
    "item_basic": {
        "aH": sorted(dat.AH_CATEGORY.items()),
    },
    "item_furnishing": {
        "moghancement": sorted(dat.MOGHANCEMENT.items()),
    },
    "item_usable": {
        "animation": sorted(dat.ITEM_ANIMATION.items()),
    },
}

# item_equipment.races (a client-DAT-only field item_dat_tools tracks -- there is no
# item_equipment.races column server-side; C:\topaz\sql\item_equipment.sql has no such
# column and no RACE_* equip-gating code exists in C:\topaz\src), item_usable.activation
# (a plain millisecond duration, not a bitmask -- itemutils.cpp:363/item_usable.h), and
# item_furnishing.element/aura (schema columns exist but no bit-decode code was found anywhere
# in C:\topaz\src to confirm a mapping) are deliberately NOT listed above -- their bit/value
# meaning is unconfirmed, and this project's rule is to say "don't know" rather than invent a
# schema. Edit those as plain numbers until a real mapping surfaces.

# Packed-nibble columns -- NOT flag bitmasks: each is N sub-values of `bits` width packed at
# fixed shifts, so the UI renders a small number input (0..2^bits-1) per sub-value instead of a
# single raw int. {table: {column: {"bits": width, "fields": [(shift, label), ...]}}}
# item_puppet.element confirmed at C:\topaz\src\map\utils\puppetutils.cpp
# (`(getElementSlots() >> (i*4)) & 0xF`) -- 8 packed 4-bit (0-15) element-capacity values, one
# nibble per element, order confirmed via the contiguous EFFECT_FIRE_MANEUVER..EFFECT_DARK_MANEUVER
# run in status_effect.h (300-307). Applies identically to puppet heads, frames, and attachments
# (equip slot is the separate, non-bitmask `item_puppet.slot` column: 1=head, 2=frame,
# 3=attachment -- ITEM_PUPPET_EQUIPSLOT enum, item_puppet.h). NOTE: the actual per-attachment
# combat behavior/stat values (e.g. Turbo Charger's haste amounts) are NOT stored in any SQL/DAT
# field at all -- they're hardcoded in each attachment's own Lua file under
# C:\topaz\scripts\globals\abilities\pets\attachments\<item_name>.lua, dispatched by item name
# (luautils.cpp OnAttachmentEquip/OnManeuverGain/etc. index
# tpz.globals.abilities.pets.attachments[itemName]). That is Lua source code, not row data, so it
# is out of scope for this row-level editor -- editing an attachment's real numeric effect means
# editing its .lua file directly, not a future GUI field.
NIBBLE_SCHEMAS = {
    "item_puppet": {
        "element": {"bits": 4, "fields": [(i * 4, name) for i, name in enumerate(dat.ELEMENTS)]},
    },
}


def bitmask_schema():
    """{table: {column: {type, bits: [{bit,label}]} | {type, width, fields: [{shift,label}]}
    | {type, options: [{value,label}]}}}."""
    result = {}
    for table, cols in BITMASK_SCHEMAS.items():
        result.setdefault(table, {})
        for col, bits in cols.items():
            result[table][col] = {
                "type": "bits",
                "bits": [{"bit": bit, "label": label} for bit, label in bits],
            }
    for table, cols in NIBBLE_SCHEMAS.items():
        result.setdefault(table, {})
        for col, spec in cols.items():
            result[table][col] = {
                "type": "nibbles",
                "width": spec["bits"],
                "fields": [{"shift": shift, "label": label} for shift, label in spec["fields"]],
            }
    enum_schemas = ENUM_SCHEMAS
    try:
        from workbench.editors.items import _db_alias
        if _db_alias.is_dsp():  # DSP's MOGHOUSE_AURA enum differs from Topaz's moghancement ids
            from workbench.editors.items import _enums_dsp
            enum_schemas = {**ENUM_SCHEMAS, "item_furnishing": {"moghancement": sorted(_enums_dsp.MOGHANCEMENT.items())}}
    except Exception:
        pass
    for table, cols in enum_schemas.items():
        result.setdefault(table, {})
        for col, options in cols.items():
            result[table][col] = {
                "type": "enum",
                "options": [{"value": value, "label": label} for value, label in options],
            }
    return result


# ---- value <-> json / sql -------------------------------------------------------------------
def _enc(v):
    if isinstance(v, (bytes, bytearray)):
        return {"__hex__": bytes(v).hex()}
    if isinstance(v, Decimal):
        return float(v)
    return v


def _dec(v):
    if isinstance(v, dict) and "__hex__" in v:
        return bytes.fromhex(v["__hex__"])
    return v


def lit(v):
    v = _dec(v)
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cols(cu, table):
    cu.execute(f"describe {table}")
    return [r[0] for r in cu.fetchall()]


def _pk_for(table):
    """Primary key columns for a table -- covers the six real item_* tables (TABLES) plus the
    three one-to-many mod tables, whose composite keys aren't in TABLES since they're never the
    target of update_item()/create_item()."""
    if table == "item_mods":
        return ["itemId", "modId"]
    if table == "item_mods_pet":
        return ["itemId", "modId", "petType"]
    if table == "item_latents":
        return ["itemId", "modId", "value", "latentId", "latentParam"]
    return TABLES[table]


def _fetch(cu, table, keyvals):
    cols = _cols(cu, table)
    where = " and ".join(f"{k}=%s" for k in _pk_for(table))
    cu.execute(f"select * from {table} where {where}", tuple(keyvals))
    r = cu.fetchall()
    return dict(zip(cols, [_enc(x) for x in r[0]])) if r else None


def _journal(comment, lines):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n-- [{time.strftime('%Y-%m-%d %H:%M:%S')}] {comment or '(no comment)'}\n")
        for l in lines:
            f.write(l + "\n")


def _save_backup(label, item_id, ops, client_snapshot="auto", metadata=None):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    if client_snapshot == "auto":
        try:
            client_snapshot = dat.capture_client_record(item_id)
        except Exception:
            client_snapshot = None
    bid = time.strftime("%Y%m%d-%H%M%S") + f"-{len([1 for _ in BACKUPS.glob('*.json')]) % 1000:03d}"
    b = {
        "id": bid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label,
        "item_id": item_id, "ops": ops, "client_record": client_snapshot,
        "metadata": metadata or {},
    }
    (BACKUPS / f"{bid}.json").write_text(json.dumps(b, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))
    return bid


def _capture(cu, table, keyvals):
    return {"table": table, "key": list(keyvals), "row": _fetch(cu, table, keyvals)}


def list_backups():
    out = []
    for f in sorted(BACKUPS.glob("*.json"), reverse=True) if BACKUPS.exists() else []:
        b = json.loads(f.read_text())
        if b.get("kind") == "batch":
            items = b.get("items") or []
            out.append({
                "id": b["id"], "ts": b["ts"], "label": b["label"], "item_id": None,
                "kind": "batch", "item_ids": [int(x["item_id"]) for x in items],
                "rows": sum(len(x.get("ops") or []) for x in items),
                "has_client_record": any(bool(x.get("client_record")) for x in items),
                "client_target": None,
            })
            continue
        snap = b.get("client_record")
        out.append({
            "id": b["id"], "ts": b["ts"], "label": b["label"], "item_id": b.get("item_id"),
            "kind": "item", "rows": len(b.get("ops") or []), "has_client_record": bool(snap),
            "client_target": snap.get("target") if snap else None,
        })
    return out


def list_item_history(item_id, limit=100):
    """Selected-item backup/change history, including legacy backups without metadata."""
    item_id, limit = int(item_id), max(1, min(int(limit), 500))
    out = []
    if not BACKUPS.exists():
        return out
    for f in sorted(BACKUPS.glob("*.json"), reverse=True):
        try:
            b = json.loads(f.read_text())
        except Exception:
            continue
        if b.get("kind") == "batch":
            member = next((x for x in (b.get("items") or []) if int(x.get("item_id", -1)) == item_id), None)
            if member is None:
                continue
            meta = b.get("metadata") or {}
            ops = member.get("ops") or []
            snap = member.get("client_record")
            out.append({
                "id": b.get("id"), "ts": b.get("ts"), "label": b.get("label") or "batch edit",
                "action_type": "batch_edit", "comment": meta.get("comment") or "",
                "summary": meta.get("summary") or "batch edit",
                "tables": sorted({op.get("table") for op in ops if op.get("table")}),
                "field_changes": [{
                    "table": BATCH_SAFE_FIELDS.get(meta.get("field"), ("batch", meta.get("field")))[0],
                    "field": BATCH_SAFE_FIELDS.get(meta.get("field"), ("batch", meta.get("field")))[1],
                    "before": (ops[0].get("row") or {}).get(BATCH_SAFE_FIELDS.get(meta.get("field"), ("", ""))[1]) if ops else None,
                    "after": meta.get("value"),
                }] if meta.get("field") else [],
                "effect_changes": [], "dat_touched": bool(snap),
                "has_client_record": bool(snap), "client_target": snap.get("target") if snap else None,
                "restorable": True, "batch": True, "legacy_metadata": False,
            })
            if len(out) >= limit:
                break
            continue
        raw_item_id = b.get("item_id", -1)
        if raw_item_id is None or int(raw_item_id) != item_id:
            continue
        meta = b.get("metadata") or {}
        ops = b.get("ops") or []
        tables = sorted({op.get("table") for op in ops if op.get("table")})
        effect_tables = {"item_mods", "item_mods_pet", "item_latents"}
        action = meta.get("action_type")
        label = str(b.get("label", ""))
        if not action:
            lower = label.lower()
            if lower.startswith("create item"):
                action = "create"
            elif lower.startswith("delete item"):
                action = "delete"
            elif lower.startswith("reconcile"):
                action = "reconcile"
            elif "restore" in lower:
                action = "restore"
            elif "edit" in lower:
                action = "edit"
            else:
                action = "backup"
        summary = meta.get("summary")
        if not summary:
            regular = [t for t in tables if t not in effect_tables]
            effects = [t for t in tables if t in effect_tables]
            bits = []
            if regular:
                bits.append("tables: " + ", ".join(regular))
            if effects:
                bits.append("effects: " + ", ".join(effects))
            summary = " · ".join(bits) or "client-record snapshot"
        snap = b.get("client_record")
        out.append({
            "id": b.get("id"), "ts": b.get("ts"), "label": label,
            "action_type": action, "comment": meta.get("comment") or "",
            "summary": summary, "tables": tables,
            "field_changes": meta.get("field_changes") or [],
            "effect_changes": meta.get("effect_changes") or [],
            "dat_touched": bool(meta.get("dat_touched")),
            "has_client_record": bool(snap),
            "client_target": snap.get("target") if snap else None,
            "restorable": bool(b.get("id")),
            "legacy_metadata": not bool(meta),
        })
        if len(out) >= limit:
            break
    return out


def restore_client_record_from_backup(bid, comment=""):
    """Restore only this item's exact client DAT record from an item backup; SQL is untouched."""
    b = json.loads((BACKUPS / f"{bid}.json").read_text())
    snapshot = b.get("client_record")
    if not snapshot:
        raise ValueError(f"backup {bid} predates exact client-record snapshots")
    item_id = int(b["item_id"])
    target = snapshot.get("target")
    current = dat.capture_client_record(item_id, target=target)
    if current is None:
        raise ValueError("current client record is unavailable for backup before record restore")
    pre_id = _save_backup(
        f"auto: before client-record restore of {bid}", item_id, [], client_snapshot=current
    )
    report = dat.restore_client_record(snapshot)
    _journal(comment or f"RESTORE client record from backup {bid}", [
        f"-- item {item_id} client record only",
        f"-- source backup {bid}; undo backup {pre_id}; target {report.get('target')}",
    ])
    return {
        "item_id": item_id, "source_backup": bid, "backup": pre_id,
        "client": report, "sql_touched": False,
    }

def restore(bid):
    """Restore a backup across SQL and the exact captured client record when available."""
    b = json.loads((BACKUPS / f"{bid}.json").read_text())
    item_id = int(b["item_id"])
    db = _item_db(); cu = db.cursor()
    pre, lines = [], []
    saved_client = b.get("client_record")
    restore_target = saved_client.get("target") if saved_client else None
    try:
        pre_client = dat.capture_client_record(item_id, target=restore_target)
    except Exception:
        pre_client = None
    for op in b["ops"]:
        pre.append(_capture(cu, op["table"], op["key"]))
    pre_id = _save_backup(f"auto: before restore of {bid}", item_id, pre, client_snapshot=pre_client)
    client_report = None
    try:
        for op in b["ops"]:
            t, kv, row = op["table"], op["key"], op["row"]
            pk = _pk_for(t)
            where = " and ".join(f"{k}={lit(v)}" for k, v in zip(pk, kv))
            if row is None:
                cu.execute(f"delete from {t} where " + " and ".join(f"{k}=%s" for k in pk), tuple(kv))
                lines.append(f"DELETE FROM {t} WHERE {where};")
            else:
                cols = list(row)
                cu.execute(
                    f"replace into {t} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})",
                    tuple(_dec(row[col]) for col in cols),
                )
                lines.append(f"REPLACE INTO {t} ({','.join(cols)}) VALUES ({','.join(lit(row[col]) for col in cols)});")

        if saved_client:
            client_report = dat.restore_client_record(saved_client)
        else:
            # Legacy backups predate exact record snapshots; restore only confirmed mapped fields.
            client_fields = {}
            for op in b["ops"]:
                if op["row"] is not None and op["table"] in TABLES:
                    client_fields.update(_map_to_client_fields(op["table"], op["row"]))
            if client_fields and dat.read_client_item(item_id) is not None:
                dat.validate_client_patch(item_id, client_fields)
                client_report = dat.patch_client_item(item_id, client_fields)

        try:
            db.commit()
        except Exception:
            db.rollback()
            if pre_client:
                dat.restore_client_record(pre_client)
            raise
    except Exception:
        try:
            db.rollback()
        finally:
            db.close()
        raise
    cu.execute("select 1 from item_basic where itemid=%s", (item_id,))
    item_exists = cu.fetchone() is not None
    db.close()
    _journal(f"RESTORE from backup {bid} ({b['label']}); pre-restore state saved as {pre_id}", lines)
    return {
        "restored": len(b["ops"]), "pre_restore_backup": pre_id,
        "client": client_report, "item_exists": item_exists,
    }

CONTENT_TABLE_HINTS = ("drop", "shop", "vendor", "recipe", "reward", "helm", "garden", "exchange", "apprais")
PLAYER_STATE_TABLE_HINTS = ("char", "inventory", "auction", "delivery", "bazaar", "account", "storage")


def _usage_category(table: str) -> str:
    t = table.lower()
    if "drop" in t:
        return "drop"
    if "recipe" in t:
        return "recipe"
    if "shop" in t or "vendor" in t:
        return "shop"
    if "reward" in t:
        return "reward"
    if "helm" in t:
        return "helm"
    if "garden" in t:
        return "gardening"
    if "exchange" in t or "apprais" in t:
        return "exchange/appraisal"
    return "content"


def _content_table_allowed(table: str) -> bool:
    t = table.lower()
    if any(x in t for x in PLAYER_STATE_TABLE_HINTS):
        return False
    return any(x in t for x in CONTENT_TABLE_HINTS)


def _row_dict(cols, row):
    return {str(k): _enc(v) for k, v in zip(cols, row)}


def _indexed_item_usage(item_id: int, internal_name: str) -> tuple[list[dict], dict]:
    """Recorded Workbench/catalog relationships and item-scoped client identity records."""
    from workbench.core.services.feature_trace_catalog import search_catalog, provider_relationships
    root = Path(__file__).parent
    dbs = [
        ("index", root / "ffxi_zone_database.db"),
        ("graph", root / "workbench.db"),
    ]
    refs = []
    coverage = {"catalog": False, "graph": False, "client_identity": False}
    candidate_nodes = set()
    for label, db_path in dbs:
        if not db_path.exists():
            continue
        con = sqlite3.connect(db_path)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if label == "index":
                coverage["catalog"] = True
                if "identity_records" in tables:
                    coverage["client_identity"] = True
                    cols = {r[1] for r in con.execute("PRAGMA table_info(identity_records)")}
                    if {"record_id", "snapshot_id", "namespace", "numeric_id"}.issubset(cols):
                        rows = con.execute(
                            "SELECT record_id,snapshot_id,namespace,numeric_id,semantic_key,confidence,evidence_id "
                            "FROM identity_records WHERE CAST(numeric_id AS TEXT)=?",
                            (str(item_id),),
                        ).fetchall()
                        for rec_id, snap, namespace, numeric_id, semantic_key, confidence, evidence_id in rows:
                            if "ITEM" not in str(namespace or "").upper():
                                continue
                            refs.append({
                                "evidence": "client_index",
                                "category": "client",
                                "record_id": rec_id,
                                "snapshot_id": snap,
                                "namespace": namespace,
                                "numeric_id": numeric_id,
                                "semantic_key": semantic_key,
                                "confidence": confidence,
                                "evidence_id": evidence_id,
                                "summary": f"client identity {namespace} {numeric_id} in snapshot {snap}",
                            })
            if "entity_relationships" in tables:
                coverage["graph"] = True

            terms = [str(item_id)]
            if internal_name:
                terms.append(internal_name)
            for term in terms:
                try:
                    rows = search_catalog(con, term, limit=200)
                except Exception:
                    rows = []
                for row in rows:
                    if str(row.get("node_type") or "").upper() != "ITEM":
                        continue
                    exact = False
                    if str(row.get("numeric_id", "")) == str(item_id):
                        exact = True
                    ident = row.get("identity") or {}
                    if any(str(v) == str(item_id) for v in ident.values()):
                        exact = True
                    if internal_name and str(row.get("display_name") or "").casefold() == internal_name.casefold():
                        exact = True
                    node_id = str(row.get("node_id") or "")
                    if re.search(r"(^|[:=&])" + re.escape(str(item_id)) + r"($|[&])", node_id):
                        exact = True
                    if exact:
                        candidate_nodes.add(node_id)

            for node_id in sorted(candidate_nodes):
                for link in provider_relationships(con, node_id):
                    refs.append({
                        "evidence": "catalog_relationship",
                        "category": "graph/catalog",
                        "relationship": link.get("relationship"),
                        "source_node": link.get("source_node"),
                        "target_node": link.get("target_node"),
                        "target_name": link.get("target_name"),
                        "target_type": link.get("target_type"),
                        "provider_native": bool(link.get("provider_native")),
                        "basis": link.get("basis"),
                        "summary": f"{link.get('relationship')} -> {link.get('target_name') or link.get('target_node')}",
                    })

                if "entity_relationships" in tables:
                    rows = con.execute(
                        "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,metadata_json "
                        "FROM entity_relationships WHERE source_node=? OR target_node=? ORDER BY relationship_id LIMIT 250",
                        (node_id, node_id),
                    ).fetchall()
                    for rid, src, dst, rel, evidence_id, confidence, status, metadata_json in rows:
                        other = dst if src == node_id else src
                        refs.append({
                            "evidence": "graph_relationship",
                            "category": "graph/catalog",
                            "relationship_id": rid,
                            "relationship": rel,
                            "source_node": src,
                            "target_node": dst,
                            "other_node": other,
                            "evidence_id": evidence_id,
                            "confidence": confidence,
                            "status": status,
                            "metadata": metadata_json,
                            "summary": f"{rel}: {src} -> {dst}",
                        })
        finally:
            con.close()

    dedup = []
    seen = set()
    for ref in refs:
        key = (
            ref.get("evidence"), ref.get("relationship_id"), ref.get("record_id"),
            ref.get("relationship"), ref.get("source_node"), ref.get("target_node"),
            ref.get("snapshot_id"), ref.get("namespace"),
        )
        if key in seen:
            continue
        seen.add(key)
        dedup.append(ref)
    return dedup, coverage


def item_usage(item_id: int, source_limit: int = 100) -> dict:
    """Conservative pre-delete usage scan against the active server DB and configured Lua tree.

    Database hits are exact equality matches against item-id-bearing content columns. Lua hits are
    explicitly lower-confidence source-text references and are never promoted to foreign-key proof.
    """
    item_id = int(item_id)
    source_limit = max(0, min(int(source_limit), 500))
    db = _item_db()
    cu = db.cursor()
    refs = []
    coverage = {"database": True, "source_scripts": False, "graph": False}
    try:
        cu.execute("show tables")
        tables = [r[0] for r in cu.fetchall()]
        for table in tables:
            if not _content_table_allowed(table):
                continue
            try:
                cu.execute("describe \`" + table + "\`")
                cols = [r[0] for r in cu.fetchall()]
            except Exception:
                continue
            lower = {c.lower(): c for c in cols}
            match_cols = []
            for key in ("itemid", "item_id"):
                if key in lower:
                    match_cols.append(lower[key])
            if "recipe" in table.lower():
                for c in cols:
                    lc = c.lower()
                    if re.fullmatch(r"ingredient\d+", lc) or re.fullmatch(r"result(?:hq\d*)?", lc) or lc in ("crystal", "hqcrystal"):
                        match_cols.append(c)
            match_cols = list(dict.fromkeys(match_cols))
            if not match_cols:
                continue
            where = " OR ".join("\`" + c + "\`=%s" for c in match_cols)
            try:
                cu.execute("select * from \`" + table + "\` where " + where + " limit 100", tuple([item_id] * len(match_cols)))
                rows = cu.fetchall()
            except Exception:
                continue
            for row in rows:
                rd = _row_dict(cols, row)
                matched = [c for c in match_cols if str(rd.get(c)) == str(item_id)]
                refs.append({
                    "evidence": "database_exact",
                    "category": _usage_category(table),
                    "table": table,
                    "matched_columns": matched,
                    "row": rd,
                    "summary": table + ": " + ", ".join(matched),
                })
    finally:
        db.close()

    try:
        current_data = get_item(item_id)
        internal_name = str(current_data.get("server", {}).get("item_basic", {}).get("name") or "")
    except Exception:
        internal_name = ""
    indexed_refs, indexed_coverage = _indexed_item_usage(item_id, internal_name)
    refs.extend(indexed_refs)
    coverage.update(indexed_coverage)

    script_refs = []
    try:
        if source_limit <= 0:
            raise StopIteration
        root = zone_plot._server_root()
        scripts = root / "scripts"
        if scripts.is_dir():
            coverage["source_scripts"] = True
            token = re.sub(r"[^A-Z0-9]+", "_", internal_name.upper()).strip("_")
            token_re = re.compile(r"\b" + re.escape(token) + r"\b") if token else None
            numeric_re = re.compile(r"(?<!\d)" + re.escape(str(item_id)) + r"(?!\d)")
            context_re = re.compile(r"item|trade|reward|drop|add|del|give|has|obtain", re.I)
            for p in scripts.rglob("*.lua"):
                if len(script_refs) >= source_limit:
                    break
                try:
                    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                except Exception:
                    continue
                for lineno, line in enumerate(lines, 1):
                    if len(script_refs) >= source_limit:
                        break
                    token_hit = bool(token_re and token_re.search(line))
                    numeric_hit = bool(numeric_re.search(line) and context_re.search(line))
                    if not (token_hit or numeric_hit):
                        continue
                    script_refs.append({
                        "evidence": "source_text",
                        "category": "script",
                        "path": str(p.relative_to(root)).replace("\\", "/"),
                        "line": lineno,
                        "match": "item_name_token" if token_hit else "numeric_item_context",
                        "text": line.strip()[:500],
                    })
    except StopIteration:
        pass
    except Exception:
        pass

    refs.extend(script_refs)
    counts = {}
    for ref in refs:
        counts[ref["category"]] = counts.get(ref["category"], 0) + 1
    return {
        "item_id": item_id,
        "server": zone_plot.get_server(),
        "references": refs,
        "counts": counts,
        "total": len(refs),
        "blocking_reference_count": sum(1 for r in refs if r["evidence"] == "database_exact"),
        "graph_reference_count": sum(1 for r in refs if r["evidence"] in ("graph_relationship", "catalog_relationship")),
        "client_reference_count": sum(1 for r in refs if r["evidence"] == "client_index"),
        "source_text_count": len(script_refs),
        "coverage": coverage,
        "notes": [
            "database_exact rows are exact item-id matches in active-server content tables",
            "graph/catalog rows are recorded Workbench/index relationships and are not promoted to live DB foreign keys",
            "client_index rows appear only when an item-scoped client identity namespace is actually indexed",
            "source_text rows are textual evidence only and may require human interpretation",
            "absence of a reference is not proof that the item is unused where a subsystem is not indexed",
        ],
    }


# ---- search -----------------------------------------------------------------------------------
def search(q, category="", min_level=-1, max_level=-1, job=-1, skill=-1, client_state="", limit=200):
    """Search server items, or opt-in DAT-only client records when client_state='dat-only'."""
    if not q or len(q) < 2:
        return []
    if client_state == "dat-only":
        return dat.search_dat_only(q, category=category, limit=limit)
    min_level, max_level, job, skill, limit = int(min_level), int(max_level), int(job), int(skill), int(limit)
    db = _item_db(); cu = db.cursor()
    where = ["b.name like %s"]
    params = [f"%{q}%"]
    if min_level >= 0:
        where.append("e.level >= %s"); params.append(min_level)
    if max_level >= 0:
        where.append("e.level <= %s"); params.append(max_level)
    if job >= 0:
        where.append("(e.jobs & %s) <> 0"); params.append(1 << job)
    if skill >= 0:
        where.append("w.skill = %s"); params.append(skill)
    sql = """select b.itemid,b.name,b.flags,b.stackSize,
                    e.level,e.jobs,e.slot,
                    w.skill,w.dmg,w.delay,
                    u.itemid,p.itemid,f.itemid
             from item_basic b
             left join item_equipment e on e.itemId=b.itemid
             left join item_weapon w on w.itemId=b.itemid
             left join item_usable u on u.itemid=b.itemid
             left join item_puppet p on p.itemid=b.itemid
             left join item_furnishing f on f.itemid=b.itemid
             where """ + " and ".join(where) + " order by b.name limit %s"
    params.append(max(limit * 3, 200))
    cu.execute(sql, tuple(params))
    rows = cu.fetchall(); db.close()
    out = []
    for itemid, name, flags, stack, level, jobs, slot, wskill, wdmg, delay, usable_id, puppet_id, furnishing_id in rows:
        if wskill is not None:
            type_name = "weapon"
        elif level is not None:
            type_name = "armor"
        elif usable_id is not None:
            type_name = "consumable"
        elif puppet_id is not None:
            type_name = "puppet"
        elif furnishing_id is not None:
            type_name = "furnishing"
        else:
            type_name = "general"
        if category and category != type_name:
            continue
        client = None
        try:
            rec = dat.read_client_item(itemid)
            client = dat.item_to_dict(rec) if rec is not None else None
        except Exception:
            client = None
        if client is None:
            cstate = "server-only"
        else:
            server_rows = {"item_basic": {"flags": flags, "stackSize": stack}}
            if level is not None:
                server_rows["item_equipment"] = {"level": level, "jobs": jobs, "slot": slot}
            if wskill is not None:
                server_rows["item_weapon"] = {"skill": wskill, "dmg": wdmg, "delay": delay}
            elif type_name == "consumable":
                server_rows["item_usable"] = {}
            elif type_name == "puppet":
                server_rows["item_puppet"] = {}
            elif type_name == "furnishing":
                server_rows["item_furnishing"] = {}
            cmp = compare_server_client(server_rows, client)
            cstate = "mismatch" if cmp["mismatches"] else "synced"
        if client_state and client_state != cstate:
            continue
        out.append({"itemid": itemid, "name": name, "type_name": type_name, "level": level,
                    "jobs": jobs, "skill": wskill, "dmg": wdmg, "delay": delay, "client_state": cstate})
        if len(out) >= limit:
            break
    return out

def _server_item_type(rows):
    """The client DAT item type a server row set should correspond to.

    Checked against real data (item_basic + client DAT, sample of ~165 items): armor that also
    has a use effect (equipment + usable rows) is client type 3, not 1, and furnishings are
    client type 0 (the DAT has no furnishing type), so neither is a mismatch."""
    if rows.get('item_weapon') is not None:
        return 4
    if rows.get('item_equipment') is not None:
        return 3
    if rows.get('item_usable') is not None:
        return 1
    if rows.get('item_puppet') is not None:
        return 5
    return 0


def _server_jobs_to_client(jobs):
    """Server job masks put WAR at bit 0; the client DAT leaves bit 0 unused and puts WAR at bit 1."""
    return None if jobs is None else int(jobs) << 1


def _client_jobs_to_server(jobs):
    return None if jobs is None else int(jobs) >> 1


def compare_server_client(rows, client):
    """Compare only fields with confirmed server<->client mappings used by the write path."""
    if client is None:
        return {'available': False, 'mismatches': [], 'matches': [], 'fields': []}
    specs = [
        ('item_type', _server_item_type(rows), client.get('type')),
        ('flags', rows.get('item_basic', {}).get('flags'), client.get('flags')),
        ('stack', rows.get('item_basic', {}).get('stackSize'), client.get('stack')),
    ]
    eq = rows.get('item_equipment')
    if eq is not None:
        specs.extend([
            ('level', eq.get('level'), client.get('level')),
            ('jobs', _server_jobs_to_client(eq.get('jobs')), client.get('jobs')),
            ('slots', eq.get('slot'), client.get('slots')),
        ])
    weapon = rows.get('item_weapon')
    if weapon is not None:
        specs.extend([
            ('damage', weapon.get('dmg'), client.get('dmg')),
            ('delay', weapon.get('delay'), client.get('delay')),
            ('skill', weapon.get('skill'), client.get('skill')),
        ])
    fields = []
    for name, server_value, client_value in specs:
        if server_value is None or client_value is None:
            continue
        same = int(server_value) == int(client_value) if isinstance(server_value, (int, float, Decimal)) and isinstance(client_value, (int, float)) else server_value == client_value
        fields.append({'field': name, 'server': server_value, 'client': client_value, 'match': same})
    return {
        'available': True,
        'fields': fields,
        'matches': [r for r in fields if r['match']],
        'mismatches': [r for r in fields if not r['match']],
    }


def validate_item_state(rows, client=None):
    """Conservative structural/mask validation using only confirmed schemas already in this module."""
    errors, warnings, info = [], [], []
    if rows.get('item_basic') is None:
        errors.append({'code': 'MISSING_BASIC', 'message': 'item_basic row is required'})
        return {'errors': errors, 'warnings': warnings, 'info': info}
    if rows.get('item_weapon') is not None and rows.get('item_equipment') is None:
        errors.append({'code': 'WEAPON_WITHOUT_EQUIPMENT', 'message': 'item_weapon exists without item_equipment'})

    for table, schemas in BITMASK_SCHEMAS.items():
        row = rows.get(table)
        if row is None:
            continue
        for field, bits in schemas.items():
            if row.get(field) is None:
                continue
            known = 0
            for bit, _label in bits:
                known |= int(bit)
            raw = int(row[field])
            unknown = raw & ~known
            if unknown:
                warnings.append({
                    'code': 'UNKNOWN_MASK_BITS',
                    'message': f'{table}.{field} has unknown/unmapped bits {unknown:#x}',
                    'table': table, 'field': field, 'value': raw, 'unknown_bits': unknown,
                })

    server_type = _server_item_type(rows)
    info.append({'code': 'SERVER_TYPE', 'message': f'server table structure resolves to item type {server_type}'})
    if client is not None and client.get('type') is not None and int(client['type']) != server_type:
        warnings.append({
            'code': 'TYPE_MISMATCH',
            'message': f"server table structure is type {server_type}, client DAT is type {client['type']}",
        })
    return {'errors': errors, 'warnings': warnings, 'info': info}

def get_item(item_id):
    """Full live row(s) for one item, across every table it actually appears in, plus its
    real client-DAT record (level/jobs/etc as the client itself sees them) for comparison."""
    item_id = int(item_id)
    db = _item_db(); cu = db.cursor()
    basic = _fetch(cu, "item_basic", [item_id])
    if basic is None:
        db.close()
        raise ValueError(f"item_basic.itemid={item_id} not found")
    rows = {"item_basic": basic}
    _en = _enums()
    for table in ("item_equipment", "item_weapon", "item_usable", "item_puppet", "item_furnishing"):
        row = _fetch(cu, table, [item_id])
        if row is not None:
            rows[table] = row
    cu.execute("select modId, value from item_mods where itemId=%s order by modId", (item_id,))
    mods = [{"modId": r[0], "value": r[1], "name": _en["MOD_NAMES"].get(r[0])} for r in cu.fetchall()]
    cu.execute("select modId, value, petType from item_mods_pet where itemId=%s order by petType, modId", (item_id,))
    pet_mods = [{"modId": r[0], "value": r[1], "petType": r[2],
                 "name": _en["MOD_NAMES"].get(r[0]), "petTypeName": dat.PET_TYPE_NAMES.get(r[2])} for r in cu.fetchall()]
    cu.execute("select modId, value, latentId, latentParam from item_latents where itemId=%s order by latentId, modId", (item_id,))
    latents = [{"modId": r[0], "value": r[1], "latentId": r[2], "latentParam": r[3],
                "name": _en["MOD_NAMES"].get(r[0]), "latentName": _en["LATENT_NAMES"].get(r[2])} for r in cu.fetchall()]
    db.close()
    client = None
    try:
        rec = dat.read_client_item(item_id)
        if rec is not None:
            client = dat.item_to_dict(rec)
    except ValueError:
        client = None
    dat_status = {"target": dat.dat_target(), "pivot_root": str(dat.pivot_root())}
    if client:
        backups = dat.list_dat_backups()
        key = client.get("dat_ui", "").replace("/", "_").replace("\\", "_")
        dat_status["dat_ui"] = client.get("dat_ui")
        dat_status["record_index"] = client.get("record_index")
        dat_status["format"] = client.get("format")
        dat_status["category"] = client.get("category")
        dat_status["has_backup"] = any(b["key"] == key for b in backups)
    comparison = compare_server_client(rows, client)
    validation = validate_item_state(rows, client)
    return {"item_id": item_id, "server": rows, "mods": mods, "pet_mods": pet_mods, "latents": latents,
            "client": client, "dat_status": dat_status, "comparison": comparison, "validation": validation}


# ---- item_mods (one-to-many: multiple (modId,value) rows per item, composite PK) ------------
# Architecturally different from every table in TABLES above -- not one row per item, so it gets
# its own get/set/delete instead of going through update_item(). modId meaning comes from
# dat.MOD_NAMES, itself extracted verbatim from C:\topaz\src\map\modifier.h's real `enum class
# Mod` (never hand-typed), per the project's "never invent a schema" rule.
def set_item_mod(item_id, mod_id, value, comment=""):
    """Insert or update one (itemId, modId) row. `value` may be 0 (that's a real value, not a
    delete) -- use delete_item_mod to actually remove a mod row."""
    item_id, mod_id, value = int(item_id), int(mod_id), int(value)
    db = _item_db(); cu = db.cursor()
    cu.execute("select modId, value from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    before = cu.fetchone()
    bid = _save_backup(f"set item_mods {item_id}/{mod_id}", item_id,
                        [{"table": "item_mods", "key": [item_id, mod_id],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[1]} if before else None}])
    cu.execute("replace into item_mods (itemId, modId, value) values (%s,%s,%s)", (item_id, mod_id, value))
    db.commit(); db.close()
    was = f"was {before[1]}" if before else "was absent"
    sql = f"REPLACE INTO item_mods (itemId, modId, value) VALUES ({item_id},{mod_id},{value});"
    _journal(comment, [f"-- item_mods {item_id}/{mod_id} {was}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_mod(item_id, mod_id, comment=""):
    item_id, mod_id = int(item_id), int(mod_id)
    db = _item_db(); cu = db.cursor()
    cu.execute("select value from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    before = cu.fetchone()
    if before is None:
        db.close()
        raise ValueError(f"item_mods itemId={item_id} modId={mod_id} not found")
    bid = _save_backup(f"delete item_mods {item_id}/{mod_id}", item_id,
                        [{"table": "item_mods", "key": [item_id, mod_id],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0]}}])
    cu.execute("delete from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    db.commit(); db.close()
    sql = f"DELETE FROM item_mods WHERE itemId={item_id} AND modId={mod_id};"
    _journal(comment, [f"-- item_mods {item_id}/{mod_id} was {before[0]}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def _enums():
    """Mod/LATENT tables for the connected server: DSP's own headers on DSP (ids differ from Topaz), else Topaz's."""
    try:
        from workbench.editors.items import _db_alias
        dsp = _db_alias.is_dsp()
    except Exception:
        dsp = False
    if dsp:
        from workbench.editors.items import _enums_dsp
        return {"MOD_NAMES": _enums_dsp.MOD_NAMES, "LATENT_NAMES": _enums_dsp.LATENT_NAMES}
    return {"MOD_NAMES": dat.MOD_NAMES, "LATENT_NAMES": dat.LATENT_NAMES}


def mod_names():
    """{modId: name} for every confirmed mod, for the UI's add-mod dropdown."""
    return _enums()["MOD_NAMES"]


def mod_metadata():
    """Source-backed modifier comments/units for Item Editor presentation."""
    return dat.mod_metadata(_enums()["MOD_NAMES"])


# ---- item_mods_pet (one-to-many: multiple (modId,petType,value) rows per item, composite PK) --
# Same modId space as item_mods (dat.MOD_NAMES). petType is dat.PET_TYPE_NAMES, extracted from
# C:\topaz\src\map\modifier.h's `enum class PetModType` (8 entries: All/Avatar/Wyvern/Automaton/
# Harlequin/Valoredge/Sharpshot/Stormwaker) -- confirmed live via itemutils.cpp's item_mods_pet
# load query casting column 3 to PetModType. petType=0 (All) applies to every pet job.
def set_item_pet_mod(item_id, mod_id, pet_type, value, comment=""):
    """Insert or update one (itemId, modId, petType) row. `value` may be 0 (real value, not a
    delete) -- use delete_item_pet_mod to actually remove a row."""
    item_id, mod_id, pet_type, value = int(item_id), int(mod_id), int(pet_type), int(value)
    db = _item_db(); cu = db.cursor()
    cu.execute("select value from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    before = cu.fetchone()
    bid = _save_backup(f"set item_mods_pet {item_id}/{mod_id}/{pet_type}", item_id,
                        [{"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0], "petType": pet_type} if before else None}])
    cu.execute("replace into item_mods_pet (itemId, modId, value, petType) values (%s,%s,%s,%s)", (item_id, mod_id, value, pet_type))
    db.commit(); db.close()
    was = f"was {before[0]}" if before else "was absent"
    sql = f"REPLACE INTO item_mods_pet (itemId, modId, value, petType) VALUES ({item_id},{mod_id},{value},{pet_type});"
    _journal(comment, [f"-- item_mods_pet {item_id}/{mod_id}/{pet_type} {was}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_pet_mod(item_id, mod_id, pet_type, comment=""):
    item_id, mod_id, pet_type = int(item_id), int(mod_id), int(pet_type)
    db = _item_db(); cu = db.cursor()
    cu.execute("select value from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    before = cu.fetchone()
    if before is None:
        db.close()
        raise ValueError(f"item_mods_pet itemId={item_id} modId={mod_id} petType={pet_type} not found")
    bid = _save_backup(f"delete item_mods_pet {item_id}/{mod_id}/{pet_type}", item_id,
                        [{"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0], "petType": pet_type}}])
    cu.execute("delete from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    db.commit(); db.close()
    sql = f"DELETE FROM item_mods_pet WHERE itemId={item_id} AND modId={mod_id} AND petType={pet_type};"
    _journal(comment, [f"-- item_mods_pet {item_id}/{mod_id}/{pet_type} was {before[0]}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def pet_type_names():
    """{petType: name} for the UI's add-pet-mod dropdown."""
    return dat.PET_TYPE_NAMES


# ---- item_latents (one-to-many: conditional/hidden mods, full 5-column composite PK) ----------
# PK is (itemId, modId, value, latentId, latentParam) -- `value` is part of the key itself (unlike
# item_mods/item_mods_pet), so there is no single-row "update the value" operation: changing value
# makes a different row by definition. This gives add/delete only, no set-in-place. modId is the
# same Mod enum as item_mods (dat.MOD_NAMES); latentId is dat.LATENT_NAMES, extracted from
# C:\topaz\src\map\latent_effect.h's real `enum class LATENT` -- confirmed live via itemutils.cpp's
# item_latents load query casting column 1 to Mod and column 3 to LATENT, then calling
# CItemEquipment::addLatent(latentId, latentParam, modID, value). latentParam's meaning is
# condition-specific (see the comment baked into each LATENT_NAMES entry) so it stays a raw number.
def add_item_latent(item_id, mod_id, value, latent_id, latent_param, comment=""):
    item_id, mod_id, value, latent_id, latent_param = int(item_id), int(mod_id), int(value), int(latent_id), int(latent_param)
    db = _item_db(); cu = db.cursor()
    cu.execute("select 1 from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    if cu.fetchone():
        db.close()
        raise ValueError("an identical item_latents row already exists")
    bid = _save_backup(f"add item_latents {item_id}/{mod_id}/{latent_id}", item_id,
                        [{"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param], "row": None}])
    cu.execute("insert into item_latents (itemId, modId, value, latentId, latentParam) values (%s,%s,%s,%s,%s)",
               (item_id, mod_id, value, latent_id, latent_param))
    db.commit(); db.close()
    sql = f"INSERT INTO item_latents (itemId, modId, value, latentId, latentParam) VALUES ({item_id},{mod_id},{value},{latent_id},{latent_param});"
    _journal(comment, [f"-- item_latents {item_id} add  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_latent(item_id, mod_id, value, latent_id, latent_param, comment=""):
    item_id, mod_id, value, latent_id, latent_param = int(item_id), int(mod_id), int(value), int(latent_id), int(latent_param)
    db = _item_db(); cu = db.cursor()
    cu.execute("select 1 from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    if not cu.fetchone():
        db.close()
        raise ValueError("item_latents row not found")
    bid = _save_backup(f"delete item_latents {item_id}/{mod_id}/{latent_id}", item_id,
                        [{"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param],
                          "row": {"itemId": item_id, "modId": mod_id, "value": value, "latentId": latent_id, "latentParam": latent_param}}])
    cu.execute("delete from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    db.commit(); db.close()
    sql = f"DELETE FROM item_latents WHERE itemId={item_id} AND modId={mod_id} AND value={value} AND latentId={latent_id} AND latentParam={latent_param};"
    _journal(comment, [f"-- item_latents {item_id} delete  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def latent_names():
    """{latentId: name} for the UI's add-latent dropdown."""
    return _enums()["LATENT_NAMES"]


def latent_metadata():
    """Source-backed latent-condition/parameter semantics for Item Editor presentation."""
    return dat.latent_metadata(_enums()["LATENT_NAMES"])


# ---- edits ----------------------------------------------------------------------------------
def _normalize_effects(effects):
    """Normalize desired effect lists and reject duplicate composite keys before any write."""
    effects = effects or {}
    result = {"mods": [], "pet_mods": [], "latents": []}
    seen = set()
    for row in effects.get("mods", []):
        item = {"modId": int(row["modId"]), "value": int(row["value"])}
        key = item["modId"]
        if key in seen:
            raise ValueError(f"duplicate item_mods modId {key}")
        seen.add(key); result["mods"].append(item)
    seen = set()
    for row in effects.get("pet_mods", []):
        item = {"modId": int(row["modId"]), "petType": int(row["petType"]), "value": int(row["value"])}
        key = (item["modId"], item["petType"])
        if key in seen:
            raise ValueError(f"duplicate item_mods_pet key {key}")
        seen.add(key); result["pet_mods"].append(item)
    seen = set()
    for row in effects.get("latents", []):
        item = {
            "modId": int(row["modId"]), "value": int(row["value"]),
            "latentId": int(row["latentId"]), "latentParam": int(row["latentParam"]),
        }
        key = (item["modId"], item["value"], item["latentId"], item["latentParam"])
        if key in seen:
            raise ValueError(f"duplicate item_latents key {key}")
        seen.add(key); result["latents"].append(item)
    return result


def _effect_validation(desired):
    warnings = []
    _en = _enums()
    for row in desired["mods"]:
        if row["modId"] not in _en["MOD_NAMES"]:
            warnings.append({"code": "UNKNOWN_MOD_ID", "message": f"item_mods modId {row['modId']} is not present in the confirmed Mod enum map"})
    for row in desired["pet_mods"]:
        if row["modId"] not in _en["MOD_NAMES"]:
            warnings.append({"code": "UNKNOWN_MOD_ID", "message": f"item_mods_pet modId {row['modId']} is not present in the confirmed Mod enum map"})
        if row["petType"] not in dat.PET_TYPE_NAMES:
            warnings.append({"code": "UNKNOWN_PET_TYPE", "message": f"item_mods_pet petType {row['petType']} is not present in the confirmed PetModType enum map"})
    for row in desired["latents"]:
        if row["modId"] not in _en["MOD_NAMES"]:
            warnings.append({"code": "UNKNOWN_MOD_ID", "message": f"item_latents modId {row['modId']} is not present in the confirmed Mod enum map"})
        if row["latentId"] not in _en["LATENT_NAMES"]:
            warnings.append({"code": "UNKNOWN_LATENT_ID", "message": f"item_latents latentId {row['latentId']} is not present in the confirmed LATENT enum map"})
    return warnings

def _effect_state(cu, item_id):
    cu.execute("select modId,value from item_mods where itemId=%s", (item_id,))
    mods = {int(r[0]): {"itemId": item_id, "modId": int(r[0]), "value": int(r[1])} for r in cu.fetchall()}
    cu.execute("select modId,value,petType from item_mods_pet where itemId=%s", (item_id,))
    pet = {(int(r[0]), int(r[2])): {"itemId": item_id, "modId": int(r[0]), "value": int(r[1]), "petType": int(r[2])} for r in cu.fetchall()}
    cu.execute("select modId,value,latentId,latentParam from item_latents where itemId=%s", (item_id,))
    lat = {(int(r[0]), int(r[1]), int(r[2]), int(r[3])): {"itemId": item_id, "modId": int(r[0]), "value": int(r[1]), "latentId": int(r[2]), "latentParam": int(r[3])} for r in cu.fetchall()}
    return {"mods": mods, "pet_mods": pet, "latents": lat}


def _effect_changes(cu, item_id, desired):
    current = _effect_state(cu, item_id)
    changes = []
    wanted_mods = {r["modId"]: r for r in desired["mods"]}
    for key in set(current["mods"]) | set(wanted_mods):
        cur = current["mods"].get(key); want = wanted_mods.get(key)
        if cur is None or want is None or int(cur["value"]) != int(want["value"]):
            changes.append(("item_mods", [item_id, key], cur, want))
    wanted_pet = {(r["modId"], r["petType"]): r for r in desired["pet_mods"]}
    for key in set(current["pet_mods"]) | set(wanted_pet):
        cur = current["pet_mods"].get(key); want = wanted_pet.get(key)
        if cur is None or want is None or int(cur["value"]) != int(want["value"]):
            changes.append(("item_mods_pet", [item_id, key[0], key[1]], cur, want))
    wanted_lat = {(r["modId"], r["value"], r["latentId"], r["latentParam"]): r for r in desired["latents"]}
    for key in set(current["latents"]) | set(wanted_lat):
        cur = current["latents"].get(key); want = wanted_lat.get(key)
        if cur is None or want is None:
            changes.append(("item_latents", [item_id, key[0], key[1], key[2], key[3]], cur, want))
    return changes


def _apply_effect_changes(cu, item_id, changes):
    sqls = []
    for table, keyvals, cur, want in changes:
        if want is None:
            pk = _pk_for(table)
            cu.execute(f"delete from {table} where " + " and ".join(f"{k}=%s" for k in pk), tuple(keyvals))
            sqls.append("DELETE FROM " + table + " WHERE " + " AND ".join(f"{k}={lit(v)}" for k, v in zip(pk, keyvals)) + ";")
        elif table == "item_mods":
            cu.execute("replace into item_mods (itemId,modId,value) values (%s,%s,%s)", (item_id, want["modId"], want["value"]))
            sqls.append(f"REPLACE INTO item_mods (itemId,modId,value) VALUES ({item_id},{want['modId']},{want['value']});")
        elif table == "item_mods_pet":
            cu.execute("replace into item_mods_pet (itemId,modId,value,petType) values (%s,%s,%s,%s)", (item_id, want["modId"], want["value"], want["petType"]))
            sqls.append(f"REPLACE INTO item_mods_pet (itemId,modId,value,petType) VALUES ({item_id},{want['modId']},{want['value']},{want['petType']});")
        else:
            cu.execute("replace into item_latents (itemId,modId,value,latentId,latentParam) values (%s,%s,%s,%s,%s)", (item_id, want["modId"], want["value"], want["latentId"], want["latentParam"]))
            sqls.append(f"REPLACE INTO item_latents (itemId,modId,value,latentId,latentParam) VALUES ({item_id},{want['modId']},{want['value']},{want['latentId']},{want['latentParam']});")
    return sqls

RECONCILE_SERVER_FIELDS = {
    "flags": ("item_basic", "flags"),
    "stack": ("item_basic", "stackSize"),
    "level": ("item_equipment", "level"),
    "jobs": ("item_equipment", "jobs"),
    "slots": ("item_equipment", "slot"),
    "damage": ("item_weapon", "dmg"),
    "delay": ("item_weapon", "delay"),
    "skill": ("item_weapon", "skill"),
}


BATCH_SAFE_FIELDS = dict(RECONCILE_SERVER_FIELDS)


def _save_batch_backup(items, field, value, comment=""):
    """One envelope containing every SQL row + exact client record touched by a batch."""
    BACKUPS.mkdir(parents=True, exist_ok=True)
    bid = time.strftime("%Y%m%d-%H%M%S") + f"-batch-{len([1 for _ in BACKUPS.glob('*-batch-*.json')]) % 1000:03d}"
    payload = {
        "id": bid,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": "batch",
        "label": f"batch edit {field}={value}",
        "item_id": None,
        "metadata": {
            "action_type": "batch_edit",
            "comment": comment or "",
            "field": field,
            "value": value,
            "summary": f"{len(items)} item(s): {field} -> {value}",
        },
        "items": items,
    }
    (BACKUPS / f"{bid}.json").write_text(json.dumps(payload, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))
    return bid


def preview_batch_edit(item_ids, field, value):
    """Validate a constrained same-field batch without writing anything."""
    if field not in BATCH_SAFE_FIELDS:
        raise ValueError(f"batch field {field!r} is not in the proven-safe whitelist")
    ids = []
    for raw in item_ids or []:
        iid = int(raw)
        if iid not in ids:
            ids.append(iid)
    if not ids:
        raise ValueError("no item ids supplied")
    if len(ids) > 200:
        raise ValueError("batch is limited to 200 unique items")
    table, column = BATCH_SAFE_FIELDS[field]
    db = _item_db(); cu = db.cursor()
    rows, errors, warnings = [], [], []
    try:
        cols = _cols(cu, table)
        if column not in cols:
            raise ValueError(f"{table} has no column {column}")
        for item_id in ids:
            op = _capture(cu, table, [item_id])
            if op["row"] is None:
                errors.append({"item_id": item_id, "message": f"{table} row does not exist"})
                continue
            before = op["row"].get(column)
            patch = {table: {column: value}}
            try:
                validation = validate_item_changes(item_id, patch)
            except Exception as ex:
                errors.append({"item_id": item_id, "message": str(ex)})
                continue
            if validation.get("errors"):
                errors.append({"item_id": item_id, "message": "; ".join(x.get("message", str(x)) for x in validation["errors"])})
                continue
            client_patch = _map_to_client_fields(table, {column: value})
            client_available = False
            if client_patch:
                try:
                    rec = dat.read_client_item(item_id)
                    client_available = rec is not None
                    if client_available:
                        dat.validate_client_patch(item_id, client_patch)
                    else:
                        errors.append({"item_id": item_id, "message": "client DAT record unavailable; bulk dual-authority edit is blocked"})
                        continue
                except Exception as ex:
                    errors.append({"item_id": item_id, "message": f"client validation failed: {ex}"})
                    continue
            rows.append({
                "item_id": item_id,
                "table": table,
                "column": column,
                "field": field,
                "before": before,
                "after": value,
                "changed": before != value,
                "client_field": next(iter(client_patch), None),
                "client_available": client_available,
            })
    finally:
        db.close()
    changed = [r for r in rows if r["changed"]]
    return {
        "field": field,
        "value": value,
        "items": rows,
        "item_count": len(rows),
        "changed_count": len(changed),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors and bool(changed),
        "safe_fields": sorted(BATCH_SAFE_FIELDS),
        "notes": [
            "batch editing is limited to fields already proven by single-item server/client reconciliation",
            "all items are validated before the first write",
            "apply uses one SQL transaction and one multi-item backup envelope",
        ],
    }


def apply_batch_edit(item_ids, field, value, comment=""):
    """Apply one proven-safe field/value across many items as one rollback-safe operation."""
    preview = preview_batch_edit(item_ids, field, value)
    if preview["errors"]:
        raise ValueError("batch validation failed: " + "; ".join(f"{e['item_id']}: {e['message']}" for e in preview["errors"]))
    changed = [r for r in preview["items"] if r["changed"]]
    if not changed:
        raise ValueError("batch contains no actual changes")

    table, column = BATCH_SAFE_FIELDS[field]
    db = _item_db(); cu = db.cursor()
    backup_items = []
    patched_snapshots = []
    sqls = []
    try:
        for row in changed:
            item_id = row["item_id"]
            op = _capture(cu, table, [item_id])
            client_snapshot = None
            try:
                client_snapshot = dat.capture_client_record(item_id)
            except Exception:
                client_snapshot = None
            backup_items.append({"item_id": item_id, "ops": [op], "client_record": client_snapshot})

        bid = _save_batch_backup(backup_items, field, value, comment)

        for row in changed:
            item_id = row["item_id"]
            cu.execute(f"update {table} set {column}=%s where {TABLES[table][0]}=%s", (value, item_id))
            sqls.append(f"UPDATE {table} SET {column}={lit(value)} WHERE {TABLES[table][0]}={item_id};")
            client_patch = _map_to_client_fields(table, {column: value})
            if client_patch and row["client_available"]:
                snapshot = next((x["client_record"] for x in backup_items if x["item_id"] == item_id), None)
                dat.patch_client_item(item_id, client_patch)
                if snapshot:
                    patched_snapshots.append(snapshot)

        db.commit()
    except Exception:
        try:
            db.rollback()
        finally:
            db.close()
        for snap in reversed(patched_snapshots):
            try:
                dat.restore_client_record(snap)
            except Exception:
                pass
        raise
    db.close()
    _journal(comment or f"batch edit {field}={value}", [f"-- batch backup {bid}", *sqls])
    return {
        "backup": bid,
        "field": field,
        "value": value,
        "changed_count": len(changed),
        "item_ids": [r["item_id"] for r in changed],
        "sql": "\n".join(sqls),
        "preview": preview,
    }


def restore_batch_backup(bid, comment=""):
    """Restore all items in one batch envelope using one SQL transaction."""
    path = BACKUPS / f"{bid}.json"
    b = json.loads(path.read_text())
    if b.get("kind") != "batch":
        raise ValueError(f"backup {bid} is not a batch backup")
    items = b.get("items") or []
    if not items:
        raise ValueError("batch backup contains no items")

    current = []
    db = _item_db(); cu = db.cursor()
    restored_dat = []
    try:
        for entry in items:
            item_id = int(entry["item_id"])
            ops = entry.get("ops") or []
            cur_ops = [_capture(cu, op["table"], op["key"]) for op in ops]
            try:
                cur_client = dat.capture_client_record(item_id)
            except Exception:
                cur_client = None
            current.append({"item_id": item_id, "ops": cur_ops, "client_record": cur_client})

        undo_id = _save_batch_backup(current, b.get("metadata", {}).get("field", "restore"), b.get("metadata", {}).get("value"), comment or f"before restoring {bid}")

        for entry in items:
            for op in entry.get("ops") or []:
                table = op["table"]
                keys = op["key"]
                saved = op.get("row")
                pk = _pk_for(table)
                where = " and ".join(f"{k}=%s" for k in pk)
                if saved is None:
                    cu.execute(f"delete from {table} where {where}", tuple(keys))
                else:
                    existing = _fetch(cu, table, keys)
                    if existing is None:
                        cols = list(saved)
                        cu.execute(
                            f"insert into {table} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})",
                            tuple(saved[c] for c in cols),
                        )
                    else:
                        cols = [c for c in saved if c not in pk]
                        cu.execute(
                            f"update {table} set {', '.join(c+'=%s' for c in cols)} where {where}",
                            tuple(saved[c] for c in cols) + tuple(keys),
                        )
            snap = entry.get("client_record")
            if snap:
                dat.restore_client_record(snap)
                restored_dat.append(int(entry["item_id"]))
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        for entry in reversed(current):
            snap = entry.get("client_record")
            if snap:
                try:
                    dat.restore_client_record(snap)
                except Exception:
                    pass
        raise
    db.close()
    _journal(comment or f"restore batch backup {bid}", [f"-- undo batch backup {undo_id}", f"-- restored {len(items)} item(s)"])
    return {"source_backup": bid, "backup": undo_id, "restored_count": len(items), "client_restored": restored_dat}




def reconcile_item(item_id, field, direction, comment=""):
    """Explicitly reconcile one confirmed overlapping field; item_type is diagnostic-only."""
    item_id = int(item_id)
    if field not in RECONCILE_SERVER_FIELDS:
        raise ValueError(f"field {field!r} is not an explicitly reconcilable overlap")
    if direction not in ("server_to_client", "client_to_server"):
        raise ValueError("direction must be server_to_client or client_to_server")
    data = get_item(item_id)
    row = next((x for x in data["comparison"]["fields"] if x["field"] == field), None)
    if row is None:
        raise ValueError(f"no decoded server/client comparison is available for {field}")
    table, column = RECONCILE_SERVER_FIELDS[field]

    if direction == "client_to_server":
        return save_item_atomic(item_id, {table: {column: _client_jobs_to_server(row["client"]) if field == "jobs" else row["client"]}}, None, comment or f"reconcile {field}: client -> server")

    current = dat.capture_client_record(item_id)
    if current is None:
        raise ValueError("no client DAT record is available to reconcile")
    bid = _save_backup(
        f"reconcile {field} server -> client", item_id, [], client_snapshot=current,
        metadata={
            "action_type": "reconcile", "comment": comment or "",
            "summary": f"{field}: client {row['client']} -> server {row['server']}",
            "field_changes": [{"table": "client_dat", "field": field, "before": row["client"], "after": row["server"]}],
            "dat_touched": True,
        },
    )
    client_key = {
        "stack": "stack", "slots": "slots", "damage": "dmg",
        "flags": "flags", "level": "level", "jobs": "jobs",
        "delay": "delay", "skill": "skill",
    }[field]
    patch = {client_key: _server_jobs_to_client(row["server"]) if field == "jobs" else row["server"]}
    dat.validate_client_patch(item_id, patch)
    report = dat.patch_client_item(item_id, patch)
    _journal(comment or f"reconcile {field}: server -> client", [
        f"-- backup {bid}",
        f"-- client DAT {client_key}: {row['client']} -> {row['server']}",
    ])
    return {"backup": bid, "field": field, "direction": direction, "client": report}

def validate_item_changes(item_id, tables, effects=None):
    """Validate a proposed table patch without writing anything."""
    item_id = int(item_id)
    db = _item_db(); cu = db.cursor()
    try:
        rows = {}
        for table in TABLES:
            row = _fetch(cu, table, [item_id])
            if row is not None:
                rows[table] = row
        for table, fields in (tables or {}).items():
            if table not in TABLES:
                raise ValueError(f"unknown item table {table!r}")
            if table not in rows:
                raise ValueError(f"{table} row does not exist for item {item_id}")
            cols = _cols(cu, table)
            bad = [k for k in fields if k not in cols]
            if bad:
                raise ValueError(f"{table} has no column(s): {', '.join(bad)}")
            rows[table] = {**rows[table], **fields}
    finally:
        db.close()
    client = None
    try:
        rec = dat.read_client_item(item_id)
        client = dat.item_to_dict(rec) if rec is not None else None
    except Exception:
        client = None
    result = validate_item_state(rows, client)
    desired_effects = _normalize_effects(effects) if effects is not None else None
    if desired_effects is not None:
        result["effect_counts"] = {k: len(v) for k, v in desired_effects.items()}
        result["warnings"].extend(_effect_validation(desired_effects))
    result["comparison"] = compare_server_client(rows, client)
    return result

def save_item_atomic(item_id, tables, effects=None, comment=""):
    """Save changed one-row item tables as one backed-up SQL transaction and one client-DAT patch.

    tables is {table: {column: value}} and should contain only fields the caller intends to
    change. All table/column/existence validation occurs before any write. If overlapping client
    fields exist, the DAT patch is first validated in memory, then written once while the SQL
    transaction is still open. If the final DB commit fails, the DAT write is rolled back from
    its just-created snapshot (or a newly-created Pivot destination is removed).
    """
    item_id = int(item_id)
    if not isinstance(tables, dict):
        raise ValueError("tables must be an object")
    desired_effects = _normalize_effects(effects) if effects is not None else None

    db = _item_db()
    cu = db.cursor()
    ops = []
    normalized = {}
    client_fields = {}
    client_available = False
    try:
        for table, fields in tables.items():
            if table not in TABLES:
                raise ValueError(f"unknown item table {table!r}")
            if not isinstance(fields, dict) or not fields:
                continue
            key = TABLES[table][0]
            op = _capture(cu, table, [item_id])
            if op["row"] is None:
                raise ValueError(f"{table}.{key}={item_id} not found")
            cols = _cols(cu, table)
            bad = [k for k in fields if k not in cols]
            if bad:
                raise ValueError(f"{table} has no column(s): {', '.join(bad)}")
            normalized[table] = dict(fields)
            ops.append(op)
            client_fields.update(_map_to_client_fields(table, fields))

        effect_changes = _effect_changes(cu, item_id, desired_effects) if desired_effects is not None else []
        if not normalized and not effect_changes:
            raise ValueError("no item changes supplied")

        proposed = {}
        for table in TABLES:
            row = _fetch(cu, table, [item_id])
            if row is not None:
                proposed[table] = row
        for table, fields in normalized.items():
            proposed[table] = {**proposed[table], **fields}
        validation = validate_item_state(proposed, None)
        if desired_effects is not None:
            validation["warnings"].extend(_effect_validation(desired_effects))
        if validation["errors"]:
            raise ValueError("; ".join(v["message"] for v in validation["errors"]))

        if client_fields:
            try:
                client_available = dat.read_client_item(item_id) is not None
            except Exception:
                client_available = False
            if client_available:
                dat.validate_client_patch(item_id, client_fields)

        for table, keyvals, cur, want in effect_changes:
            ops.append({"table": table, "key": list(keyvals), "row": cur})
        field_change_meta = [
            {"table": table, "field": field,
             "before": (next((op["row"] for op in ops if op["table"] == table and op.get("row") is not None), {}) or {}).get(field),
             "after": value}
            for table, fields in normalized.items() for field, value in fields.items()
        ]
        effect_change_meta = [
            {"table": table, "key": list(keyvals), "before": cur, "after": want}
            for table, keyvals, cur, want in effect_changes
        ]
        summary_bits = []
        if field_change_meta:
            summary_bits.append(f"{len(field_change_meta)} field change(s)")
        if effect_change_meta:
            summary_bits.append(f"{len(effect_change_meta)} effect change(s)")
        bid = _save_backup(
            f"atomic edit item {item_id}", item_id, ops,
            metadata={
                "action_type": "edit", "comment": comment or "",
                "summary": " · ".join(summary_bits),
                "field_changes": field_change_meta,
                "effect_changes": effect_change_meta,
                "dat_touched": bool(client_fields and client_available),
            },
        )
        sqls = []
        for table, fields in normalized.items():
            key = TABLES[table][0]
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            cu.execute(
                f"update {table} set {set_clause} where {key}=%s",
                tuple(fields.values()) + (item_id,),
            )
            sqls.append(
                f"UPDATE {table} SET "
                + ", ".join(f"{k}={lit(v)}" for k, v in fields.items())
                + f" WHERE {key}={item_id};"
            )
        sqls.extend(_apply_effect_changes(cu, item_id, effect_changes))

        client_report = None
        if client_fields and client_available:
            client_report = dat.patch_client_item(item_id, client_fields)
        elif client_fields:
            client_report = {
                "ok": False,
                "skipped": True,
                "error": "no client DAT record found; server transaction saved without client sync",
                "fields": list(client_fields),
            }

        try:
            db.commit()
        except Exception:
            db.rollback()
            if client_report and client_report.get("ok"):
                import shutil
                dat_path = Path(client_report["dat"])
                backup_path = client_report.get("backup_path")
                if backup_path:
                    shutil.copy2(backup_path, dat_path)
                elif not client_report.get("target_existed", True) and dat_path.exists():
                    dat_path.unlink()
            raise
    except Exception:
        try:
            db.rollback()
        finally:
            db.close()
        raise
    db.close()

    before = {op["table"]: op["row"] for op in ops}
    notes = [f"-- atomic item backup {bid}"]
    for table, fields in normalized.items():
        old = before[table]
        notes.append("-- " + table + " was (" + ", ".join(f"{k} {old.get(k)}" for k in fields) + ")")
    _journal(comment, notes + sqls)
    return {
        "backup": bid,
        "tables": sorted(normalized),
        "effect_changes": len(effect_changes),
        "sql": "\n".join(sqls),
        "client": client_report,
        "validation": validation,
    }

def update_item(item_id, table, fields, comment="", sync_client=True):
    """Update one row of one item_* table live, backed up + journalled. `fields` is a dict of
    column -> new value for that table only. If sync_client and the table/fields overlap with a
    field the client DAT also stores (level, jobs, slots, races, superior_level for item_equipment;
    dmg/delay/skill for item_weapon; flags/stack for item_basic), the client DAT record for this
    item is patched too, so the two stay in agreement."""
    item_id = int(item_id)
    if table not in TABLES:
        raise ValueError(f"unknown item table {table!r}")
    key = TABLES[table][0]
    db = _item_db(); cu = db.cursor()
    op = _capture(cu, table, [item_id])
    if op["row"] is None:
        db.close()
        raise ValueError(f"{table}.{key}={item_id} not found")
    cols = _cols(cu, table)
    bad = [k for k in fields if k not in cols]
    if bad:
        db.close()
        raise ValueError(f"{table} has no column(s): {', '.join(bad)}")
    bid = _save_backup(
        f"edit {table} {item_id}", item_id, [op],
        metadata={
            "action_type": "edit", "comment": comment or "",
            "summary": f"{table}: {len(fields)} field change(s)",
            "field_changes": [{"table": table, "field": k, "before": op["row"].get(k), "after": v} for k, v in fields.items()],
            "dat_touched": bool(sync_client and _map_to_client_fields(table, fields)),
        },
    )
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cu.execute(f"update {table} set {set_clause} where {key}=%s", tuple(fields.values()) + (item_id,))
    db.commit(); db.close()
    o = op["row"]
    was = ", ".join(f"{k} {o.get(k)}" for k in fields)
    sql = f"UPDATE {table} SET {', '.join(f'{k}={lit(v)}' for k, v in fields.items())} WHERE {key}={item_id};"
    _journal(comment, [f"-- was ({was})  backup {bid}", sql])

    client_report = None
    if sync_client:
        client_fields = _map_to_client_fields(table, fields)
        if client_fields:
            try:
                client_report = dat.patch_client_item(item_id, client_fields)
            except ValueError as ex:
                client_report = {"ok": False, "error": str(ex)}
    return {"sql": sql, "backup": bid, "client": client_report}


def _map_to_client_fields(table, fields):
    """Translate a server-column dict into the equivalent item_dat_tools field names, for the
    subset of columns that really exist on both sides. Anything server-only (MId, shieldSize,
    scriptType, rslot, ilvl_skill/parry/macc, hit, unlock_points, subskill, dmgType, aH,
    BaseSell, NoSale, sortname, validTargets/activation/animation/...) is deliberately left
    server-only -- the client record has no field for it, so there's nothing to sync."""
    out = {}
    if table == "item_equipment":
        for k in ("level", "jobs", "slot", "shieldSize"):
            if k in fields:
                v = _server_jobs_to_client(fields[k]) if k == "jobs" else fields[k]
                out["slots" if k == "slot" else ("shield_size" if k == "shieldSize" else k)] = v
    elif table == "item_weapon":
        for k in ("dmg", "delay", "skill"):
            if k in fields:
                out[k] = fields[k]
    elif table == "item_basic":
        if "flags" in fields:
            out["flags"] = fields["flags"]
        if "stackSize" in fields:
            out["stack"] = fields["stackSize"]
        # item_basic.name is NOT real display text -- it's the internal lowercase_underscore
        # name (matches sortname), same style as item_equipment/item_weapon.name. Client DAT's
        # name/singular/plural/description come from item_dat_tools' own text fields, never from
        # here. A prior version of this mapping forwarded item_basic.name into the client DAT's
        # 'name' field on every save (even when unchanged, since the edit UI always submits the
        # whole row) -- patch_client_item's text-key path then defaulted singular/plural from
        # that underscore name AND blanked description (no description supplied), corrupting the
        # item's real client-visible name/flavor text. See item 10478 (Euxine Coat +3), 2026-09-24.
    return out


def create_item(category, item_type, entry, effects=None, comment=""):
    """Allocate a real free client-DAT slot in `category` (e.g. 'Armor_1', 'Weapons',
    'Consumable' -- see item_dat_tools.ITEM_DATS), write the new item record there, then insert
    matching rows into item_basic + whichever type-table(s) TYPE_TABLES[item_type] says this
    item_type uses, all at that SAME id. Never invents an id -- the id comes only from a real
    free DAT slot found by item_dat_tools.free_slots(), per CLAUDE.md's core rule."""
    item_type = int(item_type)
    client_entry = entry
    if entry.get("jobs") is not None:
        client_entry = {**entry, "jobs": _server_jobs_to_client(entry["jobs"])}  # draft carries the server-style mask
    client_result = dat.inject_client_item(category, client_entry)
    item_id = client_result["item_id"]

    desired_effects = _normalize_effects(effects) if effects is not None else {"mods": [], "pet_mods": [], "latents": []}
    db = _item_db(); cu = db.cursor()
    cu.execute("select 1 from item_basic where itemid=%s", (item_id,))
    if cu.fetchone():
        db.close()
        raise ValueError(f"item_basic already has itemid={item_id} -- DAT slot and DB are out of sync, investigate before retrying")

    basic_row = {
        "itemid": item_id, "subid": 0,
        "name": entry.get("name", f"item_{item_id}"), "sortname": entry.get("singular", entry.get("name", ""))[:20],
        "stackSize": int(entry.get("stack", 1)), "flags": int(entry.get("flags", dat.encode_flags(entry.get("flags_decoded", [])))),
        "aH": int(entry.get("aH", 99)), "NoSale": int(entry.get("NoSale", 0)), "BaseSell": int(entry.get("BaseSell", 0)),
    }
    inserts = [("item_basic", basic_row)]

    for table in TYPE_TABLES.get(item_type, []):
        if table == "item_equipment":
            inserts.append(("item_equipment", {
                "itemId": item_id, "name": basic_row["name"], "level": int(entry.get("level", 1)),
                "ilevel": int(entry.get("ilevel", 0)), "jobs": int(entry.get("jobs", dat.encode_jobs(entry.get("jobs_list", [])))),
                "MId": int(entry.get("MId", 0)), "shieldSize": int(entry.get("shield_size", 0)),
                "scriptType": int(entry.get("scriptType", 0)), "slot": int(entry.get("slots", entry.get("slot", 0))),
                "rslot": int(entry.get("rslot", 0)),
            }))
        elif table == "item_weapon":
            inserts.append(("item_weapon", {
                "itemId": item_id, "name": basic_row["name"], "skill": int(entry.get("skill", 0)),
                "subskill": int(entry.get("subskill", 0)), "ilvl_skill": int(entry.get("ilvl_skill", 0)),
                "ilvl_parry": int(entry.get("ilvl_parry", 0)), "ilvl_macc": int(entry.get("ilvl_macc", 0)),
                "dmgType": int(entry.get("dmgType", entry.get("kind", 0))), "hit": int(entry.get("hit", 1)),
                "delay": int(entry.get("delay", 0)), "dmg": int(entry.get("dmg", 0)),
                "unlock_points": int(entry.get("unlock_points", 0)),
            }))
        elif table == "item_usable":
            inserts.append(("item_usable", {
                "itemid": item_id, "name": basic_row["name"], "validTargets": int(entry.get("validTargets", 1)),
                "activation": int(entry.get("activation", 0)), "animation": int(entry.get("animation", 0)),
                "animationTime": int(entry.get("animationTime", 0)), "maxCharges": int(entry.get("max_charges", entry.get("maxCharges", 0))),
                "useDelay": int(entry.get("use_delay", entry.get("useDelay", 0))), "reuseDelay": int(entry.get("reuse_delay", entry.get("reuseDelay", 0))),
                "aoe": int(entry.get("aoe", 0)),
            }))
        elif table == "item_puppet":
            inserts.append(("item_puppet", {
                "itemid": item_id, "name": basic_row["name"], "slot": int(entry.get("puppet_slot", entry.get("slot", 0))),
                "element": int(entry.get("element_charge", entry.get("element", 0))),
            }))
        elif table == "item_furnishing":
            inserts.append(("item_furnishing", {
                "itemid": item_id, "name": basic_row["name"], "storage": int(entry.get("storage", 0)),
                "moghancement": int(entry.get("moghancement", 0)), "element": int(entry.get("element", 0)),
                "aura": int(entry.get("aura", 0)),
            }))

    lines = []
    ops = []
    pre_client = {
        "item_id": item_id, "category": client_result["category"], "dat_ui": client_result["dat_ui"],
        "record_index": client_result["record_index"], "format": client_result["format"],
        "target": client_result["target"], "target_existed": True,
        "record_hex": client_result["previous_record_hex"],
    }
    bid = None
    try:
        for table, row in inserts:
            cols = list(row)
            cu.execute(f"insert into {table} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(row[col] for col in cols))
            lines.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(lit(row[col]) for col in cols)});")
            ops.append({"table": table, "key": [item_id], "row": None})

        effect_changes = _effect_changes(cu, item_id, desired_effects)
        for table, keyvals, _cur, _want in effect_changes:
            ops.append({"table": table, "key": list(keyvals), "row": None})
        lines.extend(_apply_effect_changes(cu, item_id, effect_changes))

        bid = _save_backup(
            f"create item {item_id} ({basic_row['name']}) in {category}",
            item_id, ops, client_snapshot=pre_client,
            metadata={
                "action_type": "create", "comment": comment or "",
                "summary": f"created {len(inserts)} SQL row(s) + {len(effect_changes)} effect row(s)",
                "effect_changes": [
                    {"table": table, "key": list(keyvals), "before": cur, "after": want}
                    for table, keyvals, cur, want in effect_changes
                ],
                "dat_touched": True,
            },
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            dat.restore_client_record(pre_client)
            raise
    except Exception:
        try:
            db.rollback()
        finally:
            db.close()
        try:
            dat.restore_client_record(pre_client)
        except Exception:
            pass
        raise
    db.close()

    _journal(comment or f"CREATE item {item_id} in {category}", [f"-- backup {bid}", f"-- client DAT: {client_result}"] + lines)
    return {
        "item_id": item_id, "backup": bid, "sql": "\n".join(lines), "client": client_result,
        "effect_changes": len(effect_changes),
    }

def clone_template(item_id):
    """Build a create_item()-ready {category, item_type, entry} template from an existing item,
    so the New Item form can start from a real, verified example instead of a blank slate needing
    every field hand-typed. Pulls display text/level/jobs/flags/dmg/etc from the source item's
    client DAT record (authoritative -- what the game actually reads) and the handful of
    server-only columns the client record has no field for (aH/NoSale/BaseSell, ilvl_skill/parry/
    macc, hit, subskill, unlock_points, validTargets/activation/animation/animationTime/
    maxCharges/useDelay/reuseDelay/aoe, puppet slot/element, storage/moghancement/element/aura)
    from SQL. Never invents anything -- every value traces back to the source item's own real
    rows/record, same as every other id/value in this project."""
    item_id = int(item_id)
    data = get_item(item_id)
    client = data.get("client")
    if client is None:
        raise ValueError(f"item {item_id} has no client DAT record to clone from")
    basic = data["server"].get("item_basic", {})
    equip = data["server"].get("item_equipment", {})
    weapon = data["server"].get("item_weapon", {})
    usable = data["server"].get("item_usable", {})
    puppet = data["server"].get("item_puppet", {})
    furnishing = data["server"].get("item_furnishing", {})

    entry = {
        "name": client.get("name", ""), "singular": client.get("singular", ""),
        "plural": client.get("plural", ""), "description": client.get("description", ""),
        "stack": client.get("stack", 1), "flags_decoded": client.get("flags_decoded", []),
        "aH": basic.get("aH", 99), "NoSale": basic.get("NoSale", 0), "BaseSell": basic.get("BaseSell", 0),
    }
    if "level" in client:
        entry.update({
            "level": client.get("level", 1), "jobs_list": client.get("jobs_list", []),
            "slots": client.get("slots", 0), "shield_size": equip.get("shieldSize", 0),
            "scriptType": equip.get("scriptType", 0), "rslot": equip.get("rslot", 0),
            "MId": equip.get("MId", 0), "ilevel": equip.get("ilevel", 0),
        })
    if client.get("type") == 4:
        entry.update({
            "skill": client.get("skill", 0), "dmg": client.get("dmg", 0), "delay": client.get("delay", 0),
            "dmgType": client.get("kind", 0),
            "subskill": weapon.get("subskill", 0), "ilvl_skill": weapon.get("ilvl_skill", 0),
            "ilvl_parry": weapon.get("ilvl_parry", 0), "ilvl_macc": weapon.get("ilvl_macc", 0),
            "hit": weapon.get("hit", 1), "unlock_points": weapon.get("unlock_points", 0),
        })
    if usable:
        entry.update({k: usable.get(k, 0) for k in
                       ("validTargets", "activation", "animation", "animationTime",
                        "maxCharges", "useDelay", "reuseDelay", "aoe")})
    if puppet:
        entry.update({"puppet_slot": puppet.get("slot", 0), "element_charge": puppet.get("element", 0)})
    if furnishing:
        entry.update({k: furnishing.get(k, 0) for k in ("storage", "moghancement", "element", "aura")})

    return {"category": client.get("category", ""), "item_type": client.get("type", 0), "entry": entry,
            "source_item_id": item_id, "mods": data["mods"], "pet_mods": data["pet_mods"], "latents": data["latents"]}


def delete_item(item_id, comment="", clear_dat=False):
    """Remove an item's rows from every item_* table it appears in. `clear_dat=True` also
    directly blanks the item's client-DAT record via item_dat_tools.delete_client_item()
    (its own DAT snapshot is taken first) so the slot immediately reads as free again;
    left False, the DAT record is not touched (it stays orphaned server-side until cleared
    separately -- matching zone_edit.py's stance of surfacing rather than auto-cleaning
    ambiguous state)."""
    item_id = int(item_id)
    db = _item_db(); cu = db.cursor()
    ops = []
    for table in TABLES:
        op = _capture(cu, table, [item_id])
        if op["row"] is not None:
            ops.append(op)
    cu.execute("select modId, value from item_mods where itemId=%s", (item_id,))
    mod_rows = cu.fetchall()
    for mod_id, value in mod_rows:
        ops.append({"table": "item_mods", "key": [item_id, mod_id],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value}})
    cu.execute("select modId, value, petType from item_mods_pet where itemId=%s", (item_id,))
    pet_mod_rows = cu.fetchall()
    for mod_id, value, pet_type in pet_mod_rows:
        ops.append({"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value, "petType": pet_type}})
    cu.execute("select modId, value, latentId, latentParam from item_latents where itemId=%s", (item_id,))
    latent_rows = cu.fetchall()
    for mod_id, value, latent_id, latent_param in latent_rows:
        ops.append({"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value, "latentId": latent_id, "latentParam": latent_param}})
    if not ops:
        db.close()
        raise ValueError(f"no item_* rows found for itemid={item_id}")
    bid = _save_backup(
        f"delete item {item_id}", item_id, ops,
        metadata={
            "action_type": "delete", "comment": comment or "",
            "summary": f"deleted {len(ops)} SQL/effect row(s)" + (" and cleared client DAT" if clear_dat else ""),
            "dat_touched": bool(clear_dat),
        },
    )
    lines = []
    for op in ops:
        if op["table"] == "item_mods":
            mod_id = op["key"][1]
            cu.execute("delete from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
            lines.append(f"DELETE FROM item_mods WHERE itemId={item_id} AND modId={mod_id};")
            continue
        if op["table"] == "item_mods_pet":
            mod_id, pet_type = op["key"][1], op["key"][2]
            cu.execute("delete from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
            lines.append(f"DELETE FROM item_mods_pet WHERE itemId={item_id} AND modId={mod_id} AND petType={pet_type};")
            continue
        if op["table"] == "item_latents":
            mod_id, value, latent_id, latent_param = op["key"][1], op["key"][2], op["key"][3], op["key"][4]
            cu.execute("delete from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
                       (item_id, mod_id, value, latent_id, latent_param))
            lines.append(f"DELETE FROM item_latents WHERE itemId={item_id} AND modId={mod_id} AND value={value} AND latentId={latent_id} AND latentParam={latent_param};")
            continue
        table, key = op["table"], TABLES[op["table"]][0]
        cu.execute(f"delete from {table} where {key}=%s", (item_id,))
        lines.append(f"DELETE FROM {table} WHERE {key}={item_id};")
    dat_result = None
    dat_warning = "client DAT record left in place -- clear it separately if you want the slot to read as free"
    try:
        if clear_dat:
            dat_result = dat.delete_client_item(item_id)
            dat_warning = None
        try:
            db.commit()
        except Exception:
            db.rollback()
            snap = json.loads((BACKUPS / f"{bid}.json").read_text()).get("client_record")
            if snap:
                dat.restore_client_record(snap)
            raise
    except Exception:
        try:
            db.rollback()
        finally:
            db.close()
        raise
    db.close()
    journal_lines = [f"-- backup {bid}"]
    if dat_result:
        journal_lines.append(f"-- client DAT cleared: {dat_result}")
    _journal(comment, journal_lines + lines)
    result = {"sql": "\n".join(lines), "backup": bid, "client_dat_cleared": dat_result is not None}
    if dat_warning:
        result["warning"] = dat_warning
    return result
