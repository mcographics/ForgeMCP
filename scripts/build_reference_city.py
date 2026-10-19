"""Build a versioned city from the supplied October 16 line drawing in a fresh Blender.

Run only in a separate --background --factory-startup process. Coordinates below
are manually interpreted image pixels, not surveyed geometry or automatic tracing.
"""
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path('G:/ForgeMCP')
OUT = ROOT / 'Saved/ReferenceCity_20261016_v1'
OUT.mkdir(exist_ok=True)
if (OUT / 'ReferenceCity_v1.blend').exists():
    raise FileExistsError('Versioned city already exists; choose a new output version')
random.seed(161026)
SCALE = 3.0  # Assumed metres per image pixel; source is uncalibrated.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0

PALETTE = [
    ('Limestone', (.48, .43, .34), .82, 0),
    ('Concrete', (.32, .34, .34), .83, 0),
    ('Brick', (.29, .115, .065), .88, 0),
    ('Ivory', (.68, .65, .54), .76, 0),
    ('Roof', (.07, .085, .095), .8, 0),
    ('Glass', (.035, .085, .12), .23, .65),
    ('Road', (.045, .051, .057), .94, 0),
    ('Pavement', (.38, .39, .37), .92, 0),
    ('Park', (.09, .19, .065), .93, 0),
    ('Water', (.012, .09, .125), .2, .35),
    ('Steel', (.23, .27, .29), .38, .7),
    ('Marking', (.83, .76, .47), .7, 0),
]
MATS = []
for name, color, rough, metal in PALETTE:
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    MATS.append(m)


