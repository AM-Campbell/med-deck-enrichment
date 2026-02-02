# Where We Left Off

## Status: Planning Step 1 — Extract AnKing deck to working format

We've completed the investigation/discovery phase and drafted a detailed plan in `PLAN.md` for the first step. The plan has not been implemented yet. There are two open questions at the bottom of `PLAN.md` that need answers before building the extraction script.

## What we figured out

### Project goal
Build tools that Claude Code uses in an agentic loop to semi-automatically review, refine, and enrich AnKing flashcards. The workflow involves:
1. Claude sees only the card front (answer hidden), attempts to answer via a subagent with minimal context
2. Claude "flips" the card, compares the subagent's answer to the real answer
3. Claude refines ambiguous/imprecise cards (e.g., expanding "Rb" to "pRB", disambiguating "Apex")
4. NER tagging with UMLS concepts (substring-level spans, not just tags)
5. Eventually: prerequisite relationships between concepts (shared NER concepts reduce the 25k×25k search space)

### Key architectural decisions made
- **Working database**: SQLite (row-heavy access pattern, not columnar)
- **Data lives in**: `med-deck-refined/deck.sqlite` + `med-deck-refined/media/`
- **Operate at note level**, not card level (notes generate multiple cards via cloze deletions)
- **Subagent approach**: Spawn a minimal-context Claude subagent (haiku) per cloze to test card clarity — creates genuine information asymmetry
- **Claude Code skills**: Will be slash-command skills that Claude invokes agenically (not batch scripts)
- **MCP server**: Will expose Python functions (view_card_front, flip_card, run_ner, etc.) as first-class tools Claude can call

### Source data facts we verified
- 28,656 AnKingOverhaul notes, field delimiter is `\x1f`
- Field order: Text=0, Extra=1, ..., One by one=16, ankihub_id=17
- One by one: 466 truthy, 28,190 empty
- Media: 40,432 files in the .apkg, manifest is zstd-compressed protobuf
- num_cards = count of distinct cloze numbers in the Text field

## What to do next

1. Answer the open questions at the bottom of `PLAN.md`
2. Build `scripts/extract_notes.py` per the plan
3. After extraction works, move on to the MCP server and skills (not yet planned in detail — we agreed to zoom in one step at a time)

## Key files
- `PLAN.md` — detailed plan for Step 1
- `CLAUDE.md` — project setup and conventions
- `src/med_deck_enrichment/matcher.py` — existing QuickUMLS wrapper (not yet used)
- `AnKing_Step_Deck_v12_with_Media.apkg` — source deck (5.5GB zip)
- `AnKing_Step_Deck_v12_with_Media.sqlite` — source deck SQLite (121MB)
