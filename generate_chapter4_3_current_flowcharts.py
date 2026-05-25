from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "thesis_figures" / "4_3_core_modules"
FONT_NAME = "Microsoft YaHei"
GRAPH_NODESEP = "0.5"
GRAPH_RANKSEP = "0.7"


NODE_STYLES = {
    "start": {
        "shape": "ellipse",
        "style": "filled",
        "fillcolor": "#E8F8F5",
        "color": "#16A085",
        "penwidth": "1.5",
    },
    "process": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#EBF5FB",
        "color": "#2874A6",
        "penwidth": "1.2",
    },
    "decision": {
        "shape": "diamond",
        "style": "filled",
        "fillcolor": "#FEF5E7",
        "color": "#D68910",
        "penwidth": "1.2",
    },
    "db": {
        "shape": "cylinder",
        "style": "filled",
        "fillcolor": "#F4ECF7",
        "color": "#7D3C98",
        "penwidth": "1.2",
    },
    "external": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#FDEDEC",
        "color": "#C0392B",
        "penwidth": "1.2",
    },
}


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def attrs(mapping: dict[str, str]) -> str:
    return ", ".join(f"{key}={q(str(value))}" for key, value in mapping.items())


def dot_executable() -> str:
    found = shutil.which("dot")
    if found:
        return found
    fallback = Path(r"C:\Program Files\Graphviz\bin\dot.exe")
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("Graphviz dot executable was not found.")


def build_dot(
    graph_name: str,
    title: str,
    nodes: list[tuple[str, str, str]],
    edges: list[tuple[str, str, str]],
    rankdir: str = "TB",
) -> str:
    graph_attrs = {
        "charset": "UTF-8",
        "rankdir": rankdir,
        "splines": "ortho",
        "nodesep": GRAPH_NODESEP,
        "ranksep": GRAPH_RANKSEP,
        "dpi": "160",
        "bgcolor": "white",
        "label": title,
        "labelloc": "t",
        "fontsize": "18",
        "fontname": FONT_NAME,
    }
    default_node = {
        "fontname": FONT_NAME,
        "fontsize": "11",
        "margin": "0.12,0.08",
    }
    default_edge = {
        "fontname": FONT_NAME,
        "fontsize": "10",
        "color": "#566573",
        "arrowhead": "vee",
    }
    lines = [
        f"digraph {graph_name} {{",
        f"  graph [{attrs(graph_attrs)}];",
        f"  node [{attrs(default_node)}];",
        f"  edge [{attrs(default_edge)}];",
    ]
    for node_id, label, kind in nodes:
        style = NODE_STYLES[kind]
        lines.append(f"  {node_id} [label={q(label)}, {attrs(style)}];")
    for src, dst, label in edges:
        label_attr = f" [label={q(label)}]" if label else ""
        lines.append(f"  {src} -> {dst}{label_attr};")
    lines.append("}")
    return "\n".join(lines)


def render(name: str, title: str, nodes, edges, rankdir: str = "TB") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dot_path = OUTPUT_DIR / f"{name}.dot"
    png_path = OUTPUT_DIR / f"{name}.png"
    dot_path.write_text(build_dot(name.replace("-", "_"), title, nodes, edges, rankdir), encoding="utf-8")
    subprocess.run(
        [dot_executable(), "-Tpng", str(dot_path), "-o", str(png_path)],
        cwd=str(ROOT_DIR),
        check=True,
    )
    print(f"generated {png_path}")


def flow_module_overview():
    nodes = [
        ("start", "基于深度学习的\n网络入侵检测系统", "start"),
        ("common", "通用支撑功能", "process"),
        ("business", "核心检测业务", "process"),
        ("admin_domain", "系统管理功能", "process"),
        ("auth", "登录认证与\n权限控制", "process"),
        ("dashboard", "系统首页与\n统计展示", "process"),
        ("upload", "数据上传与\n后台检测任务", "process"),
        ("result", "检测结果与\n历史记录", "process"),
        ("alarm", "告警管理", "process"),
        ("model", "模型管理与\n模型能力展示", "process"),
        ("traffic", "实时流量监测", "process"),
        ("user", "用户管理与\n操作审计", "process"),
    ]
    edges = [
        ("start", "common", ""),
        ("start", "business", ""),
        ("start", "admin_domain", ""),
        ("common", "auth", ""),
        ("common", "dashboard", ""),
        ("business", "upload", ""),
        ("business", "result", ""),
        ("business", "alarm", ""),
        ("business", "traffic", ""),
        ("admin_domain", "model", ""),
        ("admin_domain", "user", ""),
    ]
    render("fig4-3-1-core-module-overview", "图4.3-1 核心功能模块划分图", nodes, edges)


