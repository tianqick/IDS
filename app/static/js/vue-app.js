const { createApp, reactive, ref, computed, watch, onMounted, nextTick } = Vue;

createApp({
  setup() {
    const appState = reactive({
      loading: false,
      initializing: false,
      uploading: false,
      user: null,
      currentView: "dashboard",
      loginForm: { username: "", password: "" },
      userForm: { username: "", password: "", role: "user" },
      userEditForm: { id: null, username: "", password: "", role: "user" },
      modelForm: {
        model_name: "",
        model_path: "",
        model_type: "PyTorch",
        accuracy: "",
        precision: "",
        recall: "",
        f1_score: "",
        fpr: "",
        fnr: "",
        inference_latency_ms: "",
        description: "",
        dataset_format: "",
        required_columns_text: "",
        is_active: false,
      },
      dashboard: null,
      serverAccess: null,
      records: [],
      historyItems: [],
      recordDetail: null,
      alarms: [],
      alarmPagination: {
        page: 1,
        pageSize: 20,
        total: 0,
        pages: 0,
        hasPrev: false,
        hasNext: false,
      },
      metrics: null,
      trafficMonitor: null,
      trafficInterfaces: [],
      models: [],
      activeModelId: null,
      selectedModelId: null,
      selectedTrafficInterface: "",
      trafficTestPcapName: "",
      testingTrafficExtract: false,
      users: [],
      activeTask: null,
      message: "",
      messageType: "success",
      recordKeyword: "",
      historyKeyword: "",
      alarmStatusFilter: "all",
    });

    const uploadFile = ref(null);
    const modelFile = ref(null);
    const taskPollTimer = ref(null);
    const trafficMonitorTimer = ref(null);
    const attackChart = ref(null);
    const trendChart = ref(null);
    const isAuthenticated = computed(() => Boolean(appState.user));
    const isAdmin = computed(() => appState.user?.role === "admin");
    const selectedModel = computed(() =>
      appState.models.find((item) => item.id === appState.selectedModelId)
      || appState.models.find((item) => item.is_active)
      || null,
    );

    const navItems = computed(() => {
      const items = [
        { key: "dashboard", label: "系统首页", hint: "总览与图表" },
        { key: "upload", label: "上传检测", hint: "提交 CSV 并执行检测" },
        { key: "results", label: "检测结果", hint: "结果分析与详情" },
        { key: "history", label: "历史记录", hint: "时间线与任务追踪" },
      ];
      if (isAdmin.value) {
        items.push({ key: "alarms", label: "告警中心", hint: "告警处理与状态更新" });
        items.push({ key: "metrics", label: "性能评估", hint: "实验指标展示" });
        items.push({ key: "trafficMonitor", label: "网站流量", hint: "自动巡检流量特征" });
        items.push({ key: "models", label: "模型管理", hint: "模型信息查看" });
        items.push({ key: "users", label: "用户管理", hint: "管理员与普通用户权限" });
      }
      return items;
    });

    const filteredRecords = computed(() => {
      const keyword = appState.recordKeyword.trim().toLowerCase();
      if (!keyword) return appState.records;
      return appState.records.filter((item) =>
        [item.source_file, String(item.id), item.detect_time].some((value) =>
          String(value).toLowerCase().includes(keyword),
        ),
      );
    });

    const filteredHistoryItems = computed(() => {
      const keyword = appState.historyKeyword.trim().toLowerCase();
      if (!keyword) return appState.historyItems;
      return appState.historyItems.filter((item) =>
        [item.source_file, item.operator, item.status, String(item.id), item.detect_time].some((value) =>
          String(value).toLowerCase().includes(keyword),
        ),
      );
    });

    const alarmPageNumbers = computed(() => {
      const totalPages = Number(appState.alarmPagination.pages) || 0;
      const currentPage = Number(appState.alarmPagination.page) || 1;
      if (totalPages <= 0) return [];
      const start = Math.max(1, currentPage - 2);
      const end = Math.min(totalPages, start + 4);
      const adjustedStart = Math.max(1, end - 4);
      return Array.from({ length: end - adjustedStart + 1 }, (_, index) => adjustedStart + index);
    });

    function notify(message, type = "success") {
      appState.message = message;
      appState.messageType = type;
      window.clearTimeout(notify.timer);
      notify.timer = window.setTimeout(() => {
        if (appState.message === message) appState.message = "";
      }, 3200);
    }

    async function api(url, options = {}) {
      const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.message || "请求失败");
      }
      return data;
    }

    function stopTaskPolling() {
      if (taskPollTimer.value) {
        window.clearInterval(taskPollTimer.value);
        taskPollTimer.value = null;
      }
    }

    function stopTrafficMonitorPolling() {
      if (trafficMonitorTimer.value) {
        window.clearInterval(trafficMonitorTimer.value);
        trafficMonitorTimer.value = null;
      }
    }

    function startTrafficMonitorPolling() {
      stopTrafficMonitorPolling();
      if (!isAuthenticated.value || !isAdmin.value) return;
      if (appState.currentView !== "trafficMonitor") return;
      trafficMonitorTimer.value = window.setInterval(() => {
        loadTrafficMonitor().catch(() => {});
      }, 3000);
    }

    function renderAccessQRCodes() {
      const url = appState.serverAccess?.recommended_url || "";
      const targets = ["accessQrLogin", "accessQrDashboard"];
      for (const targetId of targets) {
        const element = document.getElementById(targetId);
        if (!element) continue;
        element.innerHTML = "";
        if (!url || !window.QRCode) continue;
        new window.QRCode(element, {
          text: url,
          width: 132,
          height: 132,
          correctLevel: window.QRCode.CorrectLevel.M,
        });
      }
    }

    watch(
      () => appState.alarmStatusFilter,
      async (value, oldValue) => {
        if (value === oldValue || appState.currentView !== "alarms" || !isAdmin.value) return;
        appState.alarmPagination.page = 1;
        await loadAlarms();
      },
    );

    watch(
      () => appState.alarmPagination.pageSize,
      async (value, oldValue) => {
        if (value === oldValue || appState.currentView !== "alarms" || !isAdmin.value) return;
        appState.alarmPagination.page = 1;
        await loadAlarms();
      },
    );

    watch(
      () => [appState.serverAccess?.recommended_url, appState.currentView, isAuthenticated.value],
      async () => {
        await nextTick();
        renderAccessQRCodes();
      },
    );

    async function pollTask(taskId, silent = false) {
      try {
        const data = await api(`/api/tasks/${taskId}`);
        appState.activeTask = data.task;
        if (data.task.status === "completed") {
          stopTaskPolling();
          appState.uploading = false;
          notify("后台检测任务已完成。");
          await loadRecords();
          await loadHistory();
          await loadDashboard();
          if (data.task.record_id) {
            await loadRecordDetail(data.task.record_id);
          }
        } else if (data.task.status === "failed") {
          stopTaskPolling();
          appState.uploading = false;
          notify(data.task.message || "任务执行失败。", "danger");
        }
      } catch (error) {
        if (!silent) {
          notify(error.message, "danger");
        }
      }
    }

    function startTaskPolling(taskId) {
      stopTaskPolling();
      taskPollTimer.value = window.setInterval(() => pollTask(taskId, true), 2000);
    }

    async function loadCurrentUser() {
      const data = await api("/api/auth/me");
      appState.user = data.user;
      appState.serverAccess = data.server_access || null;
      if (data.authenticated) {
        await loadViewData(appState.currentView);
      }
    }

    async function login() {
      appState.loading = true;
      try {
        const data = await api("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(appState.loginForm),
        });
        appState.user = data.user;
        appState.loginForm.password = "";
        appState.currentView = "dashboard";
        notify("登录成功。");
        await loadViewData("dashboard");
      } catch (error) {
        notify(error.message, "danger");
      } finally {
        appState.loading = false;
      }
    }

    async function logout() {
      stopTaskPolling();
      stopTrafficMonitorPolling();
      await api("/api/auth/logout", { method: "POST" });
      appState.user = null;
      appState.currentView = "dashboard";
      appState.dashboard = null;
      appState.records = [];
      appState.historyItems = [];
      appState.recordDetail = null;
      appState.alarms = [];
      appState.metrics = null;
      appState.trafficMonitor = null;
      appState.models = [];
      appState.users = [];
      appState.activeTask = null;
      notify("已退出登录。");
    }

    async function initDemo() {
      appState.initializing = true;
      try {
        await api("/api/auth/init-demo", { method: "POST" });
        notify("演示账号已初始化。管理员：admin/admin123，普通用户：user/user123");
      } catch (error) {
        notify(error.message, "danger");
      } finally {
        appState.initializing = false;
      }
    }

    async function loadDashboard() {
      const data = await api("/api/dashboard");
      appState.dashboard = data.data;
      await nextTick();
      renderCharts();
    }

    async function loadRecords() {
      const data = await api("/api/records");
      appState.records = data.items;
    }

    async function loadHistory() {
      const data = await api("/api/history");
      appState.historyItems = data.items;
    }

    async function loadRecordDetail(recordId) {
      const data = await api(`/api/records/${recordId}`);
      appState.recordDetail = data;
      appState.currentView = "resultDetail";
    }

    async function loadAlarms() {
      const query = new URLSearchParams({
        page: String(appState.alarmPagination.page || 1),
        page_size: String(appState.alarmPagination.pageSize || 20),
        status: appState.alarmStatusFilter || "all",
      });
      const data = await api(`/api/alarms?${query.toString()}`);
      appState.alarms = data.items;
      appState.alarmPagination = {
        page: data.pagination?.page || 1,
        pageSize: data.pagination?.page_size || 20,
        total: data.pagination?.total || 0,
        pages: data.pagination?.pages || 0,
        hasPrev: Boolean(data.pagination?.has_prev),
        hasNext: Boolean(data.pagination?.has_next),
      };
    }

    async function changeAlarmStatusFilter() {
      appState.alarmPagination.page = 1;
      await loadAlarms();
    }

    async function changeAlarmPageSize() {
      appState.alarmPagination.page = 1;
      await loadAlarms();
    }

    async function goToAlarmPage(page) {
      const targetPage = Number(page) || 1;
      if (targetPage < 1 || targetPage === appState.alarmPagination.page) return;
      if (appState.alarmPagination.pages && targetPage > appState.alarmPagination.pages) return;
      appState.alarmPagination.page = targetPage;
      await loadAlarms();
    }

    async function loadMetrics() {
      const query = appState.selectedModelId ? `?model_id=${appState.selectedModelId}` : "";
      const data = await api(`/api/metrics${query}`);
      appState.metrics = data.data;
    }

    async function loadTrafficMonitor() {
      const data = await api("/api/traffic-monitor");
      appState.trafficMonitor = data.data;
      appState.selectedTrafficInterface = data.data.capture_interface || "";
      if (!appState.trafficTestPcapName) {
        appState.trafficTestPcapName = data.data.last_generated_pcap || "";
      }
    }

    async function loadTrafficInterfaces() {
      const data = await api("/api/traffic-monitor/interfaces");
      appState.trafficInterfaces = data.items || [];
    }

    async function saveTrafficInterface() {
      try {
        if (!appState.selectedTrafficInterface) {
          notify("请先选择抓包网卡。", "danger");
          return;
        }
        const data = await api("/api/traffic-monitor/config", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ capture_interface: appState.selectedTrafficInterface }),
        });
        appState.trafficMonitor = data.data;
        notify("抓包网卡已保存。");
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function loadModels() {
      const data = await api("/api/models");
      appState.models = data.items;
      appState.activeModelId = data.active_model_id;
      if (!appState.selectedModelId) {
        appState.selectedModelId = data.active_model_id || data.items[0]?.id || null;
      } else if (!data.items.some((item) => item.id === appState.selectedModelId)) {
        appState.selectedModelId = data.active_model_id || data.items[0]?.id || null;
      }
    }

    async function loadUsers() {
      const data = await api("/api/users");
      appState.users = data.items;
    }

    async function createModel() {
      try {
        if (!appState.modelForm.dataset_format.trim()) {
          notify("请先填写数据集格式说明。", "danger");
          return;
        }
        const formData = new FormData();
        formData.append("model_name", appState.modelForm.model_name.trim());
        formData.append("model_path", appState.modelForm.model_path.trim());
        formData.append("model_type", appState.modelForm.model_type.trim());
        formData.append("accuracy", appState.modelForm.accuracy === "" ? "0" : String(Number(appState.modelForm.accuracy)));
        formData.append("precision", appState.modelForm.precision === "" ? "0" : String(Number(appState.modelForm.precision)));
        formData.append("recall", appState.modelForm.recall === "" ? "0" : String(Number(appState.modelForm.recall)));
        formData.append("f1_score", appState.modelForm.f1_score === "" ? "0" : String(Number(appState.modelForm.f1_score)));
        formData.append("fpr", appState.modelForm.fpr === "" ? "0" : String(Number(appState.modelForm.fpr)));
        formData.append("fnr", appState.modelForm.fnr === "" ? "0" : String(Number(appState.modelForm.fnr)));
        formData.append("inference_latency_ms", appState.modelForm.inference_latency_ms === "" ? "0" : String(Number(appState.modelForm.inference_latency_ms)));
        formData.append("description", appState.modelForm.description.trim());
        formData.append("dataset_format", appState.modelForm.dataset_format.trim());
        formData.append("required_columns", appState.modelForm.required_columns_text);
        formData.append("is_active", appState.modelForm.is_active ? "true" : "");
        if (modelFile.value) formData.append("model_file", modelFile.value);
        await api("/api/models", {
          method: "POST",
          body: formData,
        });
        appState.modelForm = {
          model_name: "",
          model_path: "",
          model_type: "PyTorch",
          accuracy: "",
          precision: "",
          recall: "",
          f1_score: "",
          fpr: "",
          fnr: "",
          inference_latency_ms: "",
          description: "",
          dataset_format: "",
          required_columns_text: "",
          is_active: false,
        };
        modelFile.value = null;
        notify("模型已添加。");
        await loadModels();
        await loadMetrics();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function activateModel(model) {
      try {
        await api(`/api/models/${model.id}/activate`, { method: "POST" });
        appState.selectedModelId = model.id;
        notify("模型已设为当前使用。");
        await loadModels();
        if (appState.currentView === "metrics") await loadMetrics();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function deleteModel(model) {
      if (!window.confirm(`确定删除模型 ${model.model_name} 吗？`)) return;
      try {
        await api(`/api/models/${model.id}`, { method: "DELETE" });
        notify("模型已删除。");
        await loadModels();
        if (appState.currentView === "metrics") await loadMetrics();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function startTrafficMonitor() {
      try {
        const data = await api("/api/traffic-monitor/start", { method: "POST" });
        appState.trafficMonitor = data.data;
        startTrafficMonitorPolling();
        notify("网站流量监测已启动。");
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function stopTrafficMonitor() {
      try {
        const data = await api("/api/traffic-monitor/stop", { method: "POST" });
        appState.trafficMonitor = data.data;
        stopTrafficMonitorPolling();
        notify("网站流量监测已停止。");
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function testTrafficExtract() {
      try {
        if (!appState.trafficTestPcapName.trim()) {
          notify("请先输入一个 pcap 文件名。", "danger");
          return;
        }
        appState.testingTrafficExtract = true;
        const data = await api("/api/traffic-monitor/test-extract", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pcap_name: appState.trafficTestPcapName.trim() }),
        });
        appState.trafficMonitor = data.data;
        const result = data.result;
        if (result?.ok) {
          notify(result.has_data_rows ? "PCAP 特征提取成功。" : "PCAP 转出了 CSV，但没有有效数据行。");
        } else {
          notify(result?.output_summary || "PCAP 特征提取失败。", "danger");
        }
      } catch (error) {
        notify(error.message, "danger");
      } finally {
        appState.testingTrafficExtract = false;
      }
    }

    async function createUser() {
      try {
        await api("/api/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(appState.userForm),
        });
        appState.userForm = { username: "", password: "", role: "user" };
        notify("用户创建成功。");
        await loadUsers();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    function beginEditUser(user) {
      appState.userEditForm = {
        id: user.id,
        username: user.username,
        password: "",
        role: user.role,
      };
    }

    function cancelEditUser() {
      appState.userEditForm = { id: null, username: "", password: "", role: "user" };
    }

    async function updateUser() {
      try {
        const payload = {
          username: appState.userEditForm.username,
          role: appState.userEditForm.role,
        };
        if (appState.userEditForm.password.trim()) {
          payload.password = appState.userEditForm.password.trim();
        }
        const data = await api(`/api/users/${appState.userEditForm.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (appState.user?.id === data.user.id) {
          appState.user = data.user;
        }
        cancelEditUser();
        notify("用户信息已更新。");
        await loadUsers();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function deleteUser(user) {
      if (!window.confirm(`确定删除用户 ${user.username} 吗？`)) return;
      try {
        await api(`/api/users/${user.id}`, { method: "DELETE" });
        notify("用户已删除。");
        await loadUsers();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function deleteRecord(recordId) {
      if (!window.confirm(`确定删除检测记录 #${recordId} 吗？该记录下的结果和告警也会一起删除。`)) return;
      try {
        await api(`/api/records/${recordId}`, { method: "DELETE" });
        notify("检测记录已删除。");
        if (appState.recordDetail?.record?.id === recordId) {
          appState.recordDetail = null;
          appState.currentView = "results";
        }
        await loadRecords();
        await loadHistory();
        await loadDashboard();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function updateAlarmStatus(alarm, status) {
      try {
        const data = await api(`/api/alarms/${alarm.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        alarm.status = data.alarm.status;
        notify("告警状态已更新。");
        await loadAlarms();
      } catch (error) {
        notify(error.message, "danger");
      }
    }

    async function uploadDataset() {
      if (!uploadFile.value) {
        notify("请先选择 CSV 文件。", "danger");
        return;
      }
      if (!appState.selectedModelId) {
        notify("请先选择一个模型。", "danger");
        return;
      }
      appState.uploading = true;
      const formData = new FormData();
      formData.append("dataset", uploadFile.value);
      formData.append("model_id", String(appState.selectedModelId));
      try {
        const data = await api("/api/detect/upload", {
          method: "POST",
          body: formData,
        });
        appState.activeTask = data.task;
        notify("检测任务已提交，系统正在后台处理。");
        startTaskPolling(data.task.id);
      } catch (error) {
        appState.uploading = false;
        notify(error.message, "danger");
      }
    }

    async function switchView(view) {
      if (view !== "trafficMonitor") stopTrafficMonitorPolling();
      appState.currentView = view;
      if (view !== "resultDetail") appState.recordDetail = null;
      await loadViewData(view);
      if (view === "trafficMonitor" && isAdmin.value) startTrafficMonitorPolling();
    }

    async function loadViewData(view) {
      if (!isAuthenticated.value) return;
      if (view === "dashboard") await loadDashboard();
      if (view === "upload") await loadModels();
      if (view === "results") await loadRecords();
      if (view === "history") await loadHistory();
      if (view === "alarms" && isAdmin.value) await loadAlarms();
      if (view === "metrics" && isAdmin.value) {
        await loadModels();
        await loadMetrics();
      }
      if (view === "trafficMonitor" && isAdmin.value) {
        await loadTrafficMonitor();
        await loadTrafficInterfaces();
        startTrafficMonitorPolling();
      }
      if (view === "models" && isAdmin.value) await loadModels();
      if (view === "users" && isAdmin.value) await loadUsers();
    }

    function riskClass(level) {
      if (level === "高风险") return "pill-danger";
      if (level === "中风险") return "pill-warning";
      if (level === "正常") return "pill-safe";
      return "pill-muted";
    }

    function alarmStatusClass(status) {
      if (status === "processed") return "pill-safe";
      if (status === "ignored") return "pill-muted";
      return "pill-danger";
    }

    function roleLabel(role) {
      return role === "admin" ? "管理员" : "普通用户";
    }

    function renderCharts() {
      if (!appState.dashboard) return;
      const attackChartDom = document.getElementById("attackChart");
      const trendChartDom = document.getElementById("trendChart");

      if (attackChartDom) {
        if (!attackChart.value) {
          attackChart.value = echarts.getInstanceByDom(attackChartDom) || echarts.init(attackChartDom);
        }
        attackChart.value.setOption({
          tooltip: { trigger: "item" },
          color: ["#b45309", "#047857", "#1d4ed8", "#b91c1c", "#7c3aed", "#0f766e"],
          series: [{
            type: "pie",
            radius: ["42%", "70%"],
            itemStyle: { borderRadius: 12, borderColor: "#fffdf8", borderWidth: 2 },
            label: { formatter: "{b}\n{d}%" },
            data: Object.entries(appState.dashboard.attack_distribution || {}).map(([name, value]) => ({ name, value })),
          }],
        });
      }

      if (trendChartDom) {
        if (!trendChart.value) {
          trendChart.value = echarts.getInstanceByDom(trendChartDom) || echarts.init(trendChartDom);
        }
        trendChart.value.setOption({
          tooltip: { trigger: "axis" },
          grid: { left: 36, right: 24, top: 20, bottom: 28 },
          xAxis: { type: "category", data: appState.dashboard.trend_labels || [], boundaryGap: false },
          yAxis: { type: "value" },
          series: [{
            type: "line",
            smooth: true,
            showSymbol: false,
            areaStyle: { opacity: 0.16 },
            data: appState.dashboard.trend_values || [],
            color: "#b45309",
          }],
        });
      }
    }

    onMounted(loadCurrentUser);

    return {
      appState,
      uploadFile,
      modelFile,
      isAuthenticated,
      isAdmin,
      navItems,
      filteredRecords,
      filteredHistoryItems,
      alarmPageNumbers,
      login,
      logout,
      initDemo,
      switchView,
      uploadDataset,
      selectedModel,
      createModel,
      activateModel,
      deleteModel,
      loadTrafficMonitor,
      loadTrafficInterfaces,
      saveTrafficInterface,
      startTrafficMonitor,
      stopTrafficMonitor,
      testTrafficExtract,
      loadRecordDetail,
      createUser,
      beginEditUser,
      cancelEditUser,
      updateUser,
      deleteUser,
      deleteRecord,
      updateAlarmStatus,
      changeAlarmStatusFilter,
      changeAlarmPageSize,
      goToAlarmPage,
      pollTask,
      riskClass,
      alarmStatusClass,
      roleLabel,
    };
  },
  template: `
    <div>
      <main v-if="!isAuthenticated" class="auth-shell">
        <section class="login-card">
          <div class="login-hero">
            <p class="eyebrow hero-eyebrow">Graduation Project</p>
            <h1>基于深度学习的网络入侵检测系统</h1>
            <p class="hero-copy">采用 Vue 前端、Flask API、MySQL 与 PyTorch 模型推理，支持角色权限、后台检测任务、告警管理与实验评估。</p>
            <div class="hero-tags">
              <span>Vue 3</span><span>Flask API</span><span>MySQL</span><span>PyTorch</span>
            </div>
            <button class="btn btn-outline-light hero-btn" @click="initDemo" :disabled="appState.initializing">
              {{ appState.initializing ? '初始化中...' : '初始化演示账号' }}
            </button>
            <div v-if="appState.serverAccess?.recommended_url" class="upload-note" style="margin-top: 14px; color: rgba(255,255,255,0.86);">
              <strong>手机访问：</strong><a :href="appState.serverAccess.recommended_url" target="_blank" rel="noreferrer" style="color: inherit;">{{ appState.serverAccess.recommended_url }}</a>
            </div>
            <div v-if="appState.serverAccess?.recommended_url" style="margin-top: 14px; display: inline-block; padding: 10px; background: rgba(255,255,255,0.92); border-radius: 8px;">
              <div id="accessQrLogin"></div>
            </div>
          </div>
          <div class="login-form">
            <div class="login-heading">
              <p class="eyebrow">Secure Sign In</p>
              <h2>系统登录</h2>
              <p class="text-muted">管理员：admin / admin123，普通用户：user / user123</p>
            </div>
            <div class="mb-3">
              <label class="form-label">用户名</label>
              <input v-model="appState.loginForm.username" class="form-control" placeholder="请输入用户名">
            </div>
            <div class="mb-3">
              <label class="form-label">密码</label>
              <input v-model="appState.loginForm.password" class="form-control" type="password" placeholder="请输入密码" @keyup.enter="login">
            </div>
            <button class="btn btn-primary w-100" @click="login" :disabled="appState.loading">
              {{ appState.loading ? '登录中...' : '登录系统' }}
            </button>
            <div v-if="appState.message" :class="'alert mt-3 alert-' + appState.messageType">{{ appState.message }}</div>
          </div>
        </section>
      </main>

      <div v-else class="app-shell">
        <aside class="sidebar">
          <div class="sidebar-top">
            <div class="brand">DeepIDS</div>
            <div class="brand-subtitle">Vue Frontend + Flask API</div>
          </div>
          <div class="side-profile">
            <div class="profile-avatar">{{ appState.user.username.slice(0, 1).toUpperCase() }}</div>
            <div>
              <div class="profile-name">{{ appState.user.username }}</div>
              <div class="profile-role">{{ roleLabel(appState.user.role) }}</div>
            </div>
          </div>
          <nav class="nav nav-pills flex-column gap-2 mt-4">
            <a v-for="item in navItems" :key="item.key" href="#" class="nav-link side-link" :class="{ active: appState.currentView === item.key }" @click.prevent="switchView(item.key)">
              <span>{{ item.label }}</span>
              <small>{{ item.hint }}</small>
            </a>
          </nav>
          <button class="btn btn-outline-light logout-btn" @click="logout">退出登录</button>
        </aside>

        <main class="main-shell">
          <header class="topbar">
            <div>
              <p class="eyebrow">System Workspace</p>
              <h1 class="topbar-title">网络入侵检测管理平台</h1>
            </div>
            <div class="topbar-meta">
              <span class="meta-chip">{{ roleLabel(appState.user.role) }}</span>
              <span class="meta-chip meta-chip-ghost">Session Active</span>
            </div>
          </header>

          <div v-if="appState.message" :class="'alert alert-' + appState.messageType + ' soft-alert'">{{ appState.message }}</div>

          <section v-if="appState.currentView === 'upload' && appState.activeTask" class="panel-card task-panel">
            <div class="panel-head">
              <div class="panel-title">后台任务状态</div>
              <button class="btn btn-sm btn-outline-primary" @click="pollTask(appState.activeTask.id)">刷新状态</button>
            </div>
            <p class="task-title">文件：{{ appState.activeTask.source_file }}</p>
            <div class="progress task-progress">
              <div class="progress-bar" role="progressbar" :style="{ width: appState.activeTask.progress + '%' }">
                {{ appState.activeTask.progress }}%
              </div>
            </div>
            <p class="upload-note mb-0">状态：{{ appState.activeTask.status }}，{{ appState.activeTask.message }}</p>
          </section>

          <section v-if="appState.currentView === 'dashboard' && appState.dashboard">
            <section class="hero-panel">
              <div>
                <p class="eyebrow">系统总览</p>
                <h2>从数据采集到告警追踪的一体化检测流程</h2>
                <p class="hero-note">当前账号可根据角色查看不同模块。管理员负责系统配置、告警处置与用户管理，普通用户专注于检测任务与结果分析。</p>
                <div v-if="appState.serverAccess?.recommended_url" class="upload-note" style="margin-top: 12px;">
                  <strong>手机访问：</strong><a :href="appState.serverAccess.recommended_url" target="_blank" rel="noreferrer">{{ appState.serverAccess.recommended_url }}</a>
                </div>
              </div>
              <div class="hero-mini-grid">
                <div class="mini-card"><span>模型状态</span><strong>已加载</strong></div>
                <div class="mini-card"><span>检测模式</span><strong>后台异步</strong></div>
                <div v-if="appState.serverAccess?.recommended_url" class="mini-card"><div id="accessQrDashboard" style="display: inline-block; padding: 8px; background: #fff; border-radius: 8px;"></div></div>
              </div>
            </section>
            <section class="stats-grid">
              <article class="stat-card emphasis"><p>检测任务数</p><h3>{{ appState.dashboard.record_count }}</h3><span>累计完成的检测记录</span></article>
              <article class="stat-card"><p>数据集数量</p><h3>{{ appState.dashboard.dataset_count }}</h3><span>已上传并登记的数据文件</span></article>
              <article class="stat-card"><p>告警总数</p><h3>{{ appState.dashboard.alarm_count }}</h3><span>异常流量触发的告警事件</span></article>
              <article class="stat-card"><p>{{ isAdmin ? '用户数量' : '账号角色' }}</p><h3>{{ isAdmin ? appState.dashboard.user_count : roleLabel(appState.user.role) }}</h3><span>{{ isAdmin ? '系统已注册用户总数' : '当前账号权限级别' }}</span></article>
            </section>
            <section class="panel-grid">
              <article class="panel-card"><div class="panel-head"><div class="panel-title">攻击类型分布</div><span class="panel-tag">饼图分析</span></div><div id="attackChart" class="chart-box"></div></article>
              <article class="panel-card"><div class="panel-head"><div class="panel-title">近期攻击趋势</div><span class="panel-tag">时间序列</span></div><div id="trendChart" class="chart-box"></div></article>
            </section>
          </section>

          <section v-if="appState.currentView === 'upload'">
            <section class="page-header"><div><p class="eyebrow">数据检测</p><h2>上传数据集并提交后台任务</h2></div></section>
            <section class="panel-grid upload-layout">
              <article class="panel-card upload-panel">
                <div class="panel-head"><div class="panel-title">检测任务创建</div><span class="panel-tag">Async Task</span></div>
                <label class="form-label">选择模型</label>
                <select v-model="appState.selectedModelId" class="form-select mb-3">
                  <option :value="null" disabled>请选择模型</option>
                  <option v-for="item in appState.models" :key="item.id" :value="item.id">
                    {{ item.model_name }}{{ item.is_active ? ' (Active)' : '' }}
                  </option>
                </select>
                <input class="form-control mb-3" type="file" accept=".csv" @change="uploadFile = $event.target.files[0]">
                <button class="btn btn-primary" @click="uploadDataset" :disabled="appState.uploading">
                  {{ appState.uploading ? '任务提交成功，后台处理中...' : '上传并提交后台检测任务' }}
                </button>
                <p class="upload-note">上传后请求会立即返回，系统会在后台继续执行检测，你可以留在当前页查看进度，也可以切换页面。</p>
              </article>
              <article class="panel-card">
                <div class="panel-title">当前模型数据格式</div>
                <template v-if="selectedModel">
                  <p class="upload-note mb-2"><strong>{{ selectedModel.model_name }}</strong></p>
                  <p class="upload-note">{{ selectedModel.dataset_format || '暂无格式说明' }}</p>
                  <p class="upload-note" v-if="selectedModel.description">{{ selectedModel.description }}</p>
                  <div v-if="selectedModel.required_columns?.length" class="flow-list">
                    <div class="flow-item" v-for="(column, index) in selectedModel.required_columns" :key="column">
                      <span>{{ String(index + 1).padStart(2, '0') }}</span><p>{{ column }}</p>
                    </div>
                  </div>
                </template>
                <p v-else class="upload-note mb-0">请先在模型管理中添加模型，或选择一个已有模型。</p>
              </article>
            </section>
          </section>

          <section v-if="appState.currentView === 'results'">
            <section class="page-header"><div><p class="eyebrow">结果中心</p><h2>检测结果总览</h2></div><div class="toolbar"><input v-model="appState.recordKeyword" class="form-control search-input" placeholder="按文件名、ID、时间搜索"></div></section>
            <section class="panel-card">
              <div class="table-shell">
                <table class="table align-middle">
                  <thead><tr><th>ID</th><th>文件名</th><th>样本数</th><th>正常</th><th>异常</th><th>检测时间</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr v-for="item in filteredRecords" :key="item.id">
                      <td>#{{ item.id }}</td><td>{{ item.source_file }}</td><td>{{ item.sample_count }}</td><td>{{ item.normal_count }}</td><td>{{ item.attack_count }}</td><td>{{ item.detect_time }}</td>
                      <td><div class="table-actions"><button class="btn btn-sm btn-outline-primary" @click="loadRecordDetail(item.id)">查看详情</button><button v-if="isAdmin" class="btn btn-sm btn-outline-danger" @click="deleteRecord(item.id)">删除记录</button></div></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'history'">
            <section class="page-header"><div><p class="eyebrow">审计追踪</p><h2>历史记录时间线</h2></div><div class="toolbar"><input v-model="appState.historyKeyword" class="form-control search-input" placeholder="按文件名、执行人、状态搜索"></div></section>
            <section class="panel-card">
              <div class="history-timeline">
                <div v-for="item in filteredHistoryItems" :key="item.id" class="history-entry">
                  <div class="history-marker"></div>
                  <div class="history-content">
                    <div class="history-topline"><div><strong>任务 #{{ item.id }}</strong><span class="history-file">{{ item.source_file }}</span></div><span class="status-pill" :class="item.alarm_count ? 'pill-warning' : 'pill-safe'">{{ item.status }}</span></div>
                    <p class="history-meta">执行人：{{ item.operator }} | 检测时间：{{ item.detect_time }}</p>
                    <p class="history-meta">样本总数：{{ item.sample_count }}，正常流量：{{ item.normal_count }}，异常流量：{{ item.attack_count }}，关联告警：{{ item.alarm_count }}</p>
                    <div class="table-actions"><button class="btn btn-sm btn-outline-primary" @click="loadRecordDetail(item.id)">查看详情</button><button v-if="isAdmin" class="btn btn-sm btn-outline-danger" @click="deleteRecord(item.id)">删除记录</button></div>
                  </div>
                </div>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'resultDetail' && appState.recordDetail">
            <section class="page-header"><div><p class="eyebrow">检测详情</p><h2>任务 #{{ appState.recordDetail.record.id }}</h2></div><button class="btn btn-outline-primary" @click="switchView('results')">返回列表</button></section>
            <section class="stats-grid">
              <article class="stat-card"><p>文件名</p><h3>{{ appState.recordDetail.record.source_file }}</h3><span>本次检测的数据来源</span></article>
              <article class="stat-card"><p>样本总数</p><h3>{{ appState.recordDetail.record.sample_count }}</h3><span>参与推理的样本数</span></article>
              <article class="stat-card"><p>正常流量</p><h3>{{ appState.recordDetail.record.normal_count }}</h3><span>标签为 BENIGN 的样本</span></article>
              <article class="stat-card"><p>异常流量</p><h3>{{ appState.recordDetail.record.attack_count }}</h3><span>识别为攻击的样本</span></article>
            </section>
            <section class="panel-card">
              <div class="table-shell">
                <table class="table align-middle">
                  <thead><tr><th>源 IP</th><th>目标 IP</th><th>攻击类型</th><th>风险等级</th><th>置信度</th></tr></thead>
                  <tbody>
                    <tr v-for="item in appState.recordDetail.attack_results" :key="item.id">
                      <td>{{ item.src_ip }}</td><td>{{ item.dst_ip }}</td><td>{{ item.attack_type }}</td><td><span class="status-pill" :class="riskClass(item.risk_level)">{{ item.risk_level }}</span></td><td>{{ item.confidence }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="table-actions" style="margin-top: 16px; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div class="table-actions" style="gap: 12px; align-items: center; flex-wrap: wrap;">
                  <span class="text-muted small">共 {{ appState.alarmPagination.total }} 条，当前第 {{ appState.alarmPagination.page }} / {{ appState.alarmPagination.pages || 1 }} 页</span>
                  <label class="text-muted small" style="display: inline-flex; align-items: center; gap: 8px;">
                    <span>每页</span>
                    <select v-model="appState.alarmPagination.pageSize" class="form-select form-select-sm" style="width: 88px;">
                      <option :value="20">20</option>
                      <option :value="50">50</option>
                      <option :value="100">100</option>
                    </select>
                  </label>
                </div>
                <div class="table-actions">
                  <button class="btn btn-sm btn-outline-secondary" @click="goToAlarmPage(appState.alarmPagination.page - 1)" :disabled="!appState.alarmPagination.hasPrev">上一页</button>
                  <button
                    v-for="pageNumber in alarmPageNumbers"
                    :key="'alarm-page-' + pageNumber"
                    class="btn btn-sm"
                    :class="pageNumber === appState.alarmPagination.page ? 'btn-primary' : 'btn-outline-secondary'"
                    @click="goToAlarmPage(pageNumber)"
                  >{{ pageNumber }}</button>
                  <button class="btn btn-sm btn-outline-secondary" @click="goToAlarmPage(appState.alarmPagination.page + 1)" :disabled="!appState.alarmPagination.hasNext">下一页</button>
                </div>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'alarms' && isAdmin">
            <section class="page-header"><div><p class="eyebrow">告警处置</p><h2>告警中心</h2></div><div class="toolbar"><select v-model="appState.alarmStatusFilter" class="form-select alarm-filter"><option value="all">全部状态</option><option value="unprocessed">未处理</option><option value="processed">已处理</option><option value="ignored">已忽略</option></select></div></section>
            <section class="panel-card">
              <div class="table-shell">
                <table class="table align-middle">
                  <thead><tr><th>ID</th><th>内容</th><th>等级</th><th>状态</th><th>时间</th><th>更新状态</th></tr></thead>
                  <tbody>
                    <tr v-for="item in appState.alarms" :key="item.id">
                      <td>#{{ item.id }}</td><td>{{ item.alarm_content }}</td><td><span class="status-pill" :class="riskClass(item.alarm_level)">{{ item.alarm_level }}</span></td><td><span class="status-pill" :class="alarmStatusClass(item.status)">{{ item.status }}</span></td><td>{{ item.create_time }}</td>
                      <td><div class="table-actions"><button class="btn btn-sm btn-outline-success" @click="updateAlarmStatus(item, 'processed')">标记已处理</button><button class="btn btn-sm btn-outline-secondary" @click="updateAlarmStatus(item, 'ignored')">忽略</button><button class="btn btn-sm btn-outline-danger" @click="updateAlarmStatus(item, 'unprocessed')">重置</button></div></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'metrics' && isAdmin && appState.metrics">
            <section class="page-header"><div><p class="eyebrow">实验评估</p><h2>模型性能评估</h2><p class="text-muted mb-0">{{ appState.metrics.model_name }} | {{ appState.metrics.model_path }}</p></div></section>
            <section class="stats-grid">
              <article class="stat-card emphasis"><p>准确率</p><h3>{{ (appState.metrics.accuracy * 100).toFixed(2) }}%</h3><span>Accuracy</span></article>
              <article class="stat-card"><p>精确率</p><h3>{{ appState.metrics.precision.toFixed(3) }}</h3><span>Precision</span></article>
              <article class="stat-card"><p>召回率</p><h3>{{ appState.metrics.recall.toFixed(3) }}</h3><span>Recall</span></article>
              <article class="stat-card"><p>F1-Score</p><h3>{{ appState.metrics.f1_score.toFixed(3) }}</h3><span>综合评估指标</span></article>
            </section>
            <section class="stats-grid">
              <article class="stat-card"><p>Test Samples</p><h3>{{ appState.metrics.test_samples || 0 }}</h3><span>Random seed 42, test size 10%</span></article>
              <article class="stat-card"><p>Total Records</p><h3>{{ appState.metrics.total_samples }}</h3><span>Historical detection samples</span></article>
              <article class="stat-card"><p>Total Attacks</p><h3>{{ appState.metrics.total_attacks }}</h3><span>Historical attack predictions</span></article>
              <article class="stat-card"><p>Total Benign</p><h3>{{ appState.metrics.total_normals }}</h3><span>Historical benign predictions</span></article>
            </section>
            <section class="panel-card">
              <div class="panel-head">
                <div class="panel-title">按模型切换</div>
                <span class="panel-tag">Performance</span>
              </div>
              <div class="mb-3">
                <select v-model="appState.selectedModelId" class="form-select" @change="loadMetrics">
                  <option v-for="item in appState.models" :key="'metrics-model-' + item.id" :value="item.id">
                    {{ item.model_name }}
                  </option>
                </select>
              </div>
              <div class="table-shell compact">
                <table class="table table-sm align-middle">
                  <thead>
                    <tr>
                      <th>Model Architecture</th>
                      <th>Type</th>
                      <th>Accuracy</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>F1-Score</th>
                      <th>FPR</th>
                      <th>FNR</th>
                      <th>Inference Latency (ms)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>{{ appState.metrics.model_name }}</td>
                      <td>{{ appState.metrics.model_type || '-' }}</td>
                      <td>{{ appState.metrics.accuracy.toFixed(6) }}</td>
                      <td>{{ appState.metrics.precision.toFixed(6) }}</td>
                      <td>{{ appState.metrics.recall.toFixed(6) }}</td>
                      <td>{{ appState.metrics.f1_score.toFixed(6) }}</td>
                      <td>{{ appState.metrics.fpr.toFixed(6) }}</td>
                      <td>{{ appState.metrics.fnr.toFixed(6) }}</td>
                      <td>{{ appState.metrics.inference_latency_ms.toFixed(5) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
            <section class="stats-grid">
              <article class="stat-card"><p>FPR</p><h3>{{ appState.metrics.fpr.toFixed(6) }}</h3><span>假阳性率</span></article>
              <article class="stat-card"><p>FNR</p><h3>{{ appState.metrics.fnr.toFixed(6) }}</h3><span>漏报率</span></article>
              <article class="stat-card"><p>Latency</p><h3>{{ appState.metrics.inference_latency_ms.toFixed(5) }} ms</h3><span>单次推理延迟</span></article>
              <article class="stat-card"><p>类型</p><h3>{{ appState.metrics.model_type || '-' }}</h3><span>模型类别</span></article>
            </section>
            <section v-if="appState.metrics.confusion_matrix?.length" class="panel-card">
              <div class="panel-head">
                <div class="panel-title">Confusion Matrix</div>
                <span class="panel-tag">Test Set</span>
              </div>
              <div class="table-shell compact">
                <table class="table table-sm align-middle">
                  <thead>
                    <tr>
                      <th>True \\ Pred</th>
                      <th v-for="label in appState.metrics.labels" :key="'head-' + label">{{ label }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rowIndex) in appState.metrics.confusion_matrix" :key="'row-' + rowIndex">
                      <th>{{ appState.metrics.labels[rowIndex] }}</th>
                      <td v-for="(value, colIndex) in row" :key="'cell-' + rowIndex + '-' + colIndex">{{ value }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'trafficMonitor' && isAdmin && appState.trafficMonitor">
            <section class="page-header"><div><p class="eyebrow">网站流量</p><h2>自动流量巡检</h2></div></section>
            <section class="stats-grid">
              <article class="stat-card emphasis"><p>监测状态</p><h3>{{ appState.trafficMonitor.running ? '监测线程已启动' : '监测线程已停止' }}</h3><span>仅表示后台线程状态，不代表已抓到流量</span></article>
              <article class="stat-card"><p>轮询间隔</p><h3>{{ appState.trafficMonitor.poll_interval || 0 }}s</h3><span>Traffic monitor interval</span></article>
              <article class="stat-card"><p>已处理文件</p><h3>{{ appState.trafficMonitor.processed_count || 0 }}</h3><span>自动送检完成的 CSV 数量</span></article>
              <article class="stat-card"><p>空特征文件</p><h3>{{ appState.trafficMonitor.empty_feature_count || 0 }}</h3><span>已生成 CSV 但没有有效 flow 数据行</span></article>
            </section>
            <section class="stats-grid">
              <article class="stat-card"><p>Scapy</p><h3>{{ appState.trafficMonitor.tshark_ready ? '已就绪' : '未配置' }}</h3><span>负责抓包</span></article>
              <article class="stat-card"><p>Python cicflowmeter 提取器</p><h3>{{ appState.trafficMonitor.cicflowmeter_ready ? '已就绪' : '未配置' }}</h3><span>负责从 PCAP 生成流量特征 CSV</span></article>
              <article class="stat-card"><p>网卡接口</p><h3>{{ appState.trafficMonitor.capture_interface || '未填写' }}</h3><span>Scapy capture interface</span></article>
              <article class="stat-card"><p>当前模型</p><h3>{{ appState.trafficMonitor.active_model ? appState.trafficMonitor.active_model.model_name : '未配置' }}</h3><span>巡检会使用当前启用模型</span></article>
            </section>
            <section class="stats-grid">
              <article class="stat-card"><p>抓包结果</p><h3>{{ appState.trafficMonitor.last_capture_status || 'idle' }}</h3><span>{{ appState.trafficMonitor.last_capture_error || (appState.trafficMonitor.last_generated_pcap || '最近还没有新的 pcap') }}</span></article>
              <article class="stat-card"><p>提取结果</p><h3>{{ appState.trafficMonitor.last_extract_status || 'idle' }}</h3><span>{{ appState.trafficMonitor.last_extract_error || (appState.trafficMonitor.last_generated_csv || '最近还没有新的 csv') }}</span></article>
              <article class="stat-card"><p>最近抓包文件</p><h3>{{ appState.trafficMonitor.last_generated_pcap || '暂无' }}</h3><span>{{ appState.trafficMonitor.last_capture_at || '等待新抓包' }}</span></article>
              <article class="stat-card"><p>最近提取摘要</p><h3>{{ appState.trafficMonitor.last_generated_csv || '暂无' }}</h3><span>{{ appState.trafficMonitor.last_extract_output || '等待新提取' }}</span></article>
            </section>
            <section class="panel-grid user-layout">
              <article class="panel-card">
                <div class="panel-title">控制台</div>
                <p class="upload-note">配置好 Scapy 与 Python cicflowmeter 提取器后，系统会自动抓网站流量、生成特征 CSV、并调用当前模型送检。</p>
                <div class="mb-3">
                  <label class="form-label">抓包网卡</label>
                  <select v-model="appState.selectedTrafficInterface" class="form-select">
                    <option value="" disabled>请选择网卡</option>
                    <option v-for="item in appState.trafficInterfaces" :key="item.id" :value="item.id">
                      {{ item.id }} - {{ item.label }}
                    </option>
                  </select>
                </div>
                <div class="table-actions">
                  <button class="btn btn-outline-primary" @click="loadTrafficInterfaces">刷新网卡</button>
                  <button class="btn btn-outline-success" @click="saveTrafficInterface" :disabled="!appState.selectedTrafficInterface">保存网卡</button>
                  <button class="btn btn-primary" @click="startTrafficMonitor" :disabled="appState.trafficMonitor.running || !appState.trafficMonitor.pipeline_ready">启动监测</button>
                  <button class="btn btn-outline-secondary" @click="stopTrafficMonitor" :disabled="!appState.trafficMonitor.running">停止监测</button>
                  <button class="btn btn-outline-primary" @click="loadTrafficMonitor">刷新状态</button>
                </div>
                <div class="mb-3 mt-3">
                  <label class="form-label">单独测试 PCAP</label>
                  <input v-model="appState.trafficTestPcapName" class="form-control" placeholder="例如 traffic_20260510110243.pcap">
                </div>
                <div class="table-actions">
                  <button class="btn btn-outline-primary" @click="appState.trafficTestPcapName = appState.trafficMonitor.last_generated_pcap || appState.trafficTestPcapName">使用最近抓包</button>
                  <button class="btn btn-outline-success" @click="testTrafficExtract" :disabled="appState.testingTrafficExtract || !appState.trafficTestPcapName">测试提取</button>
                </div>
                <p class="upload-note"><strong>最近抓包错误：</strong>{{ appState.trafficMonitor.last_capture_error || '无' }}</p>
                <p class="upload-note"><strong>最近提取错误：</strong>{{ appState.trafficMonitor.last_extract_error || '无' }}</p>
                <template v-if="appState.trafficMonitor.last_test_result">
                  <p class="upload-note"><strong>测试 PCAP：</strong>{{ appState.trafficMonitor.last_test_result.pcap_path }}</p>
                  <p class="upload-note"><strong>测试输出 CSV：</strong>{{ appState.trafficMonitor.last_test_result.csv_path }}</p>
                  <p class="upload-note"><strong>测试结论：</strong>{{ appState.trafficMonitor.last_test_result.ok ? (appState.trafficMonitor.last_test_result.has_data_rows ? '提取成功且有数据行' : '提取成功但 CSV 只有表头') : '提取失败' }}</p>
                  <p class="upload-note"><strong>测试摘要：</strong>{{ appState.trafficMonitor.last_test_result.output_summary || '无' }}</p>
                </template>
              </article>
              <article class="panel-card">
                <div class="panel-title">目录信息</div>
                <p class="upload-note"><strong>输入目录：</strong>{{ appState.trafficMonitor.input_dir }}</p>
                <p class="upload-note"><strong>归档目录：</strong>{{ appState.trafficMonitor.archive_dir }}</p>
                <p class="upload-note"><strong>抓包目录：</strong>{{ appState.trafficMonitor.pcap_dir }}</p>
                <p class="upload-note"><strong>PCAP 归档：</strong>{{ appState.trafficMonitor.pcap_archive_dir }}</p>
                <p class="upload-note"><strong>最近扫描：</strong>{{ appState.trafficMonitor.last_scan_at || '暂无' }}</p>
                <p class="upload-note"><strong>最近抓包：</strong>{{ appState.trafficMonitor.last_generated_pcap || '暂无' }}</p>
                <p class="upload-note"><strong>最近特征：</strong>{{ appState.trafficMonitor.last_generated_csv || '暂无' }}</p>
                <p class="upload-note"><strong>最近处理：</strong>{{ appState.trafficMonitor.last_processed_file || '暂无' }}</p>
                <p class="upload-note" v-if="appState.trafficMonitor.last_error"><strong>最近错误：</strong>{{ appState.trafficMonitor.last_error }}</p>
              </article>
            </section>
            <section class="panel-card">
              <div class="panel-title">接入步骤</div>
              <div class="flow-list">
                <div class="flow-item"><span>01</span><p>在 .env 中填写 TRAFFIC_CAPTURE_INTERFACE、CICFLOWMETER_COMMAND</p></div>
                <div class="flow-item"><span>02</span><p>系统会定时用 Scapy 抓包，PCAP 写入抓包目录</p></div>
                <div class="flow-item"><span>03</span><p>Python cicflowmeter 提取器会把 PCAP 转成流量特征 CSV，自动落到输入目录</p></div>
                <div class="flow-item"><span>04</span><p>系统检测完成后会自动归档 PCAP/CSV，结果进入“检测结果/历史记录/告警”页面</p></div>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'models' && isAdmin">
            <section class="page-header"><div><p class="eyebrow">模型管理</p><h2>当前接入模型</h2></div></section>
            <section class="panel-grid user-layout">
              <article class="panel-card">
                <div class="panel-title">新增模型</div>
                <div class="mb-3"><label class="form-label">模型名称</label><input v-model="appState.modelForm.model_name" class="form-control" placeholder="例如 Transformer IDS"></div>
                <div class="mb-3"><label class="form-label">上传模型文件</label><input class="form-control" type="file" accept=".pth" @change="modelFile = $event.target.files[0] || null"></div>
                <div class="mb-3"><label class="form-label">或手动填写模型路径</label><input v-model="appState.modelForm.model_path" class="form-control" placeholder="例如 models/transformer_ids.pth"></div>
                <div class="mb-3"><label class="form-label">模型类型</label><input v-model="appState.modelForm.model_type" class="form-control" placeholder="PyTorch"></div>
                <div class="mb-3"><label class="form-label">准确率</label><input v-model="appState.modelForm.accuracy" type="number" step="0.001" class="form-control" placeholder="0.965"></div>
                <div class="mb-3"><label class="form-label">Precision</label><input v-model="appState.modelForm.precision" type="number" step="0.000001" class="form-control" placeholder="0.996907"></div>
                <div class="mb-3"><label class="form-label">Recall</label><input v-model="appState.modelForm.recall" type="number" step="0.000001" class="form-control" placeholder="0.996845"></div>
                <div class="mb-3"><label class="form-label">F1-Score</label><input v-model="appState.modelForm.f1_score" type="number" step="0.000001" class="form-control" placeholder="0.996676"></div>
                <div class="mb-3"><label class="form-label">FPR</label><input v-model="appState.modelForm.fpr" type="number" step="0.000001" class="form-control" placeholder="0.003212"></div>
                <div class="mb-3"><label class="form-label">FNR</label><input v-model="appState.modelForm.fnr" type="number" step="0.000001" class="form-control" placeholder="0.003155"></div>
                <div class="mb-3"><label class="form-label">Inference Latency (ms)</label><input v-model="appState.modelForm.inference_latency_ms" type="number" step="0.00001" class="form-control" placeholder="0.00966"></div>
                <div class="mb-3"><label class="form-label">格式说明</label><textarea v-model="appState.modelForm.dataset_format" class="form-control" rows="3" placeholder="说明上传数据集应满足的格式" required></textarea></div>
                <div class="mb-3"><label class="form-label">字段列表</label><textarea v-model="appState.modelForm.required_columns_text" class="form-control" rows="5" placeholder="每行一个字段名"></textarea></div>
                <div class="mb-3"><label class="form-label">补充说明</label><textarea v-model="appState.modelForm.description" class="form-control" rows="3" placeholder="例如标签含义、分隔符要求、预处理要求"></textarea></div>
                <div class="form-check mb-3"><input v-model="appState.modelForm.is_active" class="form-check-input" type="checkbox" id="model-active"><label class="form-check-label" for="model-active">设为当前启用模型</label></div>
                <button class="btn btn-primary" @click="createModel">添加模型</button>
              </article>
              <article class="panel-card">
                <div class="panel-title">管理说明</div>
                <div class="flow-list">
                  <div class="flow-item"><span>01</span><p>支持直接上传 .pth 文件，也支持填写工作区内已有模型路径</p></div>
                  <div class="flow-item"><span>02</span><p>不同模型可维护不同的数据集格式说明和字段清单</p></div>
                  <div class="flow-item"><span>03</span><p>启用模型后，性能评估和上传默认都会基于当前启用模型</p></div>
                  <div class="flow-item"><span>04</span><p>已经产生检测任务或记录的模型暂不允许删除</p></div>
                </div>
              </article>
            </section>
            <section class="panel-card">
              <div class="table-shell">
                <table class="table align-middle">
                  <thead><tr><th>模型名称</th><th>路径</th><th>类型</th><th>准确率</th><th>字段数</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr v-for="item in appState.models" :key="item.id">
                      <td>
                        {{ item.model_name }}
                        <div class="text-muted small" v-if="item.dataset_format">{{ item.dataset_format }}</div>
                      </td>
                      <td>{{ item.model_path }}</td>
                      <td>{{ item.model_type }}</td>
                      <td>{{ item.accuracy }}</td>
                      <td>{{ item.required_columns.length }}</td>
                      <td><span class="status-pill" :class="item.is_active ? 'pill-safe' : 'pill-muted'">{{ item.is_active ? 'Active' : 'Inactive' }}</span></td>
                      <td>{{ item.create_time }}</td>
                      <td><div class="table-actions"><button class="btn btn-sm btn-outline-primary" @click="activateModel(item)" :disabled="item.is_active">启用</button><button class="btn btn-sm btn-outline-danger" @click="deleteModel(item)">删除</button></div></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>

          <section v-if="appState.currentView === 'users' && isAdmin">
            <section class="page-header"><div><p class="eyebrow">权限控制</p><h2>用户与角色管理</h2></div></section>
            <section class="panel-grid user-layout">
              <article class="panel-card">
                <div class="panel-title">新增用户</div>
                <div class="mb-3"><label class="form-label">用户名</label><input v-model="appState.userForm.username" class="form-control" placeholder="请输入用户名"></div>
                <div class="mb-3"><label class="form-label">密码</label><input v-model="appState.userForm.password" type="password" class="form-control" placeholder="请输入密码"></div>
                <div class="mb-3"><label class="form-label">角色</label><select v-model="appState.userForm.role" class="form-select"><option value="user">普通用户</option><option value="admin">管理员</option></select></div>
                <button class="btn btn-primary" @click="createUser">创建用户</button>
              </article>
              <article class="panel-card">
                <div class="panel-title">编辑用户</div>
                <template v-if="appState.userEditForm.id">
                  <div class="mb-3"><label class="form-label">用户名</label><input v-model="appState.userEditForm.username" class="form-control"></div>
                  <div class="mb-3"><label class="form-label">新密码</label><input v-model="appState.userEditForm.password" type="password" class="form-control" placeholder="留空则不修改"></div>
                  <div class="mb-3"><label class="form-label">角色</label><select v-model="appState.userEditForm.role" class="form-select"><option value="user">普通用户</option><option value="admin">管理员</option></select></div>
                  <div class="table-actions"><button class="btn btn-primary" @click="updateUser">保存修改</button><button class="btn btn-outline-secondary" @click="cancelEditUser">取消</button></div>
                </template>
                <p v-else class="text-muted mb-0">从右侧用户列表选择一名用户后可在此编辑信息。</p>
              </article>
            </section>
            <section class="panel-card">
              <div class="table-shell">
                <table class="table align-middle">
                  <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>创建时间</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr v-for="item in appState.users" :key="item.id">
                      <td>#{{ item.id }}</td><td>{{ item.username }}</td><td><span class="status-pill" :class="item.role === 'admin' ? 'pill-warning' : 'pill-safe'">{{ roleLabel(item.role) }}</span></td><td>{{ item.create_time }}</td>
                      <td><div class="table-actions"><button class="btn btn-sm btn-outline-primary" @click="beginEditUser(item)">编辑</button><button class="btn btn-sm btn-outline-danger" @click="deleteUser(item)">删除</button></div></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        </main>
      </div>
    </div>
  `,
}).mount("#app");
