import logging
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import NamedTuple

from docx import Document as WordDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import nsmap, qn
from docx.text.paragraph import Paragraph
from docling_core.types.doc import DoclingDocument, GroupItem

from app.ingestion.cleaning.common import clean_text, detect_lang, title_from_filename
from app.ingestion.contract import Block, ParsedDocument, ResourceMeta
from app.ingestion.converter import PARSER, PARSER_VERSION, convert
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.documents import parsed_document
from app.ingestion.loaders.docx_flowchart import Flowchart, read_flowcharts
from app.ingestion.registry import register

logger = logging.getLogger("tta.ingestion")

_W = {"w": nsmap["w"]}
_TOC_STYLE = re.compile(r"toc (heading|\d)")                   # Word's names: "TOC Heading", "toc 1" ... "toc 9"
_SKIPPED_PARTS = {"Table of Contents", "Cover Pages"}          # Word content controls that are not course content
_P, _RUN, _HIDDEN = qn("w:p"), qn("w:r"), f'{qn("w:rPr")}/{qn("w:vanish")}'
_RUN_FONT, _RUN_STYLE = f'{qn("w:rPr")}/{qn("w:rFonts")}', f'{qn("w:rPr")}/{qn("w:rStyle")}'

_MONO_FONTS = {"consolas", "courier", "courier new", "lucida console", "lucida sans typewriter",
               "menlo", "monaco", "inconsolata", "andale mono"}
_MONO_WORDS = ("mono", "code")              # Cascadia Mono, Roboto Mono, Source Code Pro, Fira Code ...
_CODE_SHARE = 0.9                           # a paragraph is code when this share of its letters is monospace
_NOT_CODE_STYLE = re.compile(r"heading|title|caption|toc|list")
_RUN_BOLD, _RUN_SIZE = f'{qn("w:rPr")}/{qn("w:b")}', f'{qn("w:rPr")}/{qn("w:sz")}'
_OUTLINE = f'{qn("w:pPr")}/{qn("w:outlineLvl")}'
_TITLE_WORDS = 12                          # a bold title line is short
_TITLE_LEVELS = 3                          # bold titles nest at most this deep, bigger font = higher level
_CAPTION_START = re.compile(r"(fig(ure)?|table|chart|graph|diagram)\b\.?\s*[\d:]", re.IGNORECASE)

# Flowcharts drawn with Word shapes: their arrows are read from the file (docx_flowchart.py).
_SHAPE_KINDS = ("paragraph", "heading", "list_item")   # the kinds Docling gives a shape's text
_SHAPE_GAP = 3                              # blocks: at most this many other blocks between two pieces of a chart


class _WordFacts(NamedTuple):
    """What Word knows about its paragraphs but Docling does not tell us."""
    captions: Counter[str]          # paragraphs in the Caption style
    skipped: Counter[str]           # table of contents and cover page lines
    visible: dict[str, str]         # text of a paragraph with hidden words -> the same text without them
    code: list[list[str]]           # runs of paragraphs set in a monospace font, line by line as Word shows them
    titles: list[tuple[str, int]]   # bold title lines (key, level), only for a file without any heading style


def _norm(text: str) -> str:
    """Clean Word's text the same way to_blocks() cleans block text, so the two compare equal."""
    return " ".join(clean_text(text).split())


def _doc_parts(element) -> set[str]:
    """The kinds of Word content control around a paragraph, e.g. "Table of Contents" or "Cover Pages"."""
    return {
        kind
        for sdt in element.iterancestors(qn("w:sdt"))
        for kind in sdt.xpath("./w:sdtPr/w:docPartObj/w:docPartGallery/@w:val", namespaces=_W)
    }


def _is_hidden(run) -> bool:
    vanish = run.find(_HIDDEN)
    return vanish is not None and vanish.get(qn("w:val"), "true") not in ("0", "false")


def _own_runs(paragraph) -> list:
    """The paragraph's runs, also inside links and tracked insertions, but not those of a text box inside it."""
    return [run for run in paragraph.iter(_RUN) if next(run.iterancestors(_P)) is paragraph]


