# Third-party models and code

GLGMesh orchestrates these projects. It does not claim ownership of their models or replace their licenses. Repository commits are pinned in `glgmesh/config.py`; weight revisions and file lists are pinned in `weights.json`. The original repositories and downloaded model notices remain under `runtime/`.

| Component | Upstream / distribution |
|---|---|
| Hunyuan Mini / 2.1 weights | https://huggingface.co/tencent/Hunyuan3D-2mini · https://huggingface.co/tencent/Hunyuan3D-2.1 |
| Hunyuan3D-Paint-v2-0 RGB weights | https://huggingface.co/tencent/Hunyuan3D-2 |
| MV-Adapter SD2.1 code / adapter | https://github.com/huanngzh/MV-Adapter · https://huggingface.co/huanngzh/mv-adapter |
| Stable Diffusion 2.1 base distribution | https://huggingface.co/sd2-community/stable-diffusion-2-1-base |
| Hunyuan MLX implementation | https://github.com/ZimengXiong/Hunyuan3D-Swift |
| TRELLIS.2 weights and code | https://huggingface.co/microsoft/TRELLIS.2-4B · https://github.com/microsoft/TRELLIS.2 |
| TRELLIS Apple port | https://github.com/apetersson/TRELLIS.2-apple-silicon |
| IDOL weights and SDK | https://huggingface.co/speridlabs/idol · https://github.com/speridlabs/idol-sdk |
| DINOv3 encoders | https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m · https://huggingface.co/facebook/dinov3-vith16plus-pretrain-lvd1689m |
| FLUX.2-dev VAE only | https://huggingface.co/black-forest-labs/FLUX.2-dev |
| Hi3D MLX port and weights | https://github.com/cguldogan/mlx-vlm · https://huggingface.co/mlx-community/Hi3Dv1.0-mlx |
| Hi3D upstream | https://github.com/hi3d-official/Hi3Dv1.0 |
| Background removal | rembg 2.0.57 / U²-Net, https://github.com/danielgatis/rembg |
| GauStudio surface reconstruction | https://github.com/GAP-LAB-CUHK-SZ/gaustudio |
| Metal Gaussian rasterizer | https://github.com/nandometzger/metal-gauss |
| CPU TSDF fusion | Open3D 0.19.0, https://github.com/isl-org/Open3D |
| Blender | Installed application, https://www.blender.org/ |
| Mesh reduction / geometry | fast-simplification, PyMeshLab, pyfqmr, trimesh, xatlas, SciPy, scikit-image |

`workers/qa_check.py`, `workers/_bpyx.py` and `workers/bake_maps.py` are adapted from the Blender Agent Skills package (`blender-asset-qa` and `blender-texture-baking`, version 1.2.0, MIT license as declared by its skill metadata). The original package declares MIT licensing in its skill metadata. The vendored helpers are self-contained; installing that package is not required. Their attribution and license text are retained in `LICENSES/Blender-Agent-Skills-MIT.txt`.

Inspect upstream model cards and licenses before redistribution or commercial use of their weights and outputs. Installing GLGMesh does not grant gated-model access; downloads use your own Hugging Face account's existing permissions.

The interactive viewer bundles Three.js 0.181.2 (MIT) and its GLTFLoader/BufferGeometryUtils addons under `ui/vendor/`. The complete upstream license is `ui/vendor/THREE-LICENSE.txt`. Source: https://github.com/mrdoob/three.js . No CDN requests are made. Rebuild with `npm ci --prefix frontend` then `npm run vendor --prefix frontend`.

Source splat rendering uses `@mkkellogg/gaussian-splats-3d` 0.4.7 (MIT), vendored under `ui/vendor/`; license: `GAUSSIAN-SPLATS-3D-LICENSE.txt`. Source: https://github.com/mkkellogg/GaussianSplats3D . Its module imports use the same bundled Three.js as the mesh viewer. `frontend/vendor.mjs` reproducibly copies both libraries from the pinned npm lockfile.

MV-Adapter integration uses the official pinned neural weights and model code, with local MPS attention chunking and CPU/Metal control rendering and projection. `patches/mv-adapter.patch` removes an unused CUDA rasterizer import; no neural weights are modified. Model and code licenses remain distinct.