def flow_auth_permission():
    nodes = [
        ("start", "用户访问系统", "start"),
        ("me", "GET /api/auth/me\n检查会话状态", "process"),
        ("has_session", "Session有效？", "decision"),
        ("login_page", "显示登录页\n输入用户名和密码", "process"),
        ("login", "POST /api/auth/login\n提交认证信息", "process"),
        ("verify", "用户名和密码\n校验通过？", "decision"),
        ("fail", "返回401\n提示错误", "process"),
        ("session", "写入Session\nuser_id / username / role", "process"),
        ("log", "写入operation_log\n登录操作日志", "db"),
        ("role", "判断用户角色", "decision"),
        ("admin", "管理员视图\n完整管理功能", "process"),
        ("normal", "普通用户视图\n检测与结果查询", "process"),
        ("api", "访问业务API", "process"),
        ("guard", "login_required /\nadmin_required校验", "decision"),
        ("execute", "执行请求并返回数据", "process"),
        ("reject", "返回401/403\n拒绝访问", "process"),
        ("end", "流程结束", "start"),
    ]
    edges = [
        ("start", "me", ""),
        ("me", "has_session", ""),
        ("has_session", "role", "是"),
        ("has_session", "login_page", "否"),
        ("login_page", "login", ""),
        ("login", "verify", ""),
        ("verify", "fail", "否"),
        ("fail", "login_page", ""),
        ("verify", "session", "是"),
        ("session", "log", ""),
        ("log", "role", ""),
        ("role", "admin", "admin"),
        ("role", "normal", "user"),
        ("admin", "api", ""),
        ("normal", "api", ""),
        ("api", "guard", ""),
        ("guard", "execute", "通过"),
        ("guard", "reject", "不通过"),
        ("execute", "end", ""),
        ("reject", "login_page", "需重新登录"),
    ]
    render("fig4-3-2-auth-permission-flow", "图4.3-2 登录认证与权限控制流程图", nodes, edges)


def flow_dashboard_stats():
    nodes = [
        ("start", "用户进入系统首页", "start"),
        ("request", "GET /api/dashboard\n请求统计数据", "process"),
        ("auth", "会话校验通过？", "decision"),
        ("scope", "根据role确定\n数据统计范围", "process"),
        ("admin", "管理员：全局统计", "process"),
        ("user", "普通用户：按user_id过滤", "process"),
        ("record", "detect_record\n记录数/样本数/趋势", "db"),
        ("result", "attack_result\n类型分布统计", "db"),
        ("alarm", "alarm_log\n告警数量与最近告警", "db"),
        ("dataset", "dataset_info / user\n数据集数与用户数", "db"),
        ("json", "组装JSON响应", "process"),
        ("render", "前端渲染\n统计卡片 + ECharts图表\n+ 最近记录列表", "process"),
        ("end", "首页展示完成", "start"),
    ]
    edges = [
        ("start", "request", ""),
        ("request", "auth", ""),
        ("auth", "scope", "是"),
        ("auth", "start", "否"),
        ("scope", "admin", "admin"),
        ("scope", "user", "user"),
        ("admin", "record", ""),
        ("user", "record", ""),
        ("record", "result", ""),
        ("result", "alarm", ""),
        ("alarm", "dataset", ""),
        ("dataset", "json", ""),
        ("json", "render", ""),
        ("render", "end", ""),
    ]
    render("fig4-3-3-dashboard-stats-flow", "图4.3-3 系统首页统计展示流程图", nodes, edges)


