"""Real stdio Landscape acceptance in a verified isolated host. Never targets the city.

Fresh runs require an untitled host; a partial run must be inspected, never blindly replayed.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _snapshot_project(project_root: Path) -> dict[str, tuple[int, str]]:
    snapshot = {}
    for path in sorted(project_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Refusing to inspect a project symlink: {path}")
        if path.is_file():
            snapshot[path.relative_to(project_root).as_posix()] = (
                path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return snapshot


async def run(session_id: str, project_file: Path, map_name: str, world_partition: bool = False):
    root = Path(__file__).resolve().parents[1]
    project_file = project_file.resolve(strict=True)
    if os.environ.get('FORGE_HOST_MODE', '').strip().lower() != 'isolated':
        raise RuntimeError('Landscape acceptance requires the dedicated isolated host')
    if Path(os.environ.get('FORGE_PROJECT_ROOT', '')).resolve(strict=True) != project_file.parent:
        raise RuntimeError('Landscape acceptance project does not match the private host state root')
    output_dir = project_file.parent / 'Saved' / 'LandscapeDevelopment'
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f'phase6-{map_name}.json'
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite acceptance report: {output}')
    report = {
        'server_mode': 'isolated',
        'session_id': session_id,
        'project_file': str(project_file),
        'steps': [],
    }

    def checkpoint():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    params = StdioServerParameters(
        command=sys.executable,
        args=['-m', 'server.isolated_host'],
        cwd=str(root),
        env=dict(os.environ),
    )
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

                async def dirty_inventory():
                    target_map_path = '/Game/ForgeMCPTests/Landscape/' + map_name
                    page = await call('unreal_inspect_dirty_packages', {'request': {
                        'limit': 50, 'target_map_path': target_map_path,
                    }})
                    assert page['read_only'] and page['offset'] == 0, page
                    rows = list(page['packages'])
                    inventory_id = page.get('snapshot_id') or page['inventory_id']
                    expected_offset = len(rows)
                    package_names = {row['package_name'] for row in rows}
                    inspected = page['packages_inspected']
                    total_dirty = page.get('total_dirty_loaded_packages')
                    inventory_complete = page['inventory_complete']
                    while page['has_more_observed_results']:
                        page = await call('unreal_inspect_dirty_packages', {'request': {
                            'limit': 50,
                            'offset': expected_offset,
                            'snapshot_id': inventory_id,
                            'target_map_path': target_map_path,
                        }})
                        page_snapshot_id = page.get('snapshot_id') or page['inventory_id']
                        assert page['read_only'] and page_snapshot_id == inventory_id, page
                        assert page['offset'] == expected_offset, page
                        assert page['packages_inspected'] == inspected, page
                        assert page['inventory_complete'] == inventory_complete, page
                        assert page.get('total_dirty_loaded_packages') == total_dirty, page
                        assert page.get('proposed_target_map_path') == target_map_path, page
                        assert page['next_offset'] == expected_offset + page['returned_count'], page
                        new_names = {row['package_name'] for row in page['packages']}
                        assert not (package_names & new_names), 'Duplicate dirty package row across pages'
                        package_names.update(new_names)
                        rows.extend(page['packages'])
                        expected_offset = page['next_offset']
                    assert len(rows) == len(package_names), 'Dirty package names are not unique'
                    if inventory_complete:
                        assert total_dirty == len(rows), page
                    return {
                        'inventory_id': inventory_id,
                        'packages_inspected': inspected,
                        'inventory_complete': inventory_complete,
                        'dirty_loaded_packages_observed': len(rows),
                        'total_dirty_loaded_packages': total_dirty,
                        'proposed_target_map_path': target_map_path,
                        'packages': rows,
                        'unresolved_engine_script_packages': [row for row in rows
                            if row.get('unresolved_engine_script_package') or
                            (row.get('script_package_candidate') and
                             (not row.get('classification_complete', False) or
                              not row.get('engine_script_provenance_verified', False)))],
                        'unresolved_project_content_packages': [row for row in rows
                            if row.get('unresolved_project_content_package')],
                        'unresolved_other_packages': [row for row in rows
                            if row.get('package_category') == 'unknown' or
                            not row.get('classification_complete', False) or
                            not row.get('ownership_scan_complete', False)],
                        'current_world_packages': [row for row in rows
                            if row.get('package_category') == 'current_world' or
                            row.get('is_current_level_package') or row.get('associated_with_current_level')],
                        'external_actor_packages': [row for row in rows
                            if row.get('package_category') == 'external_actor' or row.get('contains_external_actor')],
                        'associated_object_samples_truncated': [row for row in rows
                            if row.get('associated_objects_sample_truncated')],
                        'target_map_path_namespace_matches': [row for row in rows
                            if row.get('target_map_path_namespace_match')],
                        'unloaded_package_note': page['unloaded_package_note'],
                    }

                core_status = await call('forge_status', {})
                assert core_status.get('version') == '0.3.15', core_status
                report['core_status'] = core_status
                info = await call('unreal_project_info', {})
                assert Path(info['project_file']).resolve() == project_file.resolve(), info
                expected_level = os.environ['FORGE_ISOLATED_EXPECTED_LEVEL']
                assert not info['play_in_editor'] and info['level'] == expected_level, info
                report['identity'] = info
                report['dirty_inventory_before'] = await dirty_inventory()

                # Deliberately submit a create request outside the disposable
                # Landscape namespace. Core schema validation must reject it
                # before dispatch; a full file snapshot verifies no project
                # file changed while handling the rejected request.
                negative_before = _snapshot_project(project_file.parent)
                negative_response = await client.call_tool('unreal_preview_landscape', {
                    'session_id': session_id,
                    'request': {
                        'action': 'create',
                        'map_path': '/Game/ForgeMCPTests/Outside/' + map_name,
                        'world_partition': True,
                    },
                })
                rejected = bool(negative_response.isError)
                if negative_response.structuredContent:
                    rejected = rejected or not negative_response.structuredContent.get('ok', False)
                negative_after = _snapshot_project(project_file.parent)
                assert rejected, 'Out-of-scope Landscape create request was not rejected'
                assert negative_before == negative_after, 'Rejected out-of-scope request changed project files'
                report['out_of_scope_negative_test'] = {
                    'rejected_before_editor_dispatch': bool(negative_response.isError),
                    'request_rejected': rejected,
                    'project_file_set_unchanged': True,
                    'method': 'invalid path rejected by typed MCP/core contract before native apply',
                }
                checkpoint()

                async def apply(request, preview=None):
                    if request['action'] == 'save':
                        for _ in range(200):
                            state = await call('unreal_inspect_landscape',
                                               {'actor_path': request['actor_path']})
                            if state['landscapes'][0]['layers_up_to_date']:
                                break
                            await asyncio.sleep(.25)
                    preview = preview or await call('unreal_preview_landscape', {'request': request})
                    pid = preview['preview_id']
                    result = await call('unreal_apply_landscape', {'preview_id': pid, 'confirmation': pid})
                    return preview, result

                create_request = {
                    'action': 'create',
                    'map_path': '/Game/ForgeMCPTests/Landscape/' + map_name,
                    'components_x': 2,
                    'components_y': 2,
                    'quads_per_section': 63,
                    'sections_per_component': 1,
                    'world_partition': world_partition,
                    'partition_grid_size_components': 2,
                    'xy_scale_cm': 100,
                    'use_engine_basic_landscape_material': True,
                }
                create_preview = await call('unreal_preview_landscape', {'request': create_request})
                report['create_preview'] = create_preview
                if not create_preview.get('apply_allowed', False):
                    report['state'] = 'blocked_preflight'
                    report['blocking_reason'] = create_preview.get('apply_block_reason', 'Native Apply policy denied creation')
                    checkpoint()
                    return
                write_scope = create_preview.get('write_scope', {})
                dirty_policy = create_preview.get('dirty_package_preflight', {})
                assert dirty_policy.get('inventory_complete') is True, dirty_policy
                assert dirty_policy.get('policy_evidence_complete') is True, dirty_policy
                assert dirty_policy.get('unresolved_dirty_package_classifications') == 0, dirty_policy
                assert dirty_policy.get('blocking_dirty_loaded_packages') == 0, dirty_policy
                assert dirty_policy.get('disposable_engine_script_exceptions_applied') == 1, dirty_policy
                exception_rows = dirty_policy.get('disposable_engine_script_exception_rows', [])
                assert len(exception_rows) == 1, exception_rows
                slate = exception_rows[0]
                assert slate.get('package_path') == '/Script/SlateCore', slate
                assert slate.get('package_category') == 'engine_script', slate
                assert slate.get('classification_complete') is True, slate
                assert slate.get('ownership_scan_complete') is True, slate
                assert slate.get('engine_script_provenance_verified') is True, slate
                assert slate.get('associated_actor_count') == 0, slate
                assert slate.get('associated_with_current_level_determined') is True, slate
                assert slate.get('associated_with_current_level') is False, slate
                assert slate.get('associated_objects_sample_truncated') is True, slate
                assert write_scope.get('explicit_unknown_or_unbounded_effects'), write_scope
                assert write_scope.get('rollback_limitations'), write_scope
                assert write_scope.get('preservation_limitations'), write_scope
                assert write_scope.get('existing_package_overwrite_checks', {}).get('all_destinations_rechecked_before_apply'), write_scope
                assert write_scope.get('allowed_generated_package_namespaces'), write_scope
                assert write_scope.get('exact_known_auxiliary_file_destinations'), write_scope
                if world_partition:
                    assert any(item.get('filename_status') == 'deterministic_from_engine_default_hlod_layer_chain'
                               for item in write_scope.get('exact_known_package_destinations', [])), write_scope
                _, created = await apply(create_request, preview=create_preview)
                report['steps'].append({'create': created})
                checkpoint()
                assert created['state'] == 'completed' and created['saved'], created
                assert created.get('world_partition_created') is world_partition, created
                assert created.get('generated_package_observations_are_complete') is False, created
                actor = created['landscape']['actor_path']
                async def capture(label):
                    response = await client.call_tool('unreal_capture_screenshot',
                                                      {'session_id': session_id})
                    for block in response.content:
                        if block.type == 'image':
                            destination = output_dir / (label + '.jpg')
                            destination.write_bytes(base64.b64decode(block.data, validate=True))
                            return str(destination)
                    return None

                async def inspect():
                    data = await call('unreal_inspect_landscape', {'actor_path': actor})
                    return data['landscapes'][0]

                async def edit(action, **kwargs):
                    before = await inspect()
                    # Keep at least one observable running interval in the smoke
                    # test so progress reporting is exercised even on a fast
                    # disposable editor.  The production default remains owned
                    # by the caller; this only makes this acceptance request
                    # deterministic and bounded.
                    edit_request = {
                        'action': action,
                        'actor_path': actor,
                        'rows_per_stage': 1,
                        'stage_interval_seconds': .1,
                        **kwargs,
                    }
                    preview, job = await apply(edit_request)
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
                              'after': after, 'progress': progress, 'final_status': status}
                    report['steps'].append(record)
                    checkpoint()
                    assert (status['state'] == 'completed'
                            and status['height_readback_validated']
                            and status['collision_validation_deferred_until_save_reload']
                            and status['collision_height_source'] == 'deferred_until_save_reload'), record
                    assert after['layers'][0]['height_sha_md5'] != before['layers'][0]['height_sha_md5'], record
                    assert status['validated_after_height_md5'] == preview['after_height_md5'], record
                    # The dedicated partial-cancellation check below proves
                    # progress and stability for tiny work batches too. A
                    # four-row heightmap chunk may finish inside one tool
                    # round trip, so require multiple samples only when the
                    # request has enough stages for an intermediate state.
                    if status['total_rows'] >= 8:
                        assert len(progress) >= 2, 'No intermediate progress observed'
                    replay = await call('unreal_apply_landscape', {'preview_id': preview['preview_id'],
                                       'confirmation': preview['preview_id']}, ok=False)
                    assert replay['code'] == 'preview_not_found', replay
                    return after

                hill = await edit('raise', region=[4, 4, 30, 30], height_cm=800)
                assert hill['layers'][0]['max_local_cm'] >= 799
                valley = await edit('lower', region=[33, 33, 59, 59], height_cm=500)
                assert valley['layers'][0]['min_local_cm'] <= -499
                await edit('flatten', region=[12, 12, 22, 22], height_cm=200,
                           strength=1, stage_interval_seconds=.5)
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
                assert reloaded['complex_collision_validated_after_reload'], reloaded
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
                await edit('flatten', region=[12, 12, 22, 22], height_cm=200,
                           strength=1, stage_interval_seconds=.5)
                await edit('smooth', region=[2, 2, 61, 61], strength=.8)
                await apply({'action': 'save', 'actor_path': actor})
                _, final = await apply({'action': 'reload', 'actor_path': actor})
                assert final['persistence_validated'], final
                assert final['landscape']['layers'][0]['height_sha_md5'] == saved['height_md5'], final
                await apply({'action': 'frame', 'actor_path': final['landscape']['actor_path']})
                await asyncio.sleep(.5)
                report['final_viewport'] = await capture('final-viewport')
                report['final'] = final
                report['dirty_inventory_after_reload'] = await dirty_inventory()
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
    parser.add_argument('--world-partition', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.session_id, args.project_file, args.map_name, args.world_partition))
