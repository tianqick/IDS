# DeepIDS Graduation Project

基于 `Flask + Vue 3 + MySQL + PyTorch` 的入侵检测系统，支持：

- CSV 流量特征文件检测
- 模型管理与切换
- 告警记录与检测历史查询
- 基于 `Scapy + Python cicflowmeter` 的自动流量监测

## Project Structure

```text
model/
├─ app/
│  ├─ routes/        # Flask API / 页面路由
│  ├─ services/      # 检测、模型、流量监测核心逻辑
│  ├─ static/        # 前端静态资源
│  └─ templates/     # SPA 模板
├─ artifacts/        # 预处理元数据、评估缓存、监测配置
├─ dataset/          # 训练/评估用数据集
├─ logs/
├─ sample_data/      # 示例流量 CSV
├─ sql/              # 初始化 SQL
├─ uploads/          # 上传文件、模型、自动抓包产物
├─ app.py
├─ requirements.txt
└─ README.md
```

## Requirements

- Python 3.13.x
- MySQL 8.x
- Windows 抓包驱动，通常为 `Npcap`

说明：

- 项目当前已经移除 Java `CICFlowMeter.jar + jNetPcap` 依赖
- 流量特征提取改为 Python 库 `cicflowmeter`
- 推荐使用仓库里的 `.venv`

## Python Dependencies

项目依赖见 `requirements.txt`。

核心依赖包括：

- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- PyMySQL
- python-dotenv
- numpy
- pandas
- scikit-learn
- torch
- scapy
- cicflowmeter

## Quick Start

### 1. Create venv

如果你已经按现在的流程重建过环境，直接激活现有 `.venv` 即可：

```powershell
cd c:\graduationProject\project\model
.\.venv\Scripts\Activate.ps1
```

如果需要从头创建：

```powershell
cd c:\graduationProject\project\model
C:\Users\huang\miniconda3\python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment

```powershell
Copy-Item .env.example .env
```

示例配置：

```env
SECRET_KEY=ids-system-secret-key
DATABASE_URI=mysql+pymysql://root:123456@127.0.0.1:3306/ids_system?charset=utf8mb4
FLASK_RUN_HOST=0.0.0.0
FLASK_RUN_PORT=5000
MODEL_PATH=c:\graduationProject\project\model\1D_CNN_BiLSTM_Attn_best.pth
DATASET_DIR=c:\graduationProject\project\model\dataset
ARTIFACT_DIR=c:\graduationProject\project\model\artifacts
MODEL_INPUT_SIZE=32

TRAFFIC_FLOW_INPUT_DIR=c:\graduationProject\project\model\uploads\traffic_flows\inbox
TRAFFIC_FLOW_ARCHIVE_DIR=c:\graduationProject\project\model\uploads\traffic_flows\archive
TRAFFIC_PCAP_DIR=c:\graduationProject\project\model\uploads\traffic_flows\pcap
TRAFFIC_PCAP_ARCHIVE_DIR=c:\graduationProject\project\model\uploads\traffic_flows\pcap_archive
TRAFFIC_MONITOR_INTERVAL=10
AUTO_START_TRAFFIC_MONITOR=false
TRAFFIC_CAPTURE_INTERFACE=1
TRAFFIC_CAPTURE_DURATION=15
TRAFFIC_CAPTURE_FILTER=tcp port 5000
```

说明：

- `TRAFFIC_MONITOR_INTERVAL=10` 表示每轮监测结束后，等待 10 秒再开始下一轮
- `TRAFFIC_CAPTURE_DURATION=15` 表示每轮抓包持续 15 秒
- 所以当前默认节奏是 “抓 15 秒，等 10 秒，再抓下一轮”
- `TRAFFIC_CAPTURE_INTERFACE` 可以填网卡序号或接口名
- `TRAFFIC_CAPTURE_FILTER` 是可选的 BPF 过滤条件

### 4. Initialize database

在 MySQL 中执行：

```sql
source c:/graduationProject/project/model/sql/init.sql;
```

### 5. Start the app

```powershell
python app.py
```

访问：

```text
http://127.0.0.1:5000
```

## Demo Accounts

- `admin / admin123`
- `user / user123`

如果数据库里还没有初始账号，可以先调用 `POST /api/auth/init-demo`，或者在页面里执行演示初始化。

## Core Features

### CSV detection

- 上传符合 CIC-IDS 风格的 CSV
- 选择启用模型进行检测
- 生成检测记录、攻击结果和告警

### Model management

- 注册本地 `.pth` 模型
- 设置当前启用模型
- 查看精度、召回率、F1、FPR、FNR 等指标

### Traffic monitoring

当前自动流量监测链路是：

```text
Scapy -> PCAP -> Python cicflowmeter -> 规范化 CSV -> run_detection()
```

说明：

- `Scapy` 负责抓包
- `Python cicflowmeter` 负责把 `pcap` 转成流量特征 CSV
- 系统会把 Python 提取结果规范化为项目当前模型可接受的 CIC-IDS 风格列头
- 之后再调用当前启用模型完成检测

要让这部分正常工作，你需要：

1. 安装好 `scapy` 和 `cicflowmeter`
2. 系统具备可用抓包驱动，Windows 下一般是 `Npcap`
3. 正确设置 `TRAFFIC_CAPTURE_INTERFACE`
4. 确认当前环境就是项目的 `.venv`

## Traffic Extractor Notes

当前实现不再调用 Java CLI，而是直接走 Python 库内部能力：

- 使用 `scapy.utils.PcapReader` 读取抓到的 `pcap`
- 使用 `cicflowmeter.flow_session.FlowSession` 生成原始流特征
- 再由项目代码把列头规范化为模型期望格式

这样做的原因：

- 避开旧版 Java `CICFlowMeter` 在自动化场景下的 GUI / native 依赖问题
- 避开 Python 包自带 CLI 在当前版本下的 `bool.split()` 异常
- 单个 `pcap` 的问题更容易通过本地测试接口精确定位

## Important Files

- `app.py`
- `app/config.py`
- `app/routes/api.py`
- `app/services/data_service.py`
- `app/services/model_service.py`
- `app/services/traffic_monitor.py`
- `TRAFFIC_CAPTURE_README.md`

## Troubleshooting

### 1. Database connection failed

检查：

- `DATABASE_URI` 是否正确
- MySQL 服务是否已启动
- `ids_system` 数据库是否已创建

### 2. Model load failed

检查：

- `MODEL_PATH` 是否存在
- `.pth` 文件是否和当前模型结构兼容
- `torch` 是否已正确安装

### 3. Traffic monitor not ready

检查：

- 当前虚拟环境是否为项目 `.venv`
- `scapy` 是否已安装
- `cicflowmeter` 是否已安装
- 抓包驱动是否可用
- `TRAFFIC_CAPTURE_INTERFACE` 是否对应有效网卡

### 4. PCAP captured but CSV not generated

检查：

- `pcap` 文件里是否真的有包
- 抓到的流量是否足以组成可计算的 flow
- 当前环境里的 `cicflowmeter` 是否可导入
- 可使用 `POST /api/traffic-monitor/test-extract` 单独测试某个 `pcap`

## Notes

- 模型文件默认优先使用 `1D_CNN_BiLSTM_Attn_best.pth`
- 若不存在，则回退到 `best_hybrid_ids_model.pth`
- 流量监测依赖当前激活的管理员账号和启用模型
- `sample_data/demo_traffic.csv` 可用于基础流程验证
