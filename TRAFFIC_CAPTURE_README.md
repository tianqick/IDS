# Traffic Capture README

这份文档专门说明项目里的“抓取流量”功能现在是怎么工作的，包括：

- 完整处理链路
- 每一步用到的工具
- 关键代码位置
- 配置项含义
- 常见失败原因

## 1. 功能目标

这个功能不是只把网络包抓下来，而是把抓到的流量继续转成特征 CSV，并送进检测模型。

完整链路如下：

```text
Scapy 抓包
-> 保存为 PCAP
-> Python cicflowmeter 提取流量特征
-> 规范化为模型所需 CSV
-> run_detection() 调用模型检测
-> 结果写入数据库
-> 原始文件归档
```

## 2. 当前整体流程

### 第 1 步：启动流量监测线程

系统通过 `TrafficMonitorService.start()` 启动后台线程，循环执行抓包、提取、检测和归档。

对应代码：

- `app/services/traffic_monitor.py`

### 第 2 步：选择抓包网卡

系统先解析 `TRAFFIC_CAPTURE_INTERFACE`，把配置中的网卡序号或名称映射成 `Scapy` 实际使用的接口。

对应代码：

- `TrafficMonitorService._discover_interfaces()`
- `TrafficMonitorService._resolve_capture_interface()`

### 第 3 步：抓包

系统使用 `Scapy` 直接抓流量。

对应代码：

- `TrafficMonitorService._run_scapy_capture()`

涉及配置：

- `TRAFFIC_CAPTURE_INTERFACE`
- `TRAFFIC_CAPTURE_DURATION`
- `TRAFFIC_CAPTURE_FILTER`
- `TRAFFIC_PCAP_DIR`

说明：

- 当前输出格式是 `.pcap`
- 不再依赖 `tshark`
- 默认每轮抓包持续 `TRAFFIC_CAPTURE_DURATION` 秒

### 第 4 步：调用 Python cicflowmeter 提取

抓完包以后，系统不再调用 Java `CICFlowMeter.jar`，而是直接在 Python 进程里执行提取。

对应代码：

- `TrafficMonitorService._run_cicflowmeter_extract()`
- `TrafficMonitorService._run_python_cicflowmeter_extract()`

核心方式：

```text
PcapReader(pcap)
-> FlowSession(output_mode="csv", output_file=...)
-> 逐包喂入 session
-> 生成原始 CSV
```

当前实现特点：

- 直接使用 `cicflowmeter.flow_session.FlowSession`
- 不走 `cicflowmeter` 自带 CLI
- 避开旧 CLI 在当前版本下的兼容性问题

### 第 5 步：规范化 CSV

Python `cicflowmeter` 生成的列名和项目模型训练时使用的 CIC-IDS 风格列头并不完全一致，所以系统会做一次列头规范化。

对应代码：

- `TrafficMonitorService._normalize_python_cicflowmeter_csv()`
- `TrafficMonitorService._normalized_cicflowmeter_columns()`

结果：

- 输出到 `TRAFFIC_FLOW_INPUT_DIR`
- 文件名为项目当前检测流程预期的 `.csv`

### 第 6 步：调用模型检测

生成 CSV 后，系统会自动调用现有检测逻辑。

对应代码：

- `app/services/data_service.py`
- `app/services/model_service.py`

流程：

```text
读取 CSV
-> 预处理特征列
-> 模型推理
-> 生成攻击结果
-> 生成告警
-> 写入数据库
```

### 第 7 步：归档文件

处理完成后，系统会把 `pcap` 和 `csv` 挪到归档目录，避免重复处理。

归档目录：

- `TRAFFIC_PCAP_ARCHIVE_DIR`
- `TRAFFIC_FLOW_ARCHIVE_DIR`

## 3. 现在到底用了什么

### 抓包阶段

使用：

- `Scapy`
- `Npcap`（Windows 抓包驱动）

作用：

- 从指定网卡抓包
- 按 BPF 过滤条件筛流量
- 保存为 `pcap`

### 特征提取阶段

使用：

- `cicflowmeter`
- `scapy.utils.PcapReader`
- `cicflowmeter.flow_session.FlowSession`

作用：

- 读取 `pcap`
- 聚合 flow
- 计算每条 flow 的统计特征
- 输出原始 CSV
- 规范化为模型需要的列头

### 检测阶段

使用：

- `run_detection()`
- `ModelService`
- `torch`
- `numpy`
- `pandas`
- `scikit-learn`

### 服务管理阶段

使用：

- `Flask`
- `threading`
- `SQLAlchemy`

## 4. 配置项说明

### 抓包配置

