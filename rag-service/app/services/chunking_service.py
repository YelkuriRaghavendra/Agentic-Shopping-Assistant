import re
import tiktoken
from dataclasses import dataclass
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger   = get_logger(__name__)


_TOKENIZER = None

def _get_tokenizer():
    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER
    try:
        _TOKENIZER = tiktoken.get_encoding("cl100k_base")
        return _TOKENIZER
    except Exception:
        return None


def count_tokens(text: str) -> int:
    encoder = _get_tokenizer()
    if encoder:
        return len(encoder.encode(text))
    return max(1, int(len(text.split()) * 1.3))


@dataclass
class TextChunk:
    content:     str
    chunk_index: int
    token_count: int
    character_start:  int
    character_end:    int


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
    min_chunk: int,
) -> list[TextChunk]:
    """
    Split text into overlapping token-bounded chunks.
    Defaults come from config/ingestion_config.json if not provided.

    Steps:
      1. Split on double newlines (paragraph boundaries).
      2. If a paragraph is within chunk_size, accumulate it.
      3. If a paragraph exceeds chunk_size, split at sentence level.
      4. Apply token-level sliding window as final fallback.
    """

    if not text or not text.strip():
        return []

    total_tokens = count_tokens(text.strip())
    # If the whole text is shorter than min_chunk, keep it as one chunk
    # — don't silently discard short documents
    if total_tokens < min_chunk:
        min_chunk = max(1, total_tokens)

    # Step 1: paragraph split
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]

    # Step 2 & 3: group into chunks respecting token limits
    raw_chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)

        if paragraph_tokens > chunk_size:
            # flush current buffer first
            if current_parts:
                raw_chunks.append(" ".join(current_parts))
                current_parts, current_tokens = [], 0
            # split oversized paragraph at sentence level
            raw_chunks.extend(_split_by_sentences(paragraph, chunk_size))
            continue

        if current_tokens + paragraph_tokens > chunk_size and current_parts:
            raw_chunks.append(" ".join(current_parts))
            # overlap: keep last paragraph if it fits
            if paragraph_tokens <= overlap and current_parts:
                current_parts = [current_parts[-1], paragraph]
                current_tokens = count_tokens(current_parts[0]) + paragraph_tokens
            else:
                current_parts = [paragraph]
                current_tokens = paragraph_tokens
        else:
            current_parts.append(paragraph)
            current_tokens += paragraph_tokens

    if current_parts:
        raw_chunks.append(" ".join(current_parts))

    # Step 4: apply token-level overlap between adjacent chunks
    overlapped = _apply_overlap(raw_chunks, overlap)

    # Build result objects with character offsets
    chunks: list[TextChunk] = []
    search_start = 0

    for index, chunk_text_value in enumerate(overlapped):
        stripped = chunk_text_value.strip()
        token_count = count_tokens(stripped)
        if token_count < min_chunk:
            continue

        # find character position in original text
        pos = text.find(stripped[:50], search_start)
        character_start = pos if pos != -1 else 0
        character_end = character_start + len(stripped)
        search_start = max(0, character_end - len(stripped) // 4)

        chunks.append(TextChunk(
            content=stripped,
            chunk_index=index,
            token_count=count_tokens(stripped),
            character_start=character_start,
            character_end=character_end,
        ))

    # Re-index sequentially (min_chunk filter may have removed some)
    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index

    logger.debug(
        "chunking.complete",
        input_chars=len(text),
        output_chunks=len(chunks),
    )
    return chunks


def _split_by_sentences(text: str, chunk_size: int) -> list[str]:
    """Split a large paragraph at sentence boundaries.
    Falls back to token-level sliding window if no sentence boundaries exist."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0

    for sentence in sentences:
        sentence_token_count = count_tokens(sentence)
        if buffer_tokens + sentence_token_count > chunk_size and buffer:
            result.append(" ".join(buffer))
            buffer, buffer_tokens = [sentence], sentence_token_count
        else:
            buffer.append(sentence)
            buffer_tokens += sentence_token_count

    if buffer:
        result.append(" ".join(buffer))

    # If sentence splitting didn't help (no punctuation), fall back to
    # word-level sliding window so we don't return one massive chunk
    if len(result) == 1 and count_tokens(result[0]) > chunk_size:
        return _sliding_window(result[0], chunk_size)

    return result


def _sliding_window(text: str, chunk_size: int) -> list[str]:
    """Token-level sliding window — last resort for text with no boundaries."""
    words  = text.split()
    chunks: list[str] = []
    index = 0
    # approximate: use word count since count_tokens needs a download
    words_per_chunk = max(1, chunk_size)
    while index < len(words):
        chunk = " ".join(words[index: index + words_per_chunk])
        if chunk.strip():
            chunks.append(chunk)
        index += words_per_chunk
    return chunks or [text]


def _apply_overlap(chunks: list[str], overlap_tokens: int) -> list[str]:
    """
    Prepend the tail of the previous chunk to each chunk.
    Falls back to word-level overlap when tokenizer is unavailable.
    """
    if len(chunks) <= 1 or overlap_tokens <= 0:
        return chunks

    encoder = _get_tokenizer()
    result  = [chunks[0]]
    for index in range(1, len(chunks)):
        if encoder:
            # Count overlap_tokens worth of tokens from the end of the previous chunk
            # but decode at word boundary to avoid partial-token UTF-8 fragments
            previous_words     = chunks[index - 1].split()
            # Approximate: overlap_tokens tokens ≈ overlap_tokens words (1:1 for English)
            overlap_word_count = max(1, overlap_tokens)
            overlap_text       = " ".join(previous_words[-overlap_word_count:])
        else:
            words        = chunks[index - 1].split()
            overlap_text = " ".join(words[-max(1, overlap_tokens):])
        result.append(overlap_text + " " + chunks[index])
    return result
