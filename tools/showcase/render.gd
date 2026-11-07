extends SceneTree
# Usage: godot --path tools/showcase --script render.gd -- MANIFEST_JSON OUTPUT_DIR
# Manifest: concept {path} and models (three entries with path, label, detail, triangles, optional yaw).
var canvas: SubViewport
var pivots = []
const BG = Color("e5e2d9")
const FRAMES = 120
func _initialize(): call_deferred("run")
func label(text, x, y, size):
    var l = Label.new()
    l.text = text; l.position = Vector2(x, y); l.size.x = 400
    l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    l.add_theme_font_size_override("font_size", size)
    l.add_theme_color_override("font_color", Color("23352d"))
    canvas.add_child(l)
func run():
    var args = OS.get_cmdline_user_args()
    if args.size() != 2: push_error("Expected manifest and output directory"); quit(1); return
    var manifest = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
    var rows = manifest.models
    if not rows is Array or rows.size() != 3: quit(2); return
    var output = args[1]; DirAccess.make_dir_recursive_absolute(output)
    canvas = SubViewport.new(); canvas.size = Vector2i(1600, 560)
    canvas.render_target_update_mode = SubViewport.UPDATE_ALWAYS; root.add_child(canvas)
    var bg = ColorRect.new(); bg.size = Vector2(1600,560); bg.color = BG; canvas.add_child(bg)
    label("Concept art",0,28,23); label("Original reference",0,60,15)
    var concept_image = Image.load_from_file(manifest.concept.path)
    if concept_image == null: push_error("Cannot load concept image"); quit(6); return
    var concept = TextureRect.new(); concept.texture = ImageTexture.create_from_image(concept_image)
    concept.expand_mode = TextureRect.EXPAND_IGNORE_SIZE; concept.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    concept.position = Vector2(20,84); concept.size = Vector2(360,400); canvas.add_child(concept)
    label("Reference image",0,492,19)
    var report = []
    for i in range(3):
        var item = rows[i]
        var holder = SubViewportContainer.new(); holder.position = Vector2((i+1)*400,84); canvas.add_child(holder)
        var vp = SubViewport.new(); vp.size = Vector2i(400,400); vp.own_world_3d = true
        vp.msaa_3d = Viewport.MSAA_4X; vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS; holder.add_child(vp)
        var doc = GLTFDocument.new(); var state = GLTFState.new()
        if doc.append_from_file(item.path,state) != OK: quit(3); return
        var asset = doc.generate_scene(state); var pivot = Node3D.new(); vp.add_child(pivot); pivot.add_child(asset); pivots.append(pivot)
        var bounds = AABB(); var first = true; var tris = 0; var textures = 0
        for mesh in asset.find_children("*", "MeshInstance3D", true, false):
            mesh.lod_bias = 10000
            var box = mesh.global_transform * mesh.get_aabb()
            bounds = box if first else bounds.merge(box); first = false
            for s in range(mesh.mesh.get_surface_count()):
                tris += int(mesh.mesh.surface_get_array_index_len(s)/3)
                var mat = mesh.get_active_material(s)
                if mat is BaseMaterial3D and mat.albedo_texture != null:
                    textures += 1
                    var display = mat.duplicate(); display.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
                    mesh.set_surface_override_material(s, display)
        if tris != int(item.triangles) or textures == 0: push_error("Unexpected model contents"); quit(4); return
        var factor = 2.0/bounds.size.y
        asset.position = -bounds.get_center()*factor; asset.scale = Vector3.ONE*factor
        var env = Environment.new(); env.background_mode = Environment.BG_COLOR; env.background_color = BG
        var world = WorldEnvironment.new(); world.environment = env; vp.add_child(world)
        var cam = Camera3D.new(); cam.projection = Camera3D.PROJECTION_ORTHOGONAL; cam.size = 3.2
        cam.position = Vector3(0,.15,6); vp.add_child(cam); cam.look_at(Vector3.ZERO); cam.current = true
        label(item.label,(i+1)*400,28,23); label(item.detail,(i+1)*400,60,15)
        label(String.num_int64(tris)+" triangles",(i+1)*400,492,19)
        report.append({"label":item.label,"triangles":tris,"textured_surfaces":textures,"front_yaw":item.get("yaw",0)})
    label("MIRELING",600,527,13)
    for n in range(FRAMES):
        for i in range(3): pivots[i].rotation.y = float(rows[i].get("yaw",0))+TAU*n/FRAMES
        await process_frame; await process_frame; RenderingServer.force_draw()
        if canvas.get_texture().get_image().save_png(output.path_join("%04d.png" % n)) != OK: quit(5); return
        if n%30 == 0: print("Rendered ",n,"/",FRAMES)
    FileAccess.open(output.path_join("render-report.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
    quit()
