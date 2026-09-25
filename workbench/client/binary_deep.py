"""Dependency-free bounded static analysis helpers for client PE binaries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Any, Iterable

from .binary_index import PEImage


MAX_PATTERN_BYTES=256
DEFAULT_MAX_MATCHES=500
DEFAULT_MAX_XREFS=2000
DEFAULT_MAX_FUNCTION_CANDIDATES=5000


class BinaryAnalysisError(ValueError):
    pass


def parse_hex_pattern(pattern: str) -> tuple[int | None, ...]:
    """Parse a bounded hex pattern such as 'E8 ?? ?? ?? ?? 83 C4'."""
    tokens=[token for token in pattern.replace(",", " ").split() if token]
    if not tokens:
        raise BinaryAnalysisError("pattern is required")
    if len(tokens)>MAX_PATTERN_BYTES:
        raise BinaryAnalysisError(f"pattern exceeds maximum length ({len(tokens)} > {MAX_PATTERN_BYTES})")
    out=[]
    for token in tokens:
        if token in {"?","??","**"}:
            out.append(None)
            continue
        if len(token)!=2:
            raise BinaryAnalysisError(f"invalid hex token: {token!r}")
        try:
            out.append(int(token,16))
        except ValueError as exc:
            raise BinaryAnalysisError(f"invalid hex token: {token!r}") from exc
    return tuple(out)


def _iter_sections(image: PEImage, *, section: str | None = None, executable_only: bool = False):
    for sec in image.sections:
        if section is not None and sec.name.lower()!=section.lower():
            continue
        if executable_only and not (sec.characteristics & 0x20000000):
            continue
        if sec.raw_size<=0 or sec.raw_offset>=image.file_size:
            continue
        start=sec.raw_offset
        end=min(image.file_size,sec.raw_offset+sec.raw_size)
        if start<end:
            yield sec,start,end


def _address_record(image: PEImage, offset: int) -> dict[str,Any]:
    rva=image.offset_to_rva(offset)
    return {
        "offset":offset,
        "rva":rva,
        "va":image.image_base+rva if rva is not None else None,
        "section":image.section_for_offset(offset),
    }


def byte_search(
    path: Path,
    pattern: str,
    *,
    section: str | None = None,
    executable_only: bool = False,
    max_matches: int = DEFAULT_MAX_MATCHES,
    context_bytes: int = 8,
) -> dict[str,Any]:
    image=PEImage(Path(path))
    parsed=parse_hex_pattern(pattern)
    if max_matches<=0:
        raise BinaryAnalysisError("max_matches must be positive")
    context_bytes=max(0,min(int(context_bytes),64))
    matches=[]
    plen=len(parsed)
    for sec,start,end in _iter_sections(image,section=section,executable_only=executable_only):
        last=end-plen
        for off in range(start,last+1):
            if all(expected is None or image.data[off+i]==expected for i,expected in enumerate(parsed)):
                before=max(0,off-context_bytes)
                after=min(image.file_size,off+plen+context_bytes)
                matches.append({
                    **_address_record(image,off),
                    "length":plen,
                    "bytes":image.data[off:off+plen].hex(" "),
                    "context":image.data[before:after].hex(" "),
                    "confidence":"VERIFIED",
                })
                if len(matches)>=max_matches:
                    return {
                        "status":"OK","pattern":pattern,"matches":matches,"truncated":True,
                        "notes":["Matches are exact file-byte observations. Wildcards match any one byte."],
                    }
    return {
        "status":"OK","pattern":pattern,"matches":matches,"truncated":False,
        "notes":["Matches are exact file-byte observations. Wildcards match any one byte."],
    }


def _resolve_target(image: PEImage, *, rva: int | None = None, va: int | None = None, offset: int | None = None):
    provided=sum(value is not None for value in (rva,va,offset))
    if provided!=1:
        raise BinaryAnalysisError("provide exactly one of rva, va, or offset")
    if va is not None:
        rva=va-image.image_base
    elif offset is not None:
        rva=image.offset_to_rva(offset)
        if rva is None:
            raise BinaryAnalysisError(f"file offset 0x{offset:X} does not map to an RVA")
    target_offset=image.rva_to_offset(rva) if rva is not None else None
    return {
        "rva":rva,
        "va":image.image_base+rva if rva is not None else None,
        "offset":target_offset,
        "section":image.section_for_offset(target_offset) if target_offset is not None else None,
    }


def _control_flow_refs(image: PEImage, sec, start: int, end: int, target_rva: int):
    data=image.data
    off=start
    while off<end:
        opcode=data[off]
        insn_len=0
        kind=None
        disp_off=None
        if opcode==0xE8:
            insn_len=5; kind="CALL_REL32"; disp_off=off+1
        elif opcode==0xE9:
            insn_len=5; kind="JMP_REL32"; disp_off=off+1
        elif opcode==0x0F and off+6<=end and 0x80<=data[off+1]<=0x8F:
            insn_len=6; kind="JCC_REL32"; disp_off=off+2
        elif opcode==0xEB:
            insn_len=2; kind="JMP_REL8"
            disp=struct.unpack_from("<b",data,off+1)[0] if off+2<=end else None
            if disp is not None:
                source_rva=image.offset_to_rva(off)
                if source_rva is not None and source_rva+2+disp==target_rva:
                    yield off,kind,insn_len
        elif 0x70<=opcode<=0x7F:
            insn_len=2; kind="JCC_REL8"
            disp=struct.unpack_from("<b",data,off+1)[0] if off+2<=end else None
            if disp is not None:
                source_rva=image.offset_to_rva(off)
                if source_rva is not None and source_rva+2+disp==target_rva:
                    yield off,kind,insn_len
        if disp_off is not None and off+insn_len<=end:
            disp=struct.unpack_from("<i",data,disp_off)[0]
            source_rva=image.offset_to_rva(off)
            if source_rva is not None and source_rva+insn_len+disp==target_rva:
                yield off,kind,insn_len
        off+=1


def xrefs(
    path: Path,
    *,
    rva: int | None = None,
    va: int | None = None,
    offset: int | None = None,
    executable_only: bool = True,
    include_pointers: bool = True,
    max_results: int = DEFAULT_MAX_XREFS,
) -> dict[str,Any]:
    image=PEImage(Path(path))
    target=_resolve_target(image,rva=rva,va=va,offset=offset)
    target_rva=int(target["rva"])
    target_va=int(target["va"])
    results=[]
    seen=set()

    def add(off:int,kind:str,length:int,confidence:str,note:str):
        key=(off,kind)
        if key in seen:
            return
        seen.add(key)
        rec={
            **_address_record(image,off),
            "kind":kind,
            "length":length,
            "bytes":image.data[off:min(image.file_size,off+length)].hex(" "),
            "confidence":confidence,
            "note":note,
        }
        results.append(rec)

    for sec,start,end in _iter_sections(image,executable_only=executable_only):
        for off,kind,length in _control_flow_refs(image,sec,start,end,target_rva):
            add(off,kind,length,"INFERRED",
                "Relative branch/call bytes resolve to the target, but instruction boundaries are not independently disassembled.")
            if len(results)>=max_results:
                break
        if len(results)>=max_results:
            break

    if include_pointers and len(results)<max_results:
        needles=[]
        if image.pointer_size==4:
            needles.append(("ABSOLUTE_VA32",struct.pack("<I",target_va & 0xFFFFFFFF)))
            needles.append(("RVA32",struct.pack("<I",target_rva & 0xFFFFFFFF)))
        else:
            needles.append(("ABSOLUTE_VA64",struct.pack("<Q",target_va)))
            needles.append(("RVA32",struct.pack("<I",target_rva & 0xFFFFFFFF)))
        for sec,start,end in _iter_sections(image,executable_only=False):
            block=image.data[start:end]
            for kind,needle in needles:
                pos=block.find(needle)
                while pos>=0:
                    add(start+pos,kind,len(needle),"INFERRED",
                        "Raw little-endian pointer/value match; semantic reference requires disassembly or runtime corroboration.")
                    if len(results)>=max_results:
                        break
                    pos=block.find(needle,pos+1)
                if len(results)>=max_results:
                    break
            if len(results)>=max_results:
                break

    results.sort(key=lambda row:(row["offset"],row["kind"]))
    return {
        "status":"OK",
        "target":target,
        "xrefs":results[:max_results],
        "truncated":len(results)>=max_results,
        "notes":[
            "Control-flow xrefs are conservative candidates from opcode/relative-displacement scanning, not authoritative disassembly.",
            "Pointer/value matches are intentionally INFERRED because raw constants can be data rather than references.",
        ],
    }


def _is_executable_rva(image: PEImage, rva: int) -> bool:
    for sec in image.sections:
        span=max(sec.virtual_size,sec.raw_size)
        if sec.virtual_address<=rva<sec.virtual_address+span:
            return bool(sec.characteristics & 0x20000000) and image.rva_to_offset(rva) is not None
    return False


def function_candidates(
    path: Path,
    *,
    max_candidates: int = DEFAULT_MAX_FUNCTION_CANDIDATES,
) -> dict[str,Any]:
    image=PEImage(Path(path))
    candidates: dict[int,dict[str,Any]]={}

    def add(rva:int,reason:str,confidence:str):
        if not _is_executable_rva(image,rva):
            return
        row=candidates.setdefault(rva,{
            "rva":rva,
            "va":image.image_base+rva,
            "offset":image.rva_to_offset(rva),
            "section":image.section_for_offset(image.rva_to_offset(rva) or -1),
            "reasons":[],
            "confidence":confidence,
        })
        if reason not in row["reasons"]:
            row["reasons"].append(reason)
        if confidence=="VERIFIED_SEED":
            row["confidence"]="VERIFIED_SEED"

    add(image.entry_point_rva,"PE_ENTRY_POINT","VERIFIED_SEED")
    for row in image.exports(max_entries=max_candidates):
        add(int(row["rva"]),f"EXPORT:{row.get('name') or row.get('ordinal')}","VERIFIED_SEED")

    for sec,start,end in _iter_sections(image,executable_only=True):
        off=start
        while off+5<=end and len(candidates)<max_candidates:
            if image.data[off]==0xE8:
                source_rva=image.offset_to_rva(off)
                disp=struct.unpack_from("<i",image.data,off+1)[0]
                if source_rva is not None:
                    target_rva=source_rva+5+disp
                    add(target_rva,f"DIRECT_CALL_FROM:0x{source_rva:X}","INFERRED")
            off+=1

    rows=sorted(candidates.values(),key=lambda row:row["rva"])[:max_candidates]
    return {
        "status":"OK",
        "candidates":rows,
        "truncated":len(candidates)>max_candidates,
        "notes":[
            "These are candidate function entry points, not recovered function bodies.",
            "PE entry points and export RVAs are verified seeds; direct-call targets remain inferred until decoded/disassembled.",
        ],
    }
