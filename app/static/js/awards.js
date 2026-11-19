(function () {
  "use strict";

  const body = document.body;
  const app = document.querySelector("[data-award-app]");
  const slides = Array.from(document.querySelectorAll("[data-slide-kind]"));
  const stage = document.querySelector(".awards-stage");
  const revealOrder = [3, 2, 1];
  const groupLabels = {
    0: "Revelar 3º lugar",
    1: "Revelar 2º lugar",
    2: "Revelar 1º lugar",
    3: "Pódio completo",
  };
  let currentSlide = 0;
  let revealStep = 0;

  const groupSelect = document.querySelector("[data-group-select]");
  const groupStatus = document.querySelector("[data-group-status]");
  const revealButton = document.querySelector("[data-reveal-next]");
  const resetButton = document.querySelector("[data-reveal-reset]");
  const prevButton = document.querySelector("[data-group-prev]");
  const nextButton = document.querySelector("[data-group-next]");
  const fullscreenButton = document.querySelector("[data-fullscreen]");
  const textButton = document.querySelector("[data-slide-text-open]");
  const eventId = app?.dataset.eventId;

  function currentSlideData() {
    return slides[currentSlide] || null;
  }

  function isGroupSlide(slide) {
    return slide?.dataset.slideKind === "group";
  }

  function updateControlLabels() {
    const slide = currentSlideData();
    if (!slide) return;
    const kind = slide.dataset.slideKind;
    if (resetButton) resetButton.disabled = kind !== "group";
    if (textButton) textButton.hidden = !app || kind !== "group";
    if (!revealButton) return;
    if (kind === "group") {
      revealButton.textContent = groupLabels[revealStep];
      revealButton.disabled = revealStep >= revealOrder.length;
    } else if (kind === "opening") {
      revealButton.textContent = "Ir para a primeira categoria";
      revealButton.disabled = false;
    } else {
      revealButton.textContent = "Voltar à abertura";
      revealButton.disabled = false;
    }
  }

  function applyReveal() {
    const slide = currentSlideData();
    if (!slide) return;
    slide.querySelectorAll(".podium-slot").forEach((slot) => {
      const position = Number(slot.dataset.position);
      const revealIndex = revealOrder.indexOf(position);
      slot.classList.toggle("is-revealed", revealStep > revealIndex);
    });
    updateControlLabels();
  }

  function showSlide(index) {
    if (!slides.length) return;
    currentSlide = Math.max(0, Math.min(index, slides.length - 1));
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("is-active", slideIndex === currentSlide);
    });
    revealStep = 0;
    if (groupSelect) groupSelect.value = String(currentSlide);
    if (groupStatus) {
      groupStatus.textContent = `Slide ${currentSlide + 1} de ${slides.length}`;
    }
    if (stage) stage.scrollTop = 0;
    applyReveal();
  }

  function revealNext() {
    const slide = currentSlideData();
    if (!slide) return;
    if (isGroupSlide(slide)) {
      if (revealStep < revealOrder.length) {
        revealStep += 1;
        applyReveal();
      }
      return;
    }
    if (slide.dataset.slideKind === "opening") {
      showSlide(1);
    } else {
      showSlide(0);
    }
  }

  if (app && slides.length) {
    showSlide(0);
    revealButton?.addEventListener("click", revealNext);
    resetButton?.addEventListener("click", () => {
      revealStep = 0;
      applyReveal();
    });
    prevButton?.addEventListener("click", () => showSlide(currentSlide - 1));
    nextButton?.addEventListener("click", () => showSlide(currentSlide + 1));
    groupSelect?.addEventListener("change", () => {
      showSlide(Number(groupSelect.value));
    });
  } else {
    if (textButton) textButton.hidden = true;
    if (resetButton) resetButton.disabled = true;
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch (error) {
      // O navegador pode bloquear a solicitação sem interação direta.
    }
  }

  function updateFullscreenLabel() {
    if (!fullscreenButton) return;
    fullscreenButton.textContent = document.fullscreenElement
      ? "Sair da tela cheia"
      : "Tela cheia";
  }

  fullscreenButton?.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", updateFullscreenLabel);
  updateFullscreenLabel();

  const dialog = document.querySelector("[data-settings-dialog]");
  const settingsForm = document.querySelector("[data-theme-form]");
  const openSettings = document.querySelector("[data-settings-open]");
  const closeSettingsButtons = document.querySelectorAll("[data-settings-close]");
  const presetSelect = document.querySelector("[data-theme-preset]");
  const layoutSelect = document.querySelector("[data-theme-layout]");
  const accentInput = document.querySelector("[data-theme-accent]");
  const backgroundInput = document.querySelector("[data-theme-background]");
  const textInput = document.querySelector("[data-theme-text]");
  const opacityInput = document.querySelector("[data-bg-opacity]");
  const dimInput = document.querySelector("[data-bg-dim]");
  const opacityOutput = document.querySelector("[data-opacity-output]");
  const dimOutput = document.querySelector("[data-dim-output]");
  const preview = document.querySelector("[data-layout-preview]");
  const previewBanner = document.querySelector("[data-preview-banner]");
  const backgroundLayer = document.querySelector(".awards-background");
  const bannerImageInput = document.querySelector("[data-asset-banner]");
  const backgroundImageInput = document.querySelector("[data-asset-background]");
  const fontInput = document.querySelector("[data-asset-font]");
  let originalThemeState = null;
  let previewObjectUrl = null;
  let previewBackgroundUrl = null;
  let previewFontFace = null;

  function hexToRgb(hex) {
    return [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16),
    ];
  }

  function luminance(hex) {
    const channels = hexToRgb(hex).map((value) => {
      const channel = value / 255;
      return channel <= 0.04045
        ? channel / 12.92
        : Math.pow((channel + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  }

  function rgba(hex, alpha) {
    const [red, green, blue] = hexToRgb(hex);
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
  }

  function applyTheme(accent, background, text) {
    const dark = luminance(background) < 0.45;
    body.style.setProperty("--award-bg", background);
    body.style.setProperty("--award-accent", accent);
    body.style.setProperty("--award-text", text);
    body.style.setProperty(
      "--award-panel",
      dark ? "rgba(255, 255, 255, 0.10)" : "rgba(255, 255, 255, 0.74)"
    );
    body.style.setProperty(
      "--award-panel-strong",
      dark ? "rgba(255, 255, 255, 0.16)" : "rgba(255, 255, 255, 0.92)"
    );
    body.style.setProperty(
      "--award-border",
      dark ? "rgba(255, 255, 255, 0.22)" : "rgba(23, 50, 58, 0.14)"
    );
    body.style.setProperty("--award-muted", rgba(text, 0.7));
    body.style.setProperty("--award-accent-soft", rgba(accent, 0.2));
  }

  function setCustomEnabled(enabled) {
    [accentInput, backgroundInput, textInput].forEach((input) => {
      if (input) input.disabled = !enabled;
    });
  }

  function selectedPresetData() {
    return presetSelect?.selectedOptions?.[0] || null;
  }

  function updateRanges() {
    if (opacityInput) {
      body.style.setProperty(
        "--award-bg-opacity",
        String(Number(opacityInput.value) / 100)
      );
      if (opacityOutput) opacityOutput.value = `${opacityInput.value}%`;
    }
    if (dimInput) {
      body.style.setProperty(
        "--award-bg-dim",
        String(Number(dimInput.value) / 100)
      );
      if (dimOutput) dimOutput.value = `${dimInput.value}%`;
    }
  }

  function previewPreset() {
    if (!presetSelect) return;
    const option = selectedPresetData();
    if (!option) return;
    const isCustom = presetSelect.value === "custom";
    setCustomEnabled(isCustom);
    if (!isCustom) {
      if (accentInput) accentInput.value = option.dataset.accent;
      if (backgroundInput) backgroundInput.value = option.dataset.background;
      if (textInput) textInput.value = option.dataset.text;
    }
    const accent = accentInput?.value || option.dataset.accent;
    const background = backgroundInput?.value || option.dataset.background;
    const text = textInput?.value || option.dataset.text;
    applyTheme(accent, background, text);
  }

  function applyPreviewLayout() {
    if (!layoutSelect) return;
    body.dataset.layout = layoutSelect.value;
    if (preview) preview.dataset.previewLayout = layoutSelect.value;
  }

  function restoreThemePreview() {
    if (originalThemeState === null) return;
    body.setAttribute("style", originalThemeState.style);
    body.dataset.layout = originalThemeState.layout;
    if (preview) {
      preview.dataset.previewLayout = originalThemeState.previewLayout;
      preview.setAttribute("style", originalThemeState.previewStyle);
    }
    if (previewBanner) {
      previewBanner.setAttribute("style", originalThemeState.bannerStyle);
    }
    if (backgroundLayer) {
      backgroundLayer.setAttribute("style", originalThemeState.backgroundStyle);
    }
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = null;
    }
    if (previewBackgroundUrl) {
      URL.revokeObjectURL(previewBackgroundUrl);
      previewBackgroundUrl = null;
    }
    if (previewFontFace) {
      document.fonts.delete(previewFontFace);
      previewFontFace = null;
    }
    originalThemeState = null;
  }

  function closeSettingsPreview() {
    restoreThemePreview();
    settingsForm?.reset();
    setCustomEnabled(presetSelect?.value === "custom");
  }

  if (dialog && openSettings) {
    openSettings.addEventListener("click", () => {
      originalThemeState = {
        style: body.getAttribute("style") || "",
        layout: body.dataset.layout || "classic",
        previewLayout: preview?.dataset.previewLayout || "classic",
        previewStyle: preview?.getAttribute("style") || "",
        bannerStyle: previewBanner?.getAttribute("style") || "",
        backgroundStyle: backgroundLayer?.getAttribute("style") || "",
      };
      dialog.showModal();
      previewPreset();
      updateRanges();
      applyPreviewLayout();
    });
    closeSettingsButtons.forEach((button) => {
      button.addEventListener("click", () => {
        dialog.close();
        closeSettingsPreview();
      });
    });
    dialog.addEventListener("cancel", closeSettingsPreview);
    presetSelect?.addEventListener("change", previewPreset);
    layoutSelect?.addEventListener("change", applyPreviewLayout);
    [accentInput, backgroundInput, textInput].forEach((input) => {
      input?.addEventListener("input", () => {
        if (presetSelect?.value !== "custom") return;
        applyTheme(
          accentInput.value,
          backgroundInput.value,
          textInput.value
        );
      });
    });
    opacityInput?.addEventListener("input", updateRanges);
    dimInput?.addEventListener("input", updateRanges);

    bannerImageInput?.addEventListener("change", () => {
      const file = bannerImageInput.files?.[0];
      if (!file || !previewBanner) return;
      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = URL.createObjectURL(file);
      previewBanner.style.backgroundImage = `url("${previewObjectUrl}")`;
    });
    backgroundImageInput?.addEventListener("change", () => {
      const file = backgroundImageInput.files?.[0];
      if (!file || !backgroundLayer) return;
      if (previewBackgroundUrl) URL.revokeObjectURL(previewBackgroundUrl);
      previewBackgroundUrl = URL.createObjectURL(file);
      backgroundLayer.style.backgroundImage = `url("${previewBackgroundUrl}")`;
    });
    fontInput?.addEventListener("change", async () => {
      const file = fontInput.files?.[0];
      if (!file) return;
      try {
        const face = new FontFace("AwardPreview", await file.arrayBuffer());
        await face.load();
        if (previewFontFace) document.fonts.delete(previewFontFace);
        document.fonts.add(face);
        previewFontFace = face;
        body.style.setProperty(
          "--award-display-font",
          "'AwardPreview', 'Fira Sans', sans-serif"
        );
      } catch (error) {
        // A validação definitiva acontece no servidor.
      }
    });
  }

  const textDialog = document.querySelector("[data-slide-text-dialog]");
  const textForm = document.querySelector("[data-slide-text-form]");
  const textTitle = document.querySelector("[data-slide-text-title]");
  const textCall = document.querySelector("[data-slide-text-call]");
  const closeTextButtons = document.querySelectorAll("[data-slide-text-close]");
  let originalTextState = null;

  function openTextEditor() {
    const slide = currentSlideData();
    if (!textDialog || !textForm || !slide || !isGroupSlide(slide)) return;
    const categoryId = slide.dataset.categoryId;
    const groupSex = slide.dataset.groupSex;
    const heading = slide.querySelector("[data-slide-heading]");
    const call = slide.querySelector("[data-slide-call]");
    originalTextState = {
      heading: heading?.textContent || "",
      call: call?.textContent || "",
    };
    textForm.action = `/premiacao/${eventId}/slides/${categoryId}/${groupSex}`;
    if (textTitle) {
      textTitle.value = slide.dataset.customTitle || "";
      textTitle.placeholder = slide.dataset.defaultTitle || "";
    }
    if (textCall) textCall.value = slide.dataset.customCallText || "";
    textDialog.showModal();
  }

  function restoreTextPreview() {
    if (!originalTextState) return;
    const slide = currentSlideData();
    const heading = slide?.querySelector("[data-slide-heading]");
    const call = slide?.querySelector("[data-slide-call]");
    if (heading) heading.textContent = originalTextState.heading;
    if (call) call.textContent = originalTextState.call;
    originalTextState = null;
  }

  textButton?.addEventListener("click", openTextEditor);
  closeTextButtons.forEach((button) => {
    button.addEventListener("click", () => {
      textDialog?.close();
      restoreTextPreview();
      textForm?.reset();
    });
  });
  textDialog?.addEventListener("cancel", () => {
    restoreTextPreview();
    textForm?.reset();
  });
  textTitle?.addEventListener("input", () => {
    const slide = currentSlideData();
    const heading = slide?.querySelector("[data-slide-heading]");
    if (heading) {
      heading.textContent = textTitle.value || slide.dataset.defaultTitle || "";
    }
  });
  textCall?.addEventListener("input", () => {
    const slide = currentSlideData();
    const call = slide?.querySelector("[data-slide-call]");
    if (call) call.textContent = textCall.value;
  });

  document.addEventListener("keydown", (event) => {
    if (dialog?.open || textDialog?.open) return;
    const target = event.target;
    if (
      target instanceof HTMLElement &&
      (target.matches("input, select, textarea") || target.isContentEditable)
    ) {
      return;
    }
    if (
      event.key === " " &&
      target instanceof HTMLElement &&
      target.closest("button, a")
    ) {
      return;
    }
    if (!slides.length) {
      if (event.key.toLowerCase() === "f") {
        event.preventDefault();
        toggleFullscreen();
      }
      return;
    }
    if (event.key === " ") {
      event.preventDefault();
      revealNext();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      showSlide(currentSlide + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      showSlide(currentSlide - 1);
    } else if (event.key.toLowerCase() === "r") {
      event.preventDefault();
      revealStep = 0;
      applyReveal();
    } else if (event.key.toLowerCase() === "f") {
      event.preventDefault();
      toggleFullscreen();
    }
  });
})();