class Mesh:
    def __init__(self, name):
        self.name, self.v, self.f, self.mi = name, [], [], []

    def face(self, pts, mat):
        n = len(self.v)
        self.v.extend(pts)
        self.f.append(tuple(range(n, len(self.v))))
        self.mi.append(mat)

    def box(self, x, y, z, w, d, h, mat, angle=0):
        # x/y/w/d are image pixels; z/h are metres.
        c, s = math.cos(angle), math.sin(angle)
        pts = []
        for dz in (0, h):
            for dx, dy in ((-w/2, -d/2), (w/2, -d/2), (w/2, d/2), (-w/2, d/2)):
                pts.append(((x+dx*c-dy*s-957.5)*SCALE,
                            (410.5-y-dx*s-dy*c)*SCALE, z+dz))
        # Mirroring image Y requires this winding.
        n = len(self.v)
        self.v.extend(pts)
        self.f.extend(tuple(n+i for i in f) for f in (
            (0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
            (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)))
        self.mi.extend([mat]*6)

    def line(self, a, b, width, z, height, mat):
        dx, dy = b[0]-a[0], b[1]-a[1]
        if math.hypot(dx, dy) < .001:
            return
        self.box((a[0]+b[0])/2, (a[1]+b[1])/2, z,
                 math.hypot(dx, dy)+.05, width, height, mat, math.atan2(dy, dx))

    def polygon(self, poly, z, mat):
        vs = [Vector(((x-957.5)*SCALE, (410.5-y)*SCALE, z)) for x, y in poly]
        for tri in tessellate_polygon([vs]):
            p = [vs[v] if isinstance(v, int) else v for v in tri]
            if (p[1]-p[0]).cross(p[2]-p[0]).z < 0:
                p.reverse()
            self.face([tuple(v) for v in p], mat)

    def finish(self):
        if not self.v:
            return None
        if len(self.v) > 90000:
            objects = []
            for start in range(0, len(self.f), 18000):
                part = Mesh(self.name + '_Part' + str(start // 18000 + 1))
                for face, mat in zip(self.f[start:start+18000], self.mi[start:start+18000]):
                    part.face([self.v[i] for i in face], mat)
                objects.extend(part.finish())
            return objects
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.v, [], self.f)
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        for m in MATS:
            mesh.materials.append(m)
        for face, mat in zip(mesh.polygons, self.mi):
            face.material_index = mat
        # Remove unused slots so the transfer contract accurately describes materials.
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.material_slot_remove_unused()
        obj.select_set(False)
        obj['reference'] = 'User-supplied city line drawing, October 16 2026'
        obj['accuracy'] = 'Manual interpretation; 3m/pixel assumed, unsurveyed'
        return [obj]


def inside(x, y, p):
    hit = False
    j = len(p)-1
    for i in range(len(p)):
        a, b = p[i], p[j]
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
        j = i
    return hit


def edge_distance(x, y, poly):
    best = 1e9
    for a, b in zip(poly, poly[1:]+poly[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        t = max(0, min(1, ((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
        best = min(best, math.hypot(x-a[0]-t*dx, y-a[1]-t*dy))
    return best


# Shorelines interpreted from the visible frame, including cropped mainland edges.
DISTRICTS = [
    ('CentralIsland', [(267,278),(323,207),(415,166),(507,180),(636,219),(784,257),(936,306),(1106,365),(1277,440),(1216,493),(1102,531),(967,575),(913,608),(797,572),(660,512),(520,446),(389,365)], 22, 23),
    ('NorthEastIsland', [(928,151),(978,107),(1114,50),(1247,32),(1392,50),(1512,116),(1576,183),(1508,252),(1410,278),(1244,248),(1120,217),(1016,183)], 24, 24),
    ('WestMainland', [(-90,80),(2,61),(83,211),(148,330),(218,450),(300,523),(382,606),(402,659),(290,705),(113,769),(-40,823)], 24, 26),
    ('SouthMainland', [(-10,820),(167,753),(394,674),(542,675),(671,654),(820,674),(1012,716),(1179,765),(1292,850)], 26, 25),
    ('SouthEastDistrict', [(1448,620),(1480,579),(1467,540),(1574,470),(1672,427),(1818,451),(1955,523),(1960,850),(1743,850),(1665,763),(1570,708)], 25, 24),
    ('EastMainland', [(1740,154),(1783,101),(1819,51),(1955,52),(1955,454),(1854,452),(1774,415),(1742,361),(1738,280),(1781,217)], 25, 24),
    ('NorthWestIsland', [(114,99),(183,75),(276,81),(362,105),(390,124),(315,151),(228,161),(150,137)], 22, 21),
    ('NorthSmallIsland', [(539,85),(569,68),(633,85),(698,116),(752,147),(728,176),(643,159),(582,131)], 22, 20),
    ('NorthCropped', [(584,-15),(1011,-15),(980,43),(920,86),(865,111),(756,68),(671,39)], 23, 22),
    ('SouthPierDistrict', [(1150,736),(1204,686),(1251,649),(1306,677),(1379,737),(1436,801),(1433,850),(1304,850)], 23, 23),
]
LANDMARKS = [(513,336,100),(456,292,0),(744,287,145),(785,318,120),
             (833,419,0),(754,493,0),(1227,163,0),(558,212,95),(617,240,90)]
land = Mesh('RC_LandAndQuays')
roads = Mesh('RC_StreetsAndMarkings')
piers = Mesh('RC_WaterfrontPiers')
parks = Mesh('RC_ParksAndLandmarks')
stats = {'buildings': 0, 'districts': len(DISTRICTS), 'bridges': 0,
         'assumed_metres_per_pixel': SCALE, 'survey_accuracy': False,
         'source_image_dimensions': [1915, 821], 'objects': []}

for name, poly, sx, sy in DISTRICTS:
    land.polygon(poly, 4.0, 7)
    lo_x, hi_x = min(p[0] for p in poly), max(p[0] for p in poly)
    lo_y, hi_y = min(p[1] for p in poly), max(p[1] for p in poly)
    # Shore wall and continuous coastal boulevard.
    for a, b in zip(poly, poly[1:]+poly[:1]):
        land.line(a, b, 2.0, -3, 7, 1)
        roads.line(a, b, 4, 4.12, .16, 6)
        length = math.dist(a,b)
        for k in range(1, int(length/24)):
            t = k*24/length
            x, y = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t
            dx, dy = b[0]-a[0], b[1]-a[1]
            nx, ny = -dy/length, dx/length
            if inside(x+nx*4,y+ny*4,poly):
                nx, ny = -nx,-ny
            end = (x+nx*random.uniform(10,17), y+ny*random.uniform(10,17))
            piers.line((x,y),end,3,2,1.6,7)
    bodies, windows = Mesh('RC_'+name), Mesh('RC_'+name+'_Glazing')
    # Dense blocks: the reference's internal streets are predominantly image-axis aligned.
    for ix in range(math.floor(lo_x/sx), math.ceil(hi_x/sx)):
        for iy in range(math.floor(lo_y/sy), math.ceil(hi_y/sy)):
            x,y = (ix+.5)*sx, (iy+.5)*sy
            corners = [(x+dx,y+dy) for dx in (-sx*.45,sx*.45) for dy in (-sy*.45,sy*.45)]
            if not all(inside(a,b,poly) for a,b in corners):
                continue
            if edge_distance(x,y,poly)<13:
                continue
            # Only lay road segments inside the island to preserve the water channels.
            roads.line((x-sx/2,y-sy/2),(x+sx/2,y-sy/2),3.1,4.2,.12,6)
            roads.line((x-sx/2,y-sy/2),(x-sx/2,y+sy/2),3.1,4.2,.12,6)
            if any(math.hypot(x-lx,y-ly)<21 for lx,ly,_ in LANDMARKS):
                parks.box(x,y,4.12,sx*.77,sy*.77,.2,8)
                continue
            if random.random()<.055:
                parks.box(x,y,4.12,sx*.75,sy*.75,.2,8)
                for _ in range(4):
                    tx,ty=x+random.uniform(-6,6),y+random.uniform(-6,6)
                    parks.box(tx,ty,4.3,.6,.6,4,2)
                    parks.box(tx,ty,7,2.8,2.8,5,8)
                continue
            for dx in (-.205,.205):
                for dy in (-.205,.205):
                    bx,by=x+dx*sx,y+dy*sy
                    w,d=sx*random.uniform(.29,.36),sy*random.uniform(.27,.35)
                    downtown = name=='CentralIsland' and 620<x<960
                    h=random.uniform(14,34) if not downtown else random.uniform(35,100)
                    if name=='CentralIsland' and x<570:
                        h=random.uniform(15,43)
                    mat=random.randrange(4)
                    bodies.box(bx,by,4.4,w,d,h,mat)
                    bodies.box(bx,by,4.4+h,w*.94,d*.94,.7,4)
                    if h>45:
                        bodies.box(bx,by,5.1+h,w*.6,d*.6,h*.16,mat)
                    # Recessed-looking dark facade bands with stone corners.
                    for floor in range(1,min(5,int(h/5))):
                        z=5+floor*(h-4)/min(5,int(h/5))
                        for side in (-1,1):
                            windows.box(bx,by+side*d*.501,z,w*.84,.06,1.7,5)
                            windows.box(bx+side*w*.501,by,z,.06,d*.84,1.7,5)
                    if random.random()<.35:
                        bodies.box(bx,by,h+5.2,w*.22,d*.28,1.8,1)
                    stats['buildings']+=1
    for m in (bodies,windows):
        o=m.finish()
        if o:
            stats['objects'].extend(obj.name for obj in o)

# Iconic circular plazas, the slender spire, and central towers visible in the reference.
for x,y,h in LANDMARKS:
    if h==0:
        parks.box(x,y,4.4,19,19,.4,3)
        parks.box(x,y,4.9,14,14,.15,8)
    else:
        parks.box(x,y,4.4,10,10,7,3)
        parks.box(x,y,11.4,6,6,h*.7,0)
        parks.box(x,y,11.4+h*.7,3,3,h*.2,3)
        parks.box(x,y,11.4+h*.9,.7,.7,h*.22,10)

bridges=Mesh('RC_BridgesAndHighways')


def road_path(points,width=5,z=5):
    for a,b in zip(points,points[1:]):
        bridges.line(a,b,width,z,1.5,6)
        for side in (-1,1):
            dx,dy=b[0]-a[0],b[1]-a[1]
            le=math.hypot(dx,dy)
            nx,ny=-dy/le,dx/le
            aa=(a[0]+nx*width*.48*side,a[1]+ny*width*.48*side)
            bb=(b[0]+nx*width*.48*side,b[1]+ny*width*.48*side)
            bridges.line(aa,bb,.22,z+1.5,1,7)
        le=math.dist(a,b)
        for k in range(int(le/9)):
            t=(k+.2)*9/le
            u=min(1,t+3/le)
            bridges.line((a[0]+dx*t,a[1]+dy*t),(a[0]+dx*u,a[1]+dy*u),.16,z+1.52,.04,11)


# Expressways follow the drawing's diagonal approaches and southern interchange.
road_path([(-40,805),(227,713),(401,670),(624,671),(833,696),(1000,739),(1221,814)],7,13)
road_path([(5,85),(114,280),(217,463),(355,643),(489,840)],6,15)
road_path([(588,835),(702,734),(826,639),(970,556),(1089,516),(1205,466)],7,19)
road_path([(321,590),(396,654),(454,696),(496,770)],4,14)
road_path([(646,667),(718,684),(792,725),(840,790)],4,14)


def bridge(a,b,width=6):
    stats['bridges']+=1
    road_path([a,b],width,25)
    dx,dy=b[0]-a[0],b[1]-a[1]
    le=math.hypot(dx,dy)
    nx,ny=-dy/le,dx/le
    towers=[.27,.73]
    for t in towers:
        x,y=a[0]+dx*t,a[1]+dy*t
        for side in (-1,1):
            px,py=x+nx*width*.7*side,y+ny*width*.7*side
            bridges.box(px,py,-4,2.2,2.2,91,1)
        bridges.line((x-nx*width,y-ny*width),(x+nx*width,y+ny*width),1,77,3,1)
    # Suspension cables and hangers are real geometry, distinct from the deck.
    for side in (-1,1):
        previous=None
        for k in range(61):
            t=k/60
            x,y=a[0]+dx*t+nx*width*.55*side,a[1]+dy*t+ny*width*.55*side
            # Two peaks at tower positions with sag between them.
            z=35+48*max(math.exp(-((t-.27)/.16)**2),math.exp(-((t-.73)/.16)**2))
            current=Vector(((x-957.5)*SCALE,(410.5-y)*SCALE,z))
            if previous is not None:
                # Cable as a narrow box along XY, stepped height; adequate at city scale.
                delta=current-previous
                # General oriented cylinder mesh.
                direction=delta.normalized()
                cross=direction.cross(Vector((0,0,1))).normalized()*.35
                up=direction.cross(cross).normalized()*.35
                pts=[tuple(v+q) for v in (previous,current) for q in (cross+up,-cross+up,-cross-up,cross-up)]
                n=len(bridges.v)
                bridges.v.extend(pts)
                for f in ((0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                    bridges.f.append(tuple(n+i for i in f))
                    bridges.mi.append(10)
            if k%3==0:
                bridges.box(x,y,27,.12,.12,max(.1,z-27),10)
            previous=current


bridge((1098,525),(1730,750),6)
bridge((1415,276),(1854,448),6)
bridge((1553,189),(1818,193),5)
bridge((1315,51),(1315,-45),5)
water=Mesh('RC_HarborWater')
water.box(957.5,410.5,-4,2200,1100,1,9)
# Small ships in the channels shown in the drawing.
ships=Mesh('RC_HarborVessels')
for x,y,angle in [(409,477,.7),(576,538,.4),(1354,511,-.7),(1471,419,-.7),(1021,274,.3),(309,377,.7),(1682,240,-.8)]:
    ships.box(x,y,-1.6,13,3.2,2.5,3,angle)
    ships.box(x,y,1,7,2.6,2.4,1,angle)

for m in (land,roads,piers,parks,bridges,water,ships):
    o=m.finish()
    if o:
        stats['objects'].extend(obj.name for obj in o)

scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.world.color=(.4,.4,.4)
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.46,.62,.8,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(0,0,2000))
sun=bpy.context.object
sun.name='ReferenceCity_Sun'
sun.rotation_euler=(.45,-.35,-.6)
sun.data.energy=3
sun.data.angle=.12
bpy.ops.object.camera_add(location=(0,-3800,5300))
cam=bpy.context.object
cam.name='ReferenceCity_Overview'
cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO'
cam.data.ortho_scale=6500
cam.data.clip_end=30000
scene.camera=cam
scene.render.resolution_x=1915
scene.render.resolution_y=1050
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(OUT/'ReferenceCity_Overview.png')
scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ReferenceCity_v1.blend'))
(OUT/'manifest.json').write_text(json.dumps(stats,indent=2))
bpy.ops.render.render(write_still=True)
# Keep this isolated scene available through the existing authenticated Blender adapter.
sys.path.insert(0,str(ROOT/'blender-addon'))
import majestic_forge  # noqa: E402

majestic_forge.register()
(OUT/'ready.json').write_text(json.dumps({'session_id':f'blender-{__import__("os").getpid()}',**stats},indent=2))
print('REFERENCE_CITY_READY',flush=True)
while not (OUT/'stop').exists():
    majestic_forge._bridge.tick()
    time.sleep(.02)
majestic_forge.unregister()
