(() => {
  const PANEL_ID = "model-capabilities-panel";
  const BUTTON_ID = "model-capabilities-button";

  function normalizeRate(value) {
    const numericValue = Number(value || 0);
    if (!Number.isFinite(numericValue)) return 0;
    return numericValue > 1 ? numericValue / 100 : numericValue;
  }

  function formatPercent(value, digits = 2) {
    return `${(normalizeRate(value) * 100).toFixed(digits)}%`;
  }

  function formatScore(value, digits = 3) {
    const numericValue = Number(value || 0);
    return Number.isFinite(numericValue) ? numericValue.toFixed(digits) : "0.000";
  }

  function formatLatency(value, digits = 5) {
    const numericValue = Number(value || 0);
    return Number.isFinite(numericValue) ? numericValue.toFixed(digits) : "0.00000";
  }

  async function api(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      throw new Error(data.message || "Request failed");
    }
    return data;
  }

  function closePanel() {
    document.getElementById(PANEL_ID)?.classList.remove("open");
    document.body.classList.remove("capabilities-open");
  }

  function renderModelDetails(panel, model, metrics, isActive) {
    const requiredColumns = (model.required_columns || [])
      .map((column) => `<li>${column}</li>`)
      .join("");

    const recordLabel = panel.dataset.isAdmin === "true" ? "历史检测样本" : "我的检测样本";
    const attackLabel = panel.dataset.isAdmin === "true" ? "历史异常样本" : "我的异常样本";
    const benignLabel = panel.dataset.isAdmin === "true" ? "历史正常样本" : "我的正常样本";

    panel.querySelector("[data-role='detail']").innerHTML = `
      <div class="capability-header">
        <div>
          <h3>${model.model_name}</h3>
          <p>${model.model_type || "Unknown"}${isActive ? ' · 当前启用' : ""}</p>
        </div>
        <span class="status-pill ${isActive ? "pill-safe" : "pill-muted"}">${isActive ? "Active" : "Inactive"}</span>
      </div>
      <div class="capability-metric-grid">
        <article class="capability-metric-card">
          <span>Accuracy</span>
          <strong>${formatPercent(metrics.accuracy ?? model.accuracy)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>Precision</span>
          <strong>${formatScore(metrics.precision ?? model.precision)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>Recall</span>
          <strong>${formatScore(metrics.recall ?? model.recall)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>F1-Score</span>
          <strong>${formatScore(metrics.f1_score ?? model.f1_score)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>FPR</span>
          <strong>${formatScore(metrics.fpr ?? model.fpr, 6)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>FNR</span>
          <strong>${formatScore(metrics.fnr ?? model.fnr, 6)}</strong>
        </article>
        <article class="capability-metric-card">
          <span>Latency</span>
          <strong>${formatLatency(metrics.inference_latency_ms ?? model.inference_latency_ms, 3)} ms</strong>
        </article>
        <article class="capability-metric-card">
          <span>Test Samples</span>
          <strong>${metrics.test_samples || 0}</strong>
        </article>
        <article class="capability-metric-card">
          <span>${recordLabel}</span>
          <strong>${metrics.total_samples || 0}</strong>
        </article>
        <article class="capability-metric-card">
          <span>${attackLabel}</span>
          <strong>${metrics.total_attacks || 0}</strong>
        </article>
        <article class="capability-metric-card">
          <span>${benignLabel}</span>
          <strong>${metrics.total_normals || 0}</strong>
        </article>
        <article class="capability-metric-card">
          <span>Required Columns</span>
          <strong>${(model.required_columns || []).length}</strong>
        </article>
      </div>
      <section class="capability-section">
        <h4>数据格式要求</h4>
        <p>${model.dataset_format || "暂无格式说明"}</p>
      </section>
      <section class="capability-section">
        <h4>补充说明</h4>
        <p>${model.description || "暂无补充说明"}</p>
      </section>
      <section class="capability-section">
        <h4>必需字段</h4>
        ${requiredColumns ? `<ol class="capability-columns">${requiredColumns}</ol>` : "<p>暂无字段清单</p>"}
      </section>
    `;
  }

  async function openPanel() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;

    panel.classList.add("open");
    document.body.classList.add("capabilities-open");
    panel.querySelector("[data-role='detail']").innerHTML = "<p class='upload-note'>正在加载模型能力...</p>";

    try {
      const [{ items, active_model_id: activeModelId }, me] = await Promise.all([
        api("/api/models"),
        api("/api/auth/me"),
      ]);
      const isAdmin = Boolean(me.user && me.user.role === "admin");
      panel.dataset.isAdmin = isAdmin ? "true" : "false";

      const select = panel.querySelector("select");
      select.innerHTML = items
        .map((item) => `<option value="${item.id}" ${item.id === activeModelId ? "selected" : ""}>${item.model_name}</option>`)
        .join("");

      async function loadSelectedModel() {
        const selectedId = Number(select.value);
        const model = items.find((item) => item.id === selectedId) || items[0];
        if (!model) {
          panel.querySelector("[data-role='detail']").innerHTML = "<p class='upload-note'>当前没有可展示的模型。</p>";
          return;
        }
        const metricsResponse = await api(`/api/metrics?model_id=${model.id}`);
        renderModelDetails(panel, model, metricsResponse.data || {}, model.id === activeModelId);
      }

      select.onchange = () => {
        loadSelectedModel().catch((error) => {
          panel.querySelector("[data-role='detail']").innerHTML = `<p class='upload-note text-danger'>${error.message}</p>`;
        });
      };

      await loadSelectedModel();
    } catch (error) {
      panel.querySelector("[data-role='detail']").innerHTML = `<p class='upload-note text-danger'>${error.message}</p>`;
    }
  }

  function ensurePanel() {
    if (document.getElementById(PANEL_ID)) return;

    const panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.className = "model-capabilities-panel";
    panel.innerHTML = `
      <div class="capability-panel-head">
        <div>
          <p class="eyebrow">Model Capability</p>
          <h2>模型能力</h2>
        </div>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-role="close">关闭</button>
      </div>
      <div class="mb-3">
        <label class="form-label">选择模型</label>
        <select class="form-select"></select>
      </div>
      <div data-role="detail"></div>
    `;
    panel.querySelector("[data-role='close']").addEventListener("click", closePanel);
    document.body.appendChild(panel);
  }

  function ensureButton() {
    const nav = document.querySelector(".sidebar .nav");
    if (!nav || document.getElementById(BUTTON_ID)) return;

    const button = document.createElement("button");
    button.id = BUTTON_ID;
    button.type = "button";
    button.className = "nav-link side-link capability-trigger";
    button.innerHTML = "<span>模型能力</span><small>查看模型评估指标与输入要求</small>";
    button.addEventListener("click", openPanel);
    nav.appendChild(button);
  }

  function bootstrap() {
    if (!document.querySelector(".app-shell")) return;
    ensurePanel();
    ensureButton();
  }

  let observer = null;

  function startObserver() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      bootstrap();
      if (document.getElementById(BUTTON_ID) && document.getElementById(PANEL_ID)) {
        observer.disconnect();
        observer = null;
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bootstrap();
    if (!document.getElementById(BUTTON_ID) || !document.getElementById(PANEL_ID)) {
      startObserver();
    }
  });
})();
