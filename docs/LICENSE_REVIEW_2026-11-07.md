# GLGMesh commercial licence review

Reviewed 7 November 2026. Source commit: `0879d3ea5efdd451949133a4136f36e743698a5e`.

**Historical scope:** this review describes the MIT-licensed commit above, before the subsequent licence change. The current [GLGMesh licence](../LICENSE) requires a separate Edgechasers licence for commercial software use and attribution for code and generated assets. The third-party findings below remain relevant; their permissions do not grant commercial rights to current GLGMesh code. See [current licensing guidance](LICENSING.md).

**A paid GLGMesh product is feasible, but the complete current runtime should not be packaged and sold unchanged.** Hunyuan has territorial restrictions affecting both desktop and hosted use. The downloaded GauStudio tree contains non-commercial code. GPL components permit charging money, but require a distribution strategy compatible with their source and downstream-rights obligations.

This is a technical licence review, not a legal opinion. Have counsel confirm the final distribution boundary and any negotiated model permissions before launch. The conclusions below distinguish paid use from proprietary redistribution; they are different questions.

## Evidence and scope

Reviewed `weights.json`, `glgmesh/config.py`, setup/download code, worker imports and execution boundaries, pinned repository licences, the installed model notices, Python package metadata and the frontend lockfile. Checked upstream publisher licences/model cards online. The accompanying [inventory](license-inventory-2026-11-07.json) records 123 installed Python package/version combinations, their declared licences and local notice-file hashes, two frontend packages, and all 12 model-manifest entries.

Installed packages include extras beyond the lockfiles. This inventory is not a complete software bill of materials for a future installer: wheel-embedded native libraries, OS/SDK redistribution, every file in cloned repositories, input-art rights and model-training provenance have not received exhaustive legal clearance. No application behaviour or dependency was changed during this review.

## AI models and implementations

| Component actually selected | Licence evidence | Paid application / SaaS assessment |
| --- | --- | --- |
| Hunyuan3D-2mini shape weights | Tencent Hunyuan 3D 2.0 Community; pinned `f90a0f7…` | **Territorial blocker:** no grant for EU, UK or South Korea. Elsewhere, commercial use is conditional. |
| Hunyuan3D-2.1 shape weights | Tencent Hunyuan 3D 2.1 Community; pinned `0b94677…` | Same territorial blocker. |
| Hunyuan3D-Paint-v2-0 weights | Tencent Hunyuan 3D 2.0 Community; pinned `9cd649b…` | Same territorial blocker, including when used only for texturing. |
| Hunyuan3D-Swift implementation | MIT in pinned repository | Implementation permission does not override the separate weights licence. |
| TRELLIS.2 and TRELLIS-image-large sparse decoder | Microsoft model cards declare MIT; official code and Apple port carry MIT | Commercial use and redistribution permitted with notices. DINOv3 and imported libraries retain their own terms. |
| IDOL model and SDK | Model card declares Apache-2.0; pinned SDK contains Apache-2.0 | Commercial use permitted with licence/notice and modification obligations. Its GPL `plyfile` dependency needs separate treatment. |
| DINOv3 ViT-L and ViT-H+ encoders | Meta DINOv3 licence, August 19, 2025 | Worldwide use/redistribution grant; no non-commercial-only clause or revenue/MAU cap found. Preserve its agreement, use restrictions and redistribution terms. It is a custom licence, not MIT. |
| FLUX.2 **VAE only** | Black Forest Labs explicitly publishes the VAE as Apache-2.0 | Commercially usable under the publisher's VAE-specific grant. GLGMesh does not download the full FLUX.2-dev generator. Preserve proof of the component-specific grant. |
| Hi3Dv1.0 MLX weights | Hi3D Open License Agreement 1.0 included locally; converted model's `NOTICE` identifies original revision `705fc090…` | Explicitly permits proprietary products and SaaS, subject to attribution, acceptable-use and scale conditions below. |
| Hi3D embedded DINOv2-L / CLIP encoders | Apache-2.0 / MIT, recorded in converted bundle's `NOTICE`, `LICENSE-APACHE`, `LICENSE-CLIP` | Commercial use permitted with notices. |
| MV-Adapter code and adapter weights | Apache-2.0 repository licence and model card | Commercial use permitted; SD2.1 base has additional terms. |
| Stable Diffusion 2.1 base | Selected distribution declares CreativeML Open RAIL++-M | Commercial use/SaaS are compatible with this licence family, with enforceable use restrictions and downstream notices. Capture the exact applicable historical licence before bundling: the selected mirror does not carry `LICENSE-MODEL`, and its original licence link was inaccessible during review. Do not substitute terms for a newer Stability model. |
| rembg / U²-Net | rembg MIT; U²-Net upstream Apache-2.0 | No non-commercial-only restriction identified. Archive the upstream model licence and conversion provenance for the exact ONNX file delivered by rembg. |

