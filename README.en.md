# character-asset-kit

> An Agent Skill that turns a new character into a **cross-angle, cross-expression, cross-pose, cross-scene, training-ready, auditable** AIGC character asset library, following an enterprise-style gated pipeline (G0–G14).
> The Agent generates images and orchestrates; this Skill provides the SOP, an evidence-based prompt methodology, and deterministic scripts.

中文：[README.md](README.md)

## What problem it solves

"Generating one good-looking character" and "owning a stable, reusable character asset" are two different things. The latter requires:

1. **Freeze the identity before mass production**: spec card → white-background master; every later unit references the master.
2. **Single-unit generation, deterministic assembly**: multi-view / expression / pose units are generated one at a time; scripts cut them out, place them on standard cells, and assemble boards — "generate the whole board in one prompt" always breaks and cannot be reworked per cell.
3. **Gates and acceptance**: every gate has a checklist; the user signs off before moving on; the registry must show 0 ERROR before sealing.
4. **Prompts as assets**: every approved image is documented in a six-section record (purpose / reference feeding / verbatim prompt / size spec / acceptance / bad case).
5. **Evidence-based rewrite rules** from 210 controlled reproduction runs: the reference-image channel is stronger than the text channel; models obey qualitative / quantitative / prohibition words but ignore numeric / state words; missing information is fixed by prompts alone, while body geometry requires prompt **and** reference image.

## Status

- The methodology was proven end-to-end on two complete characters (all gates G0–G14). A third character was produced by a **fresh conversation using only this Skill** (dogfooding; G0–G12, 106 media items, 17 derived deliverables, sealed with 0 ERROR / 0 WARN). The 8 gaps it exposed have all been fixed — see [`docs/DOGFOODING.md`](docs/DOGFOODING.md) (Chinese).
- Style, gate set, directory slots, and canvas sizes are all **profile-driven**. The default profile is a Pixar/blind-box-toy 3D look (`gates-blindbox3d-v1`) — it is **just an example**, not bound to any specific character.

## Layout

```
character-asset-kit/
├── SKILL.md                     # Agent entry: hard rules, gate map, on-demand reading table
├── references/                  # Methodology brain (read on demand)
│   ├── gates-g0-g9.md           #   Core nine-gate manual
│   ├── gates-g10-g14.md         #   Micro-expressions / camera & gaze / scenes / style variants / training prep
│   ├── prompt-framework.md      #   Six-section prompt templates
│   ├── prompt-rewrite-rules.md  #   Evidence-based rewrite rules (210 runs)
│   ├── bad-cases.md             #   Failure catalog BC-01…33
│   ├── acceptance-checklists.md #   Per-gate checklists
│   ├── registry-rules.md        #   Registry E/W rule codes
│   └── style-profiles.md        #   Changing style / trimming gates
├── profiles/gates-blindbox3d-v1.json  # Example profile (gates / slots / canvases / units)
├── templates/                   # Spec card, asset manifest, training config templates
├── scripts/                     # Deterministic steps (Python 3.10+ / Pillow)
│   ├── charkit/                 #   Cutout, standard cells, nine board builders, fonts
│   └── bin/                     #   init / standard_cell / colorkey_cutout /
│                                #   build_board / asset_index / scene_board /
│                                #   style_board / trainset (+ subjectmask.swift)
├── tests/                       # Stdlib-only unittest (no network, no macOS Vision dependency)
├── examples/                    # Desensitized end-to-end walkthrough
└── docs/                        # PRD / DESIGN (SDD) / DOGFOODING (Chinese)
```

## Quick start

1. Put this directory in your Agent's skill discovery path (a symlink works), or copy it alongside your other skills.
2. When the user asks for a new character, the Agent reads `SKILL.md` and initializes a package:
   ```bash
   python3 scripts/bin/kit_init_character.py --dir CHAR-01-demo --root /path/to/library
   ```
3. Co-author the spec card (G0) → master (G1) → proceed gate by gate to sealing (G9); enable extension gates G10–G14 as needed.
4. Feeding, script commands, and acceptance items for each gate are read on demand from `references/`.

Typical script usage:

```bash
# Place a raw image onto a standard cell (auto cutout on macOS; elsewhere cut out yourself and pass --already-cutout)
python3 scripts/bin/kit_standard_cell.py --char CHAR-01-demo --unit master --in raw.png --variant white
# Color-key fallback on pure-white backgrounds when Vision fails on dark props
python3 scripts/bin/kit_colorkey_cutout.py raw.png cut.png
# Build boards (clean / review-annotated)
python3 scripts/bin/kit_build_board.py --char CHAR-01-demo --type multiview
python3 scripts/bin/kit_build_board.py --char CHAR-01-demo --type all --review
# Register and audit (sealing requires 0 ERROR)
python3 scripts/bin/kit_asset_index.py --char CHAR-01-demo --scaffold
python3 scripts/bin/kit_asset_index.py --char CHAR-01-demo --check
```

## Requirements

- Python 3.10+ and Pillow (`pip install pillow`). No other required Python dependencies.
- Automatic cutout (subjectmask) uses **macOS Vision**: Swift source ships in the repo and is compiled with `swiftc` on first init (source only, no binaries). On other platforms, cut out with any tool and pass `--already-cutout`, or use the cross-platform color-key script `kit_colorkey_cutout.py` for pure-white seamless backgrounds.
- The image model is provided by the runtime. The methodology is written against `seedream_5.0_pro` by default; substitute equivalent capabilities per `references/gates-g0-g9.md §0` in other runtimes.
- Board labels use Hiragino Sans GB by default (shipped with macOS); on other platforms point the builders at an available CJK font.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Scope limits

- **No LoRA training itself**: G14 only produces the dataset (dual caption profiles, stratified val, hash checks) plus an out-of-repo execution guide; training happens outside (kohya / ai-toolkit).
- Not for article illustration, photorealistic humans, or imitating living artists.
- Scripts handle deterministic pixel work and registry bookkeeping only; they make no aesthetic judgments. Gate decisions belong to humans.
- No pip package: the caller is an Agent — just copy the Skill directory.

## Documentation

- [docs/PRD.md](docs/PRD.md) — product requirements and format decision (Chinese)
- [docs/DESIGN.md](docs/DESIGN.md) — software design: architecture, data flow, board types, three cutout paths, decision log, test strategy (Chinese)
- [docs/DOGFOODING.md](docs/DOGFOODING.md) — third-character dogfooding report: gap distribution, rework stats, conclusions (Chinese; English translations welcome)
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributing guide (Chinese; English PRs welcome)
- [CHANGELOG.md](CHANGELOG.md) — release history

## License

MIT, see [LICENSE](LICENSE).
