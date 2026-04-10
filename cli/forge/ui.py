"""
forge.ui — shared console and output primitives.

Design principles:
  - No emojis. Ever.
  - Color is used sparingly and only to convey meaning:
      green  → success / good state
      red    → error / failure
      yellow → warning / in-progress
      blue   → label / heading accent
      dim    → secondary / metadata
  - Every line starts with a consistent 2-char prefix:
      "  " (2 spaces) — body / continuation
      Otherwise the prefix is supplied by the caller via helper functions.
  - Tables are left-aligned, no box-drawing overkill.
"""

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

console = Console(highlight=False)

# ── Low-level helpers ────────────────────────────────────────────────────────

def success(msg: str) -> None:
    """Green checkmark line."""
    console.print(f"[bold green]✓[/bold green]  {msg}")

def error(msg: str) -> None:
    """Red cross line. Use for terminal failures."""
    console.print(f"[bold red]✗[/bold red]  {msg}")

def warn(msg: str) -> None:
    """Yellow dash line. Use for non-fatal issues."""
    console.print(f"[yellow]-[/yellow]  {msg}")

def info(msg: str) -> None:
    """Dim arrow. Use for status updates / progress."""
    console.print(f"[dim]>[/dim]  {msg}")

def label(key: str, value: str, key_width: int = 14) -> None:
    """
    Aligned key/value pair. Good for summary blocks.
      Project       proj_abc123
      Repository    github.com/user/repo
    """
    console.print(f"  [dim]{key:<{key_width}}[/dim]{value}")

def blank() -> None:
    console.print("")

def rule(title: str = "") -> None:
    """Horizontal divider, optionally titled."""
    if title:
        console.rule(f"[dim]{title}[/dim]", style="dim")
    else:
        console.rule(style="dim")

def header(title: str) -> None:
    """Bold section header with a rule underneath."""
    blank()
    console.print(f"[bold]{title}[/bold]")
    console.rule(style="dim")

# ── Status badge ─────────────────────────────────────────────────────────────

_STATUS_STYLES = {
    "success":  ("green",  "success"),
    "failed":   ("red",    "failed"),
    "queued":   ("yellow", "queued"),
    "running":  ("yellow", "running"),
    "skipped":  ("dim",    "skipped"),
}

def status_badge(status: str) -> Text:
    """Returns a Rich Text object coloured by run status."""
    status_lower = status.lower() if status else "unknown"
    for key, (color, label_str) in _STATUS_STYLES.items():
        if key in status_lower:
            return Text(label_str, style=color)
    return Text(status_lower, style="dim")

# ── Tables ────────────────────────────────────────────────────────────────────

def runs_table(runs: list) -> None:
    """Render a list of CI runs as a clean table."""
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("COMMIT",  style="cyan",  no_wrap=True, width=9)
    t.add_column("STATUS",  no_wrap=True,  width=10)
    t.add_column("MESSAGE", no_wrap=True,  max_width=40)
    t.add_column("CREATED", style="dim",   no_wrap=True, width=17)

    for run in runs:
        sha     = (run.get("commit") or "")[:7]
        msg     = (run.get("message") or "(no message)")[:40]
        created = _fmt_time(run.get("created_at", ""))
        t.add_row(sha, status_badge(run.get("status", "")), msg, created)

    console.print(t)

def steps_table(steps: list) -> None:
    """Render CI step summary as a table."""
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("#",       style="dim",  no_wrap=True, width=3)
    t.add_column("STEP",    no_wrap=True, width=24)
    t.add_column("STATUS",  no_wrap=True, width=10)
    t.add_column("STARTED", style="dim",  no_wrap=True, width=17)
    t.add_column("FINISHED",style="dim",  no_wrap=True, width=17)

    for i, s in enumerate(steps, 1):
        t.add_row(
            str(i),
            s.get("name", ""),
            status_badge(s.get("status", "")),
            _fmt_time(s.get("started_at", "") or ""),
            _fmt_time(s.get("finished_at", "") or ""),
        )
    console.print(t)

def deploy_components_table(components: dict) -> None:
    """Render deployed component URLs."""
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("COMPONENT", no_wrap=True, width=20)
    t.add_column("STATUS",    no_wrap=True, width=10)
    t.add_column("URL",       style="cyan")

    for name, info in components.items():
        url    = info.get("url") or "—"
        status = info.get("status", "unknown")
        t.add_row(name, status_badge(status), url)

    console.print(t)

# ── Step log renderer ─────────────────────────────────────────────────────────

def render_step_logs(steps: list) -> None:
    """
    Print each step with stdout / stderr blocks.
    Used by `forge logs`.
    """
    for i, step in enumerate(steps, 1):
        blank()
        badge = status_badge(step.get("status", ""))
        console.print(f"  [bold]{i}. {step['name']}[/bold]  ", end="")
        console.print(badge)

        if step.get("stdout"):
            console.print("  [dim]stdout[/dim]")
            for line in step["stdout"].rstrip().splitlines():
                console.print(f"    [dim]{line}[/dim]")

        if step.get("stderr"):
            console.print("  [dim]stderr[/dim]")
            for line in step["stderr"].rstrip().splitlines():
                console.print(f"    [yellow]{line}[/yellow]")

# ── Internal helpers ──────────────────────────────────────────────────────────

def _fmt_time(ts: str) -> str:
    if not ts:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)[:16]