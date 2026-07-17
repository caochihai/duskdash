"""Selective invalidation for a new plan version."""
from __future__ import annotations

from common.schemas import Plan


def invalidated_tasks(plan: Plan, changed_inputs: set[str]) -> set[str]:
    """Invalidate directly affected tasks and all dependants, preserving other checkpoints."""
    affected = {task.task_id for task in plan.tasks if set(task.affects) & changed_inputs}
    changed = True
    while changed:
        changed = False
        for task in plan.tasks:
            if task.task_id not in affected and set(task.depends_on) & affected:
                affected.add(task.task_id)
                changed = True
    return affected
