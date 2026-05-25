"""
Generate current system function module overview diagram.
Reflects the 8-module structure of the restructured project.
"""
from pathlib import Path
import graphviz

OUTPUT_DIR = Path(r"C:\graduationProject\project\model\thesis_figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

g = graphviz.Digraph(name="fig4-2-function-modules", format="png")

g.attr("graph",
    fontname="SimHei",
    rankdir="TB",
    splines="ortho",
    nodesep="0.4",
    ranksep="0.6",
    dpi="150",
    bgcolor="white",
    label="图4.2 系统整体功能模块划分",
    fontsize="16",
    labelloc="t",
)

g.attr("node",
    fontname="SimHei",
    fontsize="10",
    shape="box",
    style="rounded,filled",
    fillcolor="#EBF5FB",
    color="#2980B9",
    penwidth="1.2",
)

g.attr("edge",
    fontname="SimHei",
    fontsize="9",
    color="#7F8C8D",
    arrowhead="vee",
)

# Top-level: system root
g.node("root", "基于深度学习的\n网络入侵检测系统", shape="box", style="filled",
       fillcolor="#D4E6F1", color="#1A5276", fontsize="12", penwidth="2")

# Layer 1: three functional domains
with g.subgraph(name="cluster_common") as c:
    c.attr(label="通用功能", fontname="SimHei", fontsize="11",
           style="rounded,dashed", color="#7F8C8D")
    c.node("login", "登录认证与权限控制\n──────────────\n· Session认证\n· admin/user角色\n· login_required/admin_required\n· 操作日志审计")
    c.node("dashboard", "系统首页与统计展示\n──────────────\n· 统计卡片(记录/告警/样本)\n· ECharts攻击类型分布饼图\n· ECharts近期趋势折线图\n· 角色过滤数据范围")

with g.subgraph(name="cluster_core") as c:
    c.attr(label="核心业务", fontname="SimHei", fontsize="11",
           style="rounded,dashed", color="#E67E22")
    c.node("detection", "数据上传与检测任务\n──────────────\n· CSV文件上传+校验\n· 后台异步线程检测\n· 分块读取+批量推理\n· 结果缓冲批量写DB\n· 前端轮询进度跟踪")
    c.node("results", "检测结果与历史记录\n──────────────\n· 记录列表(分角色过滤)\n· 关键词实时搜索\n· 攻击结果详情展示\n· 管理员删除+级联清理")
    c.node("alarms", "告警管理\n──────────────\n· 分页查询+状态筛选\n· 在线流量告警汇总\n· 状态更新(unprocessed/\n  processed/ignored)\n· 闭环处置流程")
    c.node("traffic", "实时流量监测\n──────────────\n· Scapy在线抓包\n· Python cicflowmeter特征提取\n· 78字段列名规范化映射\n· 四阶段循环监测\n· PCAP/CSV自动归档")

with g.subgraph(name="cluster_admin") as c:
    c.attr(label="系统管理", fontname="SimHei", fontsize="11",
           style="rounded,dashed", color="#8E44AD")
    c.node("models", "模型管理与性能评估\n──────────────\n· 模型注册(元数据+.pth上传)\n· 唯一激活单例模式\n· 激活切换+删除保护\n· 6项性能指标展示\n· 测试集评估缓存")
    c.node("users", "用户管理\n──────────────\n· 用户增删改查\n· 角色枚举校验\n· pbkdf2:sha256密码哈希\n· 自删除保护\n· 关联记录依赖检查")

# Edges: root → three domains
g.edge("root", "login", style="bold", color="#1A5276")
g.edge("root", "dashboard", style="bold", color="#1A5276")
g.edge("root", "detection", style="bold", color="#1A5276")
g.edge("root", "results", style="bold", color="#1A5276")
g.edge("root", "alarms", style="bold", color="#1A5276")
g.edge("root", "traffic", style="bold", color="#1A5276")
g.edge("root", "models", style="bold", color="#1A5276")
g.edge("root", "users", style="bold", color="#1A5276")

# Cross-module data flow edges (dashed)
g.edge("login", "dashboard", "认证通过后进入", style="dashed", color="#2980B9", arrowhead="none")
g.edge("detection", "results", "任务完成后跳转", style="dashed", color="#2980B9", arrowhead="none")
g.edge("results", "alarms", "攻击记录→告警", style="dashed", color="#E74C3C", arrowhead="none")
g.edge("traffic", "detection", "CSV→检测", style="dashed", color="#E67E22", arrowhead="none")

output_path = OUTPUT_DIR / "fig4-2-function-modules"
g.render(str(output_path), cleanup=True)
print(f"Generated: {output_path}.png")
