# CLAUDE.md

## Project Overview

Personal project for semi-manual enrichment of the AnKing Anki deck (~28k notes covering all of medical school). This is separate from AnkiHub contract work.

Goals:
1. Tag every card with UMLS concepts (clean up ambiguity, improve descriptions)
2. Define prerequisite relationships between concepts

## Repository Structure

- `src/med_deck_enrichment/` - Core library (matcher, card processing)
- `scripts/` - Runnable scripts (NER pipeline, TUI browser)
- `data/` - Symlinks to external data (gitignored)
- `results/` - Pipeline outputs (gitignored)

## Setup

```bash
uv sync

# Create data symlinks (one-time):
ln -s /home/amcam/SoftwareProjects/ankihub-research/data/anking-deck-with-media data/anking-deck
ln -s /home/amcam/SoftwareProjects/ankihub-research/data/umls-full/META data/umls
ln -s /home/amcam/SoftwareProjects/ankihub-research/data/umls-full/quickumls_index data/quickumls-index
```

## Code Quality

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pyright .           # type check
```

## Data Sources

- **AnKing deck**: SQLite at `data/anking-deck/AnKing_Step_Deck_v12_with_Media.sqlite`
- **UMLS**: RRF files at `data/umls/` (MRCONSO.RRF, MRSTY.RRF)
- **QuickUMLS index**: Pre-built at `data/quickumls-index/`

## Card Text Processing

Before running NER, card text needs cleaning:
1. Strip cloze markers: `{{c1::content}}` -> `content`
2. Strip HTML tags and decode entities
3. Remove `[image]` and `[audio]` placeholders if desired

## Key Constraints

- UMLS matching uses QuickUMLS (not a copy of code-umls-match, which was built on AnkiHub time)
- UMLS data files are used under personal UMLS license
