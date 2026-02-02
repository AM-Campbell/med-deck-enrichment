# Med Deck Enrichment — Plan

## Step 1: Extract AnKing deck to working format

### Output structure

```
med-deck-refined/
  deck.sqlite        # working database
  media/             # flat dir with every media file used by notes
```

### Source data facts

- Source: `AnKing_Step_Deck_v12_with_Media.apkg` (zip) 
- 28,656 AnKingOverhaul notes (mid=1659130414530), 5 IO notes (ignored)
- `notes.flds` delimiter: `\x1f` (ASCII unit separator)
- Field indices: Text=0, Extra=1, ..., One by one=16, ankihub_id=17
- One by one values: empty (28,190), truthy = y/Y/yes/y\<br\> etc. (466 notes)
- Media: 40,432 files in apkg (31k webp, 6.5k jpg, 2k png, 31 mp3)
  - Stored as numbered zip entries (0, 1, 2, ...)
  - Manifest is zstd-compressed protobuf mapping number → filename
- num_cards per note = count of distinct cloze numbers in Text field

### Text cleaning

Strip HTML **except** keep references to images and audio. Specifically:
- Decode HTML entities (`&amp;` → `&`)
- Strip all HTML tags (`<b>`, `<div>`, `<br>`, `<span>`, `<a>`, etc.)
- **Preserve** `<img src="filename">` → keep as `<img src="filename">`
- **Preserve** `[sound:filename.mp3]` → keep as-is
- **Keep** cloze markers: `{{c1::answer}}`, `{{c1::answer::hint}}`
- Strip leading/trailing whitespace, collapse multiple newlines

### Schema: `anking_notes_original`

| column     | type    | notes                                               |
|------------|---------|-----------------------------------------------------|
| id         | INTEGER | PK, from anki `notes.id`                            |
| text       | TEXT    | cleaned Text field (clozes preserved)                |
| extra      | TEXT    | cleaned Extra field                                  |
| num_cards  | INTEGER | count of distinct cloze numbers in text              |
| one_by_one | BOOLEAN | true if One by one field is truthy                   |
| tags       | TEXT    | raw tags string from anki                            |


### Media extraction

1. Parse the zstd-compressed protobuf manifest from the apkg
2. Scan all note text + extra fields for `<img src="...">` and `[sound:...]` references
3. Build set of referenced filenames
4. Extract only those files from the apkg, renamed from numeric IDs to real filenames
5. Place in `med-deck-refined/media/`

### Script: `scripts/extract_notes.py`

Reads from the `.apkg` and `.sqlite`, produces `med-deck-refined/deck.sqlite` + `media/`.

### Open questions

- Do we want to store the raw (uncleaned) text/extra too, or just the cleaned versions?
- Should the script be idempotent (re-runnable) or one-shot?
