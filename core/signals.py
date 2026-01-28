from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import SubTask, Task


def _recalc_task_spent(task_id: int) -> None:
    total = (
        SubTask.objects.filter(task_id=task_id, status=SubTask.Status.COMPLETED)
        .aggregate(v=Coalesce(Sum("budget"), Decimal("0.00")))["v"]
        or Decimal("0.00")
    )
    Task.objects.filter(id=task_id).update(spent_budget=total)


@receiver(post_save, sender=SubTask)
def subtask_saved(sender, instance: SubTask, **kwargs) -> None:
    _recalc_task_spent(instance.task_id)


@receiver(post_delete, sender=SubTask)
def subtask_deleted(sender, instance: SubTask, **kwargs) -> None:
    _recalc_task_spent(instance.task_id)