Sources: [Hunyuan Mini pinned licence](https://huggingface.co/tencent/Hunyuan3D-2mini/raw/f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6/LICENSE), [Hunyuan 2.1 licence](https://huggingface.co/tencent/Hunyuan3D-2.1/blob/main/LICENSE), [Paint pinned licence](https://huggingface.co/tencent/Hunyuan3D-2/blob/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/LICENSE), [TRELLIS.2 pinned card](https://huggingface.co/microsoft/TRELLIS.2-4B/raw/af44b45f2e35a493886929c6d786e563ec68364d/README.md), [TRELLIS decoder card](https://huggingface.co/microsoft/TRELLIS-image-large), [IDOL card](https://huggingface.co/speridlabs/idol), [DINOv3-L licence](https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m/blob/main/LICENSE.md), [DINOv3-H+ licence](https://huggingface.co/facebook/dinov3-vith16plus-pretrain-lvd1689m/blob/main/LICENSE.md), [BFL VAE announcement](https://bfl.ai/blog/flux-2), [Hi3D licence](https://huggingface.co/hi3d-official/Hi3Dv1.0/blob/main/LICENSE), [MV-Adapter card](https://huggingface.co/huanngzh/mv-adapter), [SD2.1 distribution](https://huggingface.co/sd2-community/stable-diffusion-2-1-base), [U²-Net upstream](https://github.com/xuebinqin/U-2-Net).

**Hunyuan details.** Sections 1, 2, 3 and 5 exclude the EU, UK and South Korea; section 5(c) also expressly addresses outputs/results outside that territory. A US server does not by itself authorize EU customers or EU operations. If operating from Spain, obtain a separate grant or remove these components. Section 4 requires separate permission when the licensee's products/services exceeded one million MAU in the month before the model version's release date; this is not worded as a simple ongoing GLGMesh-only cap. Distribution requires the agreement, relevant notices and downstream use conditions. The current text also requires provider identification/non-endorsement disclosures. Hunyuan branding is encouraged rather than mandatory. Using Hunyuan materials or outputs to improve other AI models is restricted. None of these restrictions disappear by converting weights to MLX or letting users download them separately.

**Hi3D details.** Commercial integrations must display “Powered by Hi3D 1.0”, linked to the official site where the location supports links. An About page or acknowledgements can satisfy the specified display locations. A separate licence is triggered above **200,000 MAU** or at **USD 1,000,000 monthly revenue** for related products/services. Section 5 provides a 60-day application window and a conditional negotiation transition, with limits on expansion. Include the agreement/required notice, identify modifications and pass its acceptable-use conditions downstream. Standalone generated meshes are expressly treated separately from redistributed model materials.

**FLUX distinction.** The full FLUX.2-dev model has non-commercial terms, but BFL's own announcement separately grants Apache-2.0 treatment to the VAE. `weights.json` downloads only `vae/config.json` and `vae/diffusion_pytorch_model.safetensors`; `workers/idol.py` uses it as an encoder. Therefore the full model's non-commercial label should not automatically disqualify the current pipeline. The gated repository still displays the broader agreement, so retain the explicit VAE grant and an exact artifact/provenance record in the release dossier; resolve any ambiguity about the delivered artifact before shipping.

## Software with material packaging obligations

| Component | Observed licence | Consequence |
| --- | --- | --- |
| PyMeshLab 2025.7.post1 | GPLv3 in installed metadata | Commercial use allowed. Distributed combined workers require GPL compliance; relevant to closed-source integration. `workers/budget.py` imports it directly, including a reduction fallback. |
| plyfile 1.1.2 | GPLv3-or-later | Commercial use allowed. IDOL's `idol/gaussian.py` directly imports it for PLY output. Apache licensing of IDOL does not remove this dependency's requirements. |
| Blender | GPL; Blender's licence page describes GPLv2-or-later source, with distribution details governed by the delivered build | Can be used commercially and sold with compliance. GLGMesh currently invokes an installed external executable and passes Python scripts. Shipping Blender brings corresponding-source and notice duties; scripts using `bpy` also need consideration. A separate process is relevant but not an automatic exemption. |
| easydict 1.13 | LGPL-3.0 | Can coexist with proprietary software subject to LGPL requirements, including notices, covered source and the user's ability to modify/replace the library as applicable. |
| certifi; orjson; tqdm | MPL-2.0 appears in their package metadata (with other licences for some portions) | Commercially compatible; retain notices and meet covered-file source obligations when distributing. MPL does not automatically require opening the whole application. |
| GauStudio core / Metal Gaussian rasterizer / Open3D | MIT top-level licences | Generally commercially compatible, but the GauStudio checkout contains exceptions below. |
| Three.js 0.181.2; GaussianSplats3D 0.4.7 | MIT | Commercial embedding permitted. Existing vendored licence files are present. |
| PyTorch, MLX, Diffusers, Transformers, ONNX Runtime, geometry/scientific libraries | Predominantly BSD, MIT or Apache-2.0 | No general commercial-use ban found in reviewed package declarations. Preserve all applicable licences, including embedded library notices. |

Local evidence: `runtime/envs/torch/lib/python3.12/site-packages/*dist-info`, `runtime/repos/idol/idol/gaussian.py`, `workers/budget.py`, `glgmesh/engine.py`, `ui/vendor/*LICENSE*`. Upstream sources: [PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab), [plyfile v1.1.2 GPL text](https://raw.githubusercontent.com/dranjan/python-plyfile/v1.1.2/COPYING), [Blender licensing](https://www.blender.org/about/license/).

GPL allows charging. For a desktop product, recipients must receive the applicable source access and rights for covered code; an EULA cannot erase those rights. Whether the surrounding program is a combined work depends on integration, not merely whether all files share an installer. Keeping an independently usable GPL worker with its corresponding source can help establish a boundary, but replacing the directly imported GPL libraries is the simpler route for a proprietary inference worker. The reviewed commit's MIT designation alone was insufficient to describe the whole installed runtime. The subsequent GLGMesh commercial-use restriction also requires compatibility review before distributing a combined work with GPL components.

For server-only GPLv3 software, network interaction without transferring a program copy is not conveying under section 0. Ordinary SaaS therefore generally does not trigger GPL's distribution source duties. This is distinct from AGPL. No AGPL declaration was found in the installed Python package metadata examined, but this does not certify every embedded file. Delivering customer containers/on-premise servers changes the analysis.

**Actual non-commercial code in the downloaded GauStudio tree:**

- `runtime/repos/gaustudio/submodules/gaustudio-diff-gaussian-rasterization/LICENSE.md` limits use to research/evaluation and expressly prohibits commercial exploitation/distribution without the licensors' prior consent.
- `runtime/repos/gaustudio/gaustudio/pipelines/initializers/mesh.py` retains an Inria non-commercial research/evaluation header despite the repository's top-level MIT licence.

The current GLGMesh adaptation in `workers/gaustudio_support/` uses `metal_gauss` and Open3D CPU TSDF. Inspection found no import of the GauStudio package in that worker path. This supports removing the unused GauStudio checkout from a commercial package rather than seeking permission for its unused components. Do not zip all of `runtime/repos/` into the product. An alternative CUDA implementation would need a fresh review.

Other false positives avoided: the TRELLIS Apple port advertises BRIA RMBG-2.0, but GLGMesh sets `rembg_model=None` and uses U²-Net; no BRIA weights appear in its manifest. Hi3D imports marching-cubes tables from a directory named `sam3d_objects`, but that actual file carries Apache-2.0 and GLGMesh does not load SAM 3D model weights. Folder names alone do not establish model use.

## Pipeline release decisions

| Pipeline | Commercial release position |
| --- | --- |
| Prototype / `fast` | Hunyuan Mini and default Hunyuan Paint block an unrestricted EU/UK/South Korea offering. Removing texture alone does not remove the shape-model restriction. |
| Medium / `medium` | Hunyuan 2.1 has the same territorial issue even with MV-Adapter texture. |
| High / `high` | Strong candidate after notices and distribution compliance: TRELLIS MIT + DINOv3 custom terms; review GPL worker dependencies and Blender delivery. |
| Production V1 / `production` | Feasible with IDOL/DINOv3/VAE terms, Hi3D branding/scale conditions, SD2.1 conditions when texturing, and GPL handling. Its coarse mesh comes from IDOL, so the current path does not require Hunyuan model weights. |
| Production V2 / `production-textured` | Strong candidate after removing unused non-commercial GauStudio files, preserving IDOL/DINOv3/VAE notices and resolving GPL delivery. It does not use Hi3D or Hunyuan weights. |

These are licensing assessments, not confirmation that the Apple Silicon application already supports a production SaaS deployment.

## Concrete release actions

1. For an unrestricted worldwide offering, remove Hunyuan shape/paint routes or obtain written permission covering the intended operating regions, customer regions and outputs. Open-sourcing the app would not solve the territorial restriction.
2. Package an explicit allowlist of required files. Exclude unused GauStudio non-commercial sources, unrelated cloned model implementations, caches, runs and credentials.
3. Decide whether desktop workers will be GPL-compliant with source, or replace PyMeshLab and GPL `plyfile` where used. Preserve Blender's separate role and resolve redistribution of the exact Blender build and `bpy` workers. A proprietary SaaS backend has fewer GPL distribution obligations.
4. Add a complete third-party notice/licence bundle and required model terms. `workers/download.py` currently fetches enumerated weight/config files for 11 manifest entries without their licences/cards; Hi3D's wildcard includes them. `THIRD_PARTY.md` links alone are not a substitute for required copies and notices.
5. Add Hi3D branding if retained, and track its MAU/revenue thresholds. Incorporate applicable model use restrictions into customer terms. Archive the exact SD2.1 licence, FLUX VAE-specific grant and U²-Net ONNX provenance.
6. Verify the final installer/container contents, including native-wheel licences, before release. Keep an inventory tied to that exact build rather than relying on the development environment.

The reviewed commit's MIT code permits sale under that grant; existing MIT rights remain available. Current GLGMesh code offered under the replacement licence has separate commercial-software and attribution conditions. Neither licence relicenses third-party models or dependencies. Generated mesh rights, input artwork and model-use restrictions remain separate from the licence for the application code.