def _run_text(paragraph, keep_hidden: bool) -> str:
    """The paragraph's text, run by run. Deleted text is never included."""
    return "".join(run.text for run in _own_runs(paragraph) if keep_hidden or not _is_hidden(run))


def _is_mono(font: str | None) -> bool:
    name = (font or "").casefold()
    return bool(name) and (name in _MONO_FONTS or any(word in name for word in _MONO_WORDS))


def _style_font(style) -> str | None:
    """A style's font, looking through the styles it is based on."""
    while style is not None:
        if style.font.name:
            return style.font.name
        style = style.base_style
    return None


def _run_font(run, paragraph_font: str | None, styles_by_id: dict) -> str | None:
    """The font a run is shown in: its own, else its character style's, else the paragraph style's.

    The document's default font is left out on purpose: it says nothing about the author marking code.
    """
    fonts = run.find(_RUN_FONT)
    if fonts is not None and (name := fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))):
        return name
    char_style = run.find(_RUN_STYLE)
    if char_style is not None and (name := _style_font(styles_by_id.get(char_style.get(qn("w:val"))))):
        return name
    return paragraph_font


def _key(text: str) -> str:
    """Words only: a title still matches when a loose ":" or "-" around it was cleaned away."""
    return " ".join(word for word in _norm(text).split() if any(ch.isalnum() for ch in word))


def _is_title_line(raw: str, letters: int, mono: int) -> bool:
    """Short, one line, not ending like a sentence, not a caption and not code."""
    text = " ".join(raw.split())
    return (bool(letters) and mono < _CODE_SHARE * letters and "\n" not in raw.strip()
            and 0 < len(text.split()) <= _TITLE_WORDS and not text.endswith((".", ",", ";"))
            and not _CAPTION_START.match(text))


def _style_value(style, read):
    """A style's own value, else the value of the style it is based on, and so on."""
    while style is not None:
        if (value := read(style)) is not None:
            return value
        style = style.base_style
    return None


def _bold_share_and_size(paragraph, style, styles_by_id: dict) -> tuple[float, float]:
    """The share of letters and digits that are bold, and the biggest font size (points), of the visible runs."""
    paragraph_bold = bool(_style_value(style, lambda s: s.font.bold))
    paragraph_size = _style_value(style, lambda s: s.font.size)
    bold_letters = all_letters = 0
    size = 0.0
    for run in _own_runs(paragraph):
        if _is_hidden(run):
            continue
        letters = sum(ch.isalnum() for ch in run.text)
        if not letters:
            continue
        flag = run.find(_RUN_BOLD)
        if flag is not None:
            bold = flag.get(qn("w:val"), "true") not in ("0", "false")
        else:
            char_style = run.find(_RUN_STYLE)
            char_bold = _style_value(styles_by_id.get(char_style.get(qn("w:val"))), lambda s: s.font.bold) \
                if char_style is not None else None
            bold = paragraph_bold if char_bold is None else char_bold
        all_letters += letters
        bold_letters += letters if bold else 0
        run_size = run.find(_RUN_SIZE)
        points = int(run_size.get(qn("w:val"))) / 2 if run_size is not None else (
            paragraph_size.pt if paragraph_size is not None else 0.0)
        size = max(size, points)
    return (bold_letters / all_letters if all_letters else 0.0), size


