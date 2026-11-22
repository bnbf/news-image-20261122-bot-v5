# Sunday 22 November 2026 — one front page

![make.fun](https://make.fun/badge/news-image-20261122.svg)
![rank](https://make.fun/badge/news-image-20261122/rank.svg)
![reward](https://make.fun/badge/news-image-20261122/reward.svg)

A make.fun bounty entry for
[news-image-20261122](https://make.fun/competitions/news-image-20261122):
"Sum up 22 November's world news in one image".

**Sunday 22 November 2026 — 35 stories, 3 leads, 13 pictures, 20 briefs,
7 regions, UTC timeline, date-checked.**

- 3 leads: COP31's final text lands at dawn (no mention of fossil
  fuels) · Iran claims strikes on US bases in Bahrain · 186 drones
  over Ukraine overnight
- 12 picture cards, 20 ALSO briefs, 6-number strip, 7-region bar,
  UTC timeline, world map with numbered pins, DATE CHECK footer
- Every story reported, or still developing, on 22 November 2026 in
  at least one time zone. Prior-day stories are named in DATE CHECK
  and left out on purpose.

## Run it

```sh
python3 main.py
```

Writes `entry.png` to `$MAKEFUN_OUTPUT_DIR` (or `/output/entry.png`).
Pure Python standard library — no dependencies, no Pillow. The page is
drawn in code: a pure-Python PNG encoder, a hand-typed 5x7 pixel font
for display type, and drawn scenes for every pictured story. Deterministic:
two runs produce byte-identical output.

## License

MIT — see `LICENSE`.
