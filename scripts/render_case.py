"""Render the case (and optionally the PCB) with Blender.

    kicad-cli pcb export glb --subst-models -o /tmp/eugeo-pcb.glb eugeo.kicad_pcb
    Blender -b -P scripts/render_case.py -- case/eugeo-case.stl /tmp/eugeo-pcb.glb out.png asm iso [case/eugeo-cover.stl]
(mode: case | asm, view: iso | hero | top | profile | back34 | badge | bottom; extra STLs as path[:acrylic|plate|keycap])
"""
import bpy, sys, math, mathutils
argv = sys.argv[sys.argv.index("--") + 1:]
stl, glb, out, mode = argv[0], argv[1], argv[2], argv[3]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.wm.stl_import(filepath=stl)
case = bpy.context.selected_objects[0]
mat = bpy.data.materials.new("resin"); mat.use_nodes = True
b = [n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]; b.inputs["Base Color"].default_value = (0.82, 0.83, 0.86, 1); b.inputs["Roughness"].default_value = 0.45
case.data.materials.append(mat)
if mode != "case":
    bpy.ops.import_scene.gltf(filepath=glb)
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    root = [o for o in bpy.context.selected_objects if o.parent is None]
    for r in root: r.scale = (1000, 1000, 1000)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    # board = the largest object in XY
    def area(o):
        bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
        xs = [p.x for p in bb]; ys = [p.y for p in bb]; zs = [p.z for p in bb]
        return (max(xs)-min(xs))*(max(ys)-min(ys)), bb
    board = max(objs, key=lambda o: area(o)[0])
    bb = area(board)[1]
    cx = (max(p.x for p in bb)+min(p.x for p in bb))/2; cy = (max(p.y for p in bb)+min(p.y for p in bb))/2
    zmin = min(p.z for p in bb); zmax = max(p.z for p in bb)
    print("board", board.name, max(p.x for p in bb)-min(p.x for p in bb), max(p.y for p in bb)-min(p.y for p in bb), zmax-zmin)
    for r in root:
        r.location.x -= cx; r.location.y -= cy; r.location.z -= zmin
MATERIALS = {   # name: (base colour, roughness, alpha)
    "acrylic": ((0.9, 0.95, 1.0, 1), 0.05, 0.35),
    "plate": ((0.06, 0.06, 0.07, 1), 0.5, 1.0),
    "keycap": ((0.93, 0.92, 0.89, 1), 0.6, 1.0),
    "switch": ((0.2, 0.2, 0.22, 1), 0.4, 1.0),
}
for extra in argv[5:]:
    path, _, kind = extra.partition(":")
    bpy.ops.wm.stl_import(filepath=path)
    o = bpy.context.selected_objects[0]
    color, rough, alpha = MATERIALS[kind or "acrylic"]
    m = bpy.data.materials.new(kind or "acrylic"); m.use_nodes = True
    bs = [n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
    bs.inputs["Base Color"].default_value = color
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Alpha"].default_value = alpha
    if alpha < 1 and hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    o.data.materials.append(m)
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
[n for n in world.node_tree.nodes if n.type == "BACKGROUND"][0].inputs[0].default_value = (0.93, 0.94, 0.96, 1)
[n for n in world.node_tree.nodes if n.type == "BACKGROUND"][0].inputs[1].default_value = 0.8
for loc, e in (((200, -300, 400), 3.0), ((-300, 200, 300), 1.5)):
    l = bpy.data.lights.new("sun", "SUN"); l.energy = e
    o = bpy.data.objects.new("sun", l); sc.collection.objects.link(o)
    o.rotation_euler = (mathutils.Vector(loc)).to_track_quat('Z', 'Y').to_euler()
cam = bpy.data.cameras.new("cam"); cam.type = "ORTHO"; cam.ortho_scale = 330; cam.clip_end = 5000
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co
views = {"iso": ((-260, -420, 330), 330), "front": ((0, -800, 120), 320), "top": ((0, 0, 900), 320), "side": ((900, 0, 0), 120), "back": ((60, 700, 160), 330), "bottom": ((0.01, -120, -700), 330)}
views["badge"] = ((-100, 400, 60), 75, (-100, 46.7, -1.6))
views["hero"] = ((-300, -460, 300), 345, (0, 0, 0))
views["profile"] = ((900, 0, 0), 110, (0, 0, -2))
views["top"] = ((0.01, 0, 900), 320, (0, 0, 0))
views["back34"] = ((-420, 520, 260), 190, (-40, 30, -5))
v = views[argv[4] if len(argv) > 4 else "iso"]
pos, scale = v[0], v[1]
target = mathutils.Vector(v[2] if len(v) > 2 else (0, 0, 0))
co.location = pos; cam.ortho_scale = scale
co.rotation_euler = (target - mathutils.Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1800, 900
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
