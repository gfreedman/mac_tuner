"""
Fix execution subsystem for MacTuner.

Modules:
  runner.py   — interactive fix session: questionary checkbox menu,
                pre-selection of safe AUTO fixes, per-fix confirmation.
  executor.py — per-level fix dispatchers: run_auto_fix, run_auto_sudo_fix,
                run_guided_fix, run_instructions_fix.
"""