def flow_upload_task_submission():
    nodes = [
        ("start", "进入上传检测页面", "start"),
        ("models", "GET /api/models\n加载模型列表", "process"),
        ("select", "选择检测模型\n选择CSV文件", "process"),
        ("check", "文件为.csv？", "decision"),
        ("reject", "提示仅支持CSV", "process"),
        ("submit", "POST /api/detect/upload\n提交dataset和model_id", "process"),
        ("save", "save_dataset()\n时间戳重命名并保存", "process"),
        ("dataset", "写入dataset_info\n统计CSV行数", "db"),
        ("task", "创建detection_task\nstatus=queued", "db"),
        ("thread", "启动后台线程\n_run_detection_task()", "process"),
        ("return", "立即返回task_id\n前端不阻塞", "process"),
        ("poll", "GET /api/tasks/<id>\n定时轮询进度", "process"),
        ("done", "任务完成或失败？", "decision"),
        ("detail", "完成后跳转\n检测详情页面", "process"),
        ("end", "提交流程结束", "start"),
    ]
    edges = [
        ("start", "models", ""),
        ("models", "select", ""),
        ("select", "check", ""),
        ("check", "reject", "否"),
        ("reject", "select", ""),
        ("check", "submit", "是"),
        ("submit", "save", ""),
        ("save", "dataset", ""),
        ("dataset", "task", ""),
        ("task", "thread", ""),
        ("thread", "return", ""),
        ("return", "poll", ""),
        ("poll", "done", ""),
        ("done", "poll", "未完成"),
        ("done", "detail", "completed"),
        ("detail", "end", ""),
    ]
    render("fig4-3-4-upload-task-submission-flow", "图4.3-4 上传检测任务提交流程图", nodes, edges)


def flow_detection_pipeline():
    nodes = [
        ("start", "后台线程开始执行", "start"),
        ("running", "更新任务状态\nstatus=running", "db"),
        ("resolve", "get_model_for_detection()\n确定模型ID和路径", "process"),
        ("service", "初始化ModelService\n加载预处理元数据和.pth权重", "process"),
        ("record", "创建detect_record\n记录检测容器", "db"),
        ("chunk", "按块读取CSV\nchunksize=5000", "process"),
        ("prepare", "列名清洗\n删除非特征列\n缺失值填充", "process"),
        ("scale", "按preprocess_meta\n执行Z-Score标准化\n重构为特征数×1张量", "process"),
        ("infer", "PyTorch批量推理\nbatch_size=1024", "process"),
        ("label", "softmax + argmax\n映射BENIGN或攻击类型\n计算风险等级", "process"),
        ("buffer", "缓存AttackResult\n攻击样本同步缓存AlarmLog", "process"),
        ("flush", "达到DB_BATCH_SIZE？", "decision"),
        ("write", "bulk_insert_mappings\n批量写入数据库", "db"),
        ("progress", "progress_callback\n更新processed_rows", "db"),
        ("more", "还有数据块？", "decision"),
        ("summary", "更新detect_record\nsample/normal/attack统计", "db"),
        ("complete", "任务completed\n或异常failed", "db"),
        ("end", "后台检测结束", "start"),
    ]
    edges = [
        ("start", "running", ""),
        ("running", "resolve", ""),
        ("resolve", "service", ""),
        ("service", "record", ""),
        ("record", "chunk", ""),
        ("chunk", "prepare", ""),
        ("prepare", "scale", ""),
        ("scale", "infer", ""),
        ("infer", "label", ""),
        ("label", "buffer", ""),
        ("buffer", "flush", ""),
        ("flush", "write", "是"),
        ("flush", "progress", "否"),
        ("write", "progress", ""),
        ("progress", "more", ""),
        ("more", "chunk", "是"),
        ("more", "summary", "否"),
        ("summary", "complete", ""),
        ("complete", "end", ""),
    ]
    render("fig4-3-5-background-detection-pipeline", "图4.3-5 后台检测与模型推理流程图", nodes, edges)


