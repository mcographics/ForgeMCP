"""Assemble and render a separate review copy; leave export-space geometry intact."""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir',required=True)
OUT=Path(parser.parse_args(sys.argv[sys.argv.index('--')+1:]).source_dir)
manifest=json.loads((OUT/'manifest.json').read_text())
destination=OUT/'ReferenceCityRegions_v2_Layout.blend'
if destination.exists():
    raise FileExistsError('Preserve the previous regional layout')
for chunk in manifest['chunks']:
    obj=bpy.data.objects[chunk['name']]
    cx,cy=chunk['center']
    obj.location=((cx-627)*3,(627-cy)*3,0)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.48,.64,.8,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(0,0,3000))
sun=bpy.context.object
sun.rotation_euler=(.35,-.4,-.7)
sun.data.energy=3
sun.data.angle=.12
bpy.ops.object.camera_add(location=(0,-2700,5500))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=4400
camera.data.clip_end=30000
scene.camera=camera
scene.render.resolution_x=1254
scene.render.resolution_y=1254
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(OUT/'Nine_Region_City_Overview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
bpy.ops.render.render(write_still=True)
print('REGIONAL_LAYOUT_SAVED_AND_RENDERED',flush=True)
