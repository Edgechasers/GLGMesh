# Architecture

GLGMesh has a standard-library Python CLI and loopback HTTP server, a browser preview, and isolated subprocess workers for each model stack. The CLI and UI share the same job runner.

## Source layout

- `glgmesh/`: configuration, setup, jobs, checkpoints, progress, HTTP API and GLB download conversion.
- `workers/`: image preparation, inference adapters, mesh reconstruction, reduction, texturing and Blender review.
- `patches/`: compatibility changes to pinned upstream repositories.
- `locks/`, `requirements-*.txt`, `weights.json`: Python dependencies and model provenance.
- `ui/`: application UI and locally vendored Three.js / GaussianSplats3D modules.
- `frontend/`: pinned npm dependencies and vendor rebuild script; no frontend build is needed to run the app.
- `tests/`: orchestration and API regression tests that do not download or run models.
- `tools/`: documentation turntable generation.

## Execution and storage

Setup explicitly downloads code and weights into `runtime/`. Inference uses offline model loading and a worker bootstrap that rejects outbound socket connections. Background removal runs locally. No hosted inference API is used.

Separate environments accommodate incompatible model dependency versions. Heavy workers run sequentially and exit between stages to release memory. A process lock prevents overlapping GLGMesh generation/setup jobs; it does not coordinate unrelated applications.

Each run under `runs/` contains the input, prepared image, immutable settings, checkpoints, logs and output artifacts. Status is written atomically. The CLI JSON stream and UI use the same progress events. Stage percentages are weighted milestones; unknown-duration operations may remain indeterminate.

Cancellation terminates the subprocess group and escalates after a grace period. Resume verifies settings, stage artifact hashes and a fingerprint of pipeline code, patches, locks and requirements. IDOL saves intermediate sampling checkpoints; TRELLIS and Hi3D also retain stage data.

## Geometry and appearance

Triangle budgets are checked against exported GLB indices. Over-budget exports fail validation; smaller results are allowed. Source geometry is retained for review, so QA findings do not necessarily mark generation itself as failed.

Production V1 retains dense Hi3D geometry for native postprocessing at new budgets. Production V2 retains the dense GauStudio mesh and appearance for Blender reduction and rebaking. Texture-only jobs preserve their original shape and source lineage.

## Browser and local API

The UI binds to loopback and checks Host/Origin and POST tokens. Run-file paths are constrained to the run directory. Images and models are not uploaded to a remote service. Meshes and splats render through vendored browser modules; no CDN is required.

Rotation can be paused, manually adjusted or disabled by reduced-motion preferences. The splat renderer loads lazily and releases its worker and GPU resources when the view changes. Texture preview and download variant selection remain independent.
