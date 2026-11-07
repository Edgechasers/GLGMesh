# Requirements and installation

## Supported platform

GLGMesh is designed to run on **Apple Silicon Macs with at least 16 GB of unified memory**. Its workers use MLX, PyTorch’s MPS backend and compiled Metal rendering code. Setup rejects other operating systems and architectures. There is no CUDA fallback in this release.

| Requirement | Purpose |
|---|---|
| Apple Silicon Mac with **16 GB or more unified memory** | Minimum design requirement; memory demand varies by pipeline |
| Python **3.12**, arm64 build, with `venv` and `pip` | Launcher and isolated inference environments |
| Blender **5.2 or newer** | Mesh reduction, baking, editable exports and review; the adapters target the 5.2 API |
| Git | Fetch pinned upstream code and apply compatibility patches |
| Xcode Command Line Tools | Compiler toolchain for native dependencies; Metal compilation is required by Production V2 |
| Internet during setup | Download Python packages, pinned repositories and model weights |
| Hugging Face account with required model access | Gated encoders and the FLUX VAE used by High/Production modes |
| Browser with WebGL support | Local mesh and Gaussian-splat previews |

The minimum design requirement is **16 GB of unified memory**. Memory and disk demand depend on the selected pipeline; this baseline is not a guarantee that every pipeline and setting fits within that capacity. The larger diffusion models need substantial free unified memory; run one inference task at a time and close other memory-heavy applications. Install Prototype first to check the basic workflow. High and Production modes should not be assumed to fit every Apple Silicon device.

Weights and environments consume multiple gigabytes per pipeline, and a complete installation requires tens of gigabytes. Converted weights, compiled caches, dense meshes, rendered views and resumable jobs add further storage. Maintain free space beyond the initial download size; files are not automatically purged.

## Install

1. Install an arm64 Python 3.12 and Blender 5.2+. Ensure `python3.12` is on `PATH`.
2. Install the command-line build tools if absent:

   ```sh
   xcode-select --install
   ```

3. Open a terminal in this repository and check the installation:

   ```sh
   python3.12 --version
   git --version
   ./glgmesh.sh doctor
   ```

4. Install one mode, then start the UI:

   ```sh
   ./glgmesh.sh setup fast
   ./glgmesh.sh ui
   ```

Other installation targets are `medium`, `high`, `production`, `production-textured`, and `all`. `setup all` installs all pipelines and their default texture methods. Use `setup fast --texture none` or `setup medium --texture none` to omit optional texturing dependencies. The UI’s **Install this mode** action uses the same installer.

## Executable overrides

The launcher uses `python3.12` from `PATH`. Blender defaults to its standard application path. For a different installation:

```sh
export GLGMESH_PYTHON="/path/to/python3.12"
export GLGMESH_BLENDER="/path/to/Blender.app/Contents/MacOS/Blender"
./glgmesh.sh doctor
```

The Python used to launch setup creates the virtual environments. Use the required version consistently. Do not mix arm64 and Rosetta Python environments.

## Gated model access

High quality uses the DINOv3 ViT-L encoder. Both Production modes use DINOv3 ViT-H+ and the **FLUX.2-dev VAE only**. Follow the access requirements on their model pages listed in [THIRD_PARTY.md](../THIRD_PARTY.md). GLGMesh does not grant access or accept model terms on your behalf.

Once the torch environment has been created, authenticate through Hugging Face’s CLI:

```sh
runtime/envs/torch/bin/hf auth login
```

If setup stopped at an authorization error, obtain access, log in and rerun the same setup command. Existing repositories, installed dependencies and downloaded files are reused. Keep credentials out of source files, shell scripts and issue reports. Authentication uses the normal Hugging Face credential store; credentials are not bundled with releases.

## Dependency layout

| Environment/component | Used by | Main dependencies |
|---|---|---|
| `runtime/envs/hunyuan` | Prototype, Medium, Hunyuan Paint | MLX 0.31.2, Hunyuan3D-Swift, NumPy, SciPy, trimesh, OpenCV; xatlas for Paint |
| `runtime/envs/torch` | TRELLIS.2, IDOL, GauStudio; MV base packages | PyTorch 2.5.1 / torchvision 0.20.1, diffusers 0.36.0, transformers 4.57.3, geometry libraries |
| `runtime/envs/hi3d` | Production V1 | MLX 0.32.4, Hi3D port, pyfqmr |
| `runtime/envs/mv` | Medium and Production V1 texturing | MV-Adapter, SD2.1; extra packages isolated from the pinned torch/Hunyuan bases |
| GauStudio additions | Production V2 | Open3D 0.19.0, Ninja, patched Metal Gaussian rasterizer |
| Blender application | Reduction, bake and review | Blender’s own bundled Python; no separate `bpy` pip install |
| Bundled browser modules | Preview | Three.js and GaussianSplats3D; no CDN dependency |

Exact pins live in `locks/`, `requirements-*.txt`, `glgmesh/config.py` and `weights.json`. Setup prefers a lock file when one exists. Repository revisions and model revisions are fixed; compatibility patches are applied locally. Environments are deliberately separated because the model ports require different MLX versions.

Node/npm are optional developer tools for rebuilding `ui/vendor/`. Godot and Pillow are only needed to regenerate documentation turntables, not to run GLGMesh.

## Troubleshooting

- **Python not found / wrong version:** install arm64 Python 3.12 or set `GLGMESH_PYTHON`.
- **Blender unavailable:** check `GLGMESH_BLENDER` and application permissions.
- **Download denied:** check authentication and access to the exact model repository.
- **Native compilation fails:** verify the Xcode tools and compiler selection; read the setup log under `runtime/`.
- **Memory pressure or very slow sampling:** stop competing inference, use a smaller pipeline, or disable optional texturing. A stalled system can run much slower than the UI estimate.
- **Resume rejected after an update:** the saved pipeline fingerprint differs. Preserve the old run and create a new job with the updated code.
- **QA findings on a completed job:** inspect the result; successful export is separate from mesh quality. Texturing does not repair source topology.
