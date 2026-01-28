document.addEventListener("DOMContentLoaded", () => {
  let draggedCard = null;

  // DRAG START
  document.querySelectorAll(".neu-task-card").forEach(card => {
    card.addEventListener("dragstart", e => {
      draggedCard = card;
      card.classList.add("dragging");
    });

    card.addEventListener("dragend", () => {
      draggedCard = null;
      card.classList.remove("dragging");
    });
  });

  // DROP ZONES
  document.querySelectorAll(".neu-kanban-col").forEach(col => {
    col.addEventListener("dragover", e => {
      e.preventDefault();
      col.classList.add("drag-over");
    });

    col.addEventListener("dragleave", () => {
      col.classList.remove("drag-over");
    });

    col.addEventListener("drop", e => {
      e.preventDefault();
      col.classList.remove("drag-over");

      if (!draggedCard) return;

      const taskId = draggedCard.dataset.taskId;
      const fromStatus = draggedCard.dataset.status;
      const toStatus = col.dataset.status;

      if (fromStatus === toStatus) return;

      // ⚠️ REGLAS FRONT (solo UX, backend valida de verdad)
      if (fromStatus === "completed" && toStatus !== "completed") {
        const reason = prompt("Motivo para regresar la tarea:");
        if (!reason) return;
        updateStatus(taskId, toStatus, reason);
      } else {
        updateStatus(taskId, toStatus);
      }
    });
  });

  function updateStatus(taskId, status, comment = "") {
    fetch(`/api/tasks/${taskId}/move/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify({
        status: status,
        comment: comment
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.ok) {
        location.reload();
      } else {
        alert(data.error || "No permitido");
      }
    })
    .catch(() => alert("Error de red"));
  }

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      document.cookie.split(";").forEach(cookie => {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        }
      });
    }
    return cookieValue;
  }
});
