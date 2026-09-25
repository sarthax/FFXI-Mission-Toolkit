#!/usr/bin/env python3
"""Conservative C++ API/binding/build indexer for external FFXI server source trees.

This is intentionally not a C++ parser. It extracts high-value evidence with conservative
regexes, records UNKNOWN rather than guessing, and accepts an external source root because the
Workbench repository itself does not contain the DSP/Topaz/LSB C++ trees.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from source_snapshot import snapshot_id
from workbench_schema import (
    AnalysisResult, Binding, DependencyEdge, EnumDefinition, Finding, Function, FunctionSignature
)

CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".hxx"}
SOL_RE = re.compile(r'SOL_REGISTER\(\s*"([A-Za-z_]\w*)"\s*,\s*([A-Za-z_]\w*)::\s*([A-Za-z_]\w*)')
LUNAR_RE = re.compile(r'LUNAR_DECLARE_METHOD\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*\)')
ENUM_RE = re.compile(r'\benum(?:\s+class)?\s+([A-Za-z_]\w*)\s*\{(?P<body>.*?)\}', re.S)
DEFINE_RE = re.compile(r'^\s*#define\s+([A-Za-z_]\w*)\s+(.+?)\s*$', re.M)
FUNCTION_RE = re.compile(
    r'(?m)^\s*(?P<prefix>(?:(?:static|inline|virtual|constexpr|const|extern|'
    r'friend|explicit|unsigned|signed|long|short|auto)\s+)*)'
    r'(?P<ret>[A-Za-z_~][\w:<>,\s*&]+?)\s+'
    r'(?P<name>[A-Za-z_]\w*(?:::\s*[A-Za-z_]\w*)?)\s*'
    r'\((?P<params>[^;{}()]*)\)\s*(?P<suffix>const\b|noexcept\b|const\s+noexcept)?\s*(?P<end>[;{])'
)
CLASS_RE = re.compile(r'\bclass\s+([A-Za-z_]\w*)|\bstruct\s+([A-Za-z_]\w*)')

def files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in CPP_EXTENSIONS:
            yield p

def line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1

def clean_type(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip())

def signature(ret: str, params: str, prefix: str, suffix: str | None, raw: str) -> FunctionSignature:
    return FunctionSignature(
        return_type=clean_type(ret),
        parameters=[clean_type(x) for x in params.split(",") if x.strip()],
        const=bool(suffix and re.search(r'\bconst\b', suffix)),
        static=bool(re.search(r'\bstatic\b', prefix)),
        noexcept=bool(suffix and "noexcept" in suffix),
        raw=raw.strip(),
    )

def extract_functions(path: Path, text: str, root: Path):
    current_class = None
    # Conservative class context: only declarations/definitions on the same file are associated.
    for m in CLASS_RE.finditer(text):
        current_class = m.group(1) or m.group(2)
        break
    for m in FUNCTION_RE.finditer(text):
        name = m.group("name").replace(" ", "")
        qualified = name
        class_name = current_class if "::" not in name else name.rsplit("::", 1)[0]
        bare = name.rsplit("::", 1)[-1]
        is_def = m.group("end") == "{"
        sig = signature(m.group("ret"), m.group("params"), m.group("prefix"), m.group("suffix"), m.group(0))
        yield Function(
            function_id=f"cpp:{path.relative_to(root).as_posix()}:{line_no(text,m.start())}:{qualified}",
            qualified_name=qualified,
            name=bare,
            class_name=class_name,
            path=path.relative_to(root).as_posix(),
            line=line_no(text,m.start()),
            kind="METHOD" if class_name else "FUNCTION",
            declaration=not is_def,
            definition=is_def,
            signature=sig,
            notes=["REGEX_HEURISTIC: C++ parser not used."],
        )

def extract_enums(path: Path, text: str, root: Path):
    for m in ENUM_RE.finditer(text):
        enum_name = m.group(1)
        next_value = 0
        for raw in m.group("body").split(","):
            raw = raw.strip()
            if not raw or raw.startswith("//"):
                continue
            if "=" in raw:
                symbol, value = [x.strip() for x in raw.split("=",1)]
                next_value = value
            else:
                symbol, value = raw, str(next_value)
            yield EnumDefinition(
                enum_id=f"enum:{path.relative_to(root).as_posix()}:{line_no(text,m.start())}:{enum_name}:{symbol}",
                enum_name=enum_name,
                source_snapshot_id=None,
                path=path.relative_to(root).as_posix(),
                line=line_no(text,m.start()),
                format="CXX_ENUM",
                value=value,
                symbol=symbol,
                notes=["REGEX_HEURISTIC: values without explicit assignments are sequentially inferred within this enum."],
            )
            if isinstance(next_value, int):
                next_value += 1

def extract_constants(path: Path, text: str, root: Path):
    for m in DEFINE_RE.finditer(text):
        yield EnumDefinition(
            enum_id=f"constant:{path.relative_to(root).as_posix()}:{line_no(text,m.start())}:{m.group(1)}",
            enum_name="",
            source_snapshot_id=None,
            path=path.relative_to(root).as_posix(),
            line=line_no(text,m.start()),
            format="CPP_DEFINE",
            value=m.group(2).strip(),
            symbol=m.group(1),
            notes=["#define indexed as a constant; semantic type is UNKNOWN."],
        )

def extract_bindings(path: Path, text: str, root: Path):
    for regex, system in ((SOL_RE, "SOL2"), (LUNAR_RE, "LUNAR")):
        for m in regex.finditer(text):
            if system == "SOL2":
                lua_name, cls, cpp_method = m.groups()
            else:
                cls, cpp_method = m.groups()
                lua_name = cpp_method
            yield Binding(
                binding_id=f"binding:{path.relative_to(root).as_posix()}:{line_no(text,m.start())}:{lua_name}",
                lua_name=lua_name,
                binding_system=system,
                cpp_symbol=f"{cls}::{cpp_method}",
                class_name=cls,
                path=path.relative_to(root).as_posix(),
                line=line_no(text,m.start()),
                status="DISCOVERED",
                notes=["Binding macro extracted directly from source."],
            )

def index(root: Path):
    funcs, enums, bindings = [], [], []
    for p in files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        funcs.extend(extract_functions(p,text,root))
        enums.extend(extract_enums(p,text,root))
        enums.extend(extract_constants(p,text,root))
        bindings.extend(extract_bindings(p,text,root))
    function_by_symbol = {}
    for f in funcs:
        function_by_symbol.setdefault(f.qualified_name, []).append(f)
    for b in bindings:
        matches = function_by_symbol.get(b.cpp_symbol, [])
        if matches:
            b.function_id = matches[0].function_id
            b.status = "RESOLVED"
        else:
            b.status = "UNRESOLVED"
            b.notes.append("No exact declaration/definition match found by extracted qualified name.")
    return funcs, enums, bindings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="External C++ server source root (DSP/Topaz/LSB/custom fork).")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    sid = snapshot_id(args.root)
    funcs, enums, bindings = index(args.root)
    for record in (*funcs, *enums, *bindings):
        record.source_snapshot_id = sid
    findings = []
    for b in bindings:
        if b.status == "UNRESOLVED":
            findings.append(Finding(
                finding_id=f"binding-unresolved:{b.binding_id}",
                analysis_id="cpp-api-index",
                subject_id=b.binding_id,
                field="function_resolution",
                value=b.cpp_symbol,
                status="UNKNOWN",
                confidence="INFERRED",
                source_snapshot_id=sid,
                notes=b.notes,
            ))
    result = AnalysisResult(
        analysis_id="cpp-api-index",
        analysis_type="CPP_API_SURFACE",
        source=str(args.root),
        status="ANALYZED",
        notes=[f"Source snapshot: {sid}.", "Conservative regex extraction; results require parser/semantic verification for ambiguous C++."],
        findings=[x.finding_id for x in findings],
        source_snapshot_id=sid,
    )
    payload = {
        "schema": 1,
        "analysis": asdict(result),
        "functions": [asdict(x) for x in funcs],
        "enums_constants": [asdict(x) for x in enums],
        "bindings": [asdict(x) for x in bindings],
        "findings": [asdict(x) for x in findings],
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
if __name__ == "__main__":
    raise SystemExit(main())
