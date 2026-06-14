#!/usr/bin/env python3
"""Generate an IDR notebook/script migration report.

Reads `dw_notebook_integrations/idr/` and compares "old" vs "new" generation
export scripts.

Rules (from AI_Instruction/migrate_notebooks.md)
----------------------------------------------
- Any subdirectory under `dw_notebook_integrations/idr/` with "_auto" in the
  directory name contains *old* scripts.
- All other subdirectories contain *new* scripts.
- Table name is parsed from the script module docstring.
- Extracted columns are determined by taking everything between the first
  SELECT and the first FROM in the SQL (as text), ignoring inline `-- ...`
  comments.
- Report is written to `dw_notebook_integrations/idr/notebook_migration_report.md`
  and overwritten each run.
- Links in the report are repo-relative (not GitHub links).
- At the end of the report list any cases where matching is not 1-to-1.

This script is intentionally "static": it does not import/run the export scripts
and does not require Snowflake access.
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ParsedScript:
    abs_path: Path
    rel_path_from_idr: Path
    generation: str  # "old" | "new"
    table_name: str  # normalized uppercase, e.g. V2_MDCR_PRVDR
    columns: tuple[str, ...]


_RE_TABLE_FROM_DOCSTRING = [
    # e.g. "Auto-generated IDROutputter implementation for IDRC_PRD....V2_MDCR_PRVDR"
    re.compile(
        r"Auto-generated IDROutputter implementation for\s+([A-Z0-9_\.]+)",
        re.IGNORECASE,
    ),
    # e.g. "Table: IDRC_PRD....V2_MDCR_PRVDR (VIEW)"
    re.compile(r"^\s*Table:\s+([A-Z0-9_\.]+)", re.IGNORECASE | re.MULTILINE),
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _module_docstring(text: str, *, path: Path) -> str | None:
    """Best-effort module docstring extraction."""
    try:
        mod = ast.parse(text)
        return ast.get_docstring(mod)
    except Exception:
        # Fallback: regex for first triple-quoted string.
        m = re.search(r"(?s)^\s*(?:r|u|ru|ur)?\s*([\"']{3})(.*?)\1", text)
        if m:
            return m.group(2)
        return None


def _parse_table_name_from_docstring(doc: str) -> str | None:
    for rx in _RE_TABLE_FROM_DOCSTRING:
        m = rx.search(doc)
        if not m:
            continue
        full = m.group(1).strip()
        # If it looks schema-qualified, table is the last segment.
        table = full.split(".")[-1]
        table = table.strip().strip("\"").strip("'")
        if table:
            return table.upper()
    return None


def _extract_sql_blob(text: str) -> str | None:
    """Extract the SQL string returned by getSelectQuery() if possible."""
    # Most generated scripts use: return """SELECT ... FROM ..."""
    m = re.search(r"(?s)def\s+getSelectQuery\s*\([^)]*\)\s*->\s*str\s*:\s*.*?\n\s*return\s+\"\"\"(.*?)\"\"\"", text)
    if m:
        return m.group(1)
    # Fallback: any triple-quoted string that contains SELECT and FROM.
    for m2 in re.finditer(r"(?s)\"\"\"(.*?)\"\"\"", text):
        blob = m2.group(1)
        if re.search(r"\bSELECT\b", blob, re.IGNORECASE) and re.search(r"\bFROM\b", blob, re.IGNORECASE):
            return blob
    return None


def _parse_columns_from_sql(sql: str) -> tuple[str, ...] | None:
    # Find SELECT keyword
    m_select = re.search(r"\bSELECT\b", sql, re.IGNORECASE)
    if not m_select:
        return None

    # Find the first FROM keyword on a new line (reduces false positives).
    m_from = re.search(r"\n\s*FROM\b", sql[m_select.end() :], re.IGNORECASE)
    if not m_from:
        # fallback to any FROM
        m_from = re.search(r"\bFROM\b", sql[m_select.end() :], re.IGNORECASE)
        if not m_from:
            return None

    select_list = sql[m_select.end() : m_select.end() + m_from.start()]

    columns: list[str] = []
    for line in select_list.splitlines():
        # Strip inline comments
        if "--" in line:
            line = line.split("--", 1)[0]
        line = line.strip()
        if not line:
            continue
        # Remove trailing commas
        if line.endswith(","):
            line = line[:-1].rstrip()
        if not line:
            continue
        columns.append(line)

    # Defensive: if the first line accidentally starts with SELECT due to weird formatting.
    if columns and re.match(r"(?i)^select\b", columns[0]):
        columns[0] = re.sub(r"(?i)^select\b", "", columns[0]).strip()
        if not columns[0]:
            columns = columns[1:]

    return tuple(columns)


def _generation_for_path(path: Path) -> str:
    # old scripts live anywhere under a directory name containing _auto
    return "old" if any("_auto" in p.name for p in path.parents) else "new"


def _iter_export_scripts(idr_dir: Path) -> list[Path]:
    """All *.py files under idr subdirectories (excluding idr root-level)."""
    results: list[Path] = []
    for py in idr_dir.rglob("*.py"):
        if not py.is_file():
            continue
        # Ignore top-level python files in idr root.
        if py.parent == idr_dir:
            continue
        results.append(py)
    return sorted(results)


def _md_link(*, rel_path_from_idr: Path) -> str:
    # Markdown file is written in idr root, so link is simply the relative path.
    p = rel_path_from_idr.as_posix()
    return f"[{p}]({p})"


def _render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body])


def parse_script(*, idr_dir: Path, abs_path: Path) -> ParsedScript | None:
    text = _read_text(abs_path)

    doc = _module_docstring(text, path=abs_path)
    if not doc:
        return None

    table = _parse_table_name_from_docstring(doc)
    if not table:
        return None

    sql_blob = _extract_sql_blob(text)
    if not sql_blob:
        return None

    columns = _parse_columns_from_sql(sql_blob)
    if not columns:
        return None

    rel = abs_path.relative_to(idr_dir)
    gen = _generation_for_path(abs_path)
    return ParsedScript(
        abs_path=abs_path,
        rel_path_from_idr=rel,
        generation=gen,
        table_name=table,
        columns=columns,
    )


def build_report(*, idr_dir: Path, out_path: Path) -> None:
    scripts = _iter_export_scripts(idr_dir)

    parsed: list[ParsedScript] = []
    parse_failures: list[Path] = []
    for p in scripts:
        ps = parse_script(idr_dir=idr_dir, abs_path=p)
        if ps is None:
            parse_failures.append(p)
        else:
            parsed.append(ps)

    old_by_table: dict[str, list[ParsedScript]] = {}
    new_by_table: dict[str, list[ParsedScript]] = {}

    for ps in parsed:
        target = old_by_table if ps.generation == "old" else new_by_table
        target.setdefault(ps.table_name, []).append(ps)

    old_tables = set(old_by_table.keys())
    new_tables = set(new_by_table.keys())

    new_only = sorted(new_tables - old_tables)
    old_only = sorted(old_tables - new_tables)
    migrated = sorted(old_tables & new_tables)

    lines: list[str] = []
    lines.append("# IDR notebook migration report")
    lines.append("")
    lines.append(f"Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append("")

    def scripts_cell(items: list[ParsedScript]) -> str:
        # sort for deterministic output
        links = [_md_link(rel_path_from_idr=i.rel_path_from_idr) for i in sorted(items, key=lambda x: x.rel_path_from_idr.as_posix())]
        return "<br>".join(links)

    if new_only:
        lines.append("## Tables in new scripts but not old")
        lines.append("")
        rows = [[t, scripts_cell(new_by_table[t])] for t in new_only]
        lines.append(_render_markdown_table(["table", "new_script(s)"], rows))
        lines.append("")

    if old_only:
        lines.append("## Tables in old scripts but not new")
        lines.append("")
        rows = [[t, scripts_cell(old_by_table[t])] for t in old_only]
        lines.append(_render_markdown_table(["table", "old_script(s)"], rows))
        lines.append("")

    migrated_one_to_one_rows: list[list[str]] = []
    non_one_to_one: list[str] = []

    for t in migrated:
        olds = old_by_table.get(t, [])
        news = new_by_table.get(t, [])
        if len(olds) != 1 or len(news) != 1:
            non_one_to_one.append(t)
            continue

        old_s = olds[0]
        new_s = news[0]

        same = set(old_s.columns) == set(new_s.columns)
        migrated_one_to_one_rows.append(
            [
                _md_link(rel_path_from_idr=old_s.rel_path_from_idr),
                _md_link(rel_path_from_idr=new_s.rel_path_from_idr),
                "same" if same else "different",
            ]
        )

    if migrated_one_to_one_rows:
        lines.append("## Migrated tables (1-to-1)")
        lines.append("")
        lines.append(_render_markdown_table(["old_script", "new_script", "same_or_different"], migrated_one_to_one_rows))
        lines.append("")

    if non_one_to_one:
        lines.append("## Non 1-to-1 matches (should be impossible)")
        lines.append("")
        for t in non_one_to_one:
            old_links = scripts_cell(old_by_table.get(t, []))
            new_links = scripts_cell(new_by_table.get(t, []))
            lines.append(f"- **{t}**")
            lines.append(f"  - old: {old_links if old_links else '(none)'}")
            lines.append(f"  - new: {new_links if new_links else '(none)'}")
        lines.append("")

    if parse_failures:
        lines.append("## Parse failures (skipped)")
        lines.append("")
        lines.append(
            "These files did not match the expected patterns (missing docstring table name and/or SELECT/FROM extraction)."
        )
        lines.append("")
        for p in sorted(parse_failures):
            rel = p.relative_to(idr_dir)
            lines.append(f"- `{rel.as_posix()}`")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print("Report written:", out_path)
    print(f"Parsed scripts: {len(parsed)}")
    print(f"Parse failures: {len(parse_failures)}")
    print(f"Old tables: {len(old_tables)}  New tables: {len(new_tables)}  Migrated: {len(migrated)}")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    dw_integrations_dir = script_dir.parent
    idr_dir_default = (dw_integrations_dir / "idr").resolve()
    out_default = (idr_dir_default / "notebook_migration_report.md").resolve()

    parser = argparse.ArgumentParser(description="Generate notebook migration markdown report for IDR export scripts")
    parser.add_argument("--idr-dir", type=Path, default=idr_dir_default, help="IDR directory to scan")
    parser.add_argument("--out", type=Path, default=out_default, help="Output markdown file path")
    args = parser.parse_args()

    idr_dir: Path = args.idr_dir.expanduser().resolve()
    out_path: Path = args.out.expanduser().resolve()

    if not idr_dir.exists():
        raise SystemExit(f"idr-dir does not exist: {idr_dir}")

    build_report(idr_dir=idr_dir, out_path=out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
