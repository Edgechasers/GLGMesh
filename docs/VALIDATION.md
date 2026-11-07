# Validation scope

Software checks and visual asset quality are different. Passing the unit suite establishes orchestration behavior; it does not establish that a model is attractive, manifold, rigged or ready for a game.

## Automated checks

Run from the repository directory:

```sh
python3.12 -m unittest discover -s tests -v
```

The suite covers mode defaults, triangle limits, texture routing, stage failure/resume, cancellation, generation locking, pipeline fingerprints, fixed pre-Hi3D reduction, saved dense-source resampling, source-splat lineage, neutral GLB export and local HTTP security. It uses synthetic job artifacts and mock workers; it does not download weights or run neural inference.

## Executed workflow checks

The integrated workflows have been exercised with real outputs:

- Fresh Hunyuan Mini and Hunyuan 2.1 generation, reduction and GLB export.
- Fresh TRELLIS.2 shape and texture generation, including a 199,999-triangle output.
- Full 50-step IDOL generation followed by GauStudio reconstruction, reduction and appearance baking.
- Hi3D refinement of a splat-derived mesh reduced to approximately 10k before refinement, followed by a 10k final output.
- Fresh Hunyuan Paint and MV-Adapter texture-only jobs, with 2K embedded textures and source triangle positions/counts verified unchanged.
- Production resampling at higher and lower budgets using retained dense intermediates.
- Actual GLB imports in Godot and front/back/three-quarter review renders.
- Browser checks of texture toggling, neutral downloads, source-splat preview and the Production V1/V2 labels.

Some checks reuse earlier completed geometry or splats to isolate downstream stages. They are not all fresh end-to-end benchmarks of the same revision. Full Production V1 generation plus its newly integrated MV texture has not been repeated as a single fresh benchmark; its stages and routing have independent coverage.

## Remaining limitations

Existing test assets have reported detached parts, enclosed components, winding issues and centered origins. Texture-only validation intentionally preserves source geometry and can therefore retain QA errors. The UI exposes these reports rather than treating successful export as a quality certificate.

The documented design baseline is Apple Silicon with at least 16 GB of unified memory. Every pipeline and setting has not been validated at that minimum, and no cross-device performance baseline is established. Initial UI timing estimates are approximate. GPU-backed generation is not covered by the source-only unit suite.

Local run logs, machine reports, source images and historical validation records are excluded from publication. The public [showcase](SHOWCASE.md) includes only curated render media and portable provenance.
