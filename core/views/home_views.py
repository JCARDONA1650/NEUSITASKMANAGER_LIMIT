from __future__ import annotations

from django.contrib.auth.decorators import login_required  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import redirect  # type: ignore


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return redirect("task_list")
