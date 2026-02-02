#!/usr/bin/env python3
"""Extract AnKing notes and media from .apkg into enriched_med_deck/."""

from __future__ import annotations

import html
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pyzstd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APKG_PATH = PROJECT_ROOT / "data" / "AnKing_Step_Deck_v12_with_Media.apkg"
OUTPUT_DIR = PROJECT_ROOT / "enriched_med_deck"
DB_PATH = OUTPUT_DIR / "deck.sqlite"
MEDIA_DIR = OUTPUT_DIR / "media"

ANKING_MODEL_ID = 1659130414530
FIELD_SEP = "\x1f"

# Field indices in notes.flds
IDX_TEXT = 0
IDX_EXTRA = 1
IDX_ONE_BY_ONE = 16

# Regex patterns
RE_CLOZE_NUM = re.compile(r"\{\{c(\d+)::")
RE_IMG_TAG = re.compile(r'<img\s[^>]*?src\s*=\s*["\']([^"\']+)["\'][^>]*?>', re.IGNORECASE)
RE_SOUND_REF = re.compile(r"\[sound:([^\]]+)\]")
RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_text(raw: str) -> str:
    """Clean a note field: strip HTML (preserving img tags and sound refs), decode entities."""
    # Protect <img> tags by replacing with placeholders
    img_placeholders: list[str] = []

    def _save_img(m: re.Match[str]) -> str:
        img_placeholders.append(m.group(0))
        return f"\x00IMG{len(img_placeholders) - 1}\x00"

    text = RE_IMG_TAG.sub(_save_img, raw)

    # Sound refs are already in [sound:...] format (not HTML), so they survive tag stripping.
    # But decode entities first, then strip tags.
    text = html.unescape(text)
    text = RE_HTML_TAG.sub("", text)

    # Restore <img> placeholders
    for i, img in enumerate(img_placeholders):
        text = text.replace(f"\x00IMG{i}\x00", img)

    text = text.strip()
    text = RE_MULTI_NEWLINE.sub("\n\n", text)
    return text


def count_cloze_numbers(text: str) -> int:
    """Count distinct cloze deletion numbers in a text field."""
    return len(set(RE_CLOZE_NUM.findall(text)))


def is_one_by_one_truthy(value: str) -> bool:
    """Check if the 'One by one' field is truthy."""
    cleaned = RE_HTML_TAG.sub("", value).strip().lower()
    return cleaned != ""


def collect_media_refs(text: str, extra: str) -> set[str]:
    """Collect all media filenames referenced in text and extra fields."""
    refs: set[str] = set()
    for field in (text, extra):
        refs.update(m.group(1) for m in RE_IMG_TAG.finditer(field))
        refs.update(m.group(1) for m in RE_SOUND_REF.finditer(field))
    return refs


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Read a protobuf varint, return (value, new_pos)."""
    value = 0
    shift = 0
    while data[pos] & 0x80:
        value |= (data[pos] & 0x7F) << shift
        shift += 7
        pos += 1
    value |= (data[pos] & 0x7F) << shift
    return value, pos + 1


def parse_media_manifest(data: bytes) -> dict[str, str]:
    """Parse the zstd-compressed protobuf media manifest.

    Returns a dict mapping zip entry number (str) -> real filename.
    The protobuf is a repeated message where each entry's position is its zip entry number,
    and field 1 within each entry is the filename.
    """
    decompressed = pyzstd.decompress(data)
    manifest: dict[str, str] = {}
    pos = 0
    entry_idx = 0

    while pos < len(decompressed):
        # Each top-level entry: tag 0x0a (field 1, wire type 2), then varint length
        if decompressed[pos] != 0x0A:
            break
        pos += 1
        outer_len, pos = _read_varint(decompressed, pos)
        entry_end = pos + outer_len

        # First field inside the entry: tag 0x0a (field 1 = filename), varint length, bytes
        if pos < entry_end and decompressed[pos] == 0x0A:
            pos += 1
            name_len, pos = _read_varint(decompressed, pos)
            filename = decompressed[pos : pos + name_len].decode("utf-8")
            manifest[str(entry_idx)] = filename

        pos = entry_end
        entry_idx += 1

    return manifest


def extract_collection_db(zf: zipfile.ZipFile) -> Path:
    """Extract and decompress the collection database from the .apkg ZIP to a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp_path = Path(tmp.name)

    if "collection.anki21b" in zf.namelist():
        compressed = zf.read("collection.anki21b")
        decompressed = pyzstd.decompress(compressed)
        tmp.write(decompressed)
    elif "collection.anki2" in zf.namelist():
        tmp.write(zf.read("collection.anki2"))
    else:
        tmp.close()
        tmp_path.unlink()
        raise ValueError("No collection database found in .apkg")

    tmp.close()
    return tmp_path


