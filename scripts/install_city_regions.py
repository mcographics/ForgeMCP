"""Install the authorized nine-region city into a verified live World Partition level.

Uses existing bounded native preview/apply commands. Saves every placement and
reloads between regions. Never replays a partial or uncertain native mutation.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from server.core.connections import ConnectionManager  # noqa: E402
from server.core.levels import CurrentLevelSaves  # noqa: E402
from server.core.workflow_journal import WorkflowJournal  # noqa: E402
from server.core.workflows import TransferCoordinator, TransferRequest  # noqa: E402

OUT=ROOT/'Saved/ReferenceCityRegions_v2/Chunks512'
ASSETS='/Game/ReferenceCityRegions_v2'


async def run(target, expected_level, reload_between_regions=True):
    manifest=json.loads((OUT/'manifest.json').read_text())
    source=json.loads((OUT/'ready.json').read_text())['session_id']
    manager=ConnectionManager.configured()
    manager.timeout=60
    manager.apply_timeout=600
    transfers=TransferCoordinator(manager,WorkflowJournal(ROOT/'Saved/ForgeWorkflows'))
    saves=CurrentLevelSaves(transfers)

    async def call(command,args=None):
        result=await manager.dispatch('unreal',command,target,args or {})
        if not result['ok']:
            raise RuntimeError(result)
        return result['data']

    async def context():
        state=await call('project_info')
        assert state['project_file']=='G:/ForgeMCP/ForgeMCPDev.uproject',state
        assert state['level']==expected_level and not state['play_in_editor'],state

    def record(name,data):
        (OUT/(name+'.json')).write_text(json.dumps(data,indent=2))

    async def checkpoint(name):
        await context()
        preview=await saves.preview(target)
        assert not any(p.get('will_delete') for p in preview['packages']),preview
        record(name+'_save_preview',preview)
        result=await saves.apply(preview['preview_id'],preview['preview_id'],target)
        record(name+'_save_result',result)
        assert result['state']=='saved',result

    async def edit_component(path,name,value):
        state=await call('component_property_info',{'component_path':path,'limit':200})
        p=next(p for p in state['properties'] if p['name']==name)
        if p['value']==value:
            return
        checked=await manager.dispatch('unreal','component_property_edit_preview',target,
                                       {'component_path':path,'property_name':name,'property_value':value})
        if not checked['ok'] and checked['error']['code']=='no_change':
            return
        assert checked['ok'],checked
        preview=checked['data']
        result=await call('component_property_edit_apply',{'preview_id':preview['preview_id'],
                          'confirmation':preview['preview_id']})
        # Blueprint reconstruction can replace the edited component. Read its
        # stable owner/component path again rather than trusting a TRASH pointer.
        observed=await call('component_property_info',{'component_path':path,'limit':200})
        record(path.rsplit('.',1)[-1]+'_'+name+'_readback',observed)
        assert next(p for p in observed['properties'] if p['name']==name)['value']==result['applied_value']

    await context()
    for region in manifest['regions']:
        name=f"BP_Region_{region['id']:02}_{region['name']}"
        found=await call('find_actors',{'name_contains':name,'limit':10})
        if found['actors']:
            assert len(found['actors'])==1,found
            path=found['actors'][0]['path']
        else:
            recipe={'asset_path':ASSETS+'/Controllers/'+name,
                    'parent_class':'/Script/Engine.LocationVolume',
                    'components':[{'name':'RegionBounds','class_path':'/Script/Engine.BoxComponent'}],
                    'location':region['center_cm'],'save':True,'place':True}
            preview=await call('blueprint_preview',{'recipe':recipe})
            record(name+'_preview',preview)
            result=await call('blueprint_apply',{'preview_id':preview['preview_id'],
                              'confirmation':preview['preview_id']})
            record(name+'_result',result)
            assert result['state']=='completed' and result['compiler_errors']==0 and result['saved'],result
            path=result['actor_path']
        ext=region['extent_cm']
        await edit_component(path+'.RegionBounds','BoxExtent',f'(X={ext[0]},Y={ext[1]},Z={ext[2]})')
        await edit_component(path+'.RegionBounds','bGenerateOverlapEvents','false')
        await checkpoint(name)
        print('REGION_CONTROL_SAVED',region['id'],flush=True)

    async def transfer_and_place(name,region,location):
        await context()
        asset=ASSETS+(f'/R{region:02}/' if region else '/Background/')+name
        result_path=OUT/(name+'_transfer_result.json')
        if result_path.exists():
            result=json.loads(result_path.read_text())
            assert result['state']=='completed',result
        else:
            previous=OUT/(name+'_transfer_preview.json')
            if previous.exists():
                pid=json.loads(previous.read_text())['preview_id']
                assert not (ROOT/'Saved/ForgeWorkflows'/pid).exists(),'Inspect interrupted workflow before resuming'
                previous.rename(OUT/(name+'_unused_preview.json'))
            request=TransferRequest(source_session_id=source,target_session_id=target,
                                    source_object=name,target_asset_path=asset,save_assets=True,place=False)
            preview=await transfers.preview(request)
            record(name+'_transfer_preview',preview)
            print('IMPORTING',name,flush=True)
            result=await transfers.apply(preview['preview_id'],preview['preview_id'])
            record(name+'_transfer_result',result)
            assert result['state']=='completed',result
        found=await call('find_actors',{'name_contains':name,'limit':10})
        if not any(a['label']==name for a in found['actors']):
            object_path=asset+'.'+name
            loaded=await manager.dispatch('unreal','mesh_info',target,{'asset_path':object_path})
            if not loaded['ok']:
                await call('open_asset',{'asset_path':asset})
            op={'op':'spawn','class_path':'/Script/Engine.StaticMeshActor','mesh_path':object_path,
                'label':name,'location':location,'tags':['ReferenceCityRegions_v2',f'CityRegion_{region:02}']}
            preview=await call('actor_preview',{'recipe':{'operations':[op]}})
            record(name+'_placement_preview',preview)
            result=await call('actor_apply',{'preview_id':preview['preview_id'],'confirmation':preview['preview_id']})
            record(name+'_placement_result',result)
            assert result['state']=='completed',result
            path=result['actors'][0]['path'] if 'actors' in result else None
        else:
            path=next(a['path'] for a in found['actors'] if a['label']==name)
        if path is None:
            found=await call('find_actors',{'name_contains':name,'limit':10})
            path=next(a['path'] for a in found['actors'] if a['label']==name)
        props=await call('actor_property_info',{'actor_path':path,'limit':200})
        spatial=next(p for p in props['properties'] if p['name']=='bIsSpatiallyLoaded')
        if region:
            assert spatial['value']=='true',props
        elif spatial['value']!='false':
            p=await call('actor_property_edit_preview',{'actor_path':path,'property_name':'bIsSpatiallyLoaded','property_value':'false'})
            await call('actor_property_edit_apply',{'preview_id':p['preview_id'],'confirmation':p['preview_id']})
        record(name+'_spatial_readback',await call('actor_property_info',{'actor_path':path,'limit':200}))
        await checkpoint(name)
        print('CHUNK_SAVED',name,flush=True)

    await transfer_and_place('RC_Harbor_Background',0,[0.,0.,0.])
    progress=[]
    for region_id in manifest['region_build_order']:
        for chunk in [c for c in manifest['chunks'] if c['region']==region_id]:
            if (OUT/'stop_import').exists():
                print('STOP_REQUESTED',flush=True)
                return
            await transfer_and_place(chunk['name'],region_id,chunk['location_cm'])
        await checkpoint(f'Region_{region_id:02}_complete')
        if not reload_between_regions:
            progress.append({'region':region_id,'chunks':len([c for c in manifest['chunks'] if c['region']==region_id]),
                             'level_saved':True,'reload_tested':False})
            record('progress',progress)
            print('REGION_SAVED',region_id,flush=True)
            continue
        # Use the normal level-open handler only after a verified checkpoint.
        opened=await call('open_asset',{'asset_path':expected_level.split('.')[0]})
        await context()
        loaded=await call('find_actors',{'tag':f'CityRegion_{region_id:02}','limit':100})
        observation={'region':region_id,'level_open':opened,'loaded_region_actors_after_reload':loaded}
        record(f'Region_{region_id:02}_reload',observation)
        progress.append({'region':region_id,'chunks':len([c for c in manifest['chunks'] if c['region']==region_id]),
                         'loaded_after_reload':loaded['total_matches']})
        record('progress',progress)
        print('REGION_COMPLETE',region_id,'LOADED_AFTER_RELOAD',loaded['total_matches'],flush=True)
    if not reload_between_regions:
        await checkpoint('All_nine_regions_complete')
        opened=await call('open_asset',{'asset_path':expected_level.split('.')[0]})
        await context()
        record('All_nine_regions_reload',opened)
    record('completed',{'level':expected_level,'regions':9,'chunks':len(manifest['chunks']),
                        'runtime_streaming_tested':False,'performance_tested':False})
    print('ALL_NINE_REGIONS_SAVED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id',required=True)
    parser.add_argument('--level',required=True)
    parser.add_argument('--source-dir',required=True)
    parser.add_argument('--reload-once',action='store_true',
                        help='Keep per-placement saves, then reload only after every region is saved')
    args=parser.parse_args()
    OUT=Path(args.source_dir).resolve()
    asyncio.run(run(args.session_id,args.level,not args.reload_once))
