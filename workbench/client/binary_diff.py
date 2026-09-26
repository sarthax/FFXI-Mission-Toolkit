"""Deterministic comparison of two precomputed client binary indexes."""
from __future__ import annotations

from typing import Any


def _key_import(row: dict[str,Any]) -> tuple:
    return (str(row.get("dll") or "").lower(),str(row.get("name") or ""),row.get("ordinal"))

def _key_export(row: dict[str,Any]) -> tuple:
    return (str(row.get("name") or ""),row.get("ordinal"))

def _key_string(row: dict[str,Any]) -> tuple:
    return (row.get("encoding"),row.get("text"))

def diff_binary_indexes(left: dict[str,Any], right: dict[str,Any], *, max_items: int = 500) -> dict[str,Any]:
    lb=dict(left.get("binary") or {})
    rb=dict(right.get("binary") or {})

    metadata_changes={}
    for key in (
        "file_size","client_build","pe_kind","machine","timestamp","characteristics",
        "subsystem","image_base","entry_point_rva","size_of_image",
    ):
        if lb.get(key)!=rb.get(key):
            metadata_changes[key]={"left":lb.get(key),"right":rb.get(key)}

    left_sections={row.get("name"):row for row in left.get("sections",[])}
    right_sections={row.get("name"):row for row in right.get("sections",[])}
    section_names=sorted(set(left_sections)|set(right_sections))
    section_changes=[]
    for name in section_names:
        l=left_sections.get(name); r=right_sections.get(name)
        if l!=r:
            section_changes.append({"name":name,"left":l,"right":r})

    def compare(field,keyfn):
        l={keyfn(row):row for row in left.get(field,[])}
        r={keyfn(row):row for row in right.get(field,[])}
        added=[r[key] for key in sorted(set(r)-set(l),key=str)]
        removed=[l[key] for key in sorted(set(l)-set(r),key=str)]
        return {
            "added":added[:max_items],
            "removed":removed[:max_items],
            "added_count":len(added),
            "removed_count":len(removed),
            "truncated":len(added)>max_items or len(removed)>max_items,
        }

    imports=compare("imports",_key_import)
    exports=compare("exports",_key_export)
    strings=compare("strings",_key_string)

    return {
        "schema":1,
        "kind":"CLIENT_BINARY_DIFF",
        "left":{"label":lb.get("label"),"filename":lb.get("filename"),"sha256":lb.get("sha256"),"client_build":lb.get("client_build")},
        "right":{"label":rb.get("label"),"filename":rb.get("filename"),"sha256":rb.get("sha256"),"client_build":rb.get("client_build")},
        "metadata_changes":metadata_changes,
        "section_changes":section_changes[:max_items],
        "section_change_count":len(section_changes),
        "imports":imports,
        "exports":exports,
        "strings":strings,
        "status":"DIFFERENT" if any((
            metadata_changes,section_changes,
            imports["added_count"],imports["removed_count"],
            exports["added_count"],exports["removed_count"],
            strings["added_count"],strings["removed_count"],
        )) else "EQUIVALENT_INDEX",
        "notes":[
            "Index diff is static evidence only; changed strings/imports/sections do not identify feature semantics by themselves.",
            "String comparison is by encoding+text rather than raw address so relocation alone does not appear as semantic drift.",
        ],
    }
