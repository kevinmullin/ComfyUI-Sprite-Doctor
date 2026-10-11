# Atlas JSON format (v1.1.0)

The exporter writes `atlas.json`. Each frame has a rectangle on a named page plus animation timing. This is **not a universal import format** for Unity, Godot, Phaser or TexturePacker; it is intended to be straightforward to adapt.

```json
{
  "frames": {
    "frame_00000": {
      "frame": {"x": 0, "y": 0, "w": 256, "h": 256},
      "page": 0,
      "sheet": "sheet.png",
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": {"x": 0, "y": 0, "w": 256, "h": 256},
      "sourceSize": {"w": 256, "h": 256},
      "source_frame": 0,
      "time_seconds": 0.0,
      "duration_ms": 125.0,
      "image_file": "frames/frame_00000.png"
    }
  },
  "meta": {
    "app": "ComfyUI SpriteSheet Exporter",
    "version": "1.1.0",
    "image": "sheet.png",
    "pages": [{"image": "sheet.png", "size": {"w": 256, "h": 256}, "columns": 1, "rows": 1}],
    "format": "RGBA8888",
    "size": {"w": 256, "h": 256},
    "frame_size": {"w": 256, "h": 256},
    "spacing": 0,
    "columns": 1,
    "page_count": 1,
    "frame_count": 1,
    "source_frame_count": 1,
    "source_fps": 24.0,
    "playback_fps": 8.0,
    "frame_step": 3,
    "start_frame": 0,
    "anchor_mode": "canvas",
    "alpha_mode": "preserve",
    "sequence": ["frame_00000"]
  }
}
```

`image_file` is `null` when individual frame export is disabled. `frame` coordinates are in **pixels** relative to the named `sheet` page. `source_frame` refers to the input batch index. `time_seconds` is the original source timestamp; `duration_ms` is the intended duration of each exported frame.

## Multi-page sheets

For large exports, `meta.pages` contains every page. Each `frames[key]` entry includes the page index and concrete sheet filename. Page 0 is also listed as `meta.image` for simple clients and backward compatibility. A multi-page reader must consult **each frame's `sheet`/`page`**, not assume everything lies on `meta.image`.

A basic playback loop follows `meta.sequence`, takes each frame's page and pixel rectangle, and waits `duration_ms` before advancing. Exported PNGs use fixed-size cells; no rotated or trimmed packing is performed.
