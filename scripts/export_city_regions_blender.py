"""Create an independent, versioned Blender source and bridge for regional chunks."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path('G:/ForgeMCP')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir',required=True)
OUT=Path(parser.parse_args(sys.argv[sys.argv.index('--')+1:]).source_dir)
manifest=json.loads((OUT/'manifest.json').read_text())
if (OUT/'ReferenceCityRegions_v2.blend').exists():
    raise FileExistsError('Preserve the existing versioned regional source')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1.0
materials=[]
for name,color,roughness,metallic in manifest['palette']:
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    mat.use_backface_culling=True
    mat.diffuse_color=(*color,1)
    node=mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Roughness'].default_value=roughness
    node.inputs['Metallic'].default_value=metallic
    materials.append(mat)
collections={}
for region in manifest['regions']:
    collection=bpy.data.collections.new(f"Region_{region['id']:02}_{region['name']}")
    bpy.context.scene.collection.children.link(collection)
    collections[region['id']]=collection
report=[]
for entry in manifest['chunks']:
    data=json.loads((OUT/(entry['name']+'.json')).read_text())
    vertices,faces,slots=[],[],[]
    lookup={}
    for face,slot in zip(data['faces'],data['materials']):
        points=[]
        for index in face:
            point=data['vertices'][index]
            if not points or (Vector(point)-Vector(points[-1])).length>1e-6:
                points.append(point)
        if len(points)>2 and (Vector(points[0])-Vector(points[-1])).length<1e-6:
            points.pop()
        if len(points)<3:
            continue
        origin=Vector(points[0])
        surface=sum(((Vector(points[i])-origin).cross(Vector(points[i+1])-origin)).length
                    for i in range(1,len(points)-1))
        if surface<1e-7:
            continue
        ids=[]
        for point in points:
            key=tuple(round(x,6) for x in point)
            if key not in lookup:
                lookup[key]=len(vertices)
                vertices.append(point)
            ids.append(lookup[key])
        if len(set(ids))>=3:
            faces.append(ids)
            slots.append(slot)
    mesh=bpy.data.meshes.new(entry['name'])
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    assert 3<=len(mesh.vertices)<=100000
    used=sorted(set(slots))
    for slot in used:
        mesh.materials.append(materials[slot])
    remap={slot:index for index,slot in enumerate(used)}
    for face,slot in zip(mesh.polygons,slots):
        face.material_index=remap[slot]
    obj=bpy.data.objects.new(entry['name'],mesh)
    collections[entry['region']].objects.link(obj)
    # Local mesh geometry is intentional. Unreal placement uses manifest location_cm.
    obj['region_id']=entry['region']
    obj['reference_metres_per_pixel']=3.0
    obj['unreal_location_cm']=entry['location_cm']
    mesh.calc_loop_triangles()
    report.append({'name':obj.name,'region':entry['region'],'vertices':len(mesh.vertices),
                   'triangles':len(mesh.loop_triangles),'material_slots':len(used)})

# One inexpensive always-loaded background surface, independent of heavy city cells.
mesh=bpy.data.meshes.new('RC_Harbor_Background')
mesh.from_pydata([(-2300,-2300,-3),(2300,-2300,-3),(2300,2300,-3),(-2300,2300,-3)],[],[(0,1,2,3)])
mesh.materials.append(materials[6])
water=bpy.data.objects.new('RC_Harbor_Background',mesh)
bpy.context.scene.collection.objects.link(water)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ReferenceCityRegions_v2.blend'))
(OUT/'geometry_report.json').write_text(json.dumps(report,indent=2))
sys.path.insert(0,str(ROOT/'blender-addon'))
import majestic_forge  # noqa: E402

majestic_forge.register()
(OUT/'ready.json').write_text(json.dumps({'session_id':f'blender-{os.getpid()}',
                                         'chunks':len(report),'region_count':9}))
print('REGIONAL_CITY_READY',len(report),flush=True)
while not (OUT/'stop').exists():
    majestic_forge._bridge.tick()
    time.sleep(.02)
majestic_forge.unregister()
