"""Portable tests: use a folder_paths stub, no running ComfyUI instance needed."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest
import torch
from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def exporter(tmp_path, monkeypatch):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(tmp_path)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    spec = importlib.util.spec_from_file_location("spritesheet_exporter_nodes", PROJECT / "nodes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SpriteSheetExport()


def _run(node, images, **kw):
    defaults = dict(
        name="unit_test", sprite_width=16, sprite_height=16, columns=2,
        start_frame=0, frame_step=1, max_frames=0, source_fps=24,
        resize_mode="contain", resize_filter="nearest", alpha_mode="preserve",
        key_color="#FFFFFF", key_tolerance=0.1, key_softness=0,
        save_individual_frames=True,
    )
    defaults.update(kw)
    result = node.export(images, **defaults)
    atlas_path = Path(result["result"][2])
    atlas = json.loads(atlas_path.read_text())
    return result, atlas, atlas_path.parent


def test_single_rgb_frame(exporter):
    frames = torch.ones((1, 8, 8, 3), dtype=torch.float32) * 0.5
    result, atlas, output = _run(exporter, frames)
    assert result["result"][0].shape == (1, 16, 16, 3)
    assert atlas["meta"]["frame_count"] == 1
    assert (output / "sheet.png").exists()
    assert (output / "frames/frame_00000.png").exists()
    assert Image.open(output / "sheet.png").mode == "RGBA"


def test_all_input_frames_and_step(exporter):
    frames = torch.rand((12, 16, 16, 3))
    _, atlas, _ = _run(exporter, frames, start_frame=1, frame_step=3, max_frames=2)
    assert [v["source_frame"] for v in atlas["frames"].values()] == [1, 4]
    assert atlas["meta"]["playback_fps"] == 8.0
    assert atlas["frames"]["frame_00001"]["duration_ms"] == pytest.approx(125.0)


def test_chroma_key_preserves_non_white(exporter):
    arr = np.ones((1, 8, 8, 3), dtype=np.float32)
    arr[:, 2:6, 2:6, :] = (1, 0, 0)
    _, atlas, output = _run(exporter, torch.from_numpy(arr), alpha_mode="chroma_key", key_color="#FFFFFF")
    png = np.array(Image.open(output / "sheet.png"))
    assert png[0, 0, 3] == 0
    assert png[14, 14, 3] == 0
    assert png[4, 4, 3] == 255


def test_foreground_mask(exporter):
    frames = torch.ones((1, 8, 8, 3))
    mask = torch.zeros((1, 8, 8))
    mask[:, :4, :] = 1
    _, _, output = _run(exporter, frames, foreground_mask=mask)
    png = np.asarray(Image.open(output / "sheet.png"))
    assert png[1, 1, 3] == 255
    assert png[14, 1, 3] == 0


def test_rgba_alpha_preserved(exporter):
    rgba = torch.zeros((1, 8, 8, 4))
    rgba[..., :3] = 0.8
    rgba[..., 3] = 0.25
    _, _, output = _run(exporter, rgba)
    image = Image.open(output / "sheet.png")
    assert np.asarray(image)[5, 5, 3] == 64


def test_spacing_and_page_split(exporter):
    frames = torch.rand((9, 10, 10, 3))
    # sheet dimensions constrain to <= 1 row at 256w x 256h each (max=512)
    _, atlas, output = _run(exporter, frames, sprite_width=256, sprite_height=256,
                            max_sheet_dimension=512, spacing=2, columns=4,
                            save_individual_frames=False)
    assert len(atlas["meta"]["pages"]) == 9
    assert atlas["meta"]["frame_count"] == 9
    assert (output / "sheet_000.png").exists()
    assert (output / "sheet_008.png").exists()
    assert not (output / "frames").exists()
    assert atlas["frames"]["frame_00008"]["sheet"] == "sheet_008.png"


def test_grid_positions(exporter):
    frames = torch.rand((4, 8, 8, 3))
    _, atlas, output = _run(exporter, frames, spacing=3)
    assert np.array(Image.open(output / "sheet.png")).shape == (35, 35, 4)
    assert atlas["frames"]["frame_00003"]["frame"] == {"x": 19, "y": 19, "w": 16, "h": 16}


def test_anchor_does_not_crop_jump_in_canvas_mode(exporter):
    frame = torch.zeros((1, 16, 16, 4))
    frame[0, 0:2, 7:9, :3] = 1
    frame[0, 0:2, 7:9, 3] = 1
    _, _, output = _run(exporter, frame, anchor_mode="canvas")
    image = np.array(Image.open(output / "sheet.png"))
    assert image[0, 7, 3] > 0
    assert image[-1, 7, 3] == 0
    _, _, output2 = _run(exporter, frame, anchor_mode="bottom_center")
    image2 = np.array(Image.open(output2 / "sheet.png"))
    assert image2[-1, 7, 3] > 0


def test_friendly_error_on_bad_mask_count(exporter):
    frames = torch.ones((3, 8, 8, 3))
    with pytest.raises(ValueError, match="same batch size"):
        _run(exporter, frames, foreground_mask=torch.ones((2, 8, 8)))


def test_frame_beyond_end(exporter):
    with pytest.raises(ValueError, match="start_frame"):
        _run(exporter, torch.ones((2, 8, 8, 3)), start_frame=2)


def test_long_sequence_pages_without_overwrite(exporter):
    frames = torch.ones((10, 8, 8, 3))
    _, atlas1, path1 = _run(exporter, frames, max_sheet_dimension=512)
    _, atlas2, path2 = _run(exporter, frames, max_sheet_dimension=512)
    assert path1 != path2
    assert atlas1["meta"]["frame_count"] == atlas2["meta"]["frame_count"]
