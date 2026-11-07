# Pipelines and output behavior

All pipelines prepare the image locally, generate geometry in isolated worker processes, enforce a final triangle ceiling, then reimport the GLB for QA and review renders. Shape inference exits before optional texturing starts. Stage progress is based on worker events, not a promise about remaining time.

## Prototype and Medium

- **Prototype (`fast`):** Hunyuan Mini, 30 shape steps; Blender Collapse reduction; optional Hunyuan Paint 2.0.
- **Medium (`medium`):** Hunyuan 2.1, 50 shape steps; Blender Collapse reduction; optional MV-Adapter SD2.1.

Both default to 10,000 triangles. The first Hunyuan 2.1 run may convert its checkpoint for the MLX port; the converted weights are retained.

Hunyuan Paint generates six 384px views with 20 UniPC steps and bakes a 2048² RGB atlas. MV-Adapter generates six geometry-conditioned 512px views with 40 shifted-SNR steps, then uses calibrated projection to bake a 2048² RGB atlas. The MV implementation uses the official neural model on MPS, with Metal control rendering and CPU/Metal projection replacing CUDA rendering and baking.

Both texture adapters preserve source triangle positions and counts. UV seams can add split vertices. They infer unseen surfaces and use constant roughness 0.85 / metallic 0; they do not generate complete PBR material maps.

`--texture auto` selects the mode default. `none` disables optional texturing. `rgb` is supported for Prototype and Medium; `mv` is supported for Medium and Production V1. The UI exposes the default method and the geometry-only option.

## High quality

**High quality (`high`)** uses TRELLIS.2 at 512 resolution with 12 sampling steps per stage, CPU reduction, UV unwrap and a native 1024² texture bake. The default budget is 200,000 triangles, so this output is substantially denser than the default low-poly modes. Supply `--triangles` to request a different budget.

Its native texturing is part of this pipeline; the optional Hunyuan/MV selector does not replace it.

## Production V1

**Production V1 (`production`)** follows:

1. IDOL generates a Gaussian splat.
2. Density-field surface reconstruction extracts a mesh at grid resolution 256 and density threshold 0.1.
3. Blender reduces that surface to approximately **10,000 intermediate triangles**, independently of the final target.
4. Hi3D runs 25 refinement steps and its native postprocessing targets the requested final budget.
5. MV-Adapter textures the reduced mesh unless `--texture none` is selected.

The surface reconstruction is a GLGMesh adapter, not an official IDOL mesh decoder. Hi3D can change the silhouette relative to the source splat.

Resampling reuses `hi3d/extracted-raw.glb`, reruns native component filtering, reduction and normalization, and then regenerates the MV texture if selected. It repeats no IDOL or Hi3D neural inference. Historical geometry-only results remain geometry-only when resampled.

## Production V2

**Production V2 (`production-textured`)** follows:

1. IDOL generates a Gaussian splat.
2. A GauStudio adaptation renders 98 calibrated 1024×1280 views using a patched Metal Gaussian renderer. Median depth at 0.5 transmittance is fused with Open3D TSDF (0.0015 voxel size / 0.006 truncation).
3. A dense UV-unwrapped intermediate receives a 4096² texture projected from the original splat views.
4. Blender reduces the dense mesh to the target budget, creates new UVs and rebakes the appearance at 4K.
5. The GLB, editable Blender file, texture and review reports are retained.

This is an Apple Silicon adaptation of the reconstruction workflow, not the unmodified upstream CUDA/VDBFusion pipeline. No Hi3D or MV-Adapter stage is used. The GLB material uses `KHR_materials_unlit`: it preserves baked appearance and shading rather than relightable PBR properties.

Resampling uses the saved GauStudio dense geometry and texture. It performs fresh target reduction, UV creation and appearance rebaking. IDOL and GauStudio reconstruction do not run again.

## Production controls and retained sources

Both Production modes accept 50–400 IDOL sampling steps (default 50). The UI increments by 25; the CLI accepts integer values. More steps increase computation and can change the result but are not a guaranteed quality improvement. Resampling retains the original sampling settings.

Targets range from 100 to 2,000,000 triangles. Both higher and lower targets are accepted; the available dense source sets the maximum recoverable detail. Resampling creates a separate job, retains source lineage and never overwrites the original result.

Keep the dense intermediate and its source run. Deleting them disables resampling. Keep the original `idol/splat.ply` and camera metadata for the **Source splat** viewer. That viewer renders the Gaussians themselves; mesh download controls still download the mesh result.

## Checkpoints, exports and limits

Cancelled or failed jobs can resume only with matching settings, source hashes, completed-stage manifests and pipeline code fingerprint. A code update can require a new job. MV native-view generation and texture baking are separate stages, so a bake retry does not repeat neural inference.

The **Without texture** download removes embedded images, texture references and vertex colors, replaces materials with neutral shading, and preserves geometry, UVs, normals and transforms. It does not repair topology or create texture data for a geometry-only source.

QA findings remain attached to each result. Reconstruction holes, detached pieces, thin appendages, dark baked regions and inconsistent generated backs may remain. “Production” names the workflow; it is not a certification of rigging readiness or final artistic quality.
