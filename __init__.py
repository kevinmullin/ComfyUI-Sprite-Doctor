"""ComfyUI SpriteSheet Exporter — MIT license, Kevin Mullin (2026)."""

# ComfyUI loads this file as a package; pytest can also collect it directly
# as a standalone file when the containing GitHub repository uses hyphens.
if __package__:
    from .nodes import SpriteSheetExport

    NODE_CLASS_MAPPINGS = {
        "SpriteSheetExport": SpriteSheetExport,
        "H3SpriteSheetExport": SpriteSheetExport,  # preserves existing workflows
    }
    NODE_DISPLAY_NAME_MAPPINGS = {
        "SpriteSheetExport": "Sprite Sheet Export (Image Batch)",
        "H3SpriteSheetExport": "H3 Sprite Sheet Export (Legacy)",
    }
else:
    # Only applies to direct file collection in a standalone test context.
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
