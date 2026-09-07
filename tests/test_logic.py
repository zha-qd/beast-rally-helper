"""Dependency-free regression checks; no screen capture or game input."""
import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace

source = Path(__file__).resolve().parents[1] / 'auto_beast_rally_gui.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
nodes = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEFAULT_CONFIG' for t in node.targets):
        nodes.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in ['normalize_config', 'deep_merge']:
        nodes.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == 'BeastRallyApp':
        node.body = [m for m in node.body if isinstance(m, ast.FunctionDef) and m.name in
                     ['_parse_march_count', '_parse_travel_time', '_parse_beast_level', '_clamp_level', '_level_range']]
        nodes.append(node)
env = dict(json=json, re=re)
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'logic', 'exec'), env)
A = env['BeastRallyApp']
assert A._parse_march_count('6/6') == (6, 6)
assert A._parse_march_count('1 ／ 6') == (1, 6)
assert A._parse_march_count('missing') == (None, None)
assert A._parse_travel_time('01:30') == 90
assert A._parse_travel_time('1:02:03') == 3723
assert A._parse_travel_time('1分20秒') == 80
assert A._parse_travel_time('missing') is None
assert A._parse_beast_level('Lv.8') == 8
assert A._parse_beast_level('等级 7') == 7
assert A._clamp_level(20) == 8
assert A._clamp_level(0) == 1
a = A()
a.var_beast_level_min = SimpleNamespace(get=lambda: '8')
a.var_beast_level_max = SimpleNamespace(get=lambda: '6')
assert a._level_range() == (6, 8)
cfg = env['normalize_config'](json.loads(json.dumps(env['DEFAULT_CONFIG'])))
assert len(cfg['window_slots']) == 3
assert all(slot['title'] == '' for slot in cfg['window_slots'])
assert cfg['window_slots'][0]['enabled']
print('PASS: march/time/level parsing, range normalization and clean initial configuration')
