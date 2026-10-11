# Contributing

Thanks for helping improve the SpriteSheet Exporter by Kevin Mullin.

1. Search existing GitHub issues first; open a focused issue for bugs/features when practical.
2. Fork or create a branch for your change.
3. Keep the custom node independent of specific generative models and avoid new large runtime dependencies.
4. Add regression tests for changes in mask handling, alpha export, sampling, page packing, output paths, and JSON mapping.
5. Run `pytest -q` and document visible changes in `CHANGELOG.md`.
6. Submit a pull request with a sample workflow/short reproduction and representative (license-safe) example frames.

Bug reports should include ComfyUI version, platform, node version, input shape (`B,H,W,C`), settings, log excerpt, and whether the saved PNG or just the preview is wrong. Avoid sharing private photos or proprietary model weights.

License: MIT. By contributing you agree your changes can be distributed under the project's MIT license.
