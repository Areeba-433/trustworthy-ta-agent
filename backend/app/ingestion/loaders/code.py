"""Code department (owner: Fariha).

Turns a C++ file (.cpp / .h / .hpp) into blocks:
  * one block per function or class/struct/enum
  * "header" blocks for everything in between (#includes, using, globals)

Rules this file guarantees:
  * every block is kind="code" and lang="code"
  * code is NEVER cleaned (no clean_text) - the text is copied exactly
  * every block has loc.line_start and loc.line_end (1-based, inclusive)
  * joining all block texts in order gives back the original file exactly
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field 
from importlib.metadata import version
from pathlib import Path

import tree_sitter_cpp
from tree_sitter import Language, Parser

from app.ingestion import messages
from app.ingestion.contract import Block, Location, ParsedDocument, ResourceMeta
from app.ingestion.documents import FileRefused, parsed_document
from app.ingestion.registry import register
from app.ingestion.storage import Timer

_CPP = Language(tree_sitter_cpp.language())

# Nodes that become their own block.
_UNIT_TYPES = {
    "function_definition",
    "class_specifier",
    "struct_specifier",
    "union_specifier",
    "enum_specifier",
    "template_declaration",
}
# Nodes we look *inside* (their contents get split too).
_CONTAINER_TYPES = {"namespace_definition", "linkage_specification"}

# #ifndef / #if / #else blocks (include guards): we look inside them.
_PREPROC_TYPES = {"preproc_ifdef", "preproc_if", "preproc_else", "preproc_elif", "preproc_elifdef"}

# Tree-sitter wraps code it cannot fully parse (e.g. a missing "}") in an ERROR node.
# The functions and classes inside are usually fine, so we look inside it too.
_ERROR_TYPES = {"ERROR"}

_COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|\*/)")


@dataclass
class Segment:
    """A run of lines [start, end] (0-based, inclusive) plus where it belongs."""

    start: int
    end: int
    path: list[str]  # heading path WITHOUT the title (title is added later)
    symbol: str | None  # e.g. "Stack::push" ; None for header/glue lines
    ctx: list[str] = field(default_factory=list)  # namespaces it sits in


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _squash(s: str) -> str:
    """'push( int   x )' -> 'push( int x )' (single spaces, no newlines)."""
    return " ".join(s.split())


def _split_lines(source: str) -> list[str]:
    """Split on '\\n' only, KEEPING the line endings so we can rebuild exactly."""
    return re.findall(r"[^\n]*\n|[^\n]+$", source)


def _decode(raw: bytes) -> str | None:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


# --------------------------------------------------------------------------
# Naming: what label does a unit get in heading_path?
# --------------------------------------------------------------------------
def _find_function_declarator(node):
    """Walk down declarator -> declarator ... until we hit function_declarator."""
    while node is not None and node.type != "function_declarator":
        node = node.child_by_field_name("declarator")
    return node


def _unit_label(node, src: bytes, known_namespaces: set[str]) -> tuple[list[str], str]:
    """Return (path parts, symbol) for a unit node."""
    if node.type == "template_declaration":
        for child in node.named_children:
            if child.type in _UNIT_TYPES or child.type == "declaration":
                inner = child
                if child.type == "declaration":  # template <..> class X {...};
                    inner = next(
                        (c for c in child.named_children if c.type in _UNIT_TYPES),
                        child,
                    )
                if inner.type in _UNIT_TYPES:
                    return _unit_label(inner, src, known_namespaces)
        return (["template"], "template")

    if node.type == "function_definition":
        fdecl = _find_function_declarator(node.child_by_field_name("declarator"))
        if fdecl is None:
            return (["function"], "function")
        name = _squash(_text(fdecl.child_by_field_name("declarator"), src))
        params_node = fdecl.child_by_field_name("parameters")
        params = _squash(_text(params_node, src)) if params_node else "()"
        if "::" in name:  # out-of-class method: void Stack::push(int x)
            scope, short = name.rsplit("::", 1)
            # Stack::push -> "class Stack" ; util::helper -> "namespace util"
            scope_label = f"namespace {scope}" if scope in known_namespaces else f"class {scope}"
            return ([scope_label, f"{short}{params}"], name)
        return ([f"{name}{params}"], name)

    # class / struct / union / enum
    keyword = node.type.split("_")[0]  # "class", "struct", "union", "enum"
    name_node = node.child_by_field_name("name")
    name = _squash(_text(name_node, src)) if name_node else "(anonymous)"
    return ([f"{keyword} {name}"], name)


def _is_unit(node) -> bool:
    if node.type in _UNIT_TYPES:
        # "class Foo;" (forward declaration, no body) is not worth its own block
        if node.type.endswith("_specifier") and node.child_by_field_name("body") is None:
            return False
        return True
    return False


def _unit_from_declaration(node):
    """`class X {...} obj;` is a 'declaration' that contains a class body."""
    if node.type != "declaration":
        return None
    for child in node.named_children:
        if child.type in _UNIT_TYPES and child.child_by_field_name("body") is not None:
            return child
    return None


def _collect_namespace_names(node, src: bytes, out: set[str]) -> None:
    for child in node.named_children:
        if child.type == "namespace_definition":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                out.add(_squash(_text(name_node, src)))
        _collect_namespace_names(child, src, out)


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------
def _collect_units(node, src: bytes, prefix: list[str], known: set[str], out: list[Segment]):
    for child in node.named_children:
        if child.type in _PREPROC_TYPES or child.type in _ERROR_TYPES:
            # #ifndef STACK_H ... #endif, or a part with a syntax error: look inside, path unchanged
            _collect_units(child, src, prefix, known, out)
            continue
        if child.type in _CONTAINER_TYPES:
            name_node = child.child_by_field_name("name")
            label = (
                f"namespace {_squash(_text(name_node, src))}"
                if child.type == "namespace_definition" and name_node is not None
                else ("namespace (anonymous)" if child.type == "namespace_definition" else 'extern "C"')
            )
            body = child.child_by_field_name("body")
            if body is not None:
                _collect_units(body, src, prefix + [label], known, out)
            continue

        unit = child if _is_unit(child) else _unit_from_declaration(child)
        if unit is None:
            continue
        path, symbol = _unit_label(unit, src, known)
        # use `child` for the line range so "};" / "} obj;" stay inside the block
        out.append(Segment(child.start_point[0], child.end_point[0], prefix + path, symbol, prefix))


def split_cpp(source: str) -> list[Segment]:
    """Cut the file into line ranges that together cover every line exactly once."""
    lines = _split_lines(source)
    n = len(lines)
    if n == 0:
        return []

    src = source.encode("utf-8")
    tree = Parser(_CPP).parse(src)
    known: set[str] = set()
    _collect_namespace_names(tree.root_node, src, known)

    units: list[Segment] = []
    _collect_units(tree.root_node, src, [], known, units)
    units.sort(key=lambda s: s.start)

    # 1) merge units that share a line (e.g. two one-line functions on one row)
    merged: list[Segment] = []
    for u in units:
        if merged and u.start <= merged[-1].end:
            merged[-1].end = max(merged[-1].end, u.end)
        else:
            merged.append(u)

    # 2) pull the comment lines directly above a unit into that unit
    prev_end = -1
    for u in merged:
        while u.start - 1 > prev_end and _COMMENT_LINE.match(lines[u.start - 1]):
            u.start -= 1
        prev_end = u.end

    # 3) fill the gaps with "header" segments so nothing is lost
    segments: list[Segment] = []
    cursor = 0
    prev_ctx: list[str] = []
    for u in merged:
        if u.start > cursor:
            # glue lines keep only the namespaces shared by the units on both sides
            segments.append(Segment(cursor, u.start - 1, _common(prev_ctx, u.ctx), None))
        segments.append(u)
        cursor = u.end + 1
        prev_ctx = u.ctx
    if cursor < n:
        segments.append(Segment(cursor, n - 1, [], None))

    # 4) blank-only segments get glued onto the previous one (text is never empty)
    final: list[Segment] = []
    pending_start = None  # blank lines at the very top of the file
    for seg in segments:
        blank = all(not lines[i].strip() for i in range(seg.start, seg.end + 1))
        if blank:
            if final:
                final[-1].end = seg.end
            elif pending_start is None:
                pending_start = seg.start
            continue
        if pending_start is not None:
            seg.start = pending_start
            pending_start = None
        final.append(seg)

    # 5) blank lines at the start of a block move to the end of the block before it
    for prev, seg in zip(final, final[1:]):
        while seg.start < seg.end and not lines[seg.start].strip():
            seg.start += 1
            prev.end += 1
    return final


def _common(a: list[str], b: list[str]) -> list[str]:
    """Longest shared start of two paths: ["ns a", "ns b"] + ["ns a"] -> ["ns a"]."""
    out = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out


# --------------------------------------------------------------------------
# load(): the department's entry point
# --------------------------------------------------------------------------
_PARSER = "tree-sitter-cpp"
_PARSER_VERSION = version("tree-sitter-cpp")


@register("code")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    timer = Timer()
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise FileRefused(messages.UNREADABLE)

    source = _decode(raw)
    if source is None:
        raise FileRefused(messages.UNREADABLE)
    if not source.strip():
        raise FileRefused(messages.NO_TEXT_FILE)

    title = meta.file_name  # e.g. "stack.cpp" (keeps .cpp / .h apart)
    lines = _split_lines(source)
    with timer("parse"):
        segments = split_cpp(source)

    blocks: list[Block] = []
    for seg in segments:
        text = "".join(lines[seg.start : seg.end + 1])  # exact copy, never cleaned
        blocks.append(
            Block(
                seq=len(blocks),
                kind="code",
                text=text,
                heading_path=[title, *seg.path],
                loc=Location(line_start=seg.start + 1, line_end=seg.end + 1),
                lang="code",
                extra={
                    "language": "cpp",
                    "symbol": seg.symbol,
                    "part": "unit" if seg.symbol else "header",
                },
            )
        )

    doc = parsed_document(meta, title=title, blocks=blocks, parser=_PARSER,
                          parser_version=_PARSER_VERSION, units_total=len(lines))
    doc.quality.seconds_taken.update(timer.seconds)
    return doc