"""
Generate flowcharts for thesis section 4.3: 核心功能模块详细设计
Uses graphviz to create professional flow diagrams.
"""
from pathlib import Path
import graphviz

OUTPUT_DIR = Path(r"C:\graduationProject\project\model\thesis_figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPH_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "11",
    "rankdir": "TB",
    "splines": "polyline",
    "nodesep": "0.5",
    "ranksep": "0.7",
    "dpi": "120",
    "bgcolor": "white",
    "labeljust": "l",
}

NODE_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "10",
    "shape": "box",
    "style": "rounded,filled",
    "fillcolor": "#EBF5FB",
    "color": "#2980B9",
    "penwidth": "1.2",
}

EDGE_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "9",
    "color": "#7F8C8D",
    "arrowhead": "vee",
}

DECISION_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "10",
    "shape": "diamond",
    "style": "filled",
    "fillcolor": "#FEF9E7",
    "color": "#F39C12",
    "penwidth": "1.2",
}

START_END_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "10",
    "shape": "ellipse",
    "style": "filled",
    "fillcolor": "#E8F8F5",
    "color": "#1ABC9C",
    "penwidth": "1.5",
}

DB_ATTRS = {
    "fontname": "SimHei",
    "fontsize": "10",
    "shape": "cylinder",
    "style": "filled",
    "fillcolor": "#F5EEF8",
    "color": "#8E44AD",
    "penwidth": "1.2",
}


def new_graph(name, label):
    g = graphviz.Digraph(name=name, format="png")
    g.attr("graph", **GRAPH_ATTRS)
    g.attr("node", **NODE_ATTRS)
    g.attr("edge", **EDGE_ATTRS)
    g.attr("graph", label=label, fontsize="14")
    return g


def decision_node(g, name, label):
    g.node(name, label, **DECISION_ATTRS)


def start_end_node(g, name, label):
    g.node(name, label, **START_END_ATTRS)


def db_node(g, name, label):
    g.node(name, label, **DB_ATTRS)


def process_node(g, name, label):
    g.node(name, label)


def make_login_auth_flow():
    """图4-3-1: 登录认证与权限控制模块流程图"""
    g = new_graph("fig4-3-login-auth", "图4.3 登录认证与权限控制模块流程")

    start_end_node(g, "start", "用户访问系统")
    process_node(g, "show_login", "显示登录页面\n(输入用户名/密码)")
    process_node(g, "submit", "POST /api/auth/login\n提交登录请求")
    decision_node(g, "validate", "验证用户名\n和密码？")
    process_node(g, "fail", "返回错误提示\n(用户名或密码错误)")
    process_node(g, "create_session", "写入Session\n(user_id, username, role)")
    db_node(g, "op_log_login", "写入操作日志\noperation_log表")
    process_node(g, "load_main", "进入系统主页\n根据role加载菜单")
    decision_node(g, "check_role", "角色判断")
    process_node(g, "admin_view", "加载管理员视图\n(完整菜单+管理功能)")
    process_node(g, "user_view", "加载普通用户视图\n(上传检测、结果查看)")
    process_node(g, "operate", "用户执行操作\n(检测/查询/管理)")
    decision_node(g, "auth_check", "每次API请求\n校验Session？")
    process_node(g, "execute", "执行请求\n返回数据")
    process_node(g, "redirect_login", "返回401\n跳转登录页")
    start_end_node(g, "end", "操作完成")

    g.edge("start", "show_login")
    g.edge("show_login", "submit")
    g.edge("submit", "validate")
    g.edge("validate", "fail", "失败")
    g.edge("fail", "show_login")
    g.edge("validate", "create_session", "成功")
    g.edge("create_session", "op_log_login")
    g.edge("op_log_login", "load_main")
    g.edge("load_main", "check_role")
    g.edge("check_role", "admin_view", "admin")
    g.edge("check_role", "user_view", "user")
    g.edge("admin_view", "operate")
    g.edge("user_view", "operate")
    g.edge("operate", "auth_check")
    g.edge("auth_check", "execute", "有效")
    g.edge("auth_check", "redirect_login", "失效")
    g.edge("redirect_login", "show_login")
    g.edge("execute", "end")

    return g


