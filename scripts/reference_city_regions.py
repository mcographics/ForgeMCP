"""Deterministic, bounded city geometry for the user's numbered 3x3 reference.

Coordinates are manually interpreted image pixels, not a surveyed reconstruction.
Region IDs follow image rows (1,2,3 / 4,5,6 / 7,8,9). Geometry uses metres.
"""
import argparse
import json
import math
import random
from pathlib import Path

IMAGE = 1254.0
REGION = IMAGE / 3
METRES_PER_PIXEL = 3.0
CHUNK_METRES = 512.0
CHUNK_PIXELS = CHUNK_METRES / METRES_PER_PIXEL
CHUNKS_PER_REGION = math.ceil(REGION / CHUNK_PIXELS)
NAMES = ['Northwest_Islands', 'Northern_Districts', 'Northeast_District',
         'Western_Mainland', 'Central_Island', 'Eastern_Crossings',
         'Southwest_Interchange', 'Southern_Grid', 'Southeast_Waterfront']
PALETTE = [
    ('Stone', [.47, .43, .35], .83, 0.0),
    ('Roof', [.085, .095, .105], .85, 0.0),
    ('Glass', [.035, .085, .12], .25, .5),
    ('Asphalt', [.045, .05, .055], .95, 0.0),
    ('Quay', [.36, .37, .34], .93, 0.0),
    ('Vegetation', [.09, .19, .065], .95, 0.0),
    ('Harbor', [.012, .09, .125], .24, .2),
    ('Steel', [.24, .28, .30], .45, .6),
    ('Markings', [.80, .77, .61], .8, 0.0),
]

DISTRICTS = [
    ('Central', [(236,408),(290,350),(380,302),(447,319),(547,355),(655,400),
                 (765,455),(858,514),(925,567),(955,620),(919,659),(850,706),
                 (787,758),(710,805),(636,833),(552,790),(468,739),(391,675),
                 (325,609),(271,530)]),
    ('Northeast', [(691,264),(706,218),(761,174),(816,143),(896,168),(975,202),
                   (1044,246),(1083,282),(1052,315),(996,339),(922,340),
                   (846,328),(772,304)]),
    ('North', [(444,0),(822,0),(799,55),(780,108),(720,157),(663,169),
               (579,139),(500,98),(431,85)]),
    ('NorthEastMainland', [(936,0),(1254,0),(1254,414),(1169,376),(1138,307),
                           (1156,229),(1221,143),(1254,52),(1088,57),(1017,40)]),
    ('West', [(0,82),(37,160),(86,267),(139,380),(182,476),(231,579),
              (281,675),(327,753),(378,797),(429,846),(481,903),(486,970),
              (432,1057),(350,1140),(223,1213),(164,1254),(0,1254)]),
    ('South', [(164,1254),(223,1213),(350,1140),(432,1057),(486,970),(481,903),
               (548,857),(683,901),(802,957),(884,1021),(954,1123),
               (1000,1224),(1000,1254)]),
    ('EastMiddle', [(1080,478),(1153,443),(1248,457),(1254,758),(1132,793),
                    (1087,765),(1044,704),(1006,652),(1006,593),(1042,531)]),
    ('EastSouth', [(1132,793),(1254,758),(1254,1254),(1025,1254),(1049,1176),
                   (1043,1100),(971,1035),(929,997),(916,962),(957,899),(1030,843)]),
    ('NorthwestPark', [(76,104),(105,68),(205,33),(288,30),(352,55),(327,91),
                       (252,128),(149,147)]),
    ('NorthwestIsland', [(100,189),(162,164),(248,169),(328,199),(366,227),
                         (322,253),(228,270),(145,244)]),
    ('NorthSmallIsland', [(433,171),(453,149),(523,176),(598,211),(632,248),
                          (599,274),(535,260),(466,220)]),
]
LANDMARKS = [(441,494,0),(481,550,135),(601,513,150),(637,556,125),
             (672,622,0),(583,711,0),(916,261,0),(430,323,90),(515,360,83)]
