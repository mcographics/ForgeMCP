"""Real stdio Landscape acceptance in a verified isolated host. Never targets the city.

Fresh runs require an untitled host; a partial run must be inspected, never blindly replayed.
"""
import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(session_id: str, project_file: Path, map_name: str):
    root = Path(__file__).resolve().parents[1]
    output = root / 'Saved/LandscapeDevelopment/acceptance.json'
    report = {'session_id': session_id, 'project_file': str(project_file), 'steps': []}

    def checkpoint():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    params = StdioServerParameters(command=sys.executable, args=['-m', 'server.main'],
                                  cwd=str(root), env={**os.environ, 'FORGE_PROJECT_ROOT': str(root)})
    try:
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()

                async def call(tool, args, ok=True):
                    response = await client.call_tool(tool, {'session_id': session_id, **args})
                    result = response.structuredContent
                    assert not response.isError and result, str(response)
                    assert result['ok'] == ok, str(result)
                    return result['data'] if ok else result['error']

                info = await call('unreal_project_info', {})
                assert Path(info['project_file']).resolve() == project_file.resolve(), info
                assert not info['play_in_editor'] and info['level'].startswith('/Temp/Untitled'), info
                report['identity'] = info
                checkpoint()

                async def apply(request):
                    if request['action'] == 'save':
                        for _ in range(200):
                            state = await call('unreal_inspect_landscape',
                                               {'actor_path': request['actor_path']})
                            if state['landscapes'][0]['layers_up_to_date']:
                                break
                            await asyncio.sleep(.25)
                    preview = await call('unreal_preview_landscape', {'request': request})
                    pid = preview['preview_id']
                    result = await call('unreal_apply_landscape', {'preview_id': pid, 'confirmation': pid})
                    return preview, result

                _, created = await apply({'action': 'create',
                                          'map_path': '/Game/ForgeMCPTests/Landscape/' + map_name})
                report['steps'].append({'create': created})
                checkpoint()
                assert created['state'] == 'completed' and created['saved'], created
                actor = created['landscape']['actor_path']
                # Native lighting in the disposable host only. No sky asset is loaded or edited.
                light = await call('unreal_preview_actors', {'recipe': {'operations': [{
                    'op': 'spawn', 'class_path': '/Script/Engine.DirectionalLight',
                    'label': 'TerrainTestLight', 'rotation': [-45, -35, 0]}]}})
                await call('unreal_apply_actors', {'preview_id': light['preview_id'],
                                                 'confirmation': light['preview_id']})

                async def capture(label):
                    response = await client.call_tool('unreal_capture_screenshot',
                                                      {'session_id': session_id})
                    for block in response.content:
                        if block.type == 'image':
                            destination = root / 'Saved/LandscapeDevelopment' / (label + '.jpg')
                            destination.write_bytes(base64.b64decode(block.data, validate=True))
                            return str(destination)
                    return None

                async def inspect():
                    data = await call('unreal_inspect_landscape', {'actor_path': actor})
                    return data['landscapes'][0]

                async def edit(action, **kwargs):
                    before = await inspect()
                    preview, job = await apply({'action': action, 'actor_path': actor, **kwargs})
                    progress = []
                    for _ in range(300):
                        status = await call('unreal_landscape_job_status', {'job_id': job['job_id']})
                        if not progress or status['rows_applied'] != progress[-1]['rows_applied']:
                            progress.append(status)
                            if (status['state'] == 'running'
                                    and status['rows_applied'] >= status['total_rows'] // 2
                                    and not any(p.get('viewport_capture') for p in progress)):
                                status['viewport_capture'] = await capture(action + '-intermediate')
                        if status['state'] != 'running':
                            break
                        await asyncio.sleep(.2)
                    await asyncio.sleep(.5)
                    after = await inspect()
                    after['viewport_capture'] = await capture(action + '-completed')
                    record = {'action': action, 'preview': preview, 'before': before,
                              'after': after, 'progress': progress}
                    report['steps'].append(record)
                    checkpoint()
                    assert status['state'] == 'completed' and status['height_readback_validated'], record
                    assert after['layers'][0]['height_sha_md5'] == preview['after_height_md5'], record
                    assert len(progress) >= 2, 'No intermediate progress observed'
                    replay = await call('unreal_apply_landscape', {'preview_id': preview['preview_id'],
                                       'confirmation': preview['preview_id']}, ok=False)
                    assert replay['code'] == 'preview_not_found', replay
                    return after

                hill = await edit('raise', region=[4, 4, 30, 30], height_cm=800)
                assert hill['layers'][0]['max_local_cm'] >= 799
                valley = await edit('lower', region=[33, 33, 59, 59], height_cm=500)
                assert valley['layers'][0]['min_local_cm'] <= -499
                await edit('flatten', region=[12, 12, 22, 22], height_cm=200, strength=1)
                await edit('smooth', region=[2, 2, 61, 61], strength=.8)
                # Native height range rejection must occur at preview, before writes.
                error = await call('unreal_preview_landscape', {'request': {'action': 'raise',
                                   'actor_path': actor, 'region': [0, 0, 63, 63],
                                   'height_cm': 100000}}, ok=False)
                assert error['code'] == 'height_out_of_range', error
                report['range_rejection'] = error
                _, saved = await apply({'action': 'save', 'actor_path': actor})
                report['steps'].append({'save': saved})
                checkpoint()
                assert saved['saved'] and saved['state'] == 'completed', saved
                _, reloaded = await apply({'action': 'reload', 'actor_path': actor})
                report['steps'].append({'reload': reloaded})
                checkpoint()
                assert reloaded['persistence_validated'], reloaded
                actor = reloaded['landscape']['actor_path']
                await apply({'action': 'frame', 'actor_path': actor})
                for _ in range(2):
                    clean = await inspect()
                    assert not clean['dirty'], 'Read-only inspection dirtied the reloaded map'
                report['inspection_preserves_clean_package'] = True
                report['initial_test_passed'] = True
                checkpoint()
                await edit('generate', region=[0, 0, 63, 63], height_cm=300)
                await edit('coastline', region=[0, 0, 63, 63], height_cm=400)
                await edit('apply_heightmap', region=[28, 28, 31, 31],
                           samples_cm=[200] * 16)
                # Cancel after the first observable stage; preserve the partial result.
                before_cancel = await inspect()
                _, job = await apply({'action': 'raise', 'actor_path': actor,
                                      'rows_per_stage': 1, 'stage_interval_seconds': .5})
                for _ in range(100):
                    status = await call('unreal_landscape_job_status', {'job_id': job['job_id']})
                    if status['rows_applied'] >= 3:
                        break
                    await asyncio.sleep(.1)
                cancelled = await call('unreal_cancel_landscape_job', {'job_id': job['job_id'],
                                       'confirmation': job['job_id']})
                assert cancelled['state'] == 'cancelled_partial', cancelled
                await asyncio.sleep(1)
                stable = await call('unreal_landscape_job_status', {'job_id': job['job_id']})
                assert stable['rows_applied'] == cancelled['rows_applied'], stable
                partial = await inspect()
                assert partial['layers'][0]['height_sha_md5'] != before_cancel['layers'][0]['height_sha_md5']
                report['cancellation'] = stable
                # Restore the initial demonstration as the saved, reloaded final landscape.
                await edit('generate', region=[0, 0, 63, 63], height_cm=0)
                await edit('raise', region=[4, 4, 30, 30], height_cm=800)
                await edit('lower', region=[33, 33, 59, 59], height_cm=500)
                await edit('flatten', region=[12, 12, 22, 22], height_cm=200, strength=1)
                await edit('smooth', region=[2, 2, 61, 61], strength=.8)
                await apply({'action': 'save', 'actor_path': actor})
                _, final = await apply({'action': 'reload', 'actor_path': actor})
                assert final['persistence_validated'], final
                assert final['landscape']['layers'][0]['height_sha_md5'] == saved['height_md5'], final
                await apply({'action': 'frame', 'actor_path': final['landscape']['actor_path']})
                await asyncio.sleep(.5)
                report['final_viewport'] = await capture('final-viewport')
                report['final'] = final
                report['state'] = 'passed'
                checkpoint()
    except BaseException as exc:
        report['state'] = 'failed'
        report['error'] = str(exc)
        checkpoint()
        raise
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--project-file', type=Path, required=True)
    parser.add_argument('--map-name', default='L_TerrainAcceptance_20261016')
    args = parser.parse_args()
    asyncio.run(run(args.session_id, args.project_file, args.map_name))
