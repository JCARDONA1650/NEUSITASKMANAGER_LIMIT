from django.urls import path

from core.views import (
    # Auth (nuevo)
    login_view, logout_view, user_register_admin,


    user_list, user_create, user_update, user_set_password, user_delete,


    # Home
    home,

    # Projects
    project_list, project_create, project_update, project_delete,

    # Sprints
    sprint_list, sprint_create, sprint_update, sprint_delete,

    # Epics
    epic_list, epic_create, epic_update, epic_delete,

    # Tasks
    task_list, task_create, task_detail, task_update, task_delete,
    task_update_status, task_move,

    # Subtasks
    subtask_update, subtask_delete,

    # Daily
    daily_list, daily_create, daily_bulk_delete,

    # Availability
    availability_list, availability_create, availability_update, availability_delete,

    # Dashboard
    dashboard,

    # Matrices
    matrix_priority, matrix_status, export_matrix_pdf,
    # Help
    help_page,
)

urlpatterns = [
    # ------------------------------------------------------------------
    # AUTH (NUEVO)
    # ------------------------------------------------------------------
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # ------------------------------------------------------------------
    # USERS (APP ADMIN - NO /admin)
    # ------------------------------------------------------------------
    path("users/", user_list, name="user_list"),
    path("users/new/", user_create, name="user_create"),
    path("users/<int:pk>/edit/", user_update, name="user_update"),
    path("users/<int:pk>/password/", user_set_password, name="user_set_password"),
    path("users/<int:pk>/delete/", user_delete, name="user_delete"),

    # "Registrarse" (pero realmente es: admin crea usuarios)
    path("register/", user_register_admin, name="register"),

    # ------------------------------------------------------------------
    # HOME
    # ------------------------------------------------------------------
    path("", home, name="home"),

    # ------------------------------------------------------------------
    # PROJECTS (ADMIN)
    # ------------------------------------------------------------------
    path("projects/", project_list, name="project_list"),
    path("projects/new/", project_create, name="project_create"),
    path("projects/<int:pk>/edit/", project_update, name="project_update"),
    path("projects/<int:pk>/delete/", project_delete, name="project_delete"),

    # ------------------------------------------------------------------
    # SPRINTS (ADMIN)
    # ------------------------------------------------------------------
    path("sprints/", sprint_list, name="sprint_list"),
    path("sprints/new/", sprint_create, name="sprint_create"),
    path("sprints/<int:pk>/edit/", sprint_update, name="sprint_update"),
    path("sprints/<int:pk>/delete/", sprint_delete, name="sprint_delete"),

    # ------------------------------------------------------------------
    # EPICS (ADMIN)
    # ------------------------------------------------------------------
    path("epics/", epic_list, name="epic_list"),
    path("epics/new/", epic_create, name="epic_create"),
    path("epics/<int:pk>/edit/", epic_update, name="epic_update"),
    path("epics/<int:pk>/delete/", epic_delete, name="epic_delete"),

    # ------------------------------------------------------------------
    # TASKS
    # ------------------------------------------------------------------
    path("tasks/", task_list, name="task_list"),
    path("tasks/new/", task_create, name="task_create"),
    path("tasks/<int:pk>/", task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", task_update, name="task_update"),
    path("tasks/<int:pk>/delete/", task_delete, name="task_delete"),
    path("tasks/<int:pk>/status/", task_update_status, name="task_update_status"),
    path("api/tasks/<int:pk>/move/", task_move, name="task_move"),

    # ------------------------------------------------------------------
    # SUBTASKS
    # ------------------------------------------------------------------
    path("subtasks/<int:pk>/edit/", subtask_update, name="subtask_update"),
    path("subtasks/<int:pk>/delete/", subtask_delete, name="subtask_delete"),

    # ------------------------------------------------------------------
    # DAILY
    # ------------------------------------------------------------------
    path("daily/", daily_list, name="daily_list"),
    path("daily/new/", daily_create, name="daily_create"),
    path("dailies/delete/", daily_bulk_delete, name="daily_bulk_delete"),

    # ------------------------------------------------------------------
    # AVAILABILITY
    # ------------------------------------------------------------------
    path("availability/", availability_list, name="availability_list"),
    path("availability/new/", availability_create, name="availability_create"),
    path("availability/<int:pk>/edit/", availability_update, name="availability_update"),
    path("availability/<int:pk>/delete/", availability_delete, name="availability_delete"),

    # ------------------------------------------------------------------
    # DASHBOARD
    # ------------------------------------------------------------------
    path("dashboard/", dashboard, name="dashboard"),

    # ------------------------------------------------------------------
    # MATRICES
    # ------------------------------------------------------------------
    path("matrix/priority/", matrix_priority, name="matrix_priority"),
    path("matrix/status/", matrix_status, name="matrix_status"),
    path("matrix/priority/export/", export_matrix_pdf, name="export_matrix_pdf"),

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------
    path("help/", help_page, name="help_page"),

    
]
