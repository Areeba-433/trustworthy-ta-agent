"""PowerPoint loader: Docling's PowerPoint reader, then the shared to_blocks().

A broken file needs no code here: convert() raises FileRefused and ingest_file() turns it into a failed document.
"""
from pathlib import Path

from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import ParsedDocument, ResourceMeta, SourceType
from app.ingestion.documents import parsed_document
from app.ingestion.registry import register

SOURCE_TYPE: SourceType = "pptx"


@register("pptx", heavy=True)
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    from app.ingestion import converter                  # 9 s to import (step 1): only once a deck is really loaded
    from app.ingestion.docling_blocks import to_blocks   # 2 s to import (step 1)

    conversion = converter.convert(path, SOURCE_TYPE, meta.file_sha256)    # a broken file raises FileRefused
    title = title_from_filename(meta.file_name)
    return parsed_document(
        meta, title=title, blocks=to_blocks(conversion.document, SOURCE_TYPE, title),
        parser=converter.PARSER, parser_version=converter.PARSER_VERSION,
        units_total=len(conversion.document.pages),      # every slide, empty and hidden ones included
        problems=conversion.problems,
    )