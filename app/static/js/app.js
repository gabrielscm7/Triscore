(function () {
  "use strict";

  const flashParams = ["ok", "warning", "error"];
  const url = new URL(window.location.href);
  let changed = false;
  flashParams.forEach((param) => {
    if (url.searchParams.has(param)) {
      url.searchParams.delete(param);
      changed = true;
    }
  });
  if (changed) {
    window.history.replaceState({}, "", url.toString());
  }

  document.querySelectorAll(".flash-close").forEach((button) => {
    button.addEventListener("click", () => {
      const flash = button.closest(".flash");
      if (flash) flash.remove();
    });
  });

  document.addEventListener("click", (event) => {
    const control = event.target.closest("[data-confirm]");
    if (control && !window.confirm(control.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });

  window.triscore = {
    async postJson(target, payload) {
      const response = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      let data = {};
      try {
        data = await response.json();
      } catch (error) {
        data = {};
      }
      if (!response.ok) {
        throw new Error(data.detail || "Não foi possível concluir a operação.");
      }
      return data;
    },
    showToast(message, isError) {
      const toast = document.createElement("div");
      toast.className = "toast" + (isError ? " toast-error" : "");
      toast.textContent = message;
      document.body.appendChild(toast);
      window.setTimeout(() => toast.remove(), 4200);
    },
  };
})();