def make_dashboard_flow():
    """图4-3-2: 系统首页与统计展示模块流程图"""
    g = new_graph("fig4-3-dashboard", "图4.4 系统首页与统计展示模块流程")

    start_end_node(g, "start", "用户登录后\n进入系统首页")
    process_node(g, "request", "GET /api/dashboard\n前端发起统计请求")
    decision_node(g, "auth", "Session与\n角色校验？")
    process_node(g, "err", "返回401/403")
    process_node(g, "query_stats", "后端查询统计数据\nbuild_dashboard_stats()")
    decision_node(g, "is_admin", "角色==admin？")
    process_node(g, "global_query", "全局数据查询\n不添加user_id过滤\n返回全平台统计")
    process_node(g, "user_query", "个人数据查询\nWHERE user_id = current_user\n仅返回自身数据")
    db_node(g, "db_records", "查询detect_record\n样本总数/正常/攻击")
    db_node(g, "db_attacks", "查询attack_result\n攻击类型分布(GROUP BY)")
    db_node(g, "db_alarms", "查询alarm_log\n告警数量统计")
    db_node(g, "db_trends", "查询detect_record\n近期攻击趋势(按日)")
    process_node(g, "aggregate", "聚合统计数据\n组装JSON响应")
    process_node(g, "render", "前端渲染页面\n统计卡片+ECharts图表")
    start_end_node(g, "end", "首页展示完成\n(统计卡片/攻击分布/\n近期趋势/最近记录)")

    g.edge("start", "request")
    g.edge("request", "auth")
    g.edge("auth", "err", "未授权")
    g.edge("err", "start")
    g.edge("auth", "query_stats", "已授权")
    g.edge("query_stats", "is_admin")
    g.edge("is_admin", "global_query", "是")
    g.edge("is_admin", "user_query", "否")
    g.edge("global_query", "db_records")
    g.edge("user_query", "db_records")
    g.edge("db_records", "db_attacks")
    g.edge("db_attacks", "db_alarms")
    g.edge("db_alarms", "db_trends")
    g.edge("db_trends", "aggregate")
    g.edge("aggregate", "render")
    g.edge("render", "end")

    return g


def make_upload_detection_flow():
    """图4-3-3: 数据上传与检测任务模块流程图"""
    g = new_graph("fig4-3-upload-detection", "图4.5 数据上传与检测任务模块流程")

    start_end_node(g, "start", "用户进入上传检测页面")
    process_node(g, "select_model", "选择检测模型\n(从model_info表中\n获取已启用模型)")
    process_node(g, "select_file", "选择待检测CSV文件\n(前端文件选择器)")
    decision_node(g, "check_ext", "文件后缀\n是否为.csv？")
    process_node(g, "reject", "提示：仅支持\nCSV文件上传")
    process_node(g, "upload", "POST /api/detect/upload\n提交文件与模型ID")
    process_node(g, "save_file", "save_dataset()\n时间戳重命名\n写入uploads/目录")
    db_node(g, "db_dataset", "登记数据集信息\ndataset_info表")
    process_node(g, "count_rows", "统计CSV样本行数\ncount_csv_rows()")
    db_node(g, "db_task", "创建DetectionTask\nstatus='queued'\ntotal_rows=样本数")
    db_node(g, "db_oplog", "操作日志\ncreate_task")
    process_node(g, "spawn_thread", "启动后台检测线程\n_run_detection_task()")
    process_node(g, "return_task", "立即返回响应\n(task_id, status='queued')")
    process_node(g, "poll", "前端定时轮询\nGET /api/tasks/<id>\n更新进度条")
    process_node(g, "bg_update_status", "后台线程\n更新task.status='running'\n逐块更新processed_rows")
    process_node(g, "bg_preprocess", "逐块读取CSV\n列名清洗/缺失值填充\n标准化(mean/std)")
    process_node(g, "bg_inference", "批量模型推理\nUniversalIDSModel\nbatch_size=1024")
    process_node(g, "bg_classify", "判定BENIGN/ATTACK\n计算risk_level")
    process_node(g, "bg_save_results", "批量写入结果缓冲区\nAttackResult + AlarmLog\n达到阈值flush到DB")
    decision_node(g, "check_done", "全部样本\n处理完成？")
    process_node(g, "bg_complete", "更新DetectRecord\nsample/normal/attack\n计数统计")
    db_node(g, "bg_update_task", "更新task.status\n='completed'\nrecord_id=检测记录ID")
    process_node(g, "poll_detect", "前端轮询检测到\nstatus='completed'\n跳转结果详情页")
    start_end_node(g, "end", "检测任务完成\n自动展示检测结果")

    g.edge("start", "select_model")
    g.edge("select_model", "select_file")
    g.edge("select_file", "check_ext")
    g.edge("check_ext", "reject", "否")
    g.edge("reject", "select_file")
    g.edge("check_ext", "upload", "是")
    g.edge("upload", "save_file")
    g.edge("save_file", "db_dataset")
    g.edge("db_dataset", "count_rows")
    g.edge("count_rows", "db_task")
    g.edge("db_task", "db_oplog")
    g.edge("db_oplog", "spawn_thread")
    g.edge("spawn_thread", "return_task")
    g.edge("return_task", "poll")
    g.edge("spawn_thread", "bg_update_status")
    g.edge("bg_update_status", "bg_preprocess")
    g.edge("bg_preprocess", "bg_inference")
    g.edge("bg_inference", "bg_classify")
    g.edge("bg_classify", "bg_save_results")
    g.edge("bg_save_results", "check_done")
    g.edge("check_done", "bg_preprocess", "否,继续处理")
    g.edge("check_done", "bg_complete", "是")
    g.edge("bg_complete", "bg_update_task")
    g.edge("bg_update_task", "poll_detect")
    g.edge("poll_detect", "end")
    g.edge("poll", "poll", "轮询间隔\n等待完成")

    return g