def flow_results_history():
    nodes = [
        ("start", "进入检测结果页面", "start"),
        ("list", "GET /api/records\n获取检测记录列表", "process"),
        ("scope", "当前角色？", "decision"),
        ("all", "管理员查看全部记录", "process"),
        ("self", "普通用户仅查看\n本人记录", "process"),
        ("records", "查询detect_record\n按detect_time降序", "db"),
        ("count", "统计关联alarm_log数量\n生成记录状态", "db"),
        ("render", "前端表格展示\n文件/样本/攻击/时间/操作者", "process"),
        ("search", "客户端关键词过滤\n文件名/编号/时间/状态", "process"),
        ("detail_req", "GET /api/records/<id>\n请求详情", "process"),
        ("detail_db", "查询DetectRecord\n和AttackResult明细", "db"),
        ("detail", "展示统计卡片\n和攻击结果列表", "process"),
        ("delete", "管理员删除记录？", "decision"),
        ("cascade", "删除attack_result/alarm_log\n置空detection_task.record_id", "db"),
        ("end", "结果查看完成", "start"),
    ]
    edges = [
        ("start", "list", ""),
        ("list", "scope", ""),
        ("scope", "all", "admin"),
        ("scope", "self", "user"),
        ("all", "records", ""),
        ("self", "records", ""),
        ("records", "count", ""),
        ("count", "render", ""),
        ("render", "search", ""),
        ("search", "detail_req", "选择记录"),
        ("detail_req", "detail_db", ""),
        ("detail_db", "detail", ""),
        ("detail", "delete", ""),
        ("delete", "cascade", "是"),
        ("delete", "end", "否"),
        ("cascade", "list", "刷新列表"),
    ]
    render("fig4-3-6-results-history-flow", "图4.3-6 检测结果与历史记录流程图", nodes, edges)


def flow_alarm_management():
    nodes = [
        ("start", "管理员进入告警中心", "start"),
        ("request", "GET /api/alarms\npage/page_size/status", "process"),
        ("query", "JOIN alarm_log 与 detect_record\n过滤traffic_%在线监测记录", "db"),
        ("filter", "按状态筛选\nunprocessed/processed/ignored", "process"),
        ("page", "分页返回告警列表", "process"),
        ("render", "前端展示告警内容\n级别/状态/时间", "process"),
        ("action", "管理员操作？", "decision"),
        ("detail", "跳转关联检测详情", "process"),
        ("patch", "PATCH /api/alarms/<id>\n提交新状态", "process"),
        ("valid", "状态值合法？", "decision"),
        ("error", "返回400错误提示", "process"),
        ("update", "更新alarm_log.status\n写入operation_log", "db"),
        ("end", "告警处理完成", "start"),
    ]
    edges = [
        ("start", "request", ""),
        ("request", "query", ""),
        ("query", "filter", ""),
        ("filter", "page", ""),
        ("page", "render", ""),
        ("render", "action", ""),
        ("action", "detail", "查看详情"),
        ("action", "patch", "更新状态"),
        ("action", "end", "仅浏览"),
        ("patch", "valid", ""),
        ("valid", "error", "否"),
        ("valid", "update", "是"),
        ("error", "render", ""),
        ("update", "request", "刷新列表"),
        ("detail", "end", ""),
    ]
    render("fig4-3-7-alarm-management-flow", "图4.3-7 告警管理流程图", nodes, edges)


def flow_model_management():
    nodes = [
        ("start", "管理员进入模型管理", "start"),
        ("list", "GET /api/models\n加载模型与active_model_id", "process"),
        ("db_list", "查询model_info\n激活模型优先排序", "db"),
        ("render", "展示模型列表\n指标/路径/字段/启用状态", "process"),
        ("action", "管理员操作？", "decision"),
        ("create", "POST /api/models\n新增模型元数据\n可上传.pth文件", "process"),
        ("validate", "校验名称/路径/格式\n路径存在且不重复", "decision"),
        ("insert", "写入model_info\n保存指标和字段要求", "db"),
        ("active", "需要设为启用？", "decision"),
        ("set_active", "set_active_model()\n取消其他模型启用\n设置唯一激活模型", "db"),
        ("activate", "POST /api/models/<id>/activate\n切换启用模型", "process"),
        ("delete", "DELETE /api/models/<id>\n删除模型", "process"),
        ("dep", "存在任务或记录引用？", "decision"),
        ("block", "阻止删除\n避免历史数据失去模型来源", "process"),
        ("oplog", "写入operation_log", "db"),
        ("end", "模型管理完成", "start"),
    ]
    edges = [
        ("start", "list", ""),
        ("list", "db_list", ""),
        ("db_list", "render", ""),
        ("render", "action", ""),
        ("action", "create", "新增"),
        ("action", "activate", "启用"),
        ("action", "delete", "删除"),
        ("action", "end", "浏览"),
        ("create", "validate", ""),
        ("validate", "render", "不通过"),
        ("validate", "insert", "通过"),
        ("insert", "active", ""),
        ("active", "set_active", "是"),
        ("active", "oplog", "否"),
        ("set_active", "oplog", ""),
        ("activate", "set_active", ""),
        ("delete", "dep", ""),
        ("dep", "block", "是"),
        ("dep", "oplog", "否，删除记录"),
        ("block", "render", ""),
        ("oplog", "list", "刷新"),
    ]
    render("fig4-3-8-model-management-flow", "图4.3-8 模型管理流程图", nodes, edges)


