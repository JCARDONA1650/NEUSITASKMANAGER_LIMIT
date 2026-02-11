from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def help_page(request):
    return render(request, "core/help.html")
