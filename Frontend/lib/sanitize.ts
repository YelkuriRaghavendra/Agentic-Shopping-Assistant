import DOMPurify from "dompurify";

const ALLOWED_TAGS = ["a", "b", "strong", "em", "i", "ul", "ol", "li", "p", "br", "span", "div", "table", "thead", "tbody", "tr", "th", "td"];
const ALLOWED_ATTR = ["href", "target", "rel", "class", "style"];

export function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    FORCE_BODY: true,
  });
}