```env
TRAFFIC_CAPTURE_INTERFACE=1
TRAFFIC_CAPTURE_DURATION=15
TRAFFIC_CAPTURE_FILTER=tcp port 5000
```

说明：

- `TRAFFIC_CAPTURE_INTERFACE`
  - 抓包网卡
  - 可以是接口序号，也可以是接口名
- `TRAFFIC_CAPTURE_DURATION`
  - 每轮抓包持续时间，单位秒
- `TRAFFIC_CAPTURE_FILTER`
  - 可选 BPF 过滤条件

### 调度配置

```env
TRAFFIC_MONITOR_INTERVAL=10
AUTO_START_TRAFFIC_MONITOR=false
```

说明：

- `TRAFFIC_MONITOR_INTERVAL`
  - 一轮处理结束后，等待多久再开始下一轮
- `AUTO_START_TRAFFIC_MONITOR`
  - 应用启动后是否自动开始后台监测

当前默认节奏是：

```text
抓 15 秒 -> 处理这一轮 PCAP/CSV -> 等 10 秒 -> 再抓下一轮
```

### 目录配置

```env
TRAFFIC_FLOW_INPUT_DIR=...
TRAFFIC_FLOW_ARCHIVE_DIR=...
TRAFFIC_PCAP_DIR=...
TRAFFIC_PCAP_ARCHIVE_DIR=...
```

说明：

- `TRAFFIC_PCAP_DIR`
  - 新抓到的 `pcap`
- `TRAFFIC_PCAP_ARCHIVE_DIR`
  - 提取完成后的 `pcap` 归档目录
- `TRAFFIC_FLOW_INPUT_DIR`
  - 规范化后的 CSV 输入目录
- `TRAFFIC_FLOW_ARCHIVE_DIR`
  - 检测完成后的 CSV 归档目录

## 5. 本地单文件测试接口

为了精确排查 “抓到包了，但没有转出 CSV” 这类问题，项目已经增加了单文件测试接口：

```text
POST /api/traffic-monitor/test-extract
```

作用：

- 指定一个现有 `pcap`
- 单独跑一次 Python `cicflowmeter` 提取
- 返回这次提取的成功/失败信息
- 更容易定位问题是在抓包、提取，还是后续检测

对应代码：

- `app/routes/api.py`
- `app/services/traffic_monitor.py`
- `app/static/js/vue-app.js`

## 6. 为什么不再用 Java CICFlowMeter

旧方案的问题主要在这里：

- 依赖 Java 运行时
- 依赖 `jNetPcap` native 库
- 自动化调用时容易踩 GUI / classpath / DLL 路径问题
- 之前这条链路就是 CSV 提取失败的主要来源

当前 Python 方案的优势：

- 环境依赖更集中，都在项目 `.venv`
- 单个 `pcap` 更容易复现和调试
- 可以直接在 Python 代码里拿到更清晰的异常
- 已经验证可以成功处理问题样本 `traffic_20260510110243.pcap`

## 7. 常见问题

### 1. 为什么界面显示“抓包成功”，但“特征提取失败”？

因为这两个状态现在已经拆开显示了，说明：

- 抓包阶段成功生成了 `pcap`
- 但提取阶段没有成功生成可用 CSV

这时优先检查：

- 当前环境是否为项目 `.venv`
- `cicflowmeter` 是否成功安装
- `pcap` 是否真的含有足够数据包
- 是否能通过单文件测试接口复现

### 2. 为什么会出现 `sample_count = 0`？

通常表示：

- 抓到的流量太少
- 包不完整
- 不足以形成有效 flow

也就是链路可能是通的，但样本内容太弱。

### 3. 为什么感觉“有 10 秒流量没抓”？

因为默认配置是：

- 抓包 15 秒
- 一轮完成后等待 10 秒

所以如果没有做连续抓包拼接，中间这 10 秒默认不抓。

### 4. 怎么验证某个 `pcap` 到底能不能转成 CSV？

直接用新增的单文件测试接口，或者走界面里的对应测试入口，单独跑那份 `pcap`。

## 8. 对应代码位置

- 抓包与自动监测主逻辑：`app/services/traffic_monitor.py`
- 检测与结果写库：`app/services/data_service.py`
- 模型推理：`app/services/model_service.py`
- API 接口：`app/routes/api.py`
- 前端交互：`app/static/js/vue-app.js`
- 配置：`app/config.py`

## 9. 一句话总结

现在这条自动流量处理链已经改成：

```text
抓包 -> Python cicflowmeter 提取 -> 规范化 CSV -> 模型检测 -> 写库 -> 归档
```

也就是说，项目已经彻底切离旧的 Java `CICFlowMeter + jNetPcap` 路线。
