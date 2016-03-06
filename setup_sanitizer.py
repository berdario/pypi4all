from unittest.mock import MagicMock
from io import StringIO
import importlib.util
import ast
import sys

class _CustomMock(MagicMock):
    def _get_child_mock(self, name, **kw):
        m = super()._get_child_mock(**kw)
        m.__str__ = lambda self: 'FIXME'
        return m

def make_mock(name):
    m = _CustomMock(name=name)
    m.__str__ = lambda self: 'FIXME'
    return m

def is_importable(module_name):
    # Trying to find a module inside a package will raise if the package is not importable
    # If the package is available, we assume that the import will succeed
    return bool(importlib.util.find_spec(module_name.split('.')[0]))

def mock_ast(name):
    return ast.Call(
        func=ast.Name(id='make_mock', ctx=ast.Load()),
        args=[ast.Str(s=name)],
        keywords=[])

def mock_assignment(name):
    return (ast.Name(id=name, ctx=ast.Store()), mock_ast(name))

def tuple_assignment(names, values):
    return ast.Assign(
        targets=[ast.Tuple(elts=list(names), ctx=ast.Store())],
        value=ast.Tuple(elts=list(values), ctx=ast.Load()))

def mocked_import(module_names, imported_identifiers):
    if all(map(is_importable, module_names)):
        return None

    return tuple_assignment(*zip(*map(mock_assignment, imported_identifiers)))

def from_alias(alias):
    return alias.asname or alias.name.split('.')[0]

def selector(_record=[], **kwargs):
    if kwargs:
        _record.append(kwargs.get('install_requires', []))
    else:
        result = _record[:]
        del _record[:]
        return result

class Sanitizer(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        node = self.generic_visit(node)
        return mocked_import([node.module], map(from_alias, node.names)) or node

    def visit_Import(self, node):
        node = self.generic_visit(node)
        # if even one of the modules in this statement is in a unavailable package, we will mock all of them
        module_names = [name.name for name in node.names]
        return mocked_import(module_names, map(from_alias, node.names)) or node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if getattr(node.func, 'id', None) == 'open' and (not node.args[1:] or 'r' in node.args[1].s):
            return ast.Call(func=ast.Name(id='StringIO', ctx=ast.Load()), args=[ast.Str(s='FIXME')], keywords=[])
        elif getattr(node.func, 'id', None) == 'setup':
            return ast.Call(func=ast.Name(id='selector', ctx=ast.Load()), args=node.args, keywords=node.keywords, starargs=node.starargs, kwargs=node.kwargs)
        else:
            return node

sanitize = Sanitizer().visit

def extract_from_setup(path, setupfile):
    setup = ast.parse(setupfile.read())
    setup = sanitize(setup)
    setup = ast.fix_missing_locations(setup)
    exec(compile(setup, path, 'exec'))
    return selector()
    

if __name__ == '__main__':
    fname = sys.argv[1]
    with open(fname) as f:
        print(extract_from_setup(fname, f))
