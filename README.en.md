# character-asset-kit · 千面工坊（Character Asset Production Line）

> *A thousand views, one identity.*
> An Agent Skill that turns a new character into a **cross-angle, cross-expression, cross-pose, cross-scene, training-ready, auditable** AIGC character asset library, following an enterprise-style gated pipeline (G0–G14).
> The Agent generates images and orchestrates; this Skill provides the SOP, an evidence-based prompt methodology, and deterministic scripts.
>
> 中文：[README.md](README.md)（中文名：千面工坊 · 角色资产生产线）

![One master produces a full character asset matrix: multi-view, expressions, details, poses, props, micro-expressions, camera & gaze, scenes, and the character sheet](docs/images/hero-asset-matrix.jpg)

## What problem it solves

"Generating one good-looking character" and "owning a stable, reusable character asset" are two different things. The latter requires:

1. **Freeze the identity before mass production**: spec card → white-background master; every later unit references the master.
2. **Single-unit generation, deterministic assembly**: multi-view / expression / pose units are generated one at a time; scripts cut them out, place them on standard cells, and assemble boards — "generate the whole board in one prompt" always breaks and cannot be reworked per cell.
3. **Gates and acceptance**: every gate has a checklist; the user signs off before moving on; the registry must show 0 ERROR before sealing.
4. **Prompts as assets**: every approved image is documented in a six-section record (purpose / reference feeding / verbatim prompt / size spec / acceptance / bad case).
5. **Evidence-based rewrite rules** from 210 controlled reproduction runs: the reference-image channel is stronger than the text channel; models obey qualitative / quantitative / prohibition words but ignore numeric / state words; missing information is fixed by prompts alone, while body geometry requires prompt **and** reference image.

![A broken cell is re-generated alone: single-unit generation plus deterministic assembly keeps a failure from spreading to the board](docs/images/compare-one-shot.jpg)

## Status

- The methodology was proven end-to-end on two complete characters (all gates G0–G14). A third character was produced by a **fresh conversation using only this Skill** (dogfooding; G0–G12, 106 media items, 17 derived deliverables, sealed with 0 ERROR / 0 WARN). The 8 gaps it exposed have all been fixed — see [`docs/DOGFOODING.md`](docs/DOGFOODING.md) (Chinese).
- Style, gate set, directory slots, and canvas sizes are all **profile-driven**. The default profile is a Pixar/blind-box-toy 3D look (`gates-blindbox3d-v1`) — it is **just an example**, not bound to any specific character.
- [`examples/CHAR-01-demo/`](examples/CHAR-01-demo/) ships a set of **desensitized real deliverable boards** (10 images, G2–G12) so you can see the actual output.

![G0–G14 gate map: one sign-off per gate; the registry must show 0 ERROR before sealing](docs/images/pipeline-gates.png)

The methodology is not guesswork: three groups of 60 controlled reproduction runs (210 images total) produced **zero identity drift across 180 identity-dimension images**. All three pre-registered hypotheses H1/H2/H3 were unsupported — the findings are reported as-is, not polished. The success rates are specific to Seedream 5.0 Pro; after switching models you must run the minimal re-validation set rather than reusing these numbers.

![Results of the 210-image controlled study: G1 85.0% / G2 83.3% / G3 75.0% usable, with zero identity drift](docs/images/evidence-210.png)

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
│   ├── runtime-portability.md   #   Multi-provider image backends + minimal re-validation
│   └── style-profiles.md        #   Changing style / trimming gates
├── profiles/gates-blindbox3d-v1.json  # Example profile (gates / slots / canvases / units)
├── templates/                   # Spec card, asset manifest, training config templates
├── scripts/                     # Deterministic steps (Python 3.10+ / Pillow)
│   ├── charkit/                 #   Cutout, standard cells, nine board builders, fonts
│   └── bin/                     #   init / standard_cell / colorkey_cutout /
│                                #   build_board / asset_index / scene_board /
│                                #   style_board / trainset / generate (+ subjectmask.swift)
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

![Real command output: package init, registry scaffolding, 0 ERROR audit, and a dry-run request shape for the image adapter](docs/images/terminal-check.jpg)

## Non-Doubao runtimes (OpenRouter / Gemini / OpenAI / Volcano Ark / compatible gateways / local CUDA)

The pipeline is decoupled from the image backend: on Doubao the host tools `image_gen`/`image_edit` (`seedream_5.0_pro`) are the default; elsewhere the bundled zero-dependency adapter `scripts/bin/kit_generate.py` supports five providers:

| provider | key env var | default model | reference images |
|---|---|---|---|
| `openrouter` (recommended) | `OPENROUTER_API_KEY` | `google/gemini-3.1-flash-image` | model-dependent; one key reaches ~30 image models |
| `google` | `GOOGLE_API_KEY` | `gemini-2.5-flash-image` | strong, limit 3 (14 for the gemini-3 family) |
| `openai` | `OPENAI_API_KEY` | `gpt-image-2.5-flare` | multipart, limit 16 |
| `ark` | `ARK_API_KEY` | none — pass the endpoint via `--model` | depends on the endpoint model |
| `custom` | `OPENAI_API_KEY` + `OPENAI_BASE_URL` | none — pass `--model` | any OpenAI Images-compatible gateway |

```bash
export OPENROUTER_API_KEY=...
# Dry-run first: prints the request shape without calling or billing
python3 scripts/bin/kit_generate.py --provider google --mode edit --ref master.png \
  --prompt-file p.txt --size 1773x2364 --dry-run
# Text-to-image / multi-reference edit (one image per call; non-PNG replies normalized to PNG)
python3 scripts/bin/kit_generate.py --provider openrouter --mode gen \
  --prompt-file p.txt --size 1773x2364 --out 99_过程稿/raw.png
python3 scripts/bin/kit_generate.py --provider google --mode edit \
  --ref master.png --ref ref.png --prompt "……" --size 1773x2364 --out raw.png
```

Model resolution: `--model` > env `<PROVIDER>_IMAGE_MODEL` > built-in default; 429/5xx retry twice with backoff, 4xx is final.
Gates, prompt framework, cell normalization, boards and ledgers are model-agnostic; but the 210-image compliance findings are seedream-specific — **before switching models, run the minimal G1/G2/G3/G7 re-validation in [runtime-portability.md](references/runtime-portability.md) §4**. Local CUDA (ComfyUI/Flux/SD) wraps behind the CLI contract in §7 of that document.

## Requirements

- Python 3.10+ and Pillow (`pip install pillow`). No other required Python dependencies.
- Automatic cutout (subjectmask) uses **macOS Vision**: Swift source ships in the repo and is compiled with `swiftc` on first init (source only, no binaries). On other platforms, cut out with any tool and pass `--already-cutout`, or use the cross-platform color-key script `kit_colorkey_cutout.py` for pure-white seamless backgrounds.
- The image model is provided by the runtime: Doubao `seedream_5.0_pro` by default, or OpenRouter/Gemini/OpenAI/Ark/compatible gateways via `kit_generate.py` — see [runtime-portability.md](references/runtime-portability.md).
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