HIGHWAYS = [([(0,1088),(154,1014),(292,925),(420,882),(546,860),(690,905),
              (804,959),(906,1051),(1030,1214)], 5.5, 13),
            ([(0,124),(88,307),(183,496),(290,700),(380,832),(482,951),(565,1254)],5.2,16),
            ([(182,1254),(365,1159),(497,1051),(619,931),(728,818),(840,742),
              (922,640)],5.5,19),
            ([(85,106),(124,76),(220,45),(285,47),(331,64),(296,87),
              (230,110),(162,127),(97,116),(85,106)],3,5),
            ([(0,125),(125,103),(245,72),(350,40)],3.5,7),
            ([(152,138),(184,95),(233,64),(277,34),(299,0)],3,8)]
BRIDGES = [((825,695),(1254,931)), ((965,375),(1224,476)),
           ((1070,278),(1245,286)), ((829,153),(829,0))]


def region_bounds(region):
    row, col = divmod(region - 1, 3)
    return col*REGION, row*REGION, (col+1)*REGION, (row+1)*REGION


def region_for(x, y):
    if not (0 <= x <= IMAGE and 0 <= y <= IMAGE):
        return None
    return min(2, int(y/REGION))*3 + min(2, int(x/REGION)) + 1


def unreal_position(x, y, z=0):
    return [(y-IMAGE/2)*METRES_PER_PIXEL*100,
            (IMAGE/2-x)*METRES_PER_PIXEL*100, z*100]


def road_clearance(x,y):
    """Keep building footprints out of measured/proposed major-road corridors."""
    minimum=math.inf
    for path,width,_ in HIGHWAYS:
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
            minimum=min(minimum,math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)-width/2)
    return minimum


