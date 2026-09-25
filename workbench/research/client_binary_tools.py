"""Read-only typed research over precomputed client binary indexes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workbench.client.binary_index import binary_header_evidence_id, binary_record_evidence_id, binary_string_corpus_evidence_id
from workbench.client.binary_deep import byte_search as deep_byte_search, function_candidates as deep_function_candidates, xrefs as deep_xrefs
from workbench.client.binary_diff import diff_binary_indexes


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
                "layout_warnings":payload.get("layout_warnings",[]),
                "authority":"CLIENT_BINARY",
                "evidence_id":binary_header_evidence_id(payload),
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
                rows.append({**row,"evidence_id":binary_record_evidence_id(field,row)})
                if len(rows)>=limit:
                    break
            return {
                "status":"OK","binary":info,"query":query,field:rows,
                "evidence_ids":[row["evidence_id"] for row in rows],
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
                    "evidence_id":binary_string_corpus_evidence_id(payload),
                })
                if len(matches)>=limit:
                    return {
                        "status":"OK","query":query,"matches":matches,"truncated":True,
                        "evidence_ids":sorted({row["evidence_id"] for row in matches}),
                    }
        return {
            "status":"OK","query":query,"matches":matches,"truncated":False,
            "evidence_ids":sorted({row["evidence_id"] for row in matches}),
        }

    def binary_diff(self, left: str, right: str, *, max_items: int = 500) -> dict[str,Any]:
        resolved={}
        for path,payload in self._indexes():
            info=payload.get("binary") or {}
            keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(path)}
            for query in (left,right):
                if query in resolved:
                    continue
                if query in keys or any(query.lower() in key.lower() for key in keys if key):
                    resolved[query]=(path,payload)
        if left not in resolved or right not in resolved:
            return {
                "status":"NOT_FOUND",
                "missing":[query for query in (left,right) if query not in resolved],
            }
        result=diff_binary_indexes(resolved[left][1],resolved[right][1],max_items=max_items)
        result["evidence_ids"]=sorted({
            binary_header_evidence_id(resolved[left][1]),
            binary_header_evidence_id(resolved[right][1]),
            binary_string_corpus_evidence_id(resolved[left][1]),
            binary_string_corpus_evidence_id(resolved[right][1]),
        })
        result["authority"]="CLIENT_BINARY"
        return result

    def _binary_source(self, binary: str):
        for index_path,payload in self._indexes():
            info=payload.get("binary") or {}
            keys={str(info.get("label") or ""),str(info.get("filename") or ""),str(info.get("sha256") or ""),str(index_path)}
            if binary not in keys and not any(binary.lower() in key.lower() for key in keys if key):
                continue
            raw=str(info.get("path") or "")
            candidates=[]
            if raw:
                source=Path(raw)
                candidates.append(source)
                if not source.is_absolute():
                    candidates.append(index_path.parent/source)
            for source in candidates:
                if source.exists() and source.is_file():
                    return index_path,payload,source
            return index_path,payload,None
        return None,None,None

    def byte_search(
        self,
        binary: str,
        pattern: str,
        *,
        section: str | None = None,
        executable_only: bool = False,
        limit: int = 500,
        context_bytes: int = 8,
    ) -> dict[str,Any]:
        _index,payload,source=self._binary_source(binary)
        if payload is None:
            return {"status":"NOT_FOUND","binary":binary}
        info=payload.get("binary") or {}
        if source is None:
            return {
                "status":"BINARY_UNAVAILABLE","binary":info,
                "error":"The indexed source binary is not accessible at its recorded path in this runtime.",
                "authority":"CLIENT_BINARY",
                "evidence_ids":[binary_header_evidence_id(payload)],
            }
        result=deep_byte_search(source,pattern,section=section,executable_only=executable_only,
            max_matches=limit,context_bytes=context_bytes)
        result.update({
            "binary":info,
            "authority":"CLIENT_BINARY",
            "evidence_ids":[binary_header_evidence_id(payload)],
        })
        return result

    def xrefs(
        self,
        binary: str,
        *,
        rva: int | None = None,
        va: int | None = None,
        offset: int | None = None,
        executable_only: bool = True,
        include_pointers: bool = True,
        limit: int = 2000,
    ) -> dict[str,Any]:
        _index,payload,source=self._binary_source(binary)
        if payload is None:
            return {"status":"NOT_FOUND","binary":binary}
        info=payload.get("binary") or {}
        if source is None:
            return {
                "status":"BINARY_UNAVAILABLE","binary":info,
                "error":"The indexed source binary is not accessible at its recorded path in this runtime.",
                "authority":"CLIENT_BINARY",
                "evidence_ids":[binary_header_evidence_id(payload)],
            }
        result=deep_xrefs(source,rva=rva,va=va,offset=offset,executable_only=executable_only,
            include_pointers=include_pointers,max_results=limit)
        result.update({
            "binary":info,
            "authority":"CLIENT_BINARY",
            "evidence_ids":[binary_header_evidence_id(payload)],
        })
        return result

    def function_candidates(self, binary: str, *, limit: int = 5000) -> dict[str,Any]:
        _index,payload,source=self._binary_source(binary)
        if payload is None:
            return {"status":"NOT_FOUND","binary":binary}
        info=payload.get("binary") or {}
        if source is None:
            return {
                "status":"BINARY_UNAVAILABLE","binary":info,
                "error":"The indexed source binary is not accessible at its recorded path in this runtime.",
                "authority":"CLIENT_BINARY",
                "evidence_ids":[binary_header_evidence_id(payload)],
            }
        result=deep_function_candidates(source,max_candidates=limit)
        result.update({
            "binary":info,
            "authority":"CLIENT_BINARY",
            "evidence_ids":[binary_header_evidence_id(payload)],
        })
        return result

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
                "evidence_ids":sorted({
                    binary_header_evidence_id(payload),
                    binary_string_corpus_evidence_id(payload),
                    *(
                        [binary_record_evidence_id("sections",section)]
                        if section is not None else []
                    ),
                }),
                "notes":["Address evidence is static mapping/context only; it does not infer function semantics."],
            }
        return {"status":"NOT_FOUND","binary":binary}
