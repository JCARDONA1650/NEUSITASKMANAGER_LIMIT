# NeusiTaskManager

**NeusiTaskManager** es un gestor de proyectos basado en metodologías ágiles desarrollado con Django y Bootstrap.  El sistema permite organizar proyectos en sprints, épicas, tareas y subtareas, asignar responsables, registrar avances diarios y visualizar métricas a través de paneles y matrices de priorización.

## Características principales

### Gestión de proyectos, sprints y épicas

* Los proyectos incluyen nombre, descripción, fechas de inicio y fin, presupuesto total y miembros asociados.  El presupuesto restante se calcula a partir del presupuesto asignado menos lo consumido por las subtareas.
* Los sprints están asociados a un proyecto y permiten agrupar tareas dentro de un rango de fechas.
* Las épicas también se vinculan a un proyecto y agrupan múltiples tareas de alto nivel.

### Tareas y subtareas

* Cada **tarea principal** pertenece a un proyecto y opcionalmente a un sprint y a una épica.  Dispone de título, descripción, esfuerzo (story points), presupuesto, estado (nueva, en progreso, completada), prioridad (urgente, importante, no urgente u otro) y responsables (uno o más integrantes).  El modelo incluye propiedades para calcular el presupuesto restante y el porcentaje de progreso en función de sus subtareas.
* Las **subtareas** dependen de una tarea principal y permiten documentar actividades más pequeñas.  Cada subtarea tiene título, descripción, esfuerzo, presupuesto, estado y un campo para adjuntar archivos de soporte.  Al crear una subtarea se valida que su presupuesto no exceda el presupuesto restante de la tarea principal.
* Un responsable (rol de desarrollador, marketing, etc.) sólo puede ver en su backlog las tareas en las que está asignado.  Los usuarios con rol de administrador, líder o scrum master pueden ver y gestionar todas las tareas.

### Roles y permisos

* NeusiTaskManager utiliza el sistema de permisos de Django.  Los permisos se definen a nivel de modelo y se agrupan mediante **Grupos**.  Los grupos `admin`, `leader` y `scrum` se consideran roles administrativos que permiten crear proyectos, sprints, épicas y tareas, así como modificar el estado de cualquier tarea.  Los demás usuarios sólo pueden visualizar las tareas en las que son responsables y crear subtareas.  La documentación de Django explica que los permisos se definen a nivel de modelo y luego se asignan a individuos o grupos【834982432765045†L40-L46】; además, cada modelo dispone de permisos predeterminados de *add*, *change* y *delete*【523604793688801†L33-L41】.
* Para comprobar si un usuario pertenece a un grupo se puede emplear un decorador personalizado.  GeeksforGeeks muestra un ejemplo de `group_required` que verifica la pertenencia del usuario al grupo y, en caso contrario, deniega el acceso【523604793688801†L154-L176】.  Este patrón se ha adaptado en el proyecto para proteger vistas administrativas.

### Matriz de prioridad y matriz de progreso

* La **matriz Aizenjaguer** agrupa las tareas según su prioridad (urgente, importante, no urgente y otras).  Incluye filtros por proyecto, sprint y responsable.  Los usuarios pueden exportar la matriz a un PDF.  La documentación oficial de Django explica que ReportLab permite generar PDF dinámicamente escribiendo sobre un objeto `HttpResponse`【925750410228291†L89-L114】; el proyecto utiliza esa técnica para producir un informe resumido de la matriz.
* La **matriz de progreso** muestra columnas para tareas nuevas, en progreso y completadas.  Actualmente la interfaz permite navegar a la tarea para actualizar su estado; el arrastre entre columnas queda como mejora futura.

### Dashboard y métricas

* El **panel de control** presenta indicadores clave como el número total de tareas y subtareas, porcentajes de progreso (tareas completadas frente al total), uso del presupuesto (monto gastado por subtareas frente al presupuesto total) y eficiencia de los registros diarios.  Los filtros permiten segmentar estas métricas por proyecto, sprint o responsable.
* La **eficiencia de dailies** se calcula tomando el número de miembros que registraron su daily dentro de la franja horaria configurada (por defecto 6 a 9 a.m.) dividido entre el total de integrantes.

### Dailies y disponibilidad

