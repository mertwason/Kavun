"""Para hesabında `float` yasağını zorlayan lint kuralı (CLAUDE.md §1).

`app/` altındaki tüm kaynaklarda `float` kullanımı (tip anotasyonu veya çağrı)
hatadır. Bilinçli istisna için satırın sonuna gerekçesiyle birlikte
`# allow-float: <gerekçe>` yorumu eklenir.

Kullanım: `python -m tools.check_money_float app`
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ALLOW_MARKER = "# allow-float:"


@dataclass(frozen=True)
class Violation:
    """Tek bir `float` kullanımı."""

    path: Path
    line: int
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: float kullanımı yasak ({self.detail}) — Decimal kullan"


class _FloatVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, allowed_lines: frozenset[int]) -> None:
        self.path = path
        self.allowed_lines = allowed_lines
        self.violations: list[Violation] = []

    def _record(self, node: ast.AST, detail: str) -> None:
        line = getattr(node, "lineno", 0)
        if line in self.allowed_lines:
            return
        self.violations.append(Violation(self.path, line, detail))

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "float":
            self._record(node, "float adı")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, float):
            self._record(node, f"float literal {node.value!r}")
        self.generic_visit(node)


def _allowed_lines(source: str) -> frozenset[int]:
    return frozenset(
        index for index, line in enumerate(source.splitlines(), start=1) if ALLOW_MARKER in line
    )


def check_source(source: str, path: Path = Path("<memory>")) -> list[Violation]:
    """Verilen kaynak metninde float ihlallerini bulur."""
    tree = ast.parse(source, filename=str(path))
    visitor = _FloatVisitor(path, _allowed_lines(source))
    visitor.visit(tree)
    return visitor.violations


def check_paths(roots: Iterable[Path]) -> list[Violation]:
    """Verilen dizin/dosyaları tarar."""
    violations: list[Violation] = []
    for root in roots:
        files = sorted(root.rglob("*.py")) if root.is_dir() else [root]
        for file in files:
            violations.extend(check_source(file.read_text(encoding="utf-8"), file))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Çıkış kodu: ihlal varsa 1."""
    args = list(argv if argv is not None else sys.argv[1:]) or ["app"]
    violations = check_paths(Path(arg) for arg in args)
    for violation in violations:
        print(violation.render())
    if violations:
        print(f"\n{len(violations)} float ihlali bulundu (CLAUDE.md §1).")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
