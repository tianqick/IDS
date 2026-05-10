# DeepIDS Graduation Project

基于 `Flask + Vue 3 + MySQL + PyTorch` 的入侵检测系统，支持：

- CSV 流量特征文件检测
- 模型管理与切换
- 告警记录与检测历史查看
- 基于 `Scapy + CICFlowMeter` 的自动流量监测

## Project Structure

```text
model/
├─ app/
│  ├─ routes/        # Flask API / 页面路由
│  ├─ services/      # 检测、模型、流量监测核心逻辑
│  ├─ static/        # 前端静态资源
│  └─ templates/     # SPA 模板
├─ artifacts/        # 预处理元数据、评估缓存、监测设置
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

- Python 3.10+
- MySQL 8.x
- Java 11+
- Windows 抓包驱动（通常是 `Npcap`）
- `CICFlowMeter.jar`
- 与当前 `CICFlowMeter` 兼容的 `jnetpcap.dll`

## Python Dependencies

项目当前代码对应的依赖见 [requirements.txt](c:\graduationProject\project\model\requirements.txt:1)：

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

## Quick Start

### 1. Create venv

```powershell
cd c:\graduationProject\project\model
python -m venv .venv
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
MODEL_PATH=c:\graduationProject\project\model\1D_CNN_BiLSTM_Attn_best.pth
DATASET_DIR=c:\graduationProject\project\model\dataset
ARTIFACT_DIR=c:\graduationProject\project\model\artifacts

TRAFFIC_FLOW_INPUT_DIR=c:\graduationProject\project\model\uploads\traffic_flows\inbox
TRAFFIC_FLOW_ARCHIVE_DIR=c:\graduationProject\project\model\uploads\traffic_flows\archive
TRAFFIC_PCAP_DIR=c:\graduationProject\project\model\uploads\traffic_flows\pcap
TRAFFIC_PCAP_ARCHIVE_DIR=c:\graduationProject\project\model\uploads\traffic_flows\pcap_archive
TRAFFIC_MONITOR_INTERVAL=10
AUTO_START_TRAFFIC_MONITOR=false
TRAFFIC_CAPTURE_INTERFACE=1
TRAFFIC_CAPTURE_DURATION=15
TRAFFIC_CAPTURE_FILTER=tcp port 5000
CICFLOWMETER_COMMAND=java -Djava.library.path=C:\tools\CICFlowMeter\native -cp C:\tools\CICFlowMeter\CICFlowMeter.jar cic.cs.unb.ca.ifm.Cmd "{pcap}" "{output_dir}"

MODEL_INPUT_SIZE=32
PREDICT_CHUNK_SIZE=5000
INFERENCE_BATCH_SIZE=1024
DB_BATCH_SIZE=2000
```

说明：

- `CICFLOWMETER_COMMAND` 不再使用 `java -jar ...`
- 当前这只 `CICFlowMeter.jar` 的默认入口会启动 GUI
- 后端自动化应改用命令行入口 `cic.cs.unb.ca.ifm.Cmd`
- `-Djava.library.path=...` 指向放置 `jnetpcap.dll` 的目录

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

如果数据库里还没有初始化账号，可以先调用 `POST /api/auth/init-demo`，或者在页面里执行演示初始化。

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

当前代码里的自动流量监测链路是：

```text
Scapy -> PCAP/PCAPNG -> CICFlowMeter CLI -> CSV -> run_detection()
```

说明：

- `Scapy` 负责抓包
- `CICFlowMeter` 负责把抓包文件转成流量特征 CSV
- 系统再调用当前启用模型做检测

要让这部分正常工作，你需要：

1. 安装好 `scapy`
2. 系统具备可用抓包驱动（Windows 下一般是 `Npcap`）
3. 正确设置 `TRAFFIC_CAPTURE_INTERFACE`
4. 正确设置 `CICFLOWMETER_COMMAND`
5. 本机能正常运行 `java -cp ... cic.cs.unb.ca.ifm.Cmd`
6. `jnetpcap.dll` 已放到 `java.library.path` 指向的目录中

## CICFlowMeter Notes

当前本地验证结果：

- `java -jar CICFlowMeter.jar` 会启动 GUI，不适合后端自动调用
- `java -cp CICFlowMeter.jar cic.cs.unb.ca.ifm.Cmd "{pcap}" "{output_dir}"` 才是正确的 CLI 入口
- 如果缺少 `jnetpcap.dll`，会报 `UnsatisfiedLinkError`

建议目录结构：

```text
C:\tools\CICFlowMeter\
├─ CICFlowMeter.jar
└─ native\
   └─ jnetpcap.dll
```

## Important Files

- [app.py](c:\graduationProject\project\model\app.py:1)
- [app/config.py](c:\graduationProject\project\model\app\config.py:1)
- [app/routes/api.py](c:\graduationProject\project\model\app\routes\api.py:1)
- [app/services/data_service.py](c:\graduationProject\project\model\app\services\data_service.py:1)
- [app/services/model_service.py](c:\graduationProject\project\model\app\services\model_service.py:1)
- [app/services/traffic_monitor.py](c:\graduationProject\project\model\app\services\traffic_monitor.py:1)

## Notes

- 模型文件默认优先使用 `1D_CNN_BiLSTM_Attn_best.pth`
- 若不存在，则回退到 `best_hybrid_ids_model.pth`
- 流量监测依赖当前激活的管理员账号和启用模型
- `sample_data/demo_traffic.csv` 可用于基础流程验证

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

- `scapy` 是否已安装
- 抓包驱动是否可用
- `TRAFFIC_CAPTURE_INTERFACE` 是否对应有效网卡
- `CICFLOWMETER_COMMAND` 是否配置为 `Cmd` 命令行入口

### 4. CICFlowMeter CLI failed

检查：

- `java` 是否在系统路径中
- `CICFlowMeter.jar` 路径是否正确
- 是否使用了 `cic.cs.unb.ca.ifm.Cmd`
- `jnetpcap.dll` 是否存在
- `-Djava.library.path` 是否指向 `jnetpcap.dll` 所在目录