def _word_facts(path: Path) -> _WordFacts:
    empty = _WordFacts(captions=Counter(), skipped=Counter(), visible={}, code=[], titles=[])
    try:
        word = WordDocument(str(path))
    except Exception:
        logger.warning("Word styles not read, python-docx failed on %s", path.name, exc_info=True)
        return empty
    captions, skipped, visible = Counter(), Counter(), {}
    code: list[list[str]] = []
    lines: list[str] = []                   # the code run being collected
    heading_mono = heading_letters = 0      # to tell a file typed all in Courier from one with code in it
    has_headings = False
    title_lines: list[tuple[str, float]] = []    # (key, font size) of bold title lines
    styles_by_id = {style.style_id: style for style in word.styles}

    def end_code_run() -> None:
        while lines and not lines[-1].strip():
            lines.pop()                     # a code run never ends in blank lines
        if lines:
            code.append(list(lines))
        lines.clear()

    # body.iter() reaches every paragraph, also inside content controls and tables.
    # word.paragraphs returns only the top-level ones and misses the table of contents and cover page.
    for element in word.element.body.iter(_P, qn("w:tbl")):
        if element.tag != _P:
            end_code_run()                  # a table ends a code run
            continue
        text = _norm(_run_text(element, keep_hidden=True))
        style = Paragraph(element, word).style
        style_name = style.name.casefold() if style is not None else ""
        if text:
            if style_name == "caption":
                captions[text] += 1
            elif _TOC_STYLE.fullmatch(style_name) or _doc_parts(element) & _SKIPPED_PARTS:
                skipped[text] += 1
            if any(_is_hidden(run) for run in _own_runs(element)):
                visible[text] = _norm(_run_text(element, keep_hidden=False))

        # Code and bold titles: only paragraphs in the body, not in a table cell or text box.
        # Code is a paragraph, not a heading, caption or list item, (nearly) all in a monospace font.
        if any(True for _ in element.iterancestors(qn("w:tc"), qn("w:txbxContent"))):
            continue
        raw = _run_text(element, keep_hidden=False)
        paragraph_font = _style_font(style)
        mono = total = 0
        for run in _own_runs(element):
            if _is_hidden(run):
                continue
            letters = len("".join(run.text.split()))
            total += letters
            if _is_mono(_run_font(run, paragraph_font, styles_by_id)):
                mono += letters
        if style_name.startswith(("heading", "title")):
            heading_mono, heading_letters = heading_mono + mono, heading_letters + total
        is_list = element.find(f'{qn("w:pPr")}/{qn("w:numPr")}') is not None
        if style_name.startswith(("heading", "title")) or element.find(_OUTLINE) is not None:
            has_headings = True
        elif not is_list and not _NOT_CODE_STYLE.search(style_name) and _is_title_line(raw, total, mono):
            bold, size = _bold_share_and_size(element, style, styles_by_id)
            if bold >= _CODE_SHARE:
                title_lines.append((_key(raw), size))
        if not raw.strip():
            if lines:
                lines.append("")            # a blank line inside a code run stays
            continue
        if (total and mono / total >= _CODE_SHARE and not is_list
                and not _NOT_CODE_STYLE.search(style_name)):
            lines.extend(raw.split("\n"))   # Shift+Enter inside a code paragraph starts a new line
        else:
            end_code_run()
    end_code_run()
    normal_font = _style_font(word.styles.default(WD_STYLE_TYPE.PARAGRAPH))
    if _is_mono(normal_font) or (heading_letters and heading_mono / heading_letters >= 0.5):
        code = []                           # the whole file is set in a monospace font: its look, not code
    titles: list[tuple[str, int]] = []
    if not has_headings:                    # a file with real headings keeps its bold lines as paragraphs
        sizes = sorted({size for _, size in title_lines}, reverse=True)
        titles = [(key, min(sizes.index(size) + 1, _TITLE_LEVELS)) for key, size in title_lines]
    return _WordFacts(captions=captions, skipped=skipped, visible=visible, code=code, titles=titles)


def _drop_word_extras(blocks: list[Block], skipped: Counter[str]) -> list[Block]:
    """Leave out the table of contents and the cover page, and take their headings out of the heading paths.

    Each skipped line is used once. Both come before the real content, so a real heading with the same
    words is kept.
    """
    out: list[Block] = []
    dropped: list[list[str]] = []          # heading paths of dropped headings, each ending in its own text
    for block in blocks:
        key = _norm(block.text)
        if block.kind in ("heading", "paragraph") and skipped[key] > 0:
            skipped[key] -= 1
            if block.kind == "heading":
                dropped.append(block.heading_path)
            continue
        remove = {len(d) - 1 for d in dropped if block.heading_path[:len(d)] == d}
        if remove:
            path = [h for i, h in enumerate(block.heading_path) if i not in remove]
            block = block.model_copy(update={"heading_path": path})
        out.append(block)
    return out