* El módulo **Daily** permite que cada usuario documente qué hizo el día anterior, qué hará hoy y cualquier impedimento.  La hora de registro se compara con la ventana configurada en `settings.DAILY_START_HOUR` y `settings.DAILY_END_HOUR`.  Los dailies creados dentro de este rango se consideran “a tiempo”; de lo contrario se marcan como fuera de horario.
* El módulo **Disponibilidad** funciona como un calendario simple para que cada miembro indique reuniones u horarios en los que no está disponible.  Los administradores pueden ver la disponibilidad de todo el equipo; los demás usuarios sólo ven la suya o la de los compañeros asignados a sus proyectos.

### Plan gratuito y límites

* Este repositorio implementa una versión *free* limitada por configuración: número máximo de proyectos (`FREE_MAX_PROJECTS`), número máximo de participantes y número máximo de roles administrativos (`FREE_MAX_ADMINS`).  Al alcanzar estos límites, la aplicación impide crear nuevas entidades y muestra un mensaje solicitando eliminar registros existentes o contactar al soporte.
* El uso de almacenamiento para adjuntos y registros diarios no se controla automáticamente; sin embargo, los administradores pueden limpiar subtareas, dailies o proyectos para liberar espacio.

## Instalación y uso

1. **Crear un entorno virtual**.  En la raíz del proyecto ejecute:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows use venv\Scripts\activate
   ```

2. **Instalar dependencias**.  Ejecute:

   ```bash
   pip install -r requirements.txt
   ```

   Entre las dependencias se encuentran Django y ReportLab.  La documentación de Django indica que ReportLab se instala con `pip install reportlab`【925750410228291†L75-L82】.

3. **Aplicar migraciones** para crear la base de datos SQLite:

   ```bash
   python manage.py migrate
   ```

4. **Crear un superusuario** (opcional pero recomendable) para acceder al panel de administración:

   ```bash
   python manage.py createsuperuser
   ```

5. **Iniciar el servidor de desarrollo**:

   ```bash
   python manage.py runserver
   ```

6. **Acceder a la aplicación** en `http://127.0.0.1:8000/`.  Para iniciar sesión utilice las credenciales de cualquier usuario creado (puede crear usuarios y grupos desde el panel de administración en `/admin/`).

## Organización del código

* `manage.py` – Utilidad de línea de comandos de Django para ejecutar el servidor, aplicar migraciones, etc.
* `neusi_task_manager/settings.py` – Configuración del proyecto.  Incluye constantes de zona horaria, límites de la versión gratuita y la ventana de registro de dailies.
* `core/models.py` – Modelos de dominio: proyectos, sprints, épicas, tareas, subtareas, dailies y disponibilidad.
* `core/forms.py` – Formularios basados en los modelos con validaciones de negocio (p.ej. control de presupuesto en subtareas o límite de proyectos).
* `core/views.py` – Vistas que implementan la lógica de la aplicación: listas, creación y detalle de entidades, dashboard, matrices y exportación a PDF.  Se utilizan los decoradores `login_required` y un decorador `group_required` inspirado en el ejemplo de GeeksforGeeks【523604793688801†L154-L176】 para restringir el acceso a usuarios según su rol.
* `core/templates/` – Plantillas HTML con Bootstrap que definen la interfaz gráfica.  Las páginas heredan de `base.html`, que contiene la barra de navegación y la carga de estilos.
* `core/static/` – Archivos estáticos (CSS).  Puede añadirse JavaScript personalizado para funciones como arrastrar y soltar en la matriz de progreso.
* `core/templatetags/role_tags.py` – Filtro personalizado para comprobar si un usuario pertenece a un grupo y así mostrar u ocultar opciones de menú.
* `requirements.txt` – Lista de dependencias del proyecto.

## Próximos pasos y mejoras

* Implementar la funcionalidad de arrastrar y soltar (drag & drop) en la matriz de progreso para cambiar el estado de las tareas sin abrir el detalle.
* Crear notificaciones automáticas cuando una tarea cambie de estado o cuando el presupuesto restante sea bajo.
* Gestionar la cuota de almacenamiento de la versión gratuita midiendo el tamaño de los archivos adjuntos y proporcionando herramientas para limpiar datos antiguos.
* Añadir pruebas unitarias y de integración para asegurar la calidad del código.

Esperamos que NeusiTaskManager sirva como punto de partida para proyectos internos de gestión ágil.  Para cualquier duda o sugerencia, consulte el código fuente o contacte con el equipo de desarrollo.