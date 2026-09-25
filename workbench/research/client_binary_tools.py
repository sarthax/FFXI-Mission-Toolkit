"""Read-only typed research over precomputed client binary indexes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ClientBinaryResearchReader:
    def __init__(self, indexes: list[Path] | tuple[Path,...]):
        self.index_paths=tuple(Path(p) for p in indexes)

    def _indexes(self):
        rows=[]
        for path in self.index_paths:
            if not path.exists():
                continue
            payload=json.loads(path.read_text(encoding="utf-8"))
            if payload.get("kind")=="CLIENT_BINARY_INDEX":
                rows.append((path,payload))
        return rows

    def binary_info(self, query: str | None = None) -> dict[str,Any]:
        matches=[]
        needle=(query or "").lower()
        for path,payload in self._indexes():
            binary=dict(payload.get("binary") or {})
            hay=" ".join(str(binary.get(k) or "") for k in ("label","filename","path","client_build","sha256")).lower()
            if needle and needle not in hay:
                continue
            matches.append({
                **binary,
                "index_path":str(path),
                "section_count":len(payload.get("sections",[])),
                "import_count":len(payload.get("imports",[])),
                "export_count":len(payload.get("exports",[])),
                "string_count":len(payload.get("strings",[])),
                "authority":"CLIENT_BINARY",
            })
        return {"status":"OK","query":query,"matches":matches}

    def sections(self, binary: str) -> dict[str,Any]:
        for path,payload in self._indexes():
            info=payload.get("binary") or {}
            keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(path)}
            if binary in keys or any(binary.lower() in key.lower() for key in keys if key):
                return {
                    "status":"OK",
                    "binary":info,
                    "sections":payload.get("sections",[]),
                    "authority":"CLIENT_BINARY",
                }
        return {"status":"NOT_FOUND","binary":binary}

    def imports(self, binary: str, *, query: str | None = None, limit: int = 100) -> dict[str,Any]:
        return self._symbol_table(binary,"imports",query,limit)

    def exports(self, binary: str, *, query: str | None = None, limit: int = 100) -> dict[str,Any]:
        return self._symbol_table(binary,"exports",query,limit)

    def _symbol_table(self,binary,field,query,limit):
        needle=(query or "").lower()
        for path,payload in self._indexes():
            info=payload.get("binary") or {}
            keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(path)}
            if binary not in keys and not any(binary.lower() in key.lower() for key in keys if key):
                continue
            rows=[]
            for row in payload.get(field,[]):
                hay=json.dumps(row,sort_keys=True).lower()
                if needle and needle not in hay:
                    continue
                rows.append(row)
                if len(rows)>=limit:
                    break
            return {
                "status":"OK","binary":info,"query":query,field:rows,
                "truncated":len(rows)>=limit,"authority":"CLIENT_BINARY",
            }
        return {"status":"NOT_FOUND","binary":binary}

    def string_search(
        self,
        query: str,
        *,
        binary: str | None = None,
        encoding: str | None = None,
        limit: int = 100,
        case_sensitive: bool = False,
    ) -> dict[str,Any]:
        if not query:
            return {"status":"ERROR","error":"query is required"}
        needle=query if case_sensitive else query.lower()
        matches=[]
        for path,payload in self._indexes():
            info=payload.get("binary") or {}
            if binary:
                keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(path)}
                if binary not in keys and not any(binary.lower() in key.lower() for key in keys if key):
                    continue
            for row in payload.get("strings",[]):
                if encoding and row.get("encoding")!=encoding:
                    continue
                text=str(row.get("text") or "")
                hay=text if case_sensitive else text.lower()
                if needle not in hay:
                    continue
                matches.append({
                    "binary":info.get("label") or info.get("filename"),
                    "sha256":info.get("sha256"),
                    **row,
                    "authority":"CLIENT_BINARY",
                    "confidence":"VERIFIED",
                })
                if len(matches)>=limit:
                    return {"status":"OK","query":query,"matches":matches,"truncated":True}
        return {"status":"OK","query":query,"matches":matches,"truncated":False}

    def address_evidence(
        self,
        binary: str,
        *,
        rva: int | None = None,
        offset: int | None = None,
    ) -> dict[str,Any]:
        if rva is None and offset is None:
            return {"status":"ERROR","error":"rva or offset is required"}
        for path,payload in self._indexes():
            info=payload.get("binary") or {}
            keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(path)}
            if binary not in keys and not any(binary.lower() in key.lower() for key in keys if key):
                continue
            target_rva=rva
            target_offset=offset
            section=None
            for sec in payload.get("sections",[]):
                if rva is not None:
                    span=max(int(sec.get("virtual_size") or 0),int(sec.get("raw_size") or 0))
                    if int(sec.get("virtual_address") or 0)<=rva<int(sec.get("virtual_address") or 0)+span:
                        section=sec
                        delta=rva-int(sec["virtual_address"])
                        if delta<int(sec.get("raw_size") or 0):
                            target_offset=int(sec["raw_offset"])+delta
                        break
                else:
                    if int(sec.get("raw_offset") or 0)<=offset<int(sec.get("raw_offset") or 0)+int(sec.get("raw_size") or 0):
                        section=sec
                        target_rva=int(sec["virtual_address"])+(offset-int(sec["raw_offset"]))
                        break
            nearby=[
                row for row in payload.get("strings",[])
                if target_offset is not None and abs(int(row.get("offset") or 0)-target_offset)<=64
            ][:20]
            return {
                "status":"OK",
                "binary":info,
                "rva":target_rva,
                "va":(int(info.get("image_base") or 0)+target_rva) if target_rva is not None else None,
                "offset":target_offset,
                "section":section,
                "nearby_strings":nearby,
                "authority":"CLIENT_BINARY",
                "notes":["Address evidence is static mapping/context only; it does not infer function semantics."],
            }
        return {"status":"NOT_FOUND","binary":binary}