def flow_model_capability_panel():
    nodes = [
        ("start", "用户点击“模型能力”", "start"),
        ("parallel", "并行请求\n/api/models\n/api/auth/me\n/api/dashboard", "process"),
        ("models", "获取模型指标\nAccuracy/Precision/Recall/F1\nFPR/FNR/Latency", "db"),
        ("me", "获取当前用户角色", "db"),
        ("dash", "获取历史检测统计\n样本/攻击/正常数量", "db"),
        ("select", "根据active_model_id\n选中当前模型", "process"),
        ("render", "展示模型能力面板\n数据格式说明\n必需字段列表\n历史样本统计", "process"),
        ("change", "切换选择模型？", "decision"),
        ("rerender", "重新渲染所选模型\n能力信息", "process"),
        ("end", "关闭面板", "start"),
    ]
    edges = [
        ("start", "parallel", ""),
        ("parallel", "models", ""),
        ("parallel", "me", ""),
        ("parallel", "dash", ""),
        ("models", "select", ""),
        ("me", "select", ""),
        ("dash", "select", ""),
        ("select", "render", ""),
        ("render", "change", ""),
        ("change", "rerender", "是"),
        ("rerender", "change", ""),
        ("change", "end", "否"),
    ]
    render("fig4-3-9-model-capability-flow", "图4.3-9 模型能力展示流程图", nodes, edges)


def flow_traffic_config_start():
    nodes = [
        ("start", "管理员进入网站流量页面", "start"),
        ("status", "GET /api/traffic-monitor\n获取监测状态", "process"),
        ("ready", "检查scapy/cicflowmeter\n和网卡配置", "process"),
        ("interfaces", "GET /api/traffic-monitor/interfaces\n发现可用网卡", "process"),
        ("select", "选择抓包网卡", "process"),
        ("save", "PATCH /api/traffic-monitor/config\n保存capture_interface", "process"),
        ("settings", "写入artifacts/\ntraffic_monitor_settings.json", "db"),
        ("pipeline", "pipeline_ready？", "decision"),
        ("start_api", "POST /api/traffic-monitor/start\n启动后台监测线程", "process"),
        ("timer", "前端每3秒轮询状态", "process"),
        ("stop", "POST /api/traffic-monitor/stop\n设置stop_event", "process"),
        ("end", "配置与启停结束", "start"),
    ]
    edges = [
        ("start", "status", ""),
        ("status", "ready", ""),
        ("ready", "interfaces", ""),
        ("interfaces", "select", ""),
        ("select", "save", ""),
        ("save", "settings", ""),
        ("settings", "pipeline", ""),
        ("pipeline", "start_api", "是"),
        ("pipeline", "status", "否，继续配置"),
        ("start_api", "timer", ""),
        ("timer", "stop", "管理员停止"),
        ("timer", "status", "持续刷新"),
        ("stop", "end", ""),
    ]
    render("fig4-3-10-traffic-config-start-flow", "图4.3-10 流量监测配置与启停流程图", nodes, edges)