def make_results_history_flow():
    """图4-3-4: 检测结果与历史记录模块流程图"""
    g = new_graph("fig4-3-results-history", "图4.6 检测结果与历史记录模块流程")

    start_end_node(g, "start", "用户进入检测结果页面")
    process_node(g, "load_list", "GET /api/records\n前端请求记录列表")
    decision_node(g, "is_admin", "角色==admin？")
    process_node(g, "filter_self", "WHERE user_id = 当前用户\n过滤自身记录")
    process_node(g, "all_records", "返回全部记录\n(admin可见所有)")
    db_node(g, "db_records", "查询detect_record\n按detect_time降序\n关联user表获取操作者")
    db_node(g, "db_alarm_count", "统计每条记录的\n告警数量(alarm_log)")
    process_node(g, "render_list", "前端渲染记录列表\n(源文件/样本数/攻击数/\n检测时间/状态/操作者)")
    process_node(g, "search_filter", "用户输入关键词\n前端filteredRecords\n实时过滤")
    process_node(g, "click_detail", "点击某条记录\n进入检测详情")
    process_node(g, "load_detail", "GET /api/records/<id>\n请求记录详情")
    db_node(g, "db_detail", "查询单个DetectRecord\n关联AttackResult列表\n(attack_type/risk_level\n/confidence/src_ip/dst_ip)")
    process_node(g, "render_detail", "前端渲染详情页\n样本总数/正常/攻击统计\n+攻击结果列表")
    decision_node(g, "is_admin2", "管理员操作？")
    process_node(g, "delete", "DELETE /api/records/<id>\n删除检测记录\n+级联删除attack_result\n+级联删除alarm_log")
    db_node(g, "db_delete", "执行删除事务\n+operation_log记录")
    process_node(g, "refresh", "刷新记录列表")
    start_end_node(g, "end", "结果查看完成")

    g.edge("start", "load_list")
    g.edge("load_list", "is_admin")
    g.edge("is_admin", "filter_self", "user")
    g.edge("is_admin", "all_records", "admin")
    g.edge("filter_self", "db_records")
    g.edge("all_records", "db_records")
    g.edge("db_records", "db_alarm_count")
    g.edge("db_alarm_count", "render_list")
    g.edge("render_list", "search_filter")
    g.edge("search_filter", "click_detail")
    g.edge("click_detail", "load_detail")
    g.edge("load_detail", "db_detail")
    g.edge("db_detail", "render_detail")
    g.edge("render_detail", "is_admin2")
    g.edge("is_admin2", "delete", "是")
    g.edge("is_admin2", "end", "否")
    g.edge("delete", "db_delete")
    g.edge("db_delete", "refresh")
    g.edge("refresh", "load_list")

    return g


