"""Static check that the arousal-scoring domain and the spending domain never
import from each other — see the boundary comment at the top of
wellness.models.transactions for the rule this enforces.

Pure AST inspection, no database needed: this walks each boundary-sensitive
module's import statements and asserts none of them name a module on the
other side of the line.
"""

import ast
from pathlib import Path

AROUSAL_MODULES = {
    "wellness.models.checkins",
    "wellness.models.baseline",
    "wellness.models.arousal",
    "wellness.services.baseline",
    "wellness.services.arousal",
}
SPENDING_MODULES = {
    "wellness.models.transactions",
    "wellness.models.financial",
    "wellness.models.banking",
    "wellness.models.goals",
}

_SRC = Path(__file__).resolve().parent.parent / "src"
_MODULE_PATH = {
    "wellness.models.checkins": _SRC / "wellness/models/checkins.py",
    "wellness.models.baseline": _SRC / "wellness/models/baseline.py",
    "wellness.models.arousal": _SRC / "wellness/models/arousal.py",
    "wellness.services.baseline": _SRC / "wellness/services/baseline.py",
    "wellness.services.arousal": _SRC / "wellness/services/arousal.py",
    "wellness.models.transactions": _SRC / "wellness/models/transactions.py",
    "wellness.models.financial": _SRC / "wellness/models/financial.py",
    "wellness.models.banking": _SRC / "wellness/models/banking.py",
    "wellness.models.goals": _SRC / "wellness/models/goals.py",
}


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _crosses_boundary(imported: set[str], forbidden: set[str]) -> set[str]:
    return {
        name
        for name in imported
        if any(name == f or name.startswith(f + ".") for f in forbidden)
    }


def test_arousal_domain_never_imports_spending_domain() -> None:
    for module in AROUSAL_MODULES:
        leaked = _crosses_boundary(_imported_module_names(_MODULE_PATH[module]), SPENDING_MODULES)
        assert not leaked, f"{module} imports spending-domain module(s): {leaked}"


def test_spending_domain_never_imports_arousal_domain() -> None:
    for module in SPENDING_MODULES:
        leaked = _crosses_boundary(_imported_module_names(_MODULE_PATH[module]), AROUSAL_MODULES)
        assert not leaked, f"{module} imports arousal-domain module(s): {leaked}"
