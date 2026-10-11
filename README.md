# ComfyUI SpriteSheet Exporter

**Export any ComfyUI image batch into sprite sheets, transparent PNG frames, and a JSON animation atlas.**

Created and maintained by **[Kevin Mullin](https://github.com/kevinmullin)** · MIT licensed · Python / ComfyUI custom node

A lightweight export node for turning image generation, image-to-video, decoded video frames, and other `IMAGE` outputs into assets for 2D games, websites, animations, and motion graphics. No specific AI model or video plugin is required.

> **Compatibility:** The original node was named `H3 Sprite Sheet Export`. The `H3SpriteSheetExport` identifier is retained so existing workflows keep working. New users should search for **Sprite Sheet Export (Image Batch)** under **Sprites / Export**.

## Features

- **Model-agnostic `IMAGE` input** — accepts a single image or batch of frames from ComfyUI nodes, regardless of which model generated them.
- **Frame selection and playback metadata** — start frame, step, limit, source FPS, original source frame indexes, timestamps, playback FPS, durations.
- **RGBA exports** — retain existing transparency, apply a white/black foreground `MASK`, or remove a flat background with chroma keying.
- **Sprite packing** — fixed-size frames, customizable columns, `contain`/`cover`/`stretch`, `nearest`/`lanczos`, and optional space between cells.
- **Automatic paging** — safely split long or high-resolution animations across multiple PNG sheets.
- **Character positioning** — preserve the original scene coordinates or optionally anchor isolated subjects to center / bottom-center.
- **Game-oriented metadata** — a searchable atlas with rectangle coordinates, durations, sheet filenames, and ordered animation frames.
- **Individual frame export** — optional transparent PNG for every selected frame.
- **Zero model dependencies** — runs on ordinary ComfyUI tensors and Pillow/NumPy/Torch already found in typical installations; no additional model download.

## Install

1. Download the repository ZIP and extract it, or clone the repository.
2. Copy the `ComfyUI-SpriteSheet-Exporter` folder **containing `__init__.py`** into your actual ComfyUI `custom_nodes/` directory.
3. If you installed the **old** `comfyui_h3_sprite_export` plugin, move its folder *out of* `custom_nodes/` before restarting. Both versions register the same legacy node identifier, and running both can cause duplicate-node conflicts.
4. Restart ComfyUI **backend**, not just the browser page.
5. Double-click the canvas, search **Sprite Sheet Export (Image Batch)**, and add the node.
6. Connect any `IMAGE` output to `images`. Queue the prompt.

For **ComfyUI Desktop on macOS**, use the backend path reported by `ComfyUI Path` in your startup log. For example:

```text
~/ComfyUI-Installs/ComfyUI/ComfyUI/custom_nodes/ComfyUI-SpriteSheet-Exporter/
├── __init__.py
├── nodes.py
├── LICENSE
└── README.md
```

If the node doesn't appear, check the backend startup log for import errors and verify that `__init__.py` is directly inside the copied folder, not nested another level.

## Example connections

```text
MiniMax H3 / other video model -> decoded IMAGE batch ----┐
Load Image -> IMAGE ---------------------------------------+---> Sprite Sheet Export (Image Batch)
Video loader -> IMAGE frames ------------------------------┘               |
                                                                            +---> sheet.png / sheet_000.png ...
Background removal -> MASK -----------------------------------------------> +---> frames/*.png (optional)
                                                                            +---> atlas.json
```

**Important:** A latent tensor, `VIDEO`, file path, or MP4 isn't an `IMAGE` batch. Decode it to `IMAGE` frames first (e.g., VAE Decode or video frame extraction). If you have multiple separate single images, concatenate them with an Image Batch node.

## Quick start

For a 15-second, 24-FPS clip sampled every third frame:

| Input | Suggested value | Notes |
| --- | --- | --- |
| `images` | Your batch output | Connect H3 Motion Context Trim `images`, or any standard IMAGE batch |
| `sprite_width` / `sprite_height` | `256` / `256` | Fixed dimensions for each frame |
| `columns` | `8` | Maximum columns per atlas page |
| `start_frame` | `0` | Skip lead-in frames if desired |
| `frame_step` | `3` | Every third source frame |
| `max_frames` | `0` | Export all sampled frames; `120` is the default limit |
| `source_fps` | `24` | Source video FPS, not desired playback FPS |
| `resize_mode` | `contain` | Preserve aspect ratio, transparent letterboxing |
| `resize_filter` | `lanczos` | Use `nearest` for pixel art |
| `alpha_mode` | `preserve` | Use a mask for complex/white character subjects |
| `anchor_mode` | `canvas` | Preserve movement / jumping within frame |
| `max_sheet_dimension` | `4096` | Auto-split when necessary |
| `save_individual_frames` | `true` | Optional one-PNG-per-frame files |

`source_fps / frame_step` is the effective playback rate. For `24 / 3 = 8 FPS`, 360 input frames produce 120 sprites if `max_frames=0`.

### Transparency

- **Already transparent?** `alpha_mode=preserve` keeps source alpha (e.g., from a suitable RGBA-producing node).
- **Flat solid background?** `alpha_mode=chroma_key`, set `key_color`, adjust tolerance and softness. **Chroma keying may also erase matching colors inside the character.**
- **Detailed background or subject sharing background color?** Connect a **foreground `MASK`** from a background-removal node, leave `alpha_mode=preserve`, and toggle `invert_mask` only if needed. White (`1`) keeps pixels; black (`0`) removes them.
- The returned `sheet_preview` is **RGB on a checkerboard** for display. The written PNG remains RGBA. The optional `IMAGE` output is *not* a transparent RGBA tensor.

For a character with **white bones against a white background**, use a segmentation mask rather than white chroma keying. See [Transparency guide](docs/TRANSPARENCY.md).

### Animation alignment

- `canvas` preserves the input frame's spatial coordinates. **Recommended for jumping, swinging, moving sprites, camera pans**, and any animation where position within the frame matters.
- `bottom_center` crops to nontransparent subject pixels and anchors them to the bottom of each cell. Useful for static, isolated characters whose source framing varies; **it removes vertical jumps**.
- `center_subject` crops to visible subject and centers it. Helpful for icons, sprites with variable source framing, and avatar sequences.
- With `bottom_center`/`center_subject`, you generally need a transparent subject or foreground mask first. Without transparency, the entire rectangular background is considered the subject.

## Output

```text
ComfyUI/output/sprite_sheets/sprite_animation_00001/
├── sheet.png             # one-page animation, or sheet_000.png, sheet_001.png ...
├── atlas.json            # frames, rects, sheet filenames, durations, source frame indexes
└── frames/               # optional: transparent individual PNGs
    ├── frame_00000.png
    └── frame_00001.png
```

A new numbered directory is created on each run; previous exports are never silently overwritten. The `sheet_path` and `atlas_path` string outputs return absolute file paths. When an animation spans several sheets, `sheet_path` points to **the first page**; `atlas.json -> meta.pages` lists all pages.

See [Atlas format](docs/ATLAS_FORMAT.md) for frame rectangle mapping and multi-page details. The JSON is a **project-defined atlas format inspired by common game-atlas conventions**, not an assertion that it can be directly imported into every game engine without adaptation.

## Development

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

CI runs the test suite. For local testing without ComfyUI, the tests stub `folder_paths` and use synthetic torch tensors. See [Contributing](CONTRIBUTING.md).

## Limitations

- ComfyUI `IMAGE` batches are required; there is no direct MP4/model/latent decoding in this node.
- No temporal consistency, AI segmentation, frame interpolation, or re-rendering: it only processes frames already generated elsewhere.
- The `frame_step` option samples frames; it does not create new in-between motion.
- Subject anchoring is frame-by-frame (not temporal tracking) and can introduce jitter. Keep `canvas` for continuous scene motion.
- Preserve/chroma key use RGB/alpha data in each IMAGE; for complex backgrounds, produce an explicit mask upstream.
- Multi-page JSON may require a loader or conversion for your game engine.

## Attribution and license

Copyright © 2026 **Kevin Mullin** ([`@kevinmullin`](https://github.com/kevinmullin)). Licensed under the [MIT License](LICENSE). Contributions welcome. This project is independently maintained and not affiliated with ComfyUI or MiniMax.
