"""
Citation service.

Replaces LLM [P1][P2] markers with real product links.
Returns both plain text and HTML versions.

Plain text: markers removed, for accessibility / fallback rendering
HTML text:  Markdown rendered to HTML, [P1] markers replaced with <a href> chips
"""

import re
import html as html_module
import markdown as md_lib

from app.api.dto.chat_dto import ProductCardDTO
from app.core.logging import get_logger

logger = get_logger(__name__)

_CITATION_RE    = re.compile(r'\[P(\d+)\]')
_PLACEHOLDER_RE = re.compile(r'CITE_P(\d+)_CITE')

# nl2br converts single newlines to <br>, matching chat UI expectations
_md = md_lib.Markdown(extensions=["nl2br"])


def _to_placeholder(match: re.Match) -> str:
    """Temporarily hide [P1] markers so the markdown parser doesn't touch them."""
    return f"CITE_P{match.group(1)}_CITE"


def _markdown_to_html(text: str) -> str:
    """
    Convert LLM markdown output to safe HTML.

    html.escape() is applied first to neutralise any raw HTML tags (XSS
    prevention). It only escapes <, >, &, ", ' — none of which are part of
    Markdown syntax (* _ # ` - etc.) — so bold/italic/lists still render.
    """
    escaped = html_module.escape(text)
    _md.reset()
    return _md.convert(escaped)


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
          answer_html  — Markdown rendered to HTML with <a href> product chips
          cited        — list of ProductCardDTO for products actually cited

        answer_html is ALWAYS proper HTML — never raw text passthrough.
        """
        # ── Collect cited product IDs in order of appearance ─────────────
        cited_ids: list[str] = []
        seen_ids:  set[str]  = set()
        for match in _CITATION_RE.finditer(llm_response):
            cid = f"P{match.group(1)}"
            if cid in citation_map and cid not in seen_ids:
                cited_ids.append(cid)
                seen_ids.add(cid)

        # ── Build product card list ───────────────────────────────────────
        cited_products: list[ProductCardDTO] = []
        for cid in cited_ids:
            data = citation_map[cid]
            cited_products.append(ProductCardDTO(
                productId=data["citation_id"],
                productName=data["title"],
                price=data.get("price"),
                rating=data.get("rating"),
                productImageUrl=data.get("image_url"),
            ))

        # ── Build HTML version ────────────────────────────────────────────
        # Step 1: replace [P1] markers with placeholders so the markdown
        #         parser doesn't interpret them as link references
        with_placeholders = _CITATION_RE.sub(_to_placeholder, llm_response)

        # Step 2: render markdown → HTML (handles bold, italic, lists, headers)
        answer_html = _markdown_to_html(with_placeholders)

        # Step 3: swap placeholders back to <a href> product chip HTML
        def _chip(match: re.Match) -> str:
            cid = f"P{match.group(1)}"
            if cid not in citation_map:
                return ""
            data  = citation_map[cid]
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

        answer_html = _PLACEHOLDER_RE.sub(_chip, answer_html)

        # ── Build plain text ──────────────────────────────────────────────
        # Remove citation markers and collapse extra spaces
        answer = _CITATION_RE.sub("", llm_response).strip()
        answer = re.sub(r'  +', ' ', answer)

        logger.debug(
            "citations.processed",
            total_in_map=len(citation_map),
            cited_count=len(cited_products),
        )

        return answer, answer_html, cited_products
