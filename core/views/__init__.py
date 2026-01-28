from .permissions import group_required, is_admin
from .auth_views import login_view, logout_view, user_register_admin
from .home_views import home

from .project_views import project_list, project_create, project_update, project_delete
from .sprint_views import sprint_list, sprint_create, sprint_update, sprint_delete
from .epic_views import epic_list, epic_create, epic_update, epic_delete

from .task_views import (
    task_list,
    task_create,
    task_detail,
    task_update,
    task_delete,
    task_update_status,
    task_move,
    subtask_update,
    subtask_delete,
)

from .daily_views import daily_list, daily_create, daily_bulk_delete

from .availability_views import (
    availability_list,
    availability_create,
    availability_update,
    availability_delete,
)

from .user_admin_views import user_list, user_create, user_update, user_set_password, user_delete
from .dashboard_views import dashboard

from .matrix_views import matrix_priority, matrix_status, export_matrix_pdf
