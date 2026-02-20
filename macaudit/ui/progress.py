"""
Progress bar renderer.

Stateless — takes (completed, total), returns a rich Text.
The caller (ScanNarrator) owns state and calls this each frame.

Output:  [████████████░░░░░░░░] 62%  ·  14 of 23 checks
"""

from rich.text import Text

from macaudit.ui.theme import COLOR_DIM


BAR_WIDTH = 22


def render_progress(completed: int, total: int) -> Text:
    """
    Return a styled progress bar as a rich Text object.

    Args:
        completed: number of checks finished
        total:     total checks to run

    Returns a single-line Text like:
        [████████████░░░░░░░░] 62%  ·  14 of 23 checks
    """
    if total == 0:
        return Text("  No checks to run", style=COLOR_DIM)

    pct = completed / total
    filled = round(BAR_WIDTH * pct)
    empty = BAR_WIDTH - filled

    done = completed == total
    bar_color = "bright_green" if done else "cyan"
    pct_color = "bright_green bold" if done else "bold cyan"

    t = Text()
    t.append("  [", style=COLOR_DIM)
    t.append("█" * filled, style=bar_color)
    t.append("░" * empty, style=COLOR_DIM)
    t.append("]  ", style=COLOR_DIM)
    t.append(f"{int(pct * 100)}%", style=pct_color)
    t.append(f"  ·  {completed} of {total} checks", style=COLOR_DIM)

    return t
