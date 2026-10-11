# Sample workflow recipes

No specific ComfyUI model is required. Connect the upstream IMAGE output to `images`.

## H3 / image-to-video (jump and banjo motion)

`H3 Motion Context Trim:images -> Sprite Sheet Export:images`

- `sprite_width=256`, `sprite_height=256`, `columns=8`
- `frame_step=3`, `source_fps=24`, `max_frames=0`
- `resize_mode=contain`, `anchor_mode=canvas` (keeps the jump visible)
- Generate a foreground MASK in a separate background-removal branch if required
- Result: 8 FPS animation; PNG sheets + an atlas with frame timing

## Single generated image

`VAE Decode:IMAGE -> Sprite Sheet Export:images`

- One image becomes a one-cell sprite sheet and optional individual frame PNG.
- For more than one independent image, use an Image Batch/concatenate node.

## Pixel art

`Pixel art generator:IMAGE batch -> Sprite Sheet Export:images`

- `resize_filter=nearest` to preserve sharp pixel edges.
- Use `resize_mode=contain` and a consistent sprite size for grid alignment.

## Long video

`Video decoder:IMAGE batch -> Sprite Sheet Export:images`

- `max_frames=0` permits all sampled frames; `max_sheet_dimension=4096` pages output automatically.
- For high-resolution sequences, adjust `frame_step`, `sprite_width`, `sprite_height` to manage file size.
