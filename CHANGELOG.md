# Changelog

## 1.1.0 — 2026-10-10

- Public release with Kevin Mullin attribution and MIT license.
- Generalized docs and UI: any ComfyUI `IMAGE` batch, no H3 dependency.
- Preserve legacy node identifier `H3SpriteSheetExport` for existing workflows.
- Automatic multi-page PNG sheet export with JSON page mappings.
- Optional transparent spacing between frames.
- Optional bottom-center / center-subject alignment (default `canvas` preserves motion).
- RGB checkerboard preview separate from RGBA on-disk PNG.
- Added portable tests, GitHub Actions CI, atlas and transparency documentation.

## 1.0.0 — Original prototype

- ComfyUI IMAGE batch input; frame sampling; configurable fixed grid; chroma key or optional foreground MASK; PNG sheets, individual PNG frames and JSON metadata.
