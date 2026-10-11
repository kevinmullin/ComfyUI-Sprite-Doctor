# Transparency and foreground masks

The exporter accepts IMAGE frame batches, with an optional MASK tensor. A ComfyUI IMAGE is commonly RGB; an ordinary H3 or other video frame usually does **not** have an alpha channel.

## Recommended workflow

1. Send the original IMAGE batch directly to the exporter `images` port.
2. In a second branch, pass the *same* IMAGE batch through a background-removal/segmentation node that outputs `MASK`.
3. Connect that `MASK` to `foreground_mask`.
4. Set `alpha_mode=preserve` and queue. If subject/background are swapped, use `invert_mask=true`.

Mask values: `1`/white means foreground/visible and `0`/black means transparent. A single mask applies to all frames; a batch mask should have one mask for **every input frame**, including frames excluded by `frame_step`. Mask width and height must match the original IMAGE dimensions. Resize and align the masks in the upstream workflow first.

Both alpha and foreground mask are multiplied. Alpha from PNG images can therefore be preserved and further constrained by mask.

## Chroma-key workflow

If the entire input background is one color, use `alpha_mode=chroma_key` and set `key_color` to a six-digit hex RGB color (`#00FF00`, `#FFFFFF`, etc.). `key_tolerance` controls the color-distance threshold; `key_softness` feathers around the threshold. Experiment in small batches first.

**Chroma keying is not segmentation.** It removes *all* matching pixels, not just connected background regions. If your subject has white bones, white clothing, white teeth, or light-colored highlights against a white background, the chroma key can punch holes in those parts. Use a foreground mask instead.

## Preview alpha

The `sheet_preview` IMAGE output and node image widget show a checkerboard-rendered RGB view. The files written to `sheet.png` / `sheet_000.png` and `frames/*.png` are true RGBA PNG files. Verify transparency in any PNG inspector/editor.