def _drop_hidden_text(blocks: list[Block], visible: dict[str, str]) -> list[Block]:
    """Word's hidden text (Font > Hidden) is not shown to students, so it is not course content."""
    out: list[Block] = []
    for block in blocks:
        key = _norm(block.text)
        if block.kind in ("heading", "paragraph") and key in visible:
            if not visible[key]:
                continue                                    # the whole paragraph was hidden
            block = block.model_copy(update={"text": visible[key]})
        out.append(block)
    return out


def _words(text: str) -> list[str]:
    """The words of a code text, line by line as the cleaner sees them. Bare symbols ("}", "|") are skipped:
    the cleaner drops a line holding nothing else, so they cannot be matched reliably."""
    return [word for line in text.split("\n") for word in _norm(line).split()
            if any(ch.isalnum() for ch in word)]


def _code_span(blocks: list[Block], first: int, want: list[str]) -> int:
    """How many blocks from `first` hold exactly the words of a code run, in order; 0 if they don't."""
    got: list[str] = []
    for count, block in enumerate(blocks[first:], start=1):
        if block.kind not in ("paragraph", "code"):
            return 0
        got += _words(block.text)
        if got != want[:len(got)]:
            return 0
        if len(got) == len(want):
            return count
    return 0


def _mark_code(blocks: list[Block], code: list[list[str]]) -> list[Block]:
    """Make each run of monospace paragraphs one code block, with Word's exact spacing.

    Docling marks a monospace paragraph as code only when it looks like code ({ } = < >, a call, a def line),
    and not at all in a file without a Normal style, so commands like "ls -la" come back as paragraphs with
    their spacing cleaned away. A run may come back as a mix of paragraph and code blocks, and a line the
    cleaner empties ("}") has no block at all, so the text is taken from Word.
    """
    out = list(blocks)
    start = 0
    for lines in code:
        want = _words("\n".join(lines))
        if not want:
            continue
        for first in range(start, len(out)):
            span = _code_span(out, first, want)
            if span:
                text = "\n".join(line.rstrip() for line in lines).strip("\n")
                out[first:first + span] = [out[first].model_copy(update={"kind": "code", "text": text, "lang": "code"})]
                start = first + 1
                break
    return out


def _mark_captions(blocks: list[Block], captions: Counter[str]) -> list[Block]:
    out: list[Block] = []
    for block in blocks:
        key = _norm(block.text)
        if block.kind == "paragraph" and captions[key] > 0:
            captions[key] -= 1
            block = block.model_copy(update={"kind": "caption"})
        out.append(block)
    return _link_captions(out)


def _link_captions(blocks: list[Block]) -> list[Block]:
    """Tie each caption to the picture next to it (contract 2.1).

    Word keeps a caption ("Figure 2: ...") as a paragraph of its own and Docling does not tie it to the
    picture, so the picture comes as a "[Figure]" placeholder with no words. A caption right below the
    placeholder (or else right above it) takes its figure_id, and the placeholder goes: the caption now
    shows that a figure was there. A table's caption is left alone.
    """
    out = list(blocks)
    taken: set[int] = set()
    for i, block in enumerate(out):
        if block.kind != "caption" or block.figure_id or block.text.casefold().startswith("table"):
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(out) and j not in taken and out[j].kind == "figure":
                out[i] = block.model_copy(update={"figure_id": out[j].figure_id})
                taken.add(j)
                break
    return [block for k, block in enumerate(out) if k not in taken]


def _promote_titles(blocks: list[Block], titles: list[tuple[str, int]], title: str) -> list[Block]:
    """In a file without any heading style, its bold title lines are its headings: make them headings and
    give every block the heading path above it, so each section gets its own chunks.

    Without this, the chunker packs paragraphs by size alone and a title can end up at the bottom of the
    previous section's chunk, away from the text it names. A title with the same words as the file's title
    is already heading_path[0], so it adds no level.
    """
    if not titles or any(block.kind == "heading" for block in blocks):
        return blocks                       # Docling found real headings (e.g. a style in another language)
    levels: dict[str, deque[int]] = defaultdict(deque)
    for key, level in titles:
        levels[key].append(level)
    stack: list[tuple[int, str]] = []
    out: list[Block] = []
    for block in blocks:
        key = _key(block.text)
        if block.kind == "paragraph" and levels.get(key):
            level = levels[key].popleft()
            if block.text.casefold().split() != title.casefold().split():
                stack = [h for h in stack if h[0] < level] + [(level, block.text)]
            out.append(block.model_copy(update={"kind": "heading", "heading_path": [title] + [h[1] for h in stack]}))
        elif stack:
            out.append(block.model_copy(update={"heading_path": block.heading_path[:1] + [h[1] for h in stack]}))
        else:
            out.append(block)
    return out


