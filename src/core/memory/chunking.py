from __future__ import annotations


def chunk_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if max_chars <= 0:
        return [text] if text else []
    ov = max(0, min(overlap_chars, max_chars - 1)) if max_chars > 1 else 0
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + max_chars, n)
        chunks.append(text[i:end])
        if end >= n:
            break
        step = max(end - ov, i + 1)
        i = step
    return chunks if chunks else ([""] if text == "" else [])