def inside(x, y, poly):
    hit = False
    for a, b in zip(poly, poly[1:]+poly[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def triangulate(poly):
    p = list(poly if area(poly)>0 else reversed(poly))
    triangles = []
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def in_tri(q,a,b,c):
        return min(cross(a,b,q),cross(b,c,q),cross(c,a,q)) >= -1e-8
    while len(p)>3:
        for i,b in enumerate(p):
            a,c=p[i-1],p[(i+1)%len(p)]
            if cross(a,b,c)>1e-8 and not any(in_tri(q,a,b,c) for j,q in enumerate(p)
                                                  if j not in ((i-1)%len(p),i,(i+1)%len(p))):
                triangles.append([a,b,c])
                p.pop(i)
                break
        else:
            raise ValueError('Invalid or degenerate shoreline polygon')
    triangles.append(p)
    return triangles


def clip_rect(poly, bounds):
    out = list(poly)
    for axis, edge, sign in ((0,bounds[0],1),(0,bounds[2],-1),
                              (1,bounds[1],1),(1,bounds[3],-1)):
        source,out=out,[]
        if not source:
            break
        for a,b in zip(source,source[1:]+source[:1]):
            ia,ib=(a[axis]-edge)*sign>=-1e-8,(b[axis]-edge)*sign>=-1e-8
            if ia:
                out.append(a)
            if ia != ib:
                t=(edge-a[axis])/(b[axis]-a[axis])
                out.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
    return out


class City:
    def __init__(self):
        self.chunks={}
        self.buildings=0
        self.rng=random.Random(16102602)

    def chunk(self,x,y):
        region=region_for(x,y)
        if region is None:
            return None
        x0,y0,x1,y1=region_bounds(region)
        col=min(CHUNKS_PER_REGION-1,int((x-x0)/CHUNK_PIXELS))
        row=min(CHUNKS_PER_REGION-1,int((y-y0)/CHUNK_PIXELS))
        key=(region,col,row)
        if key not in self.chunks:
            bounds=[x0+col*CHUNK_PIXELS,y0+row*CHUNK_PIXELS,
                    min(x1,x0+(col+1)*CHUNK_PIXELS),min(y1,y0+(row+1)*CHUNK_PIXELS)]
            center=[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2]
            self.chunks[key]={'name':f'RC_R{region:02}_C{col:02}_{row:02}',
                              'region':region,'pixel_bounds':bounds,'center':center,
                              'location_cm':unreal_position(*center),'vertices':[],
                              'faces':[],'materials':[]}
        return self.chunks[key]

    def face(self,chunk,points,material):
        cx,cy=chunk['center']
        n=len(chunk['vertices'])
        chunk['vertices'].extend([[(x-cx)*METRES_PER_PIXEL,(cy-y)*METRES_PER_PIXEL,z]
                                  for x,y,z in points])
        chunk['faces'].append(list(range(n,n+len(points))))
        chunk['materials'].append(material)

    def box(self,x,y,z,w,d,h,mat,angle=0,chunk=None):
        chunk=chunk if chunk is not None else self.chunk(x,y)
        if chunk is None:
            return
        c,s=math.cos(angle),math.sin(angle)
        points=[(x+dx*c-dy*s,y+dx*s+dy*c,z+dz) for dz in (0,h)
                for dx,dy in ((-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2))]
        for indices in ((0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)):
            self.face(chunk,[points[i] for i in indices],mat)

    def line(self,a,b,width,z,h,mat):
        length=math.dist(a,b)
        if length < .001:
            return
        count=max(1,math.ceil(length/16))  # <=48m segments, no city-wide mesh bounds.
        for i in range(count):
            t=(i+.5)/count
            self.box(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z,
                     length/count+.04,width,h,mat,math.atan2(b[1]-a[1],b[0]-a[0]))

    def ground(self,poly,material=4):
        triangles=triangulate(poly)
        for region in range(1,10):
            rx0,ry0,rx1,ry1=region_bounds(region)
            for col in range(CHUNKS_PER_REGION):
                for row in range(CHUNKS_PER_REGION):
                    bounds=[rx0+col*CHUNK_PIXELS,ry0+row*CHUNK_PIXELS,
                            min(rx1,rx0+(col+1)*CHUNK_PIXELS),
                            min(ry1,ry0+(row+1)*CHUNK_PIXELS)]
                    for triangle in triangles:
                        p=clip_rect(triangle,bounds)
                        if len(p)<3 or abs(area(p))<1e-7:
                            continue
                        ch=self.chunk((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2)
                        self.face(ch,[(x,y,4) for x,y in reversed(p)],material)

    def build(self):
        r=self.rng
        for name,poly in DISTRICTS:
            self.ground(poly,5 if name=='NorthwestPark' else 4)
            for a,b in zip(poly,poly[1:]+poly[:1]):
                self.line(a,b,1,-3,7,4)
                self.line(a,b,3,4.1,.15,3)
                le=math.dist(a,b)
                nx,ny=-(b[1]-a[1])/le,(b[0]-a[0])/le
                for k in range(1,int(le/20)):
                    t=k*20/le
                    x,y=a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t
                    if inside(x+nx*3,y+ny*3,poly):
                        nx,ny=-nx,-ny
                    self.line((x,y),(x+nx*10,y+ny*10),2.5,2,1.7,4)
            if name=='NorthwestPark':
                continue
            for ix in range(int(min(p[0] for p in poly)/21),math.ceil(max(p[0] for p in poly)/21)):
                for iy in range(int(min(p[1] for p in poly)/22),math.ceil(max(p[1] for p in poly)/22)):
                    x,y=(ix+.5)*21,(iy+.5)*22
                    if not all(inside(x+dx,y+dy,poly) for dx in (-10,10) for dy in (-10,10)):
                        continue
                    self.line((x-10.5,y-11),(x+10.5,y-11),2.6,4.2,.12,3)
                    self.line((x-10.5,y-11),(x-10.5,y+11),2.6,4.2,.12,3)
                    if any(math.hypot(x-lx,y-ly)<18 for lx,ly,_ in LANDMARKS) or r.random()<.07:
                        self.box(x,y,4.2,16,17,.2,5)
                        continue
                    for dx in (-4.3,4.3):
                        for dy in (-4.5,4.5):
                            bx,by=x+dx,y+dy
                            if road_clearance(bx,by)<6:
                                continue
                            ch=self.chunk(bx,by)
                            if ch is None:
                                continue
                            h=r.uniform(12,31)
                            if name=='Central' and 530<x<765:
                                h=r.uniform(32,100)
                            w,d=r.uniform(5.7,7.1),r.uniform(6.1,7.4)
                            self.box(bx,by,4.4,w,d,h,0,chunk=ch)
                            self.box(bx,by,h+4.4,w*.94,d*.94,.8,1,chunk=ch)
                            for floor in (h*.33,h*.66):
                                for side in (-1,1):
                                    self.box(bx,by+side*d*.501,5+floor,w*.83,.05,1.8,2,chunk=ch)
                                    self.box(bx+side*w*.501,by,5+floor,.05,d*.83,1.8,2,chunk=ch)
                            if h>50:
                                self.box(bx,by,h+5.2,w*.5,d*.5,h*.12,0,chunk=ch)
                            self.buildings+=1
        for x,y,h in LANDMARKS:
            if h:
                self.box(x,y,4.4,9,9,7,0)
                self.box(x,y,11.4,5,5,h*.72,0)
                self.box(x,y,11.4+h*.72,2,2,h*.18,7)
                self.box(x,y,11.4+h*.9,.5,.5,h*.23,7)
            else:
                self.box(x,y,4.3,19,19,.5,4)
                self.box(x,y,4.8,13,13,.2,5)
        for points,width,z in HIGHWAYS:
            for a,b in zip(points,points[1:]):
                self.line(a,b,width,z,1.4,3)
        for a,b in BRIDGES:
            self.line(a,b,5.5,25,1.6,3)
            dx,dy=b[0]-a[0],b[1]-a[1]
            le=math.hypot(dx,dy)
            nx,ny=-dy/le,dx/le
            for t in (.27,.73):
                x,y=a[0]+dx*t,a[1]+dy*t
                for side in (-1,1):
                    self.box(x+nx*3.5*side,y+ny*3.5*side,-3,1.8,1.8,82,4)
                self.line((x-nx*4,y-ny*4),(x+nx*4,y+ny*4),1,70,3,4)
            for side in (-1,1):
                for i in range(40):
                    t=(i+.5)/40
                    x,y=a[0]+dx*t+nx*3*side,a[1]+dy*t+ny*3*side
                    z=33+42*max(math.exp(-((t-.27)/.16)**2),math.exp(-((t-.73)/.16)**2))
                    self.box(x,y,27,.10,.10,z-27,7)
                    self.box(x,y,z,le/40+.02,.14,.35,7,math.atan2(dy,dx))
        return self

    def save(self,path):
        path=Path(path)
        path.mkdir(exist_ok=False,parents=True)
        chunks=[]
        for key,ch in sorted(self.chunks.items()):
            if not ch['faces']:
                continue
            assert len(ch['vertices'])<=100000, ch['name']
            (path/(ch['name']+'.json')).write_text(json.dumps(ch,separators=(',',':')))
            chunks.append({k:v for k,v in ch.items() if k not in ('vertices','faces','materials')}
                          | {'vertices':len(ch['vertices']),'triangles':sum(len(f)-2 for f in ch['faces'])})
        regions=[]
        for region in range(1,10):
            b=region_bounds(region)
            regions.append({'id':region,'name':NAMES[region-1],'pixel_bounds':b,
                            'center_cm':unreal_position((b[0]+b[2])/2,(b[1]+b[3])/2),
                            'extent_cm':[REGION*METRES_PER_PIXEL*50]*2+[50000],
                            'chunks':[c['name'] for c in chunks if c['region']==region]})
        manifest={'version':2,'reference':'User numbered 3x3 city reference, October 16 2026',
                  'image_pixels':[1254,1254],'metres_per_pixel':METRES_PER_PIXEL,
                  'accuracy':'Manual interpretation, uncalibrated assumed scale',
                  'chunk_target_metres':CHUNK_METRES,'buildings':self.buildings,
                  'regions':regions,'chunks':chunks,'palette':PALETTE,
                  'region_build_order':[5,4,6,2,8,1,3,7,9]}
        (path/'manifest.json').write_text(json.dumps(manifest,indent=2))
        return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='G:/ForgeMCP/Saved/ReferenceCityRegions_v2/Chunks512_Final')
    out=Path(parser.parse_args().output)
    result=City().build().save(out)
    print(json.dumps({'output':str(out),'regions':len(result['regions']),
                      'chunks':len(result['chunks']),'buildings':result['buildings']}))