def make_alarm_management_flow():
    """图4-3-5: 告警管理模块流程图"""
    g = new_graph("fig4-3-alarm-management", "图4.7 告警管理模块流程")

    start_end_node(g, "start", "管理员进入告警中心")
    process_node(g, "load_alarms", "GET /api/alarms\n?page=1&page_size=20\n&status=all")
    db_node(g, "db_query", "查询alarm_log\nJOIN detect_record\n过滤traffic_开头的记录\n按create_time降序分页")
    process_node(g, "render", "前端渲染告警列表\n(告警内容/告警级别/\n状态/创建时间/分页)")
    process_node(g, "filter_status", "管理员按状态筛选\n(unprocessed/processed\n/ignored)")
    decision_node(g, "action", "管理员操作？")
    process_node(g, "update", "PATCH /api/alarms/<id>\n更新告警状态\n{\"status\": \"processed\"}")
    decision_node(g, "valid_status", "状态值合法？\n(unprocessed/processed\n/ignored)")
    process_node(g, "error", "返回400错误提示")
    db_node(g, "db_update", "更新alarm_log.status\n+operation_log记录")
    process_node(g, "view_detail", "查看关联检测记录\n跳转到检测详情页\n(对应record_id)")
    process_node(g, "refresh_list", "刷新告警列表\n更新分页信息")
    start_end_node(g, "end", "告警处理完成")

    g.edge("start", "load_alarms")
    g.edge("load_alarms", "db_query")
    g.edge("db_query", "render")
    g.edge("render", "filter_status")
    g.edge("filter_status", "action")
    g.edge("action", "update", "更新状态")
    g.edge("action", "view_detail", "查看详情")
    g.edge("action", "end", "仅浏览")
    g.edge("update", "valid_status")
    g.edge("valid_status", "error", "非法值")
    g.edge("error", "refresh_list")
    g.edge("valid_status", "db_update", "合法")
    g.edge("db_update", "refresh_list")
    g.edge("view_detail", "end")
    g.edge("refresh_list", "render")
    g.edge("filter_status", "load_alarms", "切换筛选条件")

    return g


def make_model_management_flow():
    """图4-3-6: 模型管理与性能评估模块流程图"""
    g = new_graph("fig4-3-model-management", "图4.8 模型管理与性能评估模块流程")

    start_end_node(g, "start", "管理员进入模型管理页面")
    process_node(g, "load_list", "GET /api/models\n获取所有模型列表\n+active_model_id")
    db_node(g, "db_list", "查询model_info\n按is_active降序\ncreate_time降序")
    process_node(g, "render_list", "前端渲染模型列表\n(名称/类型/准确率/\nF1/启用状态/操作)")
    decision_node(g, "action", "管理员操作？")
    process_node(g, "add", "新增模型")
    process_node(g, "show_form", "显示模型注册表单\n(model_name/path/type\n/指标/字段列表等)")
    process_node(g, "fill_form", "填写模型元数据\n+上传.pth文件(可选)\n+勾选is_active")
    process_node(g, "submit", "POST /api/models\n提交表单数据")
    decision_node(g, "validate", "校验模型路径\n是否存在？")
    process_node(g, "val_fail", "返回错误\n模型文件不存在")
    decision_node(g, "check_first", "是否为第一个\n模型或勾选激活？")
    process_node(g, "deactivate", "取消其他模型激活\nset_active_model()\n唯一激活模式")
    db_node(g, "db_insert", "写入model_info表\n+operation_log")
    process_node(g, "activate", "POST /api/models/<id>\n/activate\n切换激活模型")
    decision_node(g, "check_dep", "是否有任务/记录\n依赖此模型？")
    process_node(g, "delete", "DELETE /api/models/<id>\n删除模型记录")
    process_node(g, "block", "提示：有依赖\n无法删除")
    process_node(g, "view_metrics", "查看模型性能指标\n(accuracy/precision\n/recall/f1/fpr/fnr\n/inference_latency)")
    process_node(g, "eval", "调用ModelService\n加载模型+测试集评估\n或读取缓存评价指标\n显示混淆矩阵等")
    start_end_node(g, "end", "模型管理完成")

    g.edge("start", "load_list")
    g.edge("load_list", "db_list")
    g.edge("db_list", "render_list")
    g.edge("render_list", "action")
    g.edge("action", "add", "新增")
    g.edge("action", "activate", "切换激活")
    g.edge("action", "delete", "删除")
    g.edge("action", "view_metrics", "查看指标")
    g.edge("action", "end", "浏览完毕")
    g.edge("add", "show_form")
    g.edge("show_form", "fill_form")
    g.edge("fill_form", "submit")
    g.edge("submit", "validate")
    g.edge("validate", "val_fail", "不存在")
    g.edge("val_fail", "show_form")
    g.edge("validate", "check_first", "存在")
    g.edge("check_first", "deactivate", "是")
    g.edge("check_first", "db_insert", "否")
    g.edge("deactivate", "db_insert")
    g.edge("db_insert", "render_list")
    g.edge("activate", "validate")
    g.edge("delete", "check_dep")
    g.edge("check_dep", "block", "是")
    g.edge("block", "render_list")
    g.edge("check_dep", "db_insert", "否(写operation_log+delete)")
    g.edge("view_metrics", "eval")
    g.edge("eval", "end")

    return g


