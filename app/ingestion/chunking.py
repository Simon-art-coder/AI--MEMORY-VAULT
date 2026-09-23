"""
Text chunking.
"""

_BOUNDARIES = ["\n\n", ". ", "! ", "? ", ".\n", "!\n", "?\n"]
_BOUNDARY_SEARCH_FRACTION = 0.4


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        target_end = min(start + chunk_size, text_len)

        if target_end < text_len:
            end = _find_boundary_backward(text, start, target_end) or target_end
        else:
            end = target_end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        raw_next_start = max(end - overlap, start + 1)
        start = _find_boundary_forward(text, raw_next_start, end)

    return chunks


def _find_boundary_backward(text: str, start: int, target_end: int) -> int | None:
    window_size = target_end - start
    search_from = start + int(window_size * (1 - _BOUNDARY_SEARCH_FRACTION))

    best_position = None
    for boundary in _BOUNDARIES:
        idx = text.rfind(boundary, search_from, target_end)
        if idx != -1:
            candidate = idx + len(boundary)
            if best_position is None or candidate > best_position:
                best_position = candidate

    return best_position


def _find_boundary_forward(text: str, position: int, limit: int) -> int:
    best = None
    for boundary in _BOUNDARIES:
        idx = text.find(boundary, position, limit)
        if idx != -1:
            candidate = idx + len(boundary)
            if best is None or candidate < best:
                best = candidate

    if best is not None:
        return best

    idx = text.find(" ", position, limit)
    if idx != -1:
        return idx + 1

    return position