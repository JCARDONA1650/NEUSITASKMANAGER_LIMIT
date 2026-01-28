📘 README – DESARROLLO (TÉCNICO)
NeusiTaskManager – Backend Django / Frontend HTML-CSS-JS

**NeusiTaskManager** es un gestor de proyectos basado en metodologías ágiles desarrollado con Django y Bootstrap.  El sistema permite organizar proyectos en sprints, épicas, tareas y subtareas, asignar responsables, registrar avances diarios y visualizar métricas a través de paneles y matrices de priorización.

## Características principales
📘 README – DESARROLLO (TÉCNICO)
NeusiTaskManager – Backend Django / Frontend HTML-CSS-JS
-----------------------------------------------------------

1. Visión general

NeusiTaskManager es una aplicación de gestión de proyectos basada en metodologías ágiles (Scrum / Kanban), construida con:

Backend: Django

Frontend: HTML + CSS + JavaScript (Bootstrap)

Arquitectura: Monolito Django (sin React)

Autenticación: Django Auth + Roles por grupos

Plan: Free (con límites configurables desde admin interno)

2. Stack tecnológico

Python 3.12+

Django 5/6

SQLite (desarrollo)

Bootstrap 5

JavaScript vanilla

CSS custom (tema neu / oscuro)

Django Messages Framework

Django Admin (solo para devs/owners)

3. Estructura del proyecto
NeusiTaskManager/
├── core/
│   ├── models/
│   │   ├── project.py
│   │   ├── sprint.py
│   │   ├── epic.py
│   │   ├── task.py
│   │   ├── subtask.py
│   │   ├── daily.py
│   │   ├── availability.py
│   │   ├── plan_limits.py
│   │   └── logs.py
│   │
│   ├── forms/
│   │   ├── task_forms.py
│   │   ├── subtask_forms.py
│   │   ├── users_forms.py
│   │   └── daily_forms.py
│   │
│   ├── views/
│   │   ├── task_views.py
│   │   ├── user_admin_views.py
│   │   ├── daily_views.py
│   │   └── availability_views.py
│   │
│   ├── templates/
│   │   └── core/
│   │       ├── users/
│   │       ├── tasks/
│   │       └── dashboards/
│   │
│   ├── admin.py
│   └── permissions.py
│
├── static/
│   ├── core/css/
│   └── core/js/
│
├── media/
├── templates/base.html
├── db.sqlite3
└── manage.py

4. Modelos principales (resumen)
Project

Proyecto raíz

Presupuesto total

Miembros asignados

Sprint

Periodo de tiempo

Pertenece a un proyecto

Epic

Agrupador funcional

Pertenece a un proyecto

Task (Tarea principal)

Núcleo del sistema

Tiene:

Presupuesto asignado

Presupuesto gastado (automático)

KPIs (texto)

Story points

Prioridad (Eisenhower)

Responsables

El progreso se calcula desde subtareas

SubTask

Detalle operativo

Presupuesto individual

Archivo adjunto opcional

Alimenta el presupuesto gastado de la tarea

Daily

Registro diario del usuario

Validación por horario

Availability

Disponibilidad / bloqueos de agenda

PlanLimits (Singleton)

Define límites del plan FREE:

Usuarios admin

Usuarios normales

Proyectos

Tareas

Archivos

5. Roles y permisos (backend)

Roles basados en Groups:

Rol	Capacidades
Admin	Control total
Leader	Gestión de tareas
Scrum	Gestión operativa
Normal	Solo sus tareas

Helpers clave:

group_required

is_admin

6. Lógica de límites (Plan Free)

Validada en:

Forms

Admin

Views

Si se supera un límite:

❌ No se guarda

⚠️ Mensaje claro al usuario

Ejemplo:

“Su sesión free no alcanza para seguir creando tareas…”

7. Presupuesto

El presupuesto de SubTask se resta automáticamente del presupuesto de la Task

Validación evita sobrepasar el presupuesto restante

8. Estado y logs

Cambios de estado generan registro (TaskStatusLog)

Retrocesos requieren comentario (admin)

9. Seguridad

No se expone Django Admin a clientes

Usuarios protegidos:

Superuser no editable desde UI

No se puede borrar a uno mismo

10. Estilo frontend

Tema oscuro consistente

CSS modular por vista

Sin inline styles

Z-index y dropdowns corregidos globalmente