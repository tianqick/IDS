# Traffic Capture README

这份文档专门说明项目里的“抓取流量”功能是怎么工作的，包括：

- 完整流程
- 每一步用了什么工具
- 关键代码位置
- 配置项说明
- 运行时会产出什么文件
- 常见问题

## 1. 功能目标

这个功能的目标不是只把网络包抓下来，而是把抓到的流量继续转成特征文件，并送进检测模型。

完整链路是：

```text
Scapy 抓包
-> 保存为 PCAP
-> CICFlowMeter CLI 提取流量特征
-> 生成 CSV
-> run_detection() 调用模型检测
-> 结果写入数据库
-> 原始文件归档
```

## 2. 全流程总览

项目现在的自动流量监测流程如下：

### 第 1 步：启动流量监测线程

系统通过 `TrafficMonitorService.start()` 启动后台线程。

用到的内容：

- Python `threading.Thread`
- Flask app context

对应代码：

- [app/services/traffic_monitor.py](c:\graduationProject\project\model\app\services\traffic_monitor.py:1)

作用：

- 在后台循环执行扫描
- 定时抓包
- 定时检查是否生成了新的 CSV
- 自动送检

### 第 2 步：选择抓包网卡

系统先确定要在哪个网卡上抓包。

用到的内容：

- `Scapy` 的接口枚举能力
- 配置项 `TRAFFIC_CAPTURE_INTERFACE`

对应代码：

- `TrafficMonitorService._discover_interfaces()`
- `TrafficMonitorService._resolve_capture_interface()`

作用：

- 列出本机可用网卡
- 把配置里的接口 ID 或接口名映射成 Scapy 真正使用的接口名

### 第 3 步：抓包

系统使用 `Scapy` 直接抓流量。

用到的内容：

- `scapy.all.sniff`
- `scapy.all.wrpcap`

对应代码：

- `TrafficMonitorService._run_scapy_capture()`

核心逻辑：

```text
读取配置
-> 确定网卡
-> 设置抓包时长
-> 设置 BPF 过滤器
-> sniff()
-> wrpcap() 写入 .pcap
```

这里实际用到的配置有：

- `TRAFFIC_CAPTURE_INTERFACE`
- `TRAFFIC_CAPTURE_DURATION`
- `TRAFFIC_CAPTURE_FILTER`
- `TRAFFIC_PCAP_DIR`

说明：

- 现在输出的是 `.pcap`
- 不再用 `tshark`
- 之所以用 `.pcap` 而不是 `.pcapng`，是因为后续 `CICFlowMeter` CLI 对 `.pcap` 更稳定

### 第 4 步：调用 CICFlowMeter CLI

抓完包以后，系统调用 `CICFlowMeter` 的命令行入口，把 `pcap` 转成特征 `CSV`。

用到的内容：

- Java
- `CICFlowMeter.jar`
- `cic.cs.unb.ca.ifm.Cmd`
- `jnetpcap.dll`
- `jnetpcap-pcap100.dll`

对应代码：

- `TrafficMonitorService._run_cicflowmeter_extract()`

当前命令格式：

```text
java -Djava.library.path=C:\tools\CICFlowMeter\native ^
     -cp C:\tools\CICFlowMeter\CICFlowMeter.jar ^
     cic.cs.unb.ca.ifm.Cmd "{pcap}" "{output_dir}"
```

这里每一部分的作用是：

- `java`：运行 Java 程序
- `-Djava.library.path=...`：告诉 JVM 去哪里找 native DLL
- `-cp ...CICFlowMeter.jar`：指定 classpath
- `cic.cs.unb.ca.ifm.Cmd`：命令行入口，不走 GUI
- `"{pcap}"`：输入抓包文件
- `"{output_dir}"`：输出 CSV 的目录

相关配置：

- `CICFLOWMETER_JAR_PATH`
- `JNETPCAP_LIBRARY_PATH`
- `CICFLOWMETER_COMMAND`

### 第 5 步：生成 CSV

如果 `CICFlowMeter` 正常工作，它会在输出目录生成一个流量特征 CSV。

常见文件名类似：

```text
traffic_20260508174009.pcap_Flow.csv
```

系统随后会：

- 检查目标 CSV 是否存在
- 如果 `CICFlowMeter` 实际生成了一个变体文件名，也会尝试重命名为期望名

对应代码：

- `TrafficMonitorService._run_cicflowmeter_extract()`

### 第 6 步：调用模型检测

生成 CSV 后，系统把 CSV 送入检测逻辑。

用到的内容：

- `run_detection()`
- `ModelService`
- PyTorch 模型

对应代码：

- [app/services/data_service.py](c:\graduationProject\project\model\app\services\data_service.py:1)
- [app/services/model_service.py](c:\graduationProject\project\model\app\services\model_service.py:1)

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

处理完成后，系统会把文件移走，避免重复处理。

用到的内容：

- Python `pathlib.Path.replace`

归档目录：

- 抓包文件：`TRAFFIC_PCAP_ARCHIVE_DIR`
- 特征 CSV：`TRAFFIC_FLOW_ARCHIVE_DIR`

对应代码：

- `TrafficMonitorService._capture_and_extract_once()`
- `TrafficMonitorService._process_file()`

## 3. 这个功能具体用了什么

按阶段拆开看：

### 抓包阶段

用了：

- `Scapy`
- `Npcap`（Windows 底层抓包驱动）

作用：

- 从指定网卡抓网络包
- 按过滤器只抓目标流量
- 保存为 `pcap`

### 特征提取阶段

用了：

- `CICFlowMeter.jar`
- `cic.cs.unb.ca.ifm.Cmd`
- `jnetpcap.dll`
- `jnetpcap-pcap100.dll`
- `Packet.dll`
- `wpcap.dll`

作用：

- 读取 `pcap`
- 组装 flow
- 计算每条流的统计特征
- 输出为 CSV

### 检测阶段

用了：

- `run_detection()`
- `ModelService`
- `torch`
- `numpy`
- `pandas`
- `scikit-learn`

作用：

- 读取 `CSV`
- 做预处理
- 跑模型
- 写检测结果和告警

### 服务管理阶段

用了：

- `Flask`
- `threading`
- `SQLAlchemy`

作用：

- 提供 API
- 启停监测线程
- 写入数据库
- 查询状态

## 4. 关键配置项说明

### 抓包配置

```env
TRAFFIC_CAPTURE_INTERFACE=11
TRAFFIC_CAPTURE_DURATION=15
TRAFFIC_CAPTURE_FILTER=tcp port 5000
```

说明：

- `TRAFFIC_CAPTURE_INTERFACE`
  - 抓包网卡
  - 可以是接口 ID，也可以是接口名
- `TRAFFIC_CAPTURE_DURATION`
  - 每次抓包持续多久，单位秒
- `TRAFFIC_CAPTURE_FILTER`
  - BPF 过滤器
  - 例如 `tcp port 5000`

### CICFlowMeter 配置

```env
CICFLOWMETER_JAR_PATH=C:\tools\CICFlowMeter\CICFlowMeter.jar
JNETPCAP_LIBRARY_PATH=C:\tools\CICFlowMeter\native
CICFLOWMETER_COMMAND=java -Djava.library.path=C:\tools\CICFlowMeter\native -cp C:\tools\CICFlowMeter\CICFlowMeter.jar cic.cs.unb.ca.ifm.Cmd "{pcap}" "{output_dir}"
```

说明：

- `CICFLOWMETER_JAR_PATH`
  - CICFlowMeter jar 路径
- `JNETPCAP_LIBRARY_PATH`
  - 存放 `jnetpcap.dll` 的目录
- `CICFLOWMETER_COMMAND`
  - 真正执行的命令

### 目录配置

```env
TRAFFIC_FLOW_INPUT_DIR=...
TRAFFIC_FLOW_ARCHIVE_DIR=...
TRAFFIC_PCAP_DIR=...
TRAFFIC_PCAP_ARCHIVE_DIR=...
```

说明：

- `TRAFFIC_PCAP_DIR`
  - 抓包后的临时 `pcap`
- `TRAFFIC_PCAP_ARCHIVE_DIR`
  - 抓包完成并提取后归档的 `pcap`
- `TRAFFIC_FLOW_INPUT_DIR`
  - `CICFlowMeter` 产出的 CSV 输入目录
- `TRAFFIC_FLOW_ARCHIVE_DIR`
  - 检测完成后归档的 CSV

## 5. 运行时会产生什么文件

### 抓包阶段

例如：

```text
uploads/traffic_flows/pcap/traffic_20260508173127.pcap
```

### 特征提取后

例如：

```text
uploads/traffic_flows/inbox/traffic_20260508173127.csv
```

或者工具原始产物类似：

```text
traffic_20260508173127.pcap_Flow.csv
```

### 检测完成后

CSV 会被移到：

```text
uploads/traffic_flows/archive/
```

PCAP 会被移到：

```text
uploads/traffic_flows/pcap_archive/
```

## 6. 实际验证结论

这个项目里，这条链路已经验证过：

### 已确认可用

- `Scapy` 抓包可用
- `CICFlowMeter Cmd` 可用
- `jnetpcap.dll` + `jnetpcap-pcap100.dll` 已补齐后可生成 CSV
- 自动检测记录可写入数据库

### 验证中发现的重要点

1. `java -jar CICFlowMeter.jar` 会弹 GUI  
   所以后端不能走它，必须走：

   ```text
   java -cp ... cic.cs.unb.ca.ifm.Cmd
   ```

2. `pcapng` 不稳定  
   后来改成输出 `.pcap`

3. `Loopback` 回环口不稳定  
   自动链路在 `WLAN` 这种真实网卡上更稳定

## 7. 常见问题

### 1. 为什么会弹出 CICFlowMeter 窗口？

因为用了：

```text
java -jar CICFlowMeter.jar
```

这会走 GUI 入口。

正确方式是：

```text
java -cp CICFlowMeter.jar cic.cs.unb.ca.ifm.Cmd ...
```

### 2. 为什么报 `UnsatisfiedLinkError`？

因为缺少：

- `jnetpcap.dll`
- `jnetpcap-pcap100.dll`

或者 `-Djava.library.path` 没配对。

### 3. 为什么抓到了 pcap，但没生成 CSV？

常见原因：

- `CICFLOWMETER_COMMAND` 还是旧的 `java -jar`
- `jnetpcap.dll` 没装
- 输出格式是 `pcapng`
- 抓的是 Loopback 流量，工具处理不稳定

### 4. 为什么有记录但 `sample_count = 0`？

这通常说明：

- 流量太少
- 包不完整
- 不足以形成有效 flow

也就是说链路可能是通的，但样本内容太弱。

## 8. 对应代码位置

- 抓包与自动监测主逻辑  
  [app/services/traffic_monitor.py](c:\graduationProject\project\model\app\services\traffic_monitor.py:1)

- 检测与结果写库  
  [app/services/data_service.py](c:\graduationProject\project\model\app\services\data_service.py:1)

- 模型推理  
  [app/services/model_service.py](c:\graduationProject\project\model\app\services\model_service.py:1)

- API 接口  
  [app/routes/api.py](c:\graduationProject\project\model\app\routes\api.py:1)

- 配置  
  [app/config.py](c:\graduationProject\project\model\app\config.py:1)

## 9. 一句话总结

这个“抓取流量”功能不是单纯抓包，而是一条完整的自动处理链：

```text
抓包 -> 转特征 -> 模型检测 -> 写数据库 -> 归档
```

其中每一步分别用了：

- 抓包：`Scapy + Npcap`
- 特征提取：`CICFlowMeter Cmd + jNetPcap`
- 检测：`PyTorch / pandas / numpy / scikit-learn`
- 服务管理：`Flask + threading + SQLAlchemy`
