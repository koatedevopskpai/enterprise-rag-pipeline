from ragpipeline.config import CHUNK_OVERLAP, CHUNK_SIZE


def _windows(text, size, overlap):
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    normalized = " ".join(text.split())
    windows = []
    start = 0
    while start < len(normalized):
        end = start + size
        piece = normalized[start:end].strip()
        if piece:
            windows.append(piece)
        if end >= len(normalized):
            break
        start = end - overlap
    return windows


def chunk_text(text, source_id, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    for index, piece in enumerate(_windows(text, size, overlap)):
        chunks.append(
            {
                "id": f"{source_id}-{index:04d}",
                "source_id": source_id,
                "chunk_index": index,
                "content": piece,
            }
        )
    return chunks


def split_markdown_sections(text):
    sections = []
    title = ""
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            if lines:
                sections.append((title, "\n".join(lines).strip()))
            title = line.lstrip("#").strip()
            lines = []
        else:
            lines.append(line)
    if lines:
        sections.append((title, "\n".join(lines).strip()))
    return [(t, b) for t, b in sections if b]


def chunk_markdown(text, source_id, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    children = []
    for section_index, (title, body) in enumerate(split_markdown_sections(text)):
        parent_id = f"{source_id}-p{section_index:02d}"
        raw_parent = f"{title}\n{body}" if title else body
        parent_text = " ".join(raw_parent.split())
        for child_index, piece in enumerate(_windows(parent_text, size, overlap)):
            children.append(
                {
                    "id": f"{parent_id}-c{child_index:02d}",
                    "source_id": source_id,
                    "parent_id": parent_id,
                    "section": title,
                    "content": piece,
                    "parent_content": parent_text,
                }
            )
    return children
