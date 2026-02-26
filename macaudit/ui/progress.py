"""
Progress bar renderer.

Stateless — takes (completed, total), returns a rich Text.
The caller (ScanNarrator) owns state and calls this each frame.

Output:  [████████████░░░░░░░░] 62%  ·  14 of 23 checks
"""

from rich.text import Text

from macaudit.ui.theme import COLOR_DIM, PROGRESS_BAR_COLOR, PROGRESS_COMPLETE_COLOR


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
    bar_color = PROGRESS_COMPLETE_COLOR if done else PROGRESS_BAR_COLOR
    pct_color = f"{PROGRESS_COMPLETE_COLOR} bold" if done else f"bold {PROGRESS_BAR_COLOR}"

    t = Text()
    t.append("  [", style=COLOR_DIM)
    t.append("█" * filled, style=bar_color)
    t.append("░" * empty, style=COLOR_DIM)
    t.append("]  ", style=COLOR_DIM)
    t.append(f"{int(pct * 100)}%", style=pct_color)
    t.append(f"  ·  {completed} of {total} checks", style=COLOR_DIM)

    return t
