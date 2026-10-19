"""Prepare saved regional mesh assets without placing actors or saving the level."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from server.core.connections import ConnectionManager  # noqa: E402
from server.core.workflow_journal import WorkflowJournal  # noqa: E402
from server.core.workflows import TransferCoordinator, TransferRequest  # noqa: E402


async def main(args):
    out=Path(args.source_dir)
    manifest=json.loads((out/'manifest.json').read_text())
    source=json.loads((out/'ready.json').read_text())['session_id']
    manager=ConnectionManager.configured()
    manager.timeout=60
    manager.apply_timeout=600
    transfers=TransferCoordinator(manager,WorkflowJournal(ROOT/'Saved/ForgeWorkflows'))
    objects=[{'name':'RC_Harbor_Background','region':0}]
    for region in manifest['region_build_order']:
        objects.extend(c for c in manifest['chunks'] if c['region']==region)
    progress=[]
    for item in objects:
        if (out/'pause_asset_preparation').exists():
            print('ASSET_PREPARATION_PAUSED',flush=True)
            return
        context=await manager.dispatch('unreal','project_info',args.session_id,{})
        assert context['ok'] and context['data']['level']==args.level,context
        assert not context['data']['play_in_editor']
        name,region=item['name'],item['region']
        result_file=out/(name+'_transfer_result.json')
        if result_file.exists():
            result=json.loads(result_file.read_text())
            assert result['state']=='completed',result
        else:
            previous=out/(name+'_transfer_preview.json')
            if previous.exists():
                pid=json.loads(previous.read_text())['preview_id']
                assert not (ROOT/'Saved/ForgeWorkflows'/pid).exists(),'Inspect the interrupted receipt first'
                previous.rename(out/(name+'_unused_preview.json'))
            path='/Game/ReferenceCityRegions_v2'+(f'/R{region:02}/' if region else '/Background/')+name
            request=TransferRequest(source_session_id=source,target_session_id=args.session_id,
                                    source_object=name,target_asset_path=path,save_assets=True,place=False)
            preview=await transfers.preview(request)
            (out/(name+'_transfer_preview.json')).write_text(json.dumps(preview,indent=2))
            print('IMPORTING',name,flush=True)
            result=await transfers.apply(preview['preview_id'],preview['preview_id'])
            result_file.write_text(json.dumps(result,indent=2))
            assert result['state']=='completed',result
        progress.append({'name':name,'region':region,'operation_id':result['operation_id']})
        (out/'asset_preparation_progress.json').write_text(json.dumps(progress,indent=2))
        print('ASSET_SAVED',name,flush=True)
    (out/'all_assets_prepared.json').write_text(json.dumps({'count':len(progress),'placed':False}))
    print('ALL_REGIONAL_ASSETS_SAVED',len(progress),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',required=True)
    parser.add_argument('--session-id',required=True)
    parser.add_argument('--level',required=True)
    asyncio.run(main(parser.parse_args()))
