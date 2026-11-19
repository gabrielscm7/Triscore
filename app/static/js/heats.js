(function () {
  "use strict";

  const list = document.getElementById("heat-list");
  const unassignedZone = document.getElementById("unassigned-zone");
  const generatorCategory = document.getElementById("generator-category");
  const generatorMode = document.getElementById("generator-mode");
  const generatorCount = document.getElementById("generator-count");
  const baseUrl = window.TRISCORE_EVENT_URL || "";
  const heatLimit = Number(window.TRISCORE_HEAT_LIMIT || 0);

  let dragState = null;

  function clearHints() {
    document.querySelectorAll(".drop-active, .heat-drop-target").forEach((element) => {
      element.classList.remove("drop-active", "heat-drop-target");
    });
    document.querySelectorAll(".athlete-row.drop-before").forEach((element) => {
      element.classList.remove("drop-before");
    });
  }

  function updateGeneratorCount() {
    if (!generatorCategory || !generatorMode || !generatorCount) return;
    const option = generatorCategory.selectedOptions[0];
    if (!option) {
      generatorCount.textContent = "Selecione uma categoria.";
      return;
    }
    const mode = generatorMode.value;
    const available = Number(
      mode === "M" ? option.dataset.male : mode === "F" ? option.dataset.female : option.dataset.mixed
    );
    if (!available) {
      generatorCount.textContent = "Nenhum atleta disponível neste grupo. Atletas já alocados não entram na geração.";
    } else if (heatLimit > 0) {
      const heatCount = Math.ceil(available / heatLimit);
      generatorCount.textContent =
        available + " atleta(s) disponível(is). Serão criadas " + heatCount +
        " bateria(s), com até " + heatLimit + " atletas cada.";
    } else {
      generatorCount.textContent = available + " atleta(s) disponível(is).";
    }
  }

  function chooseUsefulGeneratorDefaults() {
    if (!generatorCategory || !generatorMode) return;
    const options = Array.from(generatorCategory.options);
    const current = generatorCategory.selectedOptions[0];
    const mode = generatorMode.value;
    const currentCount = Number(
      current
        ? mode === "M"
          ? current.dataset.male
          : mode === "F"
            ? current.dataset.female
            : current.dataset.mixed
        : 0
    );
    if (currentCount > 0) return;

    const categoryWithAthletes = options.find((option) => {
      return (
        Number(option.dataset.male || 0) +
          Number(option.dataset.female || 0) +
          Number(option.dataset.mixed || 0) >
        0
      );
    });
    if (!categoryWithAthletes) return;
    generatorCategory.value = categoryWithAthletes.value;

    const selected = categoryWithAthletes;
    const availableModes = ["M", "F", "X"].filter(
      (item) =>
        Number(
          item === "M"
            ? selected.dataset.male
            : item === "F"
              ? selected.dataset.female
              : selected.dataset.mixed
        ) > 0
    );
    if (!availableModes.includes(mode) && availableModes.length) {
      generatorMode.value = availableModes[0];
    }
  }

  if (generatorCategory && generatorMode) {
    chooseUsefulGeneratorDefaults();
    generatorCategory.addEventListener("change", updateGeneratorCount);
    generatorMode.addEventListener("change", updateGeneratorCount);
    updateGeneratorCount();
  }

  function startDrag(event) {
    const heatHandle = event.target.closest("[data-heat-handle]");
    if (heatHandle) {
      const card = heatHandle.closest(".heat-card");
      if (!card) return;
      dragState = { type: "heat", heatId: Number(card.dataset.heatId) };
      card.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "heat:" + card.dataset.heatId);
      return;
    }

    const row = event.target.closest(".athlete-row");
    if (!row) return;
    dragState = {
      type: "athlete",
      athleteId: Number(row.dataset.athleteId),
      sourceHeatId: row.dataset.sourceHeat ? Number(row.dataset.sourceHeat) : null,
    };
    row.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", "athlete:" + row.dataset.athleteId);
  }

  function onDragOver(event) {
    if (!dragState) return;
    const card = event.target.closest(".heat-card");
    const inUnassigned = event.target.closest("#unassigned-zone");
    const row = event.target.closest(".athlete-row");

    if (dragState.type === "heat") {
      if (!card || Number(card.dataset.heatId) === dragState.heatId) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".heat-drop-target").forEach((element) => {
        if (element !== card) element.classList.remove("heat-drop-target");
      });
      card.classList.add("heat-drop-target");
      return;
    }

    if (card) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".heat-card.drop-active").forEach((element) => {
        if (element !== card) element.classList.remove("drop-active");
      });
      card.classList.add("drop-active");
      document.querySelectorAll(".athlete-row.drop-before").forEach((element) => {
        if (element !== row) element.classList.remove("drop-before");
      });
      if (row && row.dataset.sourceHeat && row.dataset.athleteId !== String(dragState.athleteId)) {
        row.classList.add("drop-before");
      }
      return;
    }

    if (inUnassigned) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      inUnassigned.classList.add("drop-active");
    }
  }

  async function callMove(athleteId, targetHeatId, beforeAthleteId) {
    await window.triscore.postJson(baseUrl + "/mover-atleta", {
      athlete_id: athleteId,
      target_heat_id: targetHeatId,
      before_athlete_id: beforeAthleteId,
    });
    window.location.reload();
  }

  async function callHeatOrder(heatIds) {
    await window.triscore.postJson(baseUrl + "/ordem", { heat_ids: heatIds });
    window.location.reload();
  }

  async function onDrop(event) {
    if (!dragState) return;
    const card = event.target.closest(".heat-card");
    const inUnassigned = event.target.closest("#unassigned-zone");
    const row = event.target.closest(".athlete-row");

    if (dragState.type === "heat") {
      if (!card) return;
      event.preventDefault();
      const targetHeatId = Number(card.dataset.heatId);
      if (targetHeatId === dragState.heatId) {
        clearHints();
        return;
      }
      const cards = Array.from(document.querySelectorAll(".heat-card"));
      const ids = cards.map((element) => Number(element.dataset.heatId));
      const from = ids.indexOf(dragState.heatId);
      const target = ids.indexOf(targetHeatId);
      if (from < 0 || target < 0) return;
      const rect = card.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      ids.splice(from, 1);
      let insertion = target + (after ? 1 : 0);
      if (from < insertion) insertion -= 1;
      ids.splice(insertion, 0, dragState.heatId);
      try {
        await callHeatOrder(ids);
      } catch (error) {
        window.triscore.showToast(error.message, true);
      } finally {
        clearHints();
      }
      return;
    }

    event.preventDefault();

    if (card) {
      const targetHeatId = Number(card.dataset.heatId);
      let beforeAthleteId = null;
      if (row && row.closest(".heat-card") === card) {
        const rowAthleteId = Number(row.dataset.athleteId);
        if (rowAthleteId === dragState.athleteId) {
          clearHints();
          return;
        }
        const rect = row.getBoundingClientRect();
        if (event.clientY > rect.top + rect.height / 2) {
          const next = row.nextElementSibling;
          beforeAthleteId =
            next && next.classList.contains("athlete-row")
              ? Number(next.dataset.athleteId)
              : null;
        } else {
          beforeAthleteId = rowAthleteId;
        }
      }
      try {
        await callMove(dragState.athleteId, targetHeatId, beforeAthleteId);
      } catch (error) {
        window.triscore.showToast(error.message, true);
      } finally {
        clearHints();
      }
      return;
    }

    if (inUnassigned) {
      try {
        await callMove(dragState.athleteId, null, null);
      } catch (error) {
        window.triscore.showToast(error.message, true);
      } finally {
        clearHints();
      }
    }
  }

  function endDrag() {
    if (dragState && dragState.type === "heat") {
      const card = document.querySelector(
        '.heat-card[data-heat-id="' + dragState.heatId + '"]'
      );
      if (card) card.classList.remove("dragging");
    }
    document.querySelectorAll(".athlete-row.dragging").forEach((row) => {
      row.classList.remove("dragging");
    });
    clearHints();
    dragState = null;
  }

  if (list) {
    document.addEventListener("dragstart", startDrag);
    document.addEventListener("dragover", onDragOver);
    document.addEventListener("drop", onDrop);
    document.addEventListener("dragend", endDrag);
  }
})();