def flow_traffic_capture_cycle():
    nodes = [
        ("start", "监测线程_run_loop", "start"),
        ("dirs", "创建inbox/archive\npcap/pcap_archive目录", "process"),
        ("capture", "Scapy sniff()\n按网卡/时长/BPF过滤抓包", "external"),
        ("pcap", "生成traffic_时间戳.pcap", "db"),
        ("extract", "PcapReader + FlowSession\n提取原始流特征CSV", "external"),
        ("normalize", "字段映射规范化\n补齐CIC-IDS特征列\n生成Flow ID", "process"),
        ("has_rows", "CSV存在有效flow？", "decision"),
        ("empty", "归档空CSV\nempty_feature_count++", "db"),
        ("admin", "选择首个管理员账号\n作为自动检测操作者", "process"),
        ("active", "获取当前启用模型", "process"),
        ("detect", "调用run_detection()\n执行模型推理", "process"),
        ("save", "写入DetectRecord\nAttackResult\nAlarmLog", "db"),
        ("archive", "归档PCAP和CSV\n更新processed_count", "db"),
        ("wait", "等待TRAFFIC_MONITOR_INTERVAL\n默认10秒", "process"),
        ("stop", "stop_event已设置？", "decision"),
        ("end", "线程安全退出", "start"),
    ]
    edges = [
        ("start", "dirs", ""),
        ("dirs", "capture", ""),
        ("capture", "pcap", ""),
        ("pcap", "extract", ""),
        ("extract", "normalize", ""),
        ("normalize", "has_rows", ""),
        ("has_rows", "empty", "否"),
        ("has_rows", "admin", "是"),
        ("admin", "active", ""),
        ("active", "detect", ""),
        ("detect", "save", ""),
        ("save", "archive", ""),
        ("empty", "archive", ""),
        ("archive", "wait", ""),
        ("wait", "stop", ""),
        ("stop", "capture", "否，下一轮"),
        ("stop", "end", "是"),
    ]
    render("fig4-3-11-traffic-capture-detect-cycle", "图4.3-11 在线流量抓包、提取与检测循环流程图", nodes, edges)


def flow_user_management():
    nodes = [
        ("start", "管理员进入用户管理", "start"),
        ("list", "GET /api/users\n加载用户列表", "process"),
        ("db_list", "查询user表\n按create_time降序", "db"),
        ("render", "展示用户名/角色/创建时间", "process"),
        ("action", "管理员操作？", "decision"),
        ("create", "POST /api/users\n新增用户", "process"),
        ("edit", "PATCH /api/users/<id>\n修改用户名/角色/密码", "process"),
        ("valid", "用户名非空且唯一\n角色为admin/user\n新增密码非空？", "decision"),
        ("hash", "hash_password()\n生成安全密码哈希", "process"),
        ("save", "写入或更新user表\n写operation_log", "db"),
        ("sync", "若修改当前账号\n同步刷新Session", "process"),
        ("delete", "DELETE /api/users/<id>", "process"),
        ("self", "是否删除当前账号？", "decision"),
        ("records", "是否存在检测记录？", "decision"),
        ("block", "阻止删除并提示原因", "process"),
        ("remove", "删除user记录\n写operation_log", "db"),
        ("end", "用户管理完成", "start"),
    ]
    edges = [
        ("start", "list", ""),
        ("list", "db_list", ""),
        ("db_list", "render", ""),
        ("render", "action", ""),
        ("action", "create", "新增"),
        ("action", "edit", "编辑"),
        ("action", "delete", "删除"),
        ("action", "end", "浏览"),
        ("create", "valid", ""),
        ("edit", "valid", ""),
        ("valid", "render", "不通过"),
        ("valid", "hash", "通过且需设密码"),
        ("hash", "save", ""),
        ("valid", "save", "通过且不改密码"),
        ("save", "sync", ""),
        ("sync", "list", "刷新"),
        ("delete", "self", ""),
        ("self", "block", "是"),
        ("self", "records", "否"),
        ("records", "block", "是"),
        ("records", "remove", "否"),
        ("block", "render", ""),
        ("remove", "list", "刷新"),
    ]
    render("fig4-3-12-user-management-flow", "图4.3-12 用户管理与操作审计流程图", nodes, edges)


def main() -> None:
    flow_module_overview()
    flow_auth_permission()
    flow_dashboard_stats()
    flow_upload_task_submission()
    flow_detection_pipeline()
    flow_results_history()
    flow_alarm_management()
    flow_model_management()
    flow_model_capability_panel()
    flow_traffic_config_start()
    flow_traffic_capture_cycle()
    flow_user_management()


if __name__ == "__main__":
    main()
