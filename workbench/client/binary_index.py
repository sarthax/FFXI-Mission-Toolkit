"""Dependency-free PE/COFF client binary indexing for read-only research."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


MAX_BINARY_BYTES=512 * 1024 * 1024
DEFAULT_MIN_STRING=5
DEFAULT_MAX_STRINGS=25000


class BinaryFormatError(ValueError):
    pass


@dataclass(frozen=True)
class SectionRecord:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int
    characteristics: int


class PEImage:
    def __init__(self, path: Path, *, max_bytes: int = MAX_BINARY_BYTES):
        self.path=Path(path)
        size=self.path.stat().st_size
        if size > max_bytes:
            raise BinaryFormatError(f"binary exceeds maximum indexed size ({size} > {max_bytes})")
        self.data=self.path.read_bytes()
        self.file_size=len(self.data)
        self.sections: list[SectionRecord]=[]
        self._parse_headers()

    def _u16(self, off: int) -> int:
        if off < 0 or off+2 > len(self.data):
            raise BinaryFormatError(f"u16 outside file at 0x{off:X}")
        return struct.unpack_from("<H",self.data,off)[0]

    def _u32(self, off: int) -> int:
        if off < 0 or off+4 > len(self.data):
            raise BinaryFormatError(f"u32 outside file at 0x{off:X}")
        return struct.unpack_from("<I",self.data,off)[0]

    def _u64(self, off: int) -> int:
        if off < 0 or off+8 > len(self.data):
            raise BinaryFormatError(f"u64 outside file at 0x{off:X}")
        return struct.unpack_from("<Q",self.data,off)[0]

    def _cstr(self, off: int, limit: int = 4096) -> str:
        if off < 0 or off >= len(self.data):
            return ""
        end=min(len(self.data),off+limit)
        nul=self.data.find(b"\0",off,end)
        if nul < 0:
            nul=end
        return self.data[off:nul].decode("ascii",errors="replace")

    def _parse_headers(self) -> None:
        if len(self.data)<0x40 or self.data[:2]!=b"MZ":
            raise BinaryFormatError("not a DOS MZ/PE image")
        self.pe_offset=self._u32(0x3C)
        if self.pe_offset+24>len(self.data) or self.data[self.pe_offset:self.pe_offset+4]!=b"PE\0\0":
            raise BinaryFormatError("PE signature not found")

        coff=self.pe_offset+4
        self.machine=self._u16(coff)
        self.number_of_sections=self._u16(coff+2)
        self.timestamp=self._u32(coff+4)
        self.size_of_optional_header=self._u16(coff+16)
        self.characteristics=self._u16(coff+18)

        opt=coff+20
        magic=self._u16(opt)
        if magic==0x10B:
            self.pe_kind="PE32"
            self.pointer_size=4
            self.image_base=self._u32(opt+28)
            self.number_of_rva_and_sizes=self._u32(opt+92)
            dd=opt+96
        elif magic==0x20B:
            self.pe_kind="PE32+"
            self.pointer_size=8
            self.image_base=self._u64(opt+24)
            self.number_of_rva_and_sizes=self._u32(opt+108)
            dd=opt+112
        else:
            raise BinaryFormatError(f"unsupported PE optional-header magic 0x{magic:04X}")

        self.entry_point_rva=self._u32(opt+16)
        self.section_alignment=self._u32(opt+32)
        self.file_alignment=self._u32(opt+36)
        self.size_of_image=self._u32(opt+56)
        self.size_of_headers=self._u32(opt+60)
        subsystem_off=opt+(68 if magic==0x10B else 80)
        self.subsystem=self._u16(subsystem_off)

        self.data_directories=[]
        count=min(self.number_of_rva_and_sizes,16)
        for i in range(count):
            off=dd+i*8
            if off+8>opt+self.size_of_optional_header:
                break
            self.data_directories.append({
                "index":i,
                "rva":self._u32(off),
                "size":self._u32(off+4),
            })

        section_off=opt+self.size_of_optional_header
        for i in range(self.number_of_sections):
            off=section_off+i*40
            if off+40>len(self.data):
                raise BinaryFormatError("section table extends beyond file")
            raw_name=self.data[off:off+8].split(b"\0",1)[0]
            self.sections.append(SectionRecord(
                name=raw_name.decode("ascii",errors="replace"),
                virtual_size=self._u32(off+8),
                virtual_address=self._u32(off+12),
                raw_size=self._u32(off+16),
                raw_offset=self._u32(off+20),
                characteristics=self._u32(off+36),
            ))

    def directory(self,index:int) -> dict[str,int]:
        return self.data_directories[index] if index<len(self.data_directories) else {"index":index,"rva":0,"size":0}

    def rva_to_offset(self,rva:int) -> int | None:
        if 0<=rva<self.size_of_headers and rva<len(self.data):
            return rva
        for section in self.sections:
            span=max(section.virtual_size,section.raw_size)
            if section.virtual_address<=rva<section.virtual_address+span:
                delta=rva-section.virtual_address
                if delta>=section.raw_size:
                    return None
                off=section.raw_offset+delta
                return off if off<len(self.data) else None
        return None

    def offset_to_rva(self,offset:int) -> int | None:
        if 0<=offset<self.size_of_headers:
            return offset
        for section in self.sections:
            if section.raw_offset<=offset<section.raw_offset+section.raw_size:
                return section.virtual_address+(offset-section.raw_offset)
        return None

    def section_for_offset(self,offset:int) -> str | None:
        for section in self.sections:
            if section.raw_offset<=offset<section.raw_offset+section.raw_size:
                return section.name
        return None

    def layout_warnings(self) -> list[dict[str,Any]]:
        warnings=[]
        for section in self.sections:
            executable=bool(section.characteristics & 0x20000000)
            if executable and section.virtual_size and section.raw_size==0:
                warnings.append({
                    "code":"EXECUTABLE_SECTION_WITHOUT_RAW_BYTES",
                    "section":section.name,
                    "virtual_address":section.virtual_address,
                    "virtual_size":section.virtual_size,
                    "raw_offset":section.raw_offset,
                    "raw_size":section.raw_size,
                    "severity":"INFERRED_LIMITATION",
                    "note":"Static RVA-to-file mapping/disassembly for this section may be incomplete because the PE section has virtual executable content but no raw bytes.",
                })
            if executable and section.name.upper().startswith("POL"):
                warnings.append({
                    "code":"NONSTANDARD_EXECUTABLE_SECTION",
                    "section":section.name,
                    "virtual_address":section.virtual_address,
                    "virtual_size":section.virtual_size,
                    "raw_offset":section.raw_offset,
                    "raw_size":section.raw_size,
                    "severity":"OBSERVED",
                    "note":"Executable code/data is stored in a nonstandard section name; treat normal .text-only assumptions as unsafe.",
                })
        return warnings

    def imports(self, *, max_entries: int = 50000) -> list[dict[str,Any]]:
        directory=self.directory(1)
        if not directory["rva"]:
            return []
        off=self.rva_to_offset(directory["rva"])
        if off is None:
            return []
        results=[]
        descriptors=0
        while off+20<=len(self.data) and descriptors<4096 and len(results)<max_entries:
            oft,timestamp,forwarder,name_rva,first_thunk=struct.unpack_from("<IIIII",self.data,off)
            if not any((oft,timestamp,forwarder,name_rva,first_thunk)):
                break
            descriptors+=1
            name_off=self.rva_to_offset(name_rva)
            dll=self._cstr(name_off) if name_off is not None else ""
            thunk_rva=oft or first_thunk
            thunk_off=self.rva_to_offset(thunk_rva)
            if thunk_off is not None:
                index=0
                ordinal_mask=1<<(63 if self.pointer_size==8 else 31)
                while len(results)<max_entries:
                    pos=thunk_off+index*self.pointer_size
                    if pos+self.pointer_size>len(self.data):
                        break
                    value=self._u64(pos) if self.pointer_size==8 else self._u32(pos)
                    if value==0:
                        break
                    entry={"dll":dll,"thunk_rva":thunk_rva+index*self.pointer_size,
                           "iat_rva":first_thunk+index*self.pointer_size}
                    if value & ordinal_mask:
                        entry["ordinal"]=value & 0xFFFF
                        entry["name"]=None
                        entry["hint"]=None
                    else:
                        ibn_off=self.rva_to_offset(value)
                        entry["ordinal"]=None
                        if ibn_off is None or ibn_off+2>len(self.data):
                            entry["name"]=None
                            entry["hint"]=None
                        else:
                            entry["hint"]=self._u16(ibn_off)
                            entry["name"]=self._cstr(ibn_off+2)
                    results.append(entry)
                    index+=1
            off+=20
        return results

    def exports(self, *, max_entries: int = 50000) -> list[dict[str,Any]]:
        directory=self.directory(0)
        if not directory["rva"]:
            return []
        off=self.rva_to_offset(directory["rva"])
        if off is None or off+40>len(self.data):
            return []
        fields=struct.unpack_from("<IIHHIIIIIII",self.data,off)
        _char,_ts,_maj,_min,name_rva,base,num_funcs,num_names,funcs_rva,names_rva,ords_rva=fields
        names_off=self.rva_to_offset(names_rva)
        ords_off=self.rva_to_offset(ords_rva)
        funcs_off=self.rva_to_offset(funcs_rva)
        if names_off is None or ords_off is None or funcs_off is None:
            return []
        results=[]
        for i in range(min(num_names,max_entries)):
            if names_off+i*4+4>len(self.data) or ords_off+i*2+2>len(self.data):
                break
            symbol_rva=self._u32(names_off+i*4)
            symbol_off=self.rva_to_offset(symbol_rva)
            ordinal_index=self._u16(ords_off+i*2)
            if funcs_off+ordinal_index*4+4>len(self.data):
                continue
            function_rva=self._u32(funcs_off+ordinal_index*4)
            results.append({
                "name":self._cstr(symbol_off) if symbol_off is not None else "",
                "ordinal":base+ordinal_index,
                "rva":function_rva,
                "va":self.image_base+function_rva,
            })
        return results

    def strings(self, *, min_length:int=DEFAULT_MIN_STRING, max_strings:int=DEFAULT_MAX_STRINGS) -> list[dict[str,Any]]:
        out=[]
        data=self.data

        start=None
        for i,b in enumerate(data):
            printable=32<=b<=126 or b in (9,)
            if printable and start is None:
                start=i
            elif not printable and start is not None:
                if i-start>=min_length:
                    text=data[start:i].decode("ascii",errors="replace")
                    rva=self.offset_to_rva(start)
                    out.append({"encoding":"ascii","text":text,"offset":start,"rva":rva,"va":self.image_base+rva if rva is not None else None,"section":self.section_for_offset(start)})
                    if len(out)>=max_strings:
                        return out
                start=None
        if start is not None and len(data)-start>=min_length and len(out)<max_strings:
            rva=self.offset_to_rva(start)
            out.append({"encoding":"ascii","text":data[start:].decode("ascii",errors="replace"),"offset":start,"rva":rva,"va":self.image_base+rva if rva is not None else None,"section":self.section_for_offset(start)})

        i=0
        while i+min_length*2<=len(data) and len(out)<max_strings:
            j=i
            chars=[]
            while j+1<len(data) and 32<=data[j]<=126 and data[j+1]==0:
                chars.append(chr(data[j])); j+=2
            if len(chars)>=min_length:
                rva=self.offset_to_rva(i)
                out.append({"encoding":"utf-16le","text":"".join(chars),"offset":i,"rva":rva,"va":self.image_base+rva if rva is not None else None,"section":self.section_for_offset(i)})
                i=j
            else:
                i+=1
        out.sort(key=lambda row:(row["offset"],row["encoding"]))
        return out[:max_strings]


def index_binary(
    path: Path,
    *,
    label: str | None = None,
    client_build: str | None = None,
    min_string_length: int = DEFAULT_MIN_STRING,
    max_strings: int = DEFAULT_MAX_STRINGS,
) -> dict[str,Any]:
    path=Path(path)
    image=PEImage(path)
    sha256=hashlib.sha256(image.data).hexdigest()
    sha1=hashlib.sha1(image.data).hexdigest()
    md5=hashlib.md5(image.data).hexdigest()
    imports=image.imports()
    exports=image.exports()
    strings=image.strings(min_length=min_string_length,max_strings=max_strings)
    return {
        "schema":1,
        "kind":"CLIENT_BINARY_INDEX",
        "binary":{
            "label":label or path.name,
            "path":str(path),
            "filename":path.name,
            "file_size":image.file_size,
            "sha256":sha256,
            "sha1":sha1,
            "md5":md5,
            "client_build":client_build,
            "pe_kind":image.pe_kind,
            "machine":image.machine,
            "timestamp":image.timestamp,
            "characteristics":image.characteristics,
            "subsystem":image.subsystem,
            "image_base":image.image_base,
            "entry_point_rva":image.entry_point_rva,
            "entry_point_va":image.image_base+image.entry_point_rva,
            "size_of_image":image.size_of_image,
            "section_alignment":image.section_alignment,
            "file_alignment":image.file_alignment,
        },
        "sections":[asdict(section) for section in image.sections],
        "layout_warnings":image.layout_warnings(),
        "imports":imports,
        "exports":exports,
        "strings":strings,
        "analysis":{
            "authority":"CLIENT_BINARY",
            "status":"INDEXED",
            "notes":[
                "Static PE evidence only; presence of a string/import/export does not by itself prove runtime behavior.",
                "No binary mutation or disassembly is performed by this indexer.",
            ],
        },
    }


def write_index(payload: dict[str,Any], output: Path) -> None:
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def record_token(category: str, row: dict[str,Any]) -> str:
    return hashlib.sha256(
        (category+json.dumps(row,sort_keys=True,default=str)).encode("utf-8")
    ).hexdigest()[:20]

def binary_header_evidence_id(payload: dict[str,Any]) -> str:
    sha256=str((payload.get("binary") or {}).get("sha256") or "")
    return f"evidence:client-binary:{sha256[:24]}:pe"

def binary_string_corpus_evidence_id(payload: dict[str,Any]) -> str:
    sha256=str((payload.get("binary") or {}).get("sha256") or "")
    return f"evidence:client-binary:{sha256[:24]}:strings"

def binary_record_evidence_id(category: str, row: dict[str,Any]) -> str:
    singular={"sections":"section","imports":"import","exports":"export"}.get(category,category.rstrip("s"))
    return f"evidence:client-binary-{singular}:{record_token(category,row)}"