def main() -> None:
    if not APKG_PATH.exists():
        raise FileNotFoundError(f"Source .apkg not found: {APKG_PATH}")

    print(f"Opening {APKG_PATH.name} ...")

    with zipfile.ZipFile(APKG_PATH, "r") as zf:
        # --- Extract and query the collection database ---
        print("Extracting collection database ...")
        tmp_db_path = extract_collection_db(zf)

        try:
            src_conn = sqlite3.connect(tmp_db_path)
            rows = src_conn.execute(
                "SELECT id, flds, tags FROM notes WHERE mid = ?",
                (ANKING_MODEL_ID,),
            ).fetchall()
            src_conn.close()
        finally:
            tmp_db_path.unlink()

        print(f"Found {len(rows)} AnKingOverhaul notes")

        # --- Process notes ---
        print("Cleaning notes ...")
        all_media_refs: set[str] = set()
        notes: list[tuple[int, str, str, int, int, str]] = []

        for note_id, flds, tags in rows:
            fields = flds.split(FIELD_SEP)
            raw_text = fields[IDX_TEXT]
            raw_extra = fields[IDX_EXTRA]
            raw_one_by_one = fields[IDX_ONE_BY_ONE] if len(fields) > IDX_ONE_BY_ONE else ""

            text = clean_text(raw_text)
            extra = clean_text(raw_extra)
            num_cards = count_cloze_numbers(raw_text)
            one_by_one = 1 if is_one_by_one_truthy(raw_one_by_one) else 0

            # Collect media refs from the CLEANED text (img tags are preserved there)
            # and also from raw text for sound refs
            all_media_refs.update(collect_media_refs(text, extra))
            # Also check raw fields for any sound refs that might be in HTML context
            all_media_refs.update(collect_media_refs(raw_text, raw_extra))

            notes.append((note_id, text, extra, num_cards, one_by_one, tags))

        # --- Write output database ---
        print(f"Writing {len(notes)} notes to {DB_PATH} ...")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        out_conn = sqlite3.connect(DB_PATH)
        out_conn.execute("DROP TABLE IF EXISTS source_notes")
        out_conn.execute("""
            CREATE TABLE source_notes (
                id         INTEGER PRIMARY KEY,
                text       TEXT NOT NULL,
                extra      TEXT NOT NULL,
                num_cards  INTEGER NOT NULL,
                one_by_one INTEGER NOT NULL,
                tags       TEXT NOT NULL
            )
        """)
        out_conn.executemany(
            "INSERT INTO source_notes (id, text, extra, num_cards, one_by_one, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            notes,
        )
        out_conn.commit()
        out_conn.close()
        print(f"  source_notes: {len(notes)} rows")

        # --- Extract media ---
        print("Reading media manifest ...")
        manifest = parse_media_manifest(zf.read("media"))
        # manifest maps zip entry number (str) -> real filename
        # Invert: real filename -> zip entry number
        filename_to_entry = {v: k for k, v in manifest.items()}

        # Filter to only referenced files
        referenced = all_media_refs & set(filename_to_entry.keys())
        unreferenced = all_media_refs - set(filename_to_entry.keys())
        if unreferenced:
            print(f"  Warning: {len(unreferenced)} referenced media files not found in manifest")

        print(f"Extracting {len(referenced)} media files to {MEDIA_DIR} ...")
        if MEDIA_DIR.exists():
            shutil.rmtree(MEDIA_DIR)
        MEDIA_DIR.mkdir(parents=True)

        for filename in referenced:
            entry_num = filename_to_entry[filename]
            data = zf.read(entry_num)
            (MEDIA_DIR / filename).write_bytes(data)

        print(f"  Extracted {len(referenced)} media files")

    print("Done.")


if __name__ == "__main__":
    main()
