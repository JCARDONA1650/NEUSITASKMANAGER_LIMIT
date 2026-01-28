// static/js/calendar.js

// Variable global para almacenar los detalles de eventos
let dayDetails = {};

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Cargar datos de eventos desde el elemento JSON
    const dayDetailsElement = document.getElementById('day-details-data');
    if (dayDetailsElement) {
        dayDetails = JSON.parse(dayDetailsElement.textContent);
    }
});

/**
 * Muestra el modal con los detalles de eventos del día seleccionado
 * @param {string} dateStr - Fecha en formato ISO (YYYY-MM-DD)
 */
function showDayDetails(dateStr) {
    const events = dayDetails[dateStr];
    if (!events || events.length === 0) {
        return; // No mostrar modal si no hay eventos
    }

    const modal = document.getElementById('dayModal');
    const modalDate = document.getElementById('modalDate');
    const modalEvents = document.getElementById('modalEvents');

    // Formatear fecha
    const date = new Date(dateStr + 'T00:00:00');
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    modalDate.textContent = date.toLocaleDateString('es-ES', options);

    // Renderizar eventos
    let html = '';
    events.forEach(event => {
        html += `
            <div class="event-card">
                <div class="event-user">${escapeHtml(event.user)}</div>
                <div class="event-title">${escapeHtml(event.title)}</div>
                <div class="event-time">${escapeHtml(event.start)} - ${escapeHtml(event.end)}</div>
                ${event.description ? `<div style="margin-top: 0.5rem; font-size: 0.9rem; color: var(--day-text);">${escapeHtml(event.description)}</div>` : ''}
                ${event.link ? `<div style="margin-top: 0.5rem;"><a href="${escapeHtml(event.link)}" target="_blank" style="color: var(--event-dot); font-size: 0.85rem;">Ver enlace →</a></div>` : ''}
                <div class="event-actions">
                    <a href="/availability/${event.id}/update/" class="btn-small btn-edit">Editar</a>
                    <a href="/availability/${event.id}/delete/" class="btn-small btn-delete">Eliminar</a>
                </div>
            </div>
        `;
    });
    modalEvents.innerHTML = html;

    modal.style.display = 'block';
}

/**
 * Cierra el modal
 */
function closeModal() {
    const modal = document.getElementById('dayModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Escapa caracteres HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} - Texto escapado
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cerrar modal al hacer clic fuera
window.onclick = function(event) {
    const modal = document.getElementById('dayModal');
    if (event.target === modal) {
        closeModal();
    }
}

// Cerrar modal con tecla ESC
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeModal();
    }
});