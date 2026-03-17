"""
Citation service.

Replaces LLM [P1][P2] markers with real product links.
Returns both plain text and HTML versions.

Plain text: markers kept for accessibility / fallback rendering
HTML text:  markers replaced with <a href> chips for chat UI
"""

import re
import html as html_module
from app.api.dto.chat_dto import ProductCardDTO
from app.core.logging import get_logger

logger = get_logger(__name__)

_CITATION_RE  = re.compile(r'\[P(\d+)\]')
# Convert newlines to <br> and paragraphs to <p> blocks
_NEWLINE_RE   = re.compile(r'\n{2,}')
_SINGLE_NL_RE = re.compile(r'\n')


def _text_to_html(text: str) -> str:
    """
    Convert plain text to safe HTML.
    - Escapes special HTML characters
    - Converts double newlines to paragraph breaks
    - Converts single newlines to <br>
    """
    escaped = html_module.escape(text)
    # Double newline → paragraph break
    paragraphed = _NEWLINE_RE.sub('</p><p>', escaped)
    # Single newline → line break
    lined = _SINGLE_NL_RE.sub('<br>', paragraphed)
    return f'<p>{lined}</p>' if '\n' in text or len(text) > 80 else escaped


class CitationService:

    def process(
        self,
        llm_response: str,
        citation_map: dict[str, dict],
    ) -> tuple[str, str, list[ProductCardDTO]]:
        """
        Process LLM response text.

        Returns:
          answer       — plain text (markers removed, for accessibility/fallback)
          answer_html  — safe HTML with <a href> product chips
          cited        — list of ProductCardDTO for only the products actually cited

        answer_html is ALWAYS proper HTML — never raw text passthrough.
        Even with no citations the text is HTML-escaped and formatted.
        """
        if not citation_map:
            # No products retrieved — still return safe HTML
            return llm_response, _text_to_html(llm_response), []

        cited_ids:   list[str]  = []
        seen_ids:    set[str]   = set()

        # Find all cited IDs in order of appearance (deduplicated)
        for match in _CITATION_RE.finditer(llm_response):
            cid = f"P{match.group(1)}"
            if cid in citation_map and cid not in seen_ids:
                cited_ids.append(cid)
                seen_ids.add(cid)

        # Build product card list
        cited_products: list[ProductCardDTO] = []
        for cid in cited_ids:
            data = citation_map[cid]
            cited_products.append(ProductCardDTO(
                citation_id=data["citation_id"],
                title=data["title"],
                url=data["url"],
                price=data.get("price"),
                currency=data.get("currency", "USD"),
                image_url=data.get("image_url"),
                sku=data.get("sku"),
                in_stock=data.get("in_stock", True),
                rating=data.get("rating"),
                similarity=data.get("similarity"),
            ))

        # Build HTML version — escape text, replace citation markers with chips
        def _replace_with_chip(match: re.Match) -> str:
            cid = f"P{match.group(1)}"
            if cid not in citation_map:
                return ""  # remove unknown citations silently
            data = citation_map[cid]
            url   = html_module.escape(data.get("url", "#"))
            title = html_module.escape(data.get("title", "Product"))
            sku   = html_module.escape(str(data.get("sku", "")))
            return (
                f'<a href="{url}" '
                f'class="product-chip" '
                f'data-sku="{sku}" '
                f'target="_blank" rel="noopener">'
                f'{title} ↗</a>'
            )

        # First escape the whole text, then restore citation markers,
        # then replace them with chips
        escaped_response = html_module.escape(llm_response)
        # html.escape turns [P1] into [P1] (no change) — safe to sub directly
        answer_html = _CITATION_RE.sub(_replace_with_chip, escaped_response)
        # Format newlines as HTML
        answer_html = _NEWLINE_RE.sub('</p><p>', answer_html)
        answer_html = _SINGLE_NL_RE.sub('<br>', answer_html)
        if '\n' in llm_response or len(llm_response) > 80:
            answer_html = f'<p>{answer_html}</p>'

        # Clean plain text — remove citation markers entirely
        answer = _CITATION_RE.sub("", llm_response).strip()
        # Collapse multiple spaces left behind by marker removal
        answer = re.sub(r'  +', ' ', answer)

        logger.debug(
            "citations.processed",
            total_in_map=len(citation_map),
            cited_count=len(cited_products),
        )

        return answer, answer_html, cited_products
