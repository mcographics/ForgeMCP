"""Transfer the authorized reference city into the explicitly inspected development world.

Run once. A failed/uncertain import requires inspection of its retained receipt,
not a blind retry. Existing destination assets are never overwritten.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.core.connections import ConnectionManager  # noqa: E402
from server.core.levels import CurrentLevelSaves  # noqa: E402
from server.core.workflow_journal import WorkflowJournal  # noqa: E402
from server.core.workflows import TransferCoordinator, TransferRequest  # noqa: E402

OUT = ROOT / 'Saved/ReferenceCity_20261016_v1'
LEVEL = '/Game/Levels/NewMap_PCGTest.NewMap_PCGTest'
OFFSET = [0.0, 0.0, 0.0]


async def main(target):
    info = json.loads((OUT / 'ready.json').read_text())
    manager = ConnectionManager.configured()
    manager.timeout = 45
    manager.apply_timeout = 600
    coordinator = TransferCoordinator(manager, WorkflowJournal(ROOT / 'Saved/ForgeWorkflows'))
    level_saves = CurrentLevelSaves(coordinator)
    TARGET = target
    project = await manager.dispatch('unreal', 'project_info', TARGET, {})
    assert project['ok'], project
    context = project['data']
    assert context['project_file'] == 'G:/ForgeMCP/ForgeMCPDev.uproject', context
    assert context['level'] == LEVEL, context
    assert not context['play_in_editor']
    receipts = []
    surfaces = ['RC_HarborWater', 'RC_LandAndQuays', 'RC_StreetsAndMarkings',
                'RC_WaterfrontPiers', 'RC_BridgesAndHighways', 'RC_ParksAndLandmarks',
                'RC_HarborVessels']
    names = surfaces + [name for name in info['objects'] if name not in surfaces]

    async def place(name):
        current = await manager.dispatch('unreal', 'project_info', TARGET, {})
        assert current['ok'] and current['data']['level'] == LEVEL, current
        assert not current['data']['play_in_editor']
        found = await manager.dispatch('unreal', 'find_actors', TARGET,
                                       {'name_contains': name, 'limit': 100})
        assert found['ok'], found
        if any(actor['label'] == name for actor in found['data']['actors']):
            print('ALREADY_PLACED', name, flush=True)
            return
        asset = '/Game/ReferenceCity_20261016_v1/' + name
        # Map changes can release imported meshes. Explicitly load a verified
        # existing asset only when it is no longer present in memory.
        loaded = await manager.dispatch('unreal', 'mesh_info', TARGET, {'asset_path': asset + '.' + name})
        if not loaded['ok']:
            opened = await manager.dispatch('unreal', 'open_asset', TARGET, {'asset_path': asset})
            assert opened['ok'], opened
        op = {'op': 'spawn', 'class_path': '/Script/Engine.StaticMeshActor',
              'mesh_path': asset + '.' + name, 'label': name,
              'location': OFFSET, 'tags': ['ReferenceCity_20261016_v1']}
        preview = await manager.dispatch('unreal', 'actor_preview', TARGET, {'recipe': {'operations': [op]}})
        (OUT / (name + '_placement_preview.json')).write_text(json.dumps(preview, indent=2))
        assert preview['ok'], preview
        pid = preview['data']['preview_id']
        result = await manager.dispatch('unreal', 'actor_apply', TARGET, {'preview_id': pid, 'confirmation': pid})
        (OUT / (name + '_placement_result.json')).write_text(json.dumps(result, indent=2))
        assert result['ok'] and result['data']['state'] == 'completed', result
        # Checkpoint while this sequential importer is quiescent, before the next
        # export/import can change world state and invalidate the save preview.
        save_plan = await level_saves.preview(TARGET)
        save = await level_saves.apply(save_plan['preview_id'], save_plan['preview_id'], TARGET)
        (OUT / (name + '_level_save.json')).write_text(json.dumps(save, indent=2))
        assert save['state'] == 'saved', save
        print('PLACED', name, flush=True)

    for name in names:
        # An inspected, verified reconciliation file explicitly resumes a completed
        # timed-out import without replaying the native mutation.
        recovered = OUT / (name + '_reconciled.json')
        if recovered.exists():
            evidence = json.loads(recovered.read_text())
            assert evidence['verified_complete'] is True
            receipts.append({'name': name, 'reconciled': True})
            await place(name)
            continue
        previous = OUT / (name + '_result.json')
        if previous.exists():
            result = json.loads(previous.read_text())
            assert result['state'] == 'completed', result
            receipts.append({'name': name, 'operation_id': result['operation_id']})
            await place(name)
            continue
        previous_preview = OUT / (name + '_preview.json')
        if previous_preview.exists():
            pid = json.loads(previous_preview.read_text())['preview_id']
            assert not (ROOT / 'Saved/ForgeWorkflows' / pid).exists(), 'Inspect unfinished native receipt before continuing'
            previous_preview.rename(OUT / (name + '_abandoned_preview.json'))
        request = TransferRequest(
            source_session_id=info['session_id'], target_session_id=TARGET,
            source_object=name, target_asset_path='/Game/ReferenceCity_20261016_v1/' + name,
            save_assets=True, place=False,
        )
        plan = await coordinator.preview(request)
        (OUT / (name + '_preview.json')).write_text(json.dumps(plan, indent=2))
        print('REVIEWED', name, flush=True)
        result = await coordinator.apply(plan['preview_id'], plan['preview_id'])
        (OUT / (name + '_result.json')).write_text(json.dumps(result, indent=2))
        assert result['state'] == 'completed', result
        receipts.append({'name': name, 'operation_id': result['operation_id']})
        (OUT / 'imports.json').write_text(json.dumps(receipts, indent=2))
        print('IMPORTED', name, flush=True)
        await place(name)
    print('CITY_PLACED', len(info['objects']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-session-id', required=True,
                        help='Explicit freshly inspected Unreal session; never reuse a crashed PID')
    asyncio.run(main(parser.parse_args().target_session_id))
