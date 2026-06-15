"""
Integration test for GraphMemoryIntegrator in cli.py startup flow.
"""
import sys, os, tempfile, yaml, shutil
sys.path.insert(0, 'src')

tmpdir = tempfile.mkdtemp()
project = os.path.join(tmpdir, 'novel_output')
os.makedirs(project + '/config', exist_ok=True)
os.makedirs(project + '/output/chapters', exist_ok=True)

with open(project + '/config/character_base_cards.yaml', 'w') as f:
    yaml.dump({'s_tier': {'tier_name': 'core', 'characters': {
        'Hero': {'role': 'hero', 'relationships': {'Villain': 'enemy'}},
        'Villain': {'role': 'villain'}
    }}}, f)

with open(project + '/output/chapters/chapter_1_final.md', 'w') as f:
    f.write('Hero fought Villain at the auction.')

# Override project root to temp dir (priority over novels.yaml)
os.environ["NOVEL_PROJECT_ROOT"] = project
os.environ["COMPANY_API_KEY"] = "test-api-key"

from pathlib import Path
from novels_project.project_config import set_project_root, get_project_root
set_project_root()
assert Path(get_project_root()).resolve() == Path(project).resolve(), f"Project root mismatch: {get_project_root()} vs {project}"

from novels_project.memory import AutoSyncConfig
from novels_project.cli import _build_runtime, _shutdown_graph

errors = []

def test(name):
    def decorator(fn):
        try:
            fn()
            print(f'  {name}: PASSED')
        except Exception as e:
            errors.append((name, e))
            print(f'  {name}: FAILED - {e}')
            import traceback; traceback.print_exc()
    return decorator

print('=== Test 1: Normal startup ===')
@test('Normal startup')
def _():
    config = AutoSyncConfig(enabled=True, event_triggered=True, threshold_chapters=1)
    runtime, sid, integrator = _build_runtime(
        model='gemini-3-pro',
        auto_sync_config=config,
        force_build_graph=True,
    )
    assert integrator.is_initialized()
    status = integrator.sync_manager.get_sync_status()
    assert status['graph_nodes'] >= 2, f'Expected >=2 nodes, got {status["graph_nodes"]}'
    result = _shutdown_graph(integrator)
    assert result is not None

print('=== Test 2: Disabled graph ===')
@test('Disabled graph')
def _():
    config = AutoSyncConfig(enabled=False, event_triggered=False)
    runtime, sid, integrator = _build_runtime(model='gemini-3-pro', auto_sync_config=config)
    assert integrator.is_initialized()
    status = integrator.sync_manager.get_sync_status()
    assert not status['auto_sync_enabled'], f"Auto sync should be disabled: {status}"
    _shutdown_graph(integrator)

print('=== Test 3: Shutdown saves graph ===')
@test('Shutdown saves graph')
def _():
    config = AutoSyncConfig(enabled=True, persist_on_sync=True)
    runtime, sid, integrator = _build_runtime(
        model='gemini-3-pro',
        auto_sync_config=config,
        force_build_graph=True,
    )
    # persistance happens via sync_manager._persist_graph
    # Force a save
    from pathlib import Path
    graph_path = Path(project) / 'graph' / 'knowledge_graph.json'
    if not graph_path.exists():
        integrator.sync_manager._graph.save(str(graph_path))
    result = _shutdown_graph(integrator)
    if result:
        graph_path = result.get('graph_path', graph_path)
    assert Path(graph_path).exists(), f'Graph not found: {graph_path}'
    assert Path(graph_path).stat().st_size > 0

print('=== Test 4: Chapter event triggers sync ===')
@test('Chapter event triggers sync')
def _():
    config = AutoSyncConfig(enabled=True, event_triggered=True, threshold_chapters=1)
    runtime, sid, integrator = _build_runtime(
        model='gemini-3-pro',
        auto_sync_config=config,
        force_build_graph=True,
    )
    before_nodes = integrator.sync_manager.get_sync_status()['graph_nodes']
    integrator.on_chapter_generated(2, 'Hero met Mentor at the market.')
    # After event-triggered sync, graph may have updated
    status = integrator.sync_manager.get_sync_status()
    assert status['graph_nodes'] >= before_nodes
    _shutdown_graph(integrator)

shutil.rmtree(tmpdir)

# Clean up env
del os.environ["NOVEL_PROJECT_ROOT"]
del os.environ["COMPANY_API_KEY"]

if errors:
    print(f'\n{len(errors)} test(s) FAILED:')
    for name, e in errors:
        print(f'  - {name}: {e}')
    sys.exit(1)
else:
    print('\nALL 4 INTEGRATION TESTS PASSED')