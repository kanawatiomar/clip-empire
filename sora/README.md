# Sora Pipeline — Clip Empire

AI-generated B-roll footage via OpenAI's Sora API, purpose-built for Clip Empire channels.

---

## Setup

1. Add your OpenAI API key to `.env` in clip_empire root:
   ```
   OPENAI_API_KEY=sk-...
   ```

2. Install dependency (requests only — no new packages needed):
   ```
   pip install requests
   ```

---

## Usage

### Generate clips for one channel
```bash
cd ventures/clip_empire
python -m sora.generator --channel market_meltdowns --count 5
```

### Dry run (see prompts without generating)
```bash
python -m sora.generator --channel crypto_confessions --dry-run
```

### Batch all 10 channels
```bash
python -m sora.batch --per-channel 3     # ~30 clips, ~$24
python -m sora.batch --dry-run           # preview + cost estimate
```

### Use higher quality model
```bash
python -m sora.generator --channel ai_did_what --count 3 --model sora-2-pro
```

---

## Cost Reference

| Model | Per second | 8s clip | 30 clips |
|-------|-----------|---------|----------|
| sora-2 | $0.10 | $0.80 | $24 |
| sora-2-pro | $0.50 | $4.00 | $120 |

**Recommendation:** Use `sora-2` for stockpiling. Use `sora-2-pro` only for hero clips.

---

## Output

Footage saved to: `sora/footage/<channel>/<channel>_YYYYMMDD_HHMMSS_pXX.mp4`

State tracked in: `sora/gen_state.json` (prevents duplicate generations)

---

## Prompt Library

- 15 prompts per channel × 10 channels = **150 total unique prompts**
- All prompts: no real people, no copyrighted content, Shorts-optimized
- Vertical 9:16 (720×1280) by default

### Channels Covered
- market_meltdowns — crashing markets, red tickers, burning cash
- crypto_confessions — Bitcoin shattering, blockchain visuals, rug pulls
- rich_or_ruined — gold, luxury, collapse, transformation
- startup_graveyard — empty offices, shuttered companies, failed pitches
- self_made_clips — ambition, grind, dawn hustle, breakthrough moments
- ai_did_what — neural networks, robot awakening, circuit boards
- gym_moments — chalk dust, barbell slams, sweat, iron
- kitchen_chaos — fire, steam, knife work, flambé explosions
- cases_unsolved — dark hallways, evidence boards, rain on pavement
- unfiltered_clips — satisfying, abstract, oddly beautiful

---

## Integration with Upload Pipeline

Generated footage in `sora/footage/` can be fed directly into the existing
Clip Empire publisher. Add a caption overlay, trending audio, and queue for upload.

Future: auto-feed sora clips into pipeline when source clip queue runs low.
