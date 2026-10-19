"""Reload the saved city in a separate Blender process, inspect and render a closer view."""
import json
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path('G:/ForgeMCP/Saved/ReferenceCity_20261016_v1')
scene = bpy.context.scene
manifest = json.loads((OUT / 'manifest.json').read_text())
meshes = {obj.name: obj for obj in scene.objects if obj.type == 'MESH'}
assert set(meshes) == set(manifest['objects'])
report = {'saved_blend_reloaded': True, 'mesh_count': len(meshes), 'meshes': []}
for obj in meshes.values():
    obj.data.calc_loop_triangles()
    assert len(obj.data.vertices) <= 100000
    assert all(slot.material is not None for slot in obj.material_slots)
    report['meshes'].append({'name': obj.name, 'vertices': len(obj.data.vertices),
                             'triangles': len(obj.data.loop_triangles),
                             'materials': len(obj.material_slots)})
(OUT / 'blender_reload_verification.json').write_text(json.dumps(report, indent=2))
camera = scene.camera
camera.location = (400, -2400, 1850)
camera.rotation_euler = (Vector((-250, 0, 30)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'PERSP'
camera.data.lens = 34
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.filepath = str(OUT / 'ReferenceCity_Central_View.png')
bpy.ops.render.render(write_still=True)
print('CITY_RELOAD_AND_RENDER_VERIFIED', len(meshes), flush=True)