def make_traffic_monitor_flow():
    """图4-3-7: 实时流量监测模块流程图"""
    g = new_graph("fig4-3-traffic-monitor", "图4.9 实时流量监测模块流程")

    start_end_node(g, "start", "管理员进入流量监测页面")
    process_node(g, "config", "GET /api/traffic-monitor\n获取监测状态")
    process_node(g, "check_ready", "检查环境就绪状态\nscapy_ready/\ncicflowmeter_ready/\npipeline_ready")
    decision_node(g, "ready", "环境就绪？\n(pipeline_ready)")
    process_node(g, "setup", "配置抓包参数\nPATCH /api/traffic-monitor\n/config\n设置网卡接口")
    process_node(g, "list_ifaces", "GET /api/traffic-monitor\n/interfaces\n获取可用网卡列表")
    process_node(g, "select_iface", "选择抓包网卡\n(如WLAN/Ethernet)")
    process_node(g, "start_monitor", "POST /api/traffic-monitor\n/start\n启动流量监测线程")
    process_node(g, "bg_capture", "后台:Scapy抓包\nsniff(iface, duration,\nfilter)\n生成PCAP文件")
    process_node(g, "bg_extract", "后台:Python cicflowmeter\nFlowSession处理PCAP\n生成原始特征CSV")
    process_node(g, "bg_normalize", "后台:列名规范化\n_normalize_python_\ncicflowmeter_csv()\n映射78个字段")
    decision_node(g, "has_data", "CSV是否有\n有效数据行？")
    process_node(g, "archive_empty", "归档空文件\nempty_feature_count++")
    process_node(g, "bg_detect", "调用run_detection()\n使用当前激活模型\n执行入侵检测")
    db_node(g, "db_save", "保存检测结果\nDetectRecord+AttackResult\n+AlarmLog")
    process_node(g, "archive", "归档PCAP→pcap_archive\n归档CSV→archive\nprocessed_count++")
    process_node(g, "update_status", "更新监测状态\nlast_scan_at\nlast_processed_file等")
    process_node(g, "poll_interval", "等待轮询间隔\n(默认10秒)")
    decision_node(g, "stopped", "管理员是否\n停止监测？")
    process_node(g, "stop", "POST /api/traffic-monitor\n/stop\n设置stop_event")
    process_node(g, "show_status", "前端定时刷新\n展示监测状态面板\n(运行状态/处理数量/\n最近活动时间)")
    start_end_node(g, "end", "监测流程结束")

    g.edge("start", "config")
    g.edge("config", "check_ready")
    g.edge("check_ready", "ready")
    g.edge("ready", "setup", "是")
    g.edge("ready", "show_status", "否(显示未就绪)")
    g.edge("setup", "list_ifaces")
    g.edge("list_ifaces", "select_iface")
    g.edge("select_iface", "start_monitor")
    g.edge("start_monitor", "bg_capture")
    g.edge("bg_capture", "bg_extract")
    g.edge("bg_extract", "bg_normalize")
    g.edge("bg_normalize", "has_data")
    g.edge("has_data", "archive_empty", "否")
    g.edge("has_data", "bg_detect", "是")
    g.edge("archive_empty", "archive")
    g.edge("bg_detect", "db_save")
    g.edge("db_save", "archive")
    g.edge("archive", "update_status")
    g.edge("update_status", "show_status")
    g.edge("show_status", "poll_interval")
    g.edge("poll_interval", "stopped")
    g.edge("stopped", "bg_capture", "否,继续")
    g.edge("stopped", "stop", "是")
    g.edge("stop", "end")

    return g


