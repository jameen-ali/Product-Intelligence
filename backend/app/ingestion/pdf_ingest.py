"""
PDF ingestion pipeline using Docling.
Produces a structured document representation preserving page/section/table provenance.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class TextBlock:
    block_id: str
    text: str
    page: int
    section_header: Optional[str] = None
    block_type: str = "text"  # text | table | heading
    bbox: Optional[dict] = None

@dataclass
class ParsedDocument:
    filename: str
    file_hash: str
    page_count: int
    blocks: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    raw_text: str = ""  # flat concatenation for embedding fallback
    parse_error: Optional[str] = None

def parse_pdf(pdf_path: str, file_hash: str) -> ParsedDocument:
    """
    Parse a PDF with Docling, extracting structured blocks with page provenance.
    Returns ParsedDocument. On Docling failure, returns document with parse_error set.
    """
    path = Path(pdf_path)
    if not path.exists():
        return ParsedDocument(
            filename=path.name, file_hash=file_hash,
            page_count=0, parse_error=f"File not found: {pdf_path}"
        )

    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document

        blocks = []
        raw_parts = []
        current_section = None

        # Iterate Docling document elements
        for item, level in doc.iterate_items():
            item_type = type(item).__name__

            page_num = 1
            bbox_data = None
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                page_num = getattr(prov, "page_no", 1)
                if hasattr(prov, "bbox"):
                    b = prov.bbox
                    bbox_data = {"l": getattr(b, "l", 0), "t": getattr(b, "t", 0),
                                 "r": getattr(b, "r", 0), "b": getattr(b, "b", 0)}

            text = ""
            block_type = "text"

            if hasattr(item, "text") and item.text:
                text = item.text.strip()
            elif hasattr(item, "export_to_markdown"):
                text = item.export_to_markdown().strip()

            if "Section" in item_type or "Heading" in item_type:
                block_type = "heading"
                current_section = text
            elif "Table" in item_type:
                block_type = "table"
                if hasattr(item, "export_to_markdown"):
                    text = item.export_to_markdown()

            if not text:
                continue

            block_id = f"block_{len(blocks):04d}"
            blocks.append(TextBlock(
                block_id=block_id,
                text=text,
                page=page_num,
                section_header=current_section,
                block_type=block_type,
                bbox=bbox_data
            ))
            raw_parts.append(text)

        # Page count from metadata
        page_count = 0
        if hasattr(doc, "pages") and doc.pages:
            page_count = len(doc.pages)

        return ParsedDocument(
            filename=path.name,
            file_hash=file_hash,
            page_count=page_count,
            blocks=blocks,
            metadata={"source_format": "pdf", "block_count": len(blocks)},
            raw_text="\n".join(raw_parts),
        )

    except ImportError:
        logger.error("Docling is not installed. Run: pip install docling")
        return ParsedDocument(
            filename=Path(pdf_path).name, file_hash=file_hash,
            page_count=0, parse_error="Docling not installed"
        )
    except Exception as e:
        logger.error(f"Docling parsing failed for {pdf_path}: {e}")
        return ParsedDocument(
            filename=Path(pdf_path).name, file_hash=file_hash,
            page_count=0, parse_error=str(e)
        )
