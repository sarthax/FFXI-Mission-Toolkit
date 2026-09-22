"""Structured tree -> luaparser AST -> Lua source text. Comments are
inserted as a post-render text pass since luaparser's renderer drops them.

We use luaparser's ``astnodes`` for AST types but bypass ``to_lua_source`` —
its multimethod dispatch dominates runtime. The local ``_print`` covers the
~20 node types we actually emit and is ~5x faster.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from luaparser import astnodes as N

from . import work_area as W
from .structure import IfNode, Raw

_MSG_CALL_RE = re.compile(r"(say|dialog|systemMessage)\((\d+)")
_DIALOG_ASSIGN_RE = re.compile(r"^\s*(\w+)\s*=\s*\w+:dialog\((\d+)")
_BRANCH_RE = re.compile(r"^\s*(?:if|elseif)\s+(\w+)\s*==\s*(\d+)\s+then\s*$")
_PREVIEW_MAX = 80


@dataclass
class EmitContext:
    imed: list[int] | None = None
    strings: dict[int, str] = field(default_factory=dict)
    entities: dict[int, str] | None = None
    actor_id: int | None = None

    def value(self, addr: int) -> N.Expression:
        return W.value(addr, self.imed)

    def entity(self, eid: int) -> N.Expression:
        return W.entity(eid, self.entities, self.actor_id)

    def coord(self, addr: int) -> N.Expression:
        node = W.value(addr, self.imed)
        if isinstance(node, N.Number):
            return N.Number(round(W.coord_float(node.n), 3))
        return node

    def yaw(self, addr: int) -> N.Expression:
        node = W.value(addr, self.imed)
        if isinstance(node, N.Number):
            return N.Number(W.yaw_byte(node.n))
        return node

    def invoke(self, receiver: str, method: str, args: list) -> N.Invoke:
        return N.Invoke(source=N.Name(receiver), func=N.Name(method), args=args)


def render(stmts: list, name: str, ctx: EmitContext) -> str:
    body = _emit_block(stmts, ctx)
    # Drop a trailing bare `return` — Lua functions return implicitly, and
    # END_REQSTACK / END_EVENT at the natural function end is just noise.
    # We keep them inside if/branches because there they encode an early exit
    # the reader otherwise can't see.
    if body and isinstance(body[-1], N.Return) and not body[-1].values:
        body = body[:-1]
    fn = N.Function(
        name=N.Name(name),
        args=[N.Name("npc"), N.Name("player"), N.Name("params")],
        body=N.Block(body=body),
    )
    src = _print(fn, 0)
    src = _annotate_messages(src, ctx)
    src = _annotate_dialog_branches(src, ctx)
    return src


def _emit_block(stmts: list, ctx: EmitContext) -> list:
    out: list = []
    for stmt in stmts:
        if isinstance(stmt, Raw):
            node = stmt.inst.opdef.emit(ctx, stmt.inst.args)
            if node is None:
                continue
            if isinstance(node, list):
                out.extend(node)
            else:
                out.append(node)
        elif isinstance(stmt, IfNode):
            out.append(_build_if(stmt, ctx))
    return out


def _build_if(if_node: IfNode, ctx: EmitContext) -> N.If:
    test = if_node.cond_inst.opdef.emit(ctx, if_node.cond_inst.args)
    then_body = _emit_block(if_node.then, ctx)
    else_body = _emit_block(if_node.else_, ctx)

    # Empty then-branch with non-empty else usually means the bytecode had
    # `if cond then GOTO merge end <work>` — the then-path skipped the work
    # via an unconditional jump that the structurer absorbed. Invert and swap
    # so the body reads naturally instead of `if cond then end <orphan code>`.
    # Limited to == / != for safety. NOTE: this rewrites control flow and
    # will NOT round-trip through the compiler unless the compiler also
    # recognizes the inverse shape.
    if not then_body and else_body and isinstance(test, (N.EqToOp, N.NotEqToOp)):
        then_body, else_body = else_body, then_body
        cls = N.NotEqToOp if isinstance(test, N.EqToOp) else N.EqToOp
        test = cls(left=test.left, right=test.right)

    # Collapse `else { if(...) }` into elseif.
    if len(else_body) == 1 and isinstance(else_body[0], N.If):
        inner = else_body[0]
        orelse = N.ElseIf(test=inner.test, body=inner.body, orelse=inner.orelse)
    elif else_body:
        orelse = N.Block(body=else_body)
    else:
        orelse = None

    return N.If(test=test, body=N.Block(body=then_body), orelse=orelse)


def _annotate_dialog_branches(src: str, ctx: EmitContext) -> str:
    """Tag ``if/elseif var == N`` branches with the matching option text from
    the dialog the variable was bound to. Splits the dialog message on the
    FFXI ``"... ? Opt1. Opt2. ..."`` convention."""
    lines = src.split("\n")
    selectors: dict[str, list[str]] = {}

    for i, line in enumerate(lines):
        if m := _DIALOG_ASSIGN_RE.match(line):
            var, msg_id = m.group(1), int(m.group(2))
            text = ctx.strings.get(msg_id)
            if text:
                prompt, opts = _split_dialog(text)
                if opts:
                    selectors[var] = opts
                    lines[i] = _replace_inline_comment(line, prompt)
            continue

        if m := _BRANCH_RE.match(line):
            opts = selectors.get(m.group(1))
            if opts is None:
                continue
            idx = int(m.group(2))
            if 0 <= idx < len(opts):
                lines[i] = f"{line}  -- {opts[idx]}"

    return "\n".join(lines)


def _split_dialog(text: str) -> tuple[str, list[str]]:
    """``"Dig here? Yep. Nope." -> ("Dig here?", ["Yep", "Nope"])``."""
    if "?" not in text:
        return text, []
    prompt, rest = text.rsplit("?", 1)
    prompt = (prompt + "?").strip()
    opts: list[str] = []
    rest = rest.strip()
    while rest:
        idx = rest.find(". ")
        if idx == -1:
            opts.append(rest.rstrip(".").strip())
            break
        opts.append(rest[:idx].strip())
        rest = rest[idx + 2 :]
    return prompt, [o for o in opts if o]


def _replace_inline_comment(line: str, new_comment: str) -> str:
    pos = line.find("--")
    head = line[:pos].rstrip() if pos != -1 else line.rstrip()
    return f"{head}  -- {new_comment}"


def _annotate_messages(src: str, ctx: EmitContext) -> str:
    if not ctx.strings:
        return src

    lines = []
    for line in src.split("\n"):
        if "--" in line:
            lines.append(line)
            continue
        m = _MSG_CALL_RE.search(line)
        if not m:
            lines.append(line)
            continue
        text = ctx.strings.get(int(m.group(2)))
        if not text:
            lines.append(line)
            continue
        preview = text[: _PREVIEW_MAX - 3] + "..." if len(text) > _PREVIEW_MAX else text
        preview = preview.replace("\n", " ").replace("  ", " ")
        lines.append(f"{line}  -- {preview}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Custom Lua printer for the AST subset our opcodes emit. luaparser's renderer
# is correct but slow (~50% of decompile time was multimethod dispatch).

_BINOPS = {
    N.AddOp: " + ",
    N.SubOp: " - ",
    N.MultOp: " * ",
    N.FloatDivOp: " / ",
    N.FloorDivOp: " // ",
    N.ModOp: " % ",
    N.ExpoOp: " ^ ",
    N.BAndOp: " & ",
    N.BOrOp: " | ",
    N.BXorOp: " ~ ",
    N.BShiftLOp: " << ",
    N.BShiftROp: " >> ",
    N.EqToOp: " == ",
    N.NotEqToOp: " ~= ",
    N.LessThanOp: " < ",
    N.GreaterThanOp: " > ",
    N.LessOrEqThanOp: " <= ",
    N.GreaterOrEqThanOp: " >= ",
    N.AndLoOp: " and ",
    N.OrLoOp: " or ",
    N.Concat: " .. ",
}


def _print(node, depth: int) -> str:
    pad = "    " * depth

    if isinstance(node, N.Function):
        args = ", ".join(_expr(a) for a in node.args)
        body = _print_block(node.body, depth + 1)
        return f"{pad}function {node.name.id}({args})\n{body}\n{pad}end"

    if isinstance(node, N.If):
        return _print_if(node, depth)

    if isinstance(node, N.Assign):
        targets = ", ".join(_expr(t) for t in node.targets)
        values = ", ".join(_expr(v) for v in node.values)
        return f"{pad}{targets} = {values}"

    if isinstance(node, N.Return):
        if not node.values:
            return f"{pad}return"
        return f"{pad}return {', '.join(_expr(v) for v in node.values)}"

    # Bare expression statements (Invoke / Call as statement).
    return f"{pad}{_expr(node)}"


def _print_block(block: N.Block, depth: int) -> str:
    return "\n".join(_print(s, depth) for s in block.body)


def _print_if(node: N.If, depth: int) -> str:
    pad = "    " * depth
    out = [f"{pad}if {_expr(node.test)} then", _print_block(node.body, depth + 1)]
    orelse = node.orelse
    while isinstance(orelse, N.ElseIf):
        out.append(f"{pad}elseif {_expr(orelse.test)} then")
        out.append(_print_block(orelse.body, depth + 1))
        orelse = orelse.orelse
    if isinstance(orelse, N.Block):
        out.append(f"{pad}else")
        out.append(_print_block(orelse, depth + 1))
    out.append(f"{pad}end")
    return "\n".join(out)


def _expr(node) -> str:
    if isinstance(node, N.Name):
        return node.id
    if isinstance(node, N.Number):
        return repr(node.n) if isinstance(node.n, float) else str(node.n)
    if isinstance(node, N.String):
        return f'"{node.raw}"'
    if isinstance(node, N.Index):
        return f"{_expr(node.value)}[{_expr(node.idx)}]"
    if isinstance(node, N.Invoke):
        args = ", ".join(_expr(a) for a in node.args)
        return f"{_expr(node.source)}:{node.func.id}({args})"
    if isinstance(node, N.Call):
        args = ", ".join(_expr(a) for a in node.args)
        return f"{_expr(node.func)}({args})"
    if op := _BINOPS.get(type(node)):
        return f"{_expr(node.left)}{op}{_expr(node.right)}"
    raise TypeError(f"don't know how to render {type(node).__name__}")