def make_user_management_flow():
    """图4-3-8: 用户管理模块流程图"""
    g = new_graph("fig4-3-user-management", "图4.10 用户管理模块流程")

    start_end_node(g, "start", "管理员进入用户管理页面")
    process_node(g, "load_users", "GET /api/users\n获取所有用户列表")
    db_node(g, "db_list", "查询user表\n按create_time降序")
    process_node(g, "render", "前端渲染用户列表\n(用户名/角色/创建时间)")
    decision_node(g, "action", "管理员操作？")
    process_node(g, "add", "新增用户")
    process_node(g, "edit", "编辑用户")
    process_node(g, "del", "删除用户")
    process_node(g, "fill_add", "填写表单\n(用户名/密码/角色)")
    process_node(g, "fill_edit", "修改信息\n(用户名/角色/新密码)")
    process_node(g, "submit_add", "POST /api/users\n提交新增请求")
    process_node(g, "submit_edit", "PATCH /api/users/<id>\n提交修改请求")
    decision_node(g, "validate", "校验：用户名\n唯一性+角色合法性\n+密码非空？")
    process_node(g, "val_fail", "返回错误提示\n(用户名已存在/角色\n非法/密码为空)")
    decision_node(g, "check_self", "是否删除\n自己？")
    decision_node(g, "has_records", "是否有关联\n检测记录？")
    process_node(g, "block_self", "提示：不能删除\n当前登录账号")
    process_node(g, "block_records", "提示：有检测记录\n无法删除")
    process_node(g, "exec_del", "DELETE /api/users/<id>\n执行删除")
    db_node(g, "db_save", "写入/更新user表\n+operation_log记录")
    process_node(g, "refresh", "刷新用户列表")
    start_end_node(g, "end", "用户管理完成")

    g.edge("start", "load_users")
    g.edge("load_users", "db_list")
    g.edge("db_list", "render")
    g.edge("render", "action")
    g.edge("action", "add", "新增")
    g.edge("action", "edit", "编辑")
    g.edge("action", "del", "删除")
    g.edge("action", "end", "浏览完毕")
    g.edge("add", "fill_add")
    g.edge("fill_add", "submit_add")
    g.edge("edit", "fill_edit")
    g.edge("fill_edit", "submit_edit")
    g.edge("submit_add", "validate")
    g.edge("submit_edit", "validate")
    g.edge("validate", "val_fail", "不通过")
    g.edge("val_fail", "render")
    g.edge("validate", "db_save", "通过")
    g.edge("del", "check_self")
    g.edge("check_self", "block_self", "是")
    g.edge("block_self", "render")
    g.edge("check_self", "has_records", "否")
    g.edge("has_records", "block_records", "是")
    g.edge("block_records", "render")
    g.edge("has_records", "exec_del", "否")
    g.edge("exec_del", "db_save")
    g.edge("db_save", "refresh")
    g.edge("refresh", "render")

    return g


def main():
    flows = [
        ("fig4-3-login-auth", make_login_auth_flow, "登录认证与权限控制"),
        ("fig4-3-dashboard", make_dashboard_flow, "系统首页与统计展示"),
        ("fig4-3-upload-detection", make_upload_detection_flow, "数据上传与检测任务"),
        ("fig4-3-results-history", make_results_history_flow, "检测结果与历史记录"),
        ("fig4-3-alarm-management", make_alarm_management_flow, "告警管理"),
        ("fig4-3-model-management", make_model_management_flow, "模型管理与性能评估"),
        ("fig4-3-traffic-monitor", make_traffic_monitor_flow, "实时流量监测"),
        ("fig4-3-user-management", make_user_management_flow, "用户管理"),
    ]

    for name, maker, desc in flows:
        print(f"Generating {name} ({desc})...")
        g = maker()
        output_path = OUTPUT_DIR / name
        g.render(str(output_path), cleanup=True)
        print(f"  -> {output_path}.png")

    print("\nAll flowcharts generated successfully!")


if __name__ == "__main__":
    main()