def _plain_words(text: str) -> str:
    """Letters and digits only, lower case, space around: "Records removed before screening:" contains the
    piece "before screening" that Docling split off where the bold ends."""
    return " " + " ".join(re.findall(r"\w+", _norm(text).casefold())) + " "


def _shape_text_refs(doc: DoclingDocument) -> set[str]:
    """Ids of the texts Docling took from Word text boxes, i.e. the words inside shapes."""
    refs: set[str] = set()
    for item in doc.texts:
        node = item
        while node.parent is not None:
            node = node.parent.resolve(doc)
            if isinstance(node, GroupItem) and node.name == "textbox":
                refs.add(item.self_ref)
                break
    return refs


def _flowcharts(path: Path) -> list[Flowchart]:
    try:
        return read_flowcharts(path)
    except Exception:                       # a drawing this reader does not understand must not stop the file
        logger.warning("flowcharts not read in %s", path.name, exc_info=True)
        return []


def _add_flowcharts(blocks: list[Block], charts: list[Flowchart],
                    shape_refs: set[str]) -> tuple[list[Block], set[str]]:
    """Put each flowchart, written out with its arrows, where Docling left the loose words of its shapes.

    Docling gives each paragraph inside a shape as its own block ("Records screened", "(n =3007)", ...) and
    nothing about the arrows. A block is a piece of a flowchart when it came from a shape and its words are
    in one of the flowchart's paragraphs (Docling may split a paragraph where the formatting changes).
    The longest run of such blocks, with at most _SHAPE_GAP other blocks between two of them, is replaced
    by one figure_text block in the place of the first one. A shape's text elsewhere in the file is kept.
    Returns the blocks and the ids of the blocks taken out.
    """
    out = list(blocks)
    taken: set[str] = set()
    for chart in charts:
        paragraphs = [words for text in chart.texts if (words := _plain_words(text)).strip()]
        hits = [i for i, block in enumerate(out)
                if block.kind in _SHAPE_KINDS and block.extra.get("ref") in shape_refs
                and (words := _plain_words(block.text)).strip() and any(words in p for p in paragraphs)]
        if not hits:
            logger.info("a flowchart was read but Docling has no text from its shapes; left as it was")
            continue
        runs = [[hits[0]]]
        for i in hits[1:]:
            if i - runs[-1][-1] <= _SHAPE_GAP + 1:
                runs[-1].append(i)
            else:
                runs.append([i])
        run = max(runs, key=len)
        first = out[run[0]]
        chart_block = Block(
            seq=0, kind="figure_text", text=chart.text, heading_path=first.heading_path, loc=first.loc,
            lang=detect_lang(chart.text), extra={"ref": first.extra.get("ref"), "source": "shapes"},
        )
        taken.update(out[i].extra.get("ref") for i in run)
        drop = set(run)
        out = out[:run[0]] + [chart_block] + [b for i, b in enumerate(out) if i > run[0] and i not in drop]
    return out, taken


@register("docx", heavy=True)
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    title = title_from_filename(meta.file_name)
    conversion = convert(path, "docx", meta.file_sha256)
    facts = _word_facts(path)
    blocks = to_blocks(conversion.document, "docx", title)
    blocks = _drop_word_extras(blocks, facts.skipped)
    blocks = _drop_hidden_text(blocks, facts.visible)
    blocks = _mark_code(blocks, facts.code)
    blocks = _mark_captions(blocks, facts.captions)
    blocks = _promote_titles(blocks, facts.titles, title)
    charts = _flowcharts(path)
    if charts:
        blocks, _ = _add_flowcharts(blocks, charts, _shape_text_refs(conversion.document))
    return parsed_document(
        meta, title=title, blocks=blocks, parser=PARSER, parser_version=PARSER_VERSION,
        units_total=len(blocks), problems=conversion.problems,
    )
