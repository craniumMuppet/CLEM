from pathlib import Path
import ast
import climate_model as cm


def test_record_has_no_free_cfg_reference():
    source = Path(cm.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'record':
            target = node
            break
    assert target is not None
    free_cfg = [
        n for n in ast.walk(target)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == 'cfg'
    ]
    assert not free_cfg


def test_record_initial_snapshot_succeeds():
    model = cm.ProcessClimateModel(
        cm.ModelConfig(
            resolution_deg=10.0,
            scenario='constant',
            duration_years=1.0,
            auto_initialize_from_1850=False,
        )
    )
    row = model.record(0.0)
    assert isinstance(row, dict)
    assert 'amoc_sv' in row
