"""Sprite sheet export from standard ComfyUI IMAGE batches.

Copyright (c) 2026 Kevin Mullin. MIT License.
ComfyUI IMAGE: [batch,height,width,channels], normalized floats in [0,1].
"""

from __future__ import annotations

from pathlib import Path
import json
import math
import re

import folder_paths
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageOps


class SpriteSheetExport:
    """Export animation frames, transparent PNG sprite sheets, and atlas JSON."""

    CATEGORY = "Sprites / Export"
    FUNCTION = "export"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("sheet_preview", "sheet_path", "atlas_path")
    DESCRIPTION = (
        "Exports any ComfyUI IMAGE batch into PNG sprites and a JSON atlas. "
        "Supports sampling, masks, chroma key, and automatic multi-page packing. "
        "IMAGE must be a single image or a batch of frames."
    )

    # Avoid massive full-resolution PNGs or wasteful ComfyUI previews.
    MAX_PAGE_PIXELS = 32_000_000

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Any ComfyUI IMAGE batch, from any model or video frame decoder."}),
                "name": ("STRING", {"default": "sprite_animation", "multiline": False}),
                "sprite_width": ("INT", {"default": 256, "min": 16, "max": 2048, "step": 16}),
                "sprite_height": ("INT", {"default": 256, "min": 16, "max": 2048, "step": 16}),
                "columns": ("INT", {"default": 8, "min": 1, "max": 128}),
                "start_frame": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "frame_step": ("INT", {"default": 3, "min": 1, "max": 1000}),
                "max_frames": ("INT", {"default": 120, "min": 0, "max": 10000,
                                      "tooltip": "0 = all sampled frames; automatic sheet paging still applies."}),
                "source_fps": ("FLOAT", {"default": 24.0, "min": 0.1, "max": 240.0, "step": 0.1}),
                "resize_mode": (["contain", "cover", "stretch"],),
                "resize_filter": (["lanczos", "nearest"],),
                "alpha_mode": (["preserve", "chroma_key"], {
                    "tooltip": "Preserve input alpha or remove an approximately uniform color background."}),
                "key_color": ("STRING", {"default": "#FFFFFF", "multiline": False}),
                "key_tolerance": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "step": 0.01}),
                "key_softness": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "save_individual_frames": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "foreground_mask": ("MASK", {"tooltip": "White/1 = visible. Black/0 = transparent. One mask or one per input image."}),
                "invert_mask": ("BOOLEAN", {"default": False}),
                "anchor_mode": (["canvas", "bottom_center", "center_subject"], {
                    "tooltip": "Canvas preserves movement through the shot; subject anchors stabilize isolated character crops."}),
                "spacing": ("INT", {"default": 0, "min": 0, "max": 64,
                                    "tooltip": "Transparent pixel gap between sprites in the sheet."}),
                "max_sheet_dimension": ("INT", {"default": 4096, "min": 512, "max": 16384, "step": 256,
                                                "tooltip": "Automatically start a new PNG page rather than exceed this width or height."}),
            },
        }

    @staticmethod
    def _parse_rgb_hex(value: str) -> np.ndarray:
        value = str(value).strip().lstrip("#")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
            raise ValueError("key_color must be a six-digit hex color, e.g. #FFFFFF")
        return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)

    @staticmethod
    def _as_rgba(image: torch.Tensor) -> Image.Image:
        if image.ndim != 3 or image.shape[-1] not in (1, 3, 4):
            raise ValueError("IMAGE frames must be [H,W,C] with 1, 3 or 4 channels")
        pixels = (image.detach().clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()
        if pixels.shape[-1] == 1:
            return Image.fromarray(pixels[:, :, 0], mode="L").convert("RGBA")
        if pixels.shape[-1] == 3:
            return Image.fromarray(pixels, mode="RGB").convert("RGBA")
        return Image.fromarray(pixels, mode="RGBA")

    @staticmethod
    def _get_mask_array(masks: torch.Tensor, index: int, batch_size: int, frame_shape: tuple[int, int]) -> np.ndarray:
        if masks.ndim == 4 and masks.shape[1] == 1:
            masks = masks[:, 0]
        elif masks.ndim == 4 and masks.shape[-1] == 1:
            masks = masks[..., 0]
        if masks.ndim == 2:
            selected = masks
        elif masks.ndim == 3:
            if masks.shape[0] == 1:
                selected = masks[0]
            elif masks.shape[0] == batch_size:
                selected = masks[index]
            else:
                raise ValueError("foreground_mask must have 1 mask or the same batch size as images")
        else:
            raise ValueError("foreground_mask should have dimensions [H,W] or [B,H,W]")
        if tuple(selected.shape) != frame_shape:
            raise ValueError("foreground_mask resolution must match input images; resize it before connecting")
        return selected.detach().float().clamp(0, 1).cpu().numpy()

    @classmethod
    def _apply_transparency(cls, sprite: Image.Image, mode: str, color: np.ndarray | None,
                            tolerance: float, softness: float, mask: np.ndarray | None) -> Image.Image:
        alpha = np.asarray(sprite.getchannel("A"), dtype=np.float32) / 255.0
        if mode == "chroma_key":
            pixels = np.asarray(sprite.convert("RGB"), dtype=np.float32)
            distance = np.linalg.norm(pixels - color, axis=2) / (255.0 * math.sqrt(3.0))
            if softness <= 1e-8:
                matte = (distance > tolerance).astype(np.float32)
            else:
                matte = np.clip((distance - tolerance) / softness, 0, 1)
            alpha = alpha * matte
        if mask is not None:
            alpha = alpha * mask
        sprite.putalpha(Image.fromarray(np.rint(alpha * 255).astype(np.uint8), mode="L"))
        return sprite

    @staticmethod
    def _resize(sprite: Image.Image, width: int, height: int, mode: str,
                resample: Image.Resampling, anchor: str) -> Image.Image:
        target = (width, height)
        if anchor != "canvas":
            # Crop to the *visible* subject only when the user explicitly requests
            # positional anchoring; canvas mode maintains jump and travel offsets.
            bounds = sprite.getchannel("A").getbbox()
            if bounds:
                sprite = sprite.crop(bounds)
            elif not sprite.getchannel("A").getextrema()[1]:
                return Image.new("RGBA", target, (0, 0, 0, 0))
        if mode == "stretch":
            resized = sprite.resize(target, resample)
            return resized
        if mode == "cover":
            return ImageOps.fit(sprite, target, resample, centering=(0.5, 0.5))
        content = ImageOps.contain(sprite, target, resample)
        if anchor == "bottom_center":
            y = height - content.height
        else:
            y = (height - content.height) // 2
        x = (width - content.width) // 2
        result = Image.new("RGBA", target, (0, 0, 0, 0))
        result.paste(content, (x, y))
        return result

    @staticmethod
    def _safe_output_dir(name: str) -> Path:
        clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip())[:64].strip("_") or "sprite_animation"
        parent = Path(folder_paths.get_output_directory()) / "sprite_sheets"
        parent.mkdir(parents=True, exist_ok=True)
        for i in range(1, 100000):
            candidate = parent / f"{clean}_{i:05d}"
            try:
                candidate.mkdir()
                return candidate
            except FileExistsError:
                pass
        raise RuntimeError("Unable to reserve a sprite output directory")

    @classmethod
    def _page_geometry(cls, frame_count: int, width: int, height: int, columns: int,
                       spacing: int, limit: int) -> tuple[int, int]:
        if width > limit or height > limit or width * height > cls.MAX_PAGE_PIXELS:
            raise ValueError("Sprite dimensions exceed the selected sheet dimension/pixel limit")
        max_columns = max(1, (limit + spacing) // (width + spacing))
        actual_columns = min(frame_count, columns, max_columns)
        sheet_width = actual_columns * width + (actual_columns - 1) * spacing
        max_rows_dim = (limit + spacing) // (height + spacing)
        # Enforce maximum pixels as well as side lengths, even for partial pages.
        max_height_pixels = cls.MAX_PAGE_PIXELS // sheet_width
        max_rows_pixels = (max_height_pixels + spacing) // (height + spacing)
        rows_per_page = min(max_rows_dim, max_rows_pixels)
        if rows_per_page < 1:
            raise ValueError("One row exceeds the sheet size budget; reduce dimensions or columns")
        return actual_columns, rows_per_page

    @staticmethod
    def _preview(first_sheet: Image.Image) -> torch.Tensor:
        preview = first_sheet.copy()
        preview.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        # ComfyUI IMAGE preview is RGB; the *saved* PNG retains transparency.
        backing = Image.new("RGB", preview.size, (225, 225, 225))
        draw = ImageDraw.Draw(backing)
        block = 16
        for y in range(0, preview.height, block):
            for x in range(0, preview.width, block):
                if (x // block + y // block) % 2:
                    draw.rectangle((x, y, min(x + block - 1, preview.width - 1),
                                    min(y + block - 1, preview.height - 1)), fill=(245, 245, 245))
        backing.paste(preview, (0, 0), preview.getchannel("A"))
        return torch.from_numpy(np.asarray(backing, dtype=np.float32).copy() / 255.0).unsqueeze(0)

    def export(self, images, name="sprite_animation", sprite_width=256, sprite_height=256,
               columns=8, start_frame=0, frame_step=3, max_frames=120, source_fps=24.0,
               resize_mode="contain", resize_filter="lanczos", alpha_mode="preserve",
               key_color="#FFFFFF", key_tolerance=0.10, key_softness=0.05,
               save_individual_frames=True, foreground_mask=None, invert_mask=False,
               anchor_mode="canvas", spacing=0, max_sheet_dimension=4096):
        if not isinstance(images, torch.Tensor) or images.ndim != 4 or images.shape[-1] not in (1, 3, 4):
            raise ValueError("images must be a ComfyUI IMAGE tensor [B,H,W,C], with C=1/3/4")
        if images.shape[0] == 0:
            raise ValueError("No image frames were received")
        if start_frame >= images.shape[0]:
            raise ValueError("start_frame must be smaller than the IMAGE batch size")
        if frame_step < 1 or source_fps <= 0 or columns < 1 or max_frames < 0:
            raise ValueError("Invalid timing or packing values")
        if alpha_mode not in ("preserve", "chroma_key"):
            raise ValueError("Unknown alpha_mode")
        if anchor_mode not in ("canvas", "bottom_center", "center_subject"):
            raise ValueError("Unknown anchor_mode")
        if resize_mode not in ("contain", "cover", "stretch"):
            raise ValueError("Unknown resize_mode")
        if resize_filter not in ("lanczos", "nearest"):
            raise ValueError("Unknown resize_filter")
        if not 0 <= key_tolerance <= 1 or not 0 <= key_softness <= 1 or spacing < 0:
            raise ValueError("Invalid transparency or sprite spacing values")
        source_indices = list(range(start_frame, int(images.shape[0]), frame_step))
        if max_frames:
            source_indices = source_indices[:max_frames]
        count = len(source_indices)
        actual_columns, rows_per_page = self._page_geometry(
            count, sprite_width, sprite_height, columns, spacing, max_sheet_dimension
        )
        per_page = actual_columns * rows_per_page
        page_count = math.ceil(count / per_page)
        output = self._safe_output_dir(name)
        frames_dir = output / "frames"
        if save_individual_frames:
            frames_dir.mkdir()
        key_rgb = self._parse_rgb_hex(key_color) if alpha_mode == "chroma_key" else None
        resample = Image.Resampling.NEAREST if resize_filter == "nearest" else Image.Resampling.LANCZOS
        duration_ms = 1000.0 * frame_step / float(source_fps)
        pages = []
        atlas_frames = {}
        sequence = []
        first_sheet = None

        for page_index in range(page_count):
            page_start = page_index * per_page
            page_indices = source_indices[page_start:page_start + per_page]
            rows = math.ceil(len(page_indices) / actual_columns)
            page_columns = min(actual_columns, len(page_indices))
            page_width = page_columns * sprite_width + (page_columns - 1) * spacing
            page_height = rows * sprite_height + (rows - 1) * spacing
            page = Image.new("RGBA", (page_width, page_height), (0, 0, 0, 0))
            image_name = "sheet.png" if page_count == 1 else f"sheet_{page_index:03d}.png"
            for local_index, frame_index in enumerate(page_indices):
                sprite = self._as_rgba(images[frame_index])
                mask = None
                if foreground_mask is not None:
                    mask = self._get_mask_array(
                        foreground_mask, frame_index, int(images.shape[0]),
                        (int(images.shape[1]), int(images.shape[2]))
                    )
                    if invert_mask:
                        mask = 1.0 - mask
                sprite = self._apply_transparency(sprite, alpha_mode, key_rgb,
                                                  key_tolerance, key_softness, mask)
                sprite = self._resize(sprite, sprite_width, sprite_height, resize_mode,
                                      resample, anchor_mode)
                col = local_index % actual_columns
                row = local_index // actual_columns
                x = col * (sprite_width + spacing)
                y = row * (sprite_height + spacing)
                page.paste(sprite, (x, y))
                global_index = page_start + local_index
                key = f"frame_{global_index:05d}"
                file_name = f"frames/{key}.png" if save_individual_frames else None
                if file_name:
                    sprite.save(output / file_name, format="PNG")
                atlas_frames[key] = {
                    "frame": {"x": x, "y": y, "w": sprite_width, "h": sprite_height},
                    "page": page_index,
                    "sheet": image_name,
                    "rotated": False,
                    "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": sprite_width, "h": sprite_height},
                    "sourceSize": {"w": sprite_width, "h": sprite_height},
                    "source_frame": frame_index,
                    "time_seconds": round(frame_index / float(source_fps), 6),
                    "duration_ms": round(duration_ms, 4),
                    "image_file": file_name,
                }
                sequence.append(key)
            page.save(output / image_name, format="PNG")
            pages.append({"image": image_name, "size": {"w": page_width, "h": page_height},
                          "columns": page_columns, "rows": rows})
            if first_sheet is None:
                first_sheet = page

        atlas = {
            "frames": atlas_frames,
            "meta": {
                "app": "ComfyUI SpriteSheet Exporter",
                "version": "1.1.0",
                "image": pages[0]["image"],
                "pages": pages,
                "format": "RGBA8888",
                "size": pages[0]["size"],
                "scale": "1",
                "frame_size": {"w": sprite_width, "h": sprite_height},
                "spacing": spacing,
                "columns": actual_columns,
                "page_count": page_count,
                "frame_count": count,
                "source_frame_count": int(images.shape[0]),
                "source_fps": float(source_fps),
                "playback_fps": float(source_fps) / frame_step,
                "frame_step": frame_step,
                "start_frame": start_frame,
                "anchor_mode": anchor_mode,
                "alpha_mode": alpha_mode,
                "sequence": sequence,
            }
        }
        atlas_path = output / "atlas.json"
        atlas_path.write_text(json.dumps(atlas, indent=2), encoding="utf-8")
        relative_folder = output.relative_to(Path(folder_paths.get_output_directory())).as_posix()
        return {
            "ui": {"images": [{"filename": pages[0]["image"], "subfolder": relative_folder, "type": "output"}]},
            "result": (self._preview(first_sheet), str(output / pages[0]["image"]), str(atlas_path)),
        }


# Backward compatibility: existing workflow JSONs refer to H3SpriteSheetExport.
H3SpriteSheetExport = SpriteSheetExport
