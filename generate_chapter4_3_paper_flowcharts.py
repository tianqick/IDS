from __future__ import annotations

from pathlib import Path

import generate_chapter4_3_current_flowcharts as charts


charts.OUTPUT_DIR = Path(__file__).resolve().parent / "thesis_figures" / "4_3_paper_flowcharts"
charts.GRAPH_NODESEP = "0.25"
charts.GRAPH_RANKSEP = "0.35"


def module_structure():
    nodes = [
        ("sys", "入侵检测系统", "start"),
        ("common", "通用支撑", "process"),
        ("detect", "检测业务", "process"),
        ("admin", "系统管理", "process"),
        ("auth", "登录认证", "process"),
        ("dashboard", "首页统计", "process"),
        ("upload", "上传检测", "process"),
        ("result", "结果历史", "process"),
        ("alarm", "告警管理", "process"),
        ("traffic", "流量监测", "process"),
        ("model", "模型管理", "process"),
        ("user", "用户管理", "process"),
    ]
    edges = [
        ("sys", "common", ""),
        ("sys", "detect", ""),
        ("sys", "admin", ""),
        ("common", "auth", ""),
        ("common", "dashboard", ""),
        ("detect", "upload", ""),
        ("detect", "result", ""),
        ("detect", "alarm", ""),
        ("detect", "traffic", ""),
        ("admin", "model", ""),
        ("admin", "user", ""),
    ]
    charts.render("fig4-3-paper-1-module-structure", "图4.3-1 核心功能模块划分图", nodes, edges)


def login_permission():
    nodes = [
        ("start", "访问系统", "start"),
        ("session", "检查会话", "decision"),
        ("login", "登录认证", "process"),
        ("role", "识别角色", "decision"),
        ("menu", "加载功能菜单", "process"),
        ("guard", "接口权限校验", "decision"),
        ("biz", "执行业务操作", "process"),
        ("end", "结束", "start"),
    ]
    edges = [
        ("start", "session", ""),
        ("session", "role", "有效"),
        ("session", "login", "无效"),
        ("login", "role", "认证通过"),
        ("role", "menu", "admin/user"),
        ("menu", "guard", ""),
        ("guard", "biz", "通过"),
        ("guard", "login", "拒绝"),
        ("biz", "end", ""),
    ]
    charts.render("fig4-3-paper-2-login-permission", "图4.3-2 登录认证与权限控制流程图", nodes, edges)


def dashboard_stats():
    nodes = [
        ("start", "进入首页", "start"),
        ("scope", "确定统计范围", "decision"),
        ("query", "汇总业务数据", "db"),
        ("stats", "生成统计结果", "process"),
        ("chart", "渲染图表与列表", "process"),
        ("end", "展示完成", "start"),
    ]
    edges = [
        ("start", "scope", ""),
        ("scope", "query", "管理员/普通用户"),
        ("query", "stats", ""),
        ("stats", "chart", ""),
        ("chart", "end", ""),
    ]
    charts.render("fig4-3-paper-3-dashboard-stats", "图4.3-3 系统首页统计展示流程图", nodes, edges)


def offline_detection():
    nodes = [
        ("start", "选择模型与CSV", "start"),
        ("task", "创建检测任务", "db"),
        ("async", "后台异步执行", "process"),
        ("prep", "数据预处理", "process"),
        ("infer", "模型推理", "process"),
        ("save", "保存结果与告警", "db"),
        ("detail", "展示检测详情", "process"),
        ("end", "结束", "start"),
    ]
    edges = [
        ("start", "task", "上传提交"),
        ("task", "async", ""),
        ("async", "prep", ""),
        ("prep", "infer", ""),
        ("infer", "save", ""),
        ("save", "detail", ""),
        ("detail", "end", ""),
    ]
    charts.render("fig4-3-paper-4-offline-detection", "图4.3-4 数据上传与检测任务流程图", nodes, edges)


def result_alarm():
    nodes = [
        ("start", "进入结果页面", "start"),
        ("scope", "按角色过滤记录", "decision"),
        ("list", "展示历史记录", "process"),
        ("detail", "查看检测详情", "process"),
        ("alarm", "生成或查看告警", "process"),
        ("handle", "更新告警状态", "db"),
        ("end", "结束", "start"),
    ]
    edges = [
        ("start", "scope", ""),
        ("scope", "list", "admin/user"),
        ("list", "detail", "选择记录"),
        ("detail", "alarm", "存在攻击"),
        ("alarm", "handle", "管理员处理"),
        ("handle", "end", ""),
        ("detail", "end", "仅查看"),
    ]
    charts.render("fig4-3-paper-5-result-alarm", "图4.3-5 结果展示与告警处理流程图", nodes, edges)


def model_management():
    nodes = [
        ("start", "进入模型管理", "start"),
        ("meta", "登记模型信息", "process"),
        ("check", "校验模型文件", "decision"),
        ("active", "设置启用模型", "db"),
        ("detect", "供检测任务调用", "process"),
        ("cap", "展示模型能力", "process"),
        ("end", "结束", "start"),
    ]
    edges = [
        ("start", "meta", ""),
        ("meta", "check", ""),
        ("check", "meta", "不通过"),
        ("check", "active", "通过"),
        ("active", "detect", ""),
        ("detect", "cap", ""),
        ("cap", "end", ""),
    ]
    charts.render("fig4-3-paper-6-model-management", "图4.3-6 模型管理流程图", nodes, edges)


def traffic_monitoring():
    nodes = [
        ("start", "配置网卡参数", "start"),
        ("run", "启动监测线程", "process"),
        ("pcap", "抓取PCAP", "external"),
        ("csv", "提取流量特征", "external"),
        ("norm", "规范化字段", "process"),
        ("detect", "调用模型检测", "process"),
        ("archive", "保存结果并归档", "db"),
        ("loop", "继续监测？", "decision"),
        ("end", "停止监测", "start"),
    ]
    edges = [
        ("start", "run", ""),
        ("run", "pcap", ""),
        ("pcap", "csv", ""),
        ("csv", "norm", ""),
        ("norm", "detect", ""),
        ("detect", "archive", ""),
        ("archive", "loop", ""),
        ("loop", "pcap", "是"),
        ("loop", "end", "否"),
    ]
    charts.render("fig4-3-paper-7-traffic-monitoring", "图4.3-7 实时流量监测流程图", nodes, edges)


def user_management():
    nodes = [
        ("start", "进入用户管理", "start"),
        ("op", "新增/编辑/删除", "process"),
        ("check", "校验账号与角色", "decision"),
        ("save", "保存用户信息", "db"),
        ("log", "记录操作日志", "db"),
        ("end", "结束", "start"),
    ]
    edges = [
        ("start", "op", ""),
        ("op", "check", ""),
        ("check", "op", "不通过"),
        ("check", "save", "通过"),
        ("save", "log", ""),
        ("log", "end", ""),
    ]
    charts.render("fig4-3-paper-8-user-management", "图4.3-8 用户管理流程图", nodes, edges)


def main() -> None:
    module_structure()
    login_permission()
    dashboard_stats()
    offline_detection()
    result_alarm()
    model_management()
    traffic_monitoring()
    user_management()


if __name__ == "__main__":
    main()
