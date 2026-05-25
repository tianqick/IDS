# 第4章修订稿（4.4-4.5）

## 4.4 系统功能模块设计

### 4.4.1 数据管理模块设计

数据管理模块主要负责检测数据文件的上传、存储、登记与基础校验，是系统执行入侵检测任务的入口模块。用户在前端页面中选择待检测的 CSV 文件后，系统首先对文件后缀和格式进行检查，仅允许符合要求的数据文件进入后续处理流程。为避免同名文件覆盖，系统在保存文件时会自动为原始文件名添加时间戳，并结合安全文件名生成机制将文件写入上传目录。

在文件落盘后，系统会进一步统计样本数量，并将原始文件名、保存路径、样本数和上传时间写入 `dataset_info` 表中，以便后续追踪数据来源。该模块不仅为入侵检测提供标准化输入，也为历史数据管理和实验记录归档提供基础支撑。数据管理模块流程如图4.2所示。

图4.2：`fig4-2-data-module-flow.png`

### 4.4.2 模型管理模块设计

模型管理模块主要面向管理员开放，用于维护系统中接入的深度学习模型信息。管理员可以新增模型记录，填写模型名称、模型路径、模型类型、评价指标、数据格式说明以及所需字段列表等内容。系统在保存模型前，会对模型路径、字段说明和必要元数据进行校验，以保证模型记录的完整性和可用性。

模型信息保存成功后，系统会将相关内容写入 `model_info` 表中。若管理员勾选“设为当前启用模型”，系统会自动取消其他模型的激活状态，并将该模型设置为当前唯一启用模型。这样可以保证检测任务始终使用明确的目标模型，避免推理过程中模型来源不一致的问题。模型管理模块流程如图4.3所示。

图4.3：`fig4-3-model-module-flow.png`

### 4.4.3 入侵检测模块设计

入侵检测模块是系统的核心功能模块，主要负责完成从检测任务创建、数据预处理、模型推理到结果写回数据库的完整过程。用户在前端选择检测模型并上传待检测文件后，系统会创建一条后台检测任务记录，并将任务状态写入 `detection_task` 表。随后，后端线程按块读取 CSV 数据，对每个数据块执行列名清洗、缺失值处理、无穷值替换、特征补齐和标准化等预处理操作，再调用当前启用的 PyTorch 模型完成批量推理。

在推理结果生成后，系统根据预测标签判断是否为攻击流量。若识别为攻击流量，则保存攻击结果并生成对应告警日志；若识别为正常流量，则仅进行样本数累计。全部检测完成后，系统统一更新 `detect_record` 表中的样本总数、正常流量数量、异常流量数量及模型相关信息，并同步写入操作日志。该模块采用后台异步执行方式，有效避免了大文件检测时前端长时间阻塞的问题。入侵检测模块流程如图4.4所示。

图4.4：`fig4-4-detection-module-flow.png`

### 4.4.4 结果展示模块设计

结果展示模块主要负责将检测结果以列表、详情和统计图表等形式呈现给用户。当前端发起结果查询请求时，后端会联合查询 `detect_record`、`attack_result` 和 `alarm_log` 等表中的相关信息，并返回检测记录总览、攻击样本详情以及告警状态等数据。前端再基于这些数据渲染结果中心、检测详情页和统计图表区域，使用户能够直观了解每次检测任务的执行情况。

对于普通用户，该模块主要提供检测记录查看、结果详情查看和历史记录检索等功能；对于管理员，在此基础上还可执行检测记录删除和告警状态更新等操作，从而实现结果可视化与管理能力相结合。结果展示模块流程如图4.5所示。

图4.5：`fig4-5-result-module-flow.png`

### 4.4.5 流量监测模块设计

流量监测模块用于实现在线流量采集、流量特征提取和自动检测，是系统从离线数据检测扩展到在线巡检的重要组成部分。管理员首先在页面中配置抓包网卡、抓包时长和轮询间隔等参数，系统据此启动流量监测线程并进入周期性扫描状态。随后，系统通过 Scapy 抓取网络流量并生成 PCAP 文件，再调用 Python cicflowmeter 提取流量特征 CSV。

由于在线提取得到的字段名称与训练时使用的 CIC-IDS2017 风格列名不完全一致，因此系统会在送检前对字段进行规范化映射，将其转换为模型可接受的输入格式。完成列名规范化后，系统调用当前启用模型执行自动检测，并将检测结果、告警信息以及 PCAP/CSV 文件归档到相应目录中。若监测线程继续运行，则系统进入下一轮抓包与检测流程；若管理员停止监测，则流程结束。流量监测模块流程如图4.6所示。

图4.6：`fig4-6-traffic-module-flow.png`

## 4.5 数据库设计

### 4.5.1 概念结构设计

根据系统的业务需求和模块划分，数据库概念结构设计主要围绕系统用户、模型信息、数据集信息、检测任务、检测记录、攻击结果、告警日志和操作日志等核心实体展开。系统用户实体主要描述登录账号及角色权限信息；模型信息实体描述模型路径、性能指标和启用状态；数据集信息实体记录上传文件的来源与样本数；检测任务实体用于表示后台异步检测过程；检测记录实体描述每次任务执行后的统计结果；攻击结果实体保存具体攻击样本信息；告警日志实体保存异常事件告警；操作日志实体保存关键操作行为。

从实体关系来看，一个系统用户可以对应多条检测任务和多条检测记录；一条检测记录可以对应多条攻击结果和多条告警日志；一个模型可以在逻辑上被多条检测任务和检测记录引用；一条检测任务在执行完成后可以生成一条检测记录。数据库概念结构设计图如图4.7所示。

图4.7：`fig4-7-er-concept-design.png`

### 4.5.2 逻辑结构设计

在逻辑结构设计阶段，本文采用关系型数据库对各实体及其关系进行组织，并以主键、外键和逻辑关联字段的形式建立数据约束关系。系统中各主要数据表及关系可概括如下。

| 表名 | 主键 | 关键外键/关联字段 | 主要功能 |
| --- | --- | --- | --- |
| `user` | `id` | 无 | 保存系统用户账号、密码和角色信息 |
| `model_info` | `id` | 无 | 保存模型路径、评价指标、格式说明和启用状态 |
| `dataset_info` | `id` | 无 | 保存上传数据文件的信息 |
| `detection_task` | `id` | `user_id`、`record_id`、`model_id` | 保存后台异步检测任务状态与进度 |
| `detect_record` | `id` | `user_id`、`model_id` | 保存每次检测任务的总体结果 |
| `attack_result` | `id` | `record_id` | 保存攻击样本详细信息 |
| `alarm_log` | `id` | `record_id` | 保存告警内容、级别和处理状态 |
| `operation_log` | `id` | `username`（逻辑关联） | 保存登录、模型切换、删除记录等操作行为 |

从关系映射上看，`user` 与 `detection_task`、`detect_record` 之间均为一对多关系；`detect_record` 与 `attack_result`、`alarm_log` 之间均为一对多关系；`model_info` 与 `detection_task`、`detect_record` 之间属于逻辑上的一对多引用关系；`detection_task` 与 `detect_record` 之间通过 `record_id` 建立任务执行结果映射关系。上述设计能够较好地支撑系统中任务调度、结果归档、模型切换和日志追踪等业务需求。

### 4.5.3 数据字典设计

为保证数据库表结构定义清晰、字段语义明确，本文对系统主要数据表进行数据字典设计。各表的字段说明如下。

#### （1）系统用户表 `user`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 用户编号 |
| `username` | VARCHAR(50) | UNIQUE | 否 | 登录用户名 |
| `password` | VARCHAR(255) | - | 否 | 登录密码（加密存储） |
| `role` | VARCHAR(20) | - | 否 | 用户角色，取值为 `admin` 或 `user` |
| `create_time` | DATETIME | - | 是 | 用户创建时间 |

#### （2）模型信息表 `model_info`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 模型编号 |
| `model_name` | VARCHAR(100) | - | 否 | 模型名称 |
| `model_path` | VARCHAR(255) | - | 否 | 模型文件路径 |
| `model_type` | VARCHAR(50) | - | 是 | 模型类别 |
| `accuracy` | FLOAT | - | 是 | 准确率 |
| `metric_precision` | FLOAT | - | 是 | 精确率 |
| `metric_recall` | FLOAT | - | 是 | 召回率 |
| `metric_f1_score` | FLOAT | - | 是 | F1 值 |
| `metric_fpr` | FLOAT | - | 是 | 误报率 |
| `metric_fnr` | FLOAT | - | 是 | 漏报率 |
| `metric_inference_latency_ms` | FLOAT | - | 是 | 单批次推理时延 |
| `description` | TEXT | - | 是 | 模型描述 |
| `dataset_format` | TEXT | - | 是 | 数据格式说明 |
| `required_columns` | TEXT | - | 是 | 所需字段列表 |
| `is_active` | BOOLEAN | - | 否 | 是否为当前启用模型 |
| `create_time` | DATETIME | - | 是 | 记录创建时间 |

#### （3）数据集信息表 `dataset_info`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 数据集编号 |
| `dataset_name` | VARCHAR(100) | - | 否 | 原始文件名 |
| `file_path` | VARCHAR(255) | - | 否 | 文件存储路径 |
| `sample_count` | INT | - | 是 | 样本数量 |
| `upload_time` | DATETIME | - | 是 | 上传时间 |

#### （4）检测任务表 `detection_task`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 任务编号 |
| `user_id` | INT | FK | 否 | 发起任务的用户编号 |
| `record_id` | INT | FK | 是 | 任务完成后关联的检测记录编号 |
| `model_id` | INT | 逻辑关联 | 是 | 所使用模型编号 |
| `source_file` | VARCHAR(255) | - | 否 | 源文件名 |
| `file_path` | VARCHAR(255) | - | 否 | 文件路径 |
| `total_rows` | INT | - | 是 | 总样本行数 |
| `processed_rows` | INT | - | 是 | 已处理样本行数 |
| `status` | VARCHAR(20) | - | 否 | 任务状态 |
| `message` | VARCHAR(255) | - | 是 | 任务提示信息 |
| `create_time` | DATETIME | - | 是 | 创建时间 |
| `update_time` | DATETIME | - | 是 | 更新时间 |

#### （5）检测记录表 `detect_record`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 检测记录编号 |
| `user_id` | INT | FK | 否 | 所属用户编号 |
| `source_file` | VARCHAR(255) | - | 是 | 检测源文件名 |
| `model_id` | INT | 逻辑关联 | 是 | 所使用模型编号 |
| `model_name` | VARCHAR(100) | - | 是 | 模型名称 |
| `model_path` | VARCHAR(255) | - | 是 | 模型路径 |
| `sample_count` | INT | - | 是 | 样本总数 |
| `normal_count` | INT | - | 是 | 正常流量数量 |
| `attack_count` | INT | - | 是 | 攻击流量数量 |
| `detect_time` | DATETIME | - | 是 | 检测完成时间 |

#### （6）攻击结果表 `attack_result`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 攻击结果编号 |
| `record_id` | INT | FK | 否 | 所属检测记录编号 |
| `attack_type` | VARCHAR(50) | - | 否 | 攻击类型 |
| `risk_level` | VARCHAR(20) | - | 是 | 风险等级 |
| `confidence` | FLOAT | - | 是 | 预测置信度 |
| `src_ip` | VARCHAR(50) | - | 是 | 源 IP 地址 |
| `dst_ip` | VARCHAR(50) | - | 是 | 目的 IP 地址 |
| `create_time` | DATETIME | - | 是 | 创建时间 |

#### （7）告警日志表 `alarm_log`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 告警编号 |
| `record_id` | INT | FK | 否 | 所属检测记录编号 |
| `alarm_content` | VARCHAR(255) | - | 否 | 告警内容 |
| `alarm_level` | VARCHAR(20) | - | 是 | 告警级别 |
| `status` | VARCHAR(20) | - | 是 | 告警处理状态 |
| `create_time` | DATETIME | - | 是 | 创建时间 |

#### （8）操作日志表 `operation_log`

| 字段名 | 类型 | 键 | 允许空 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | INT | PK | 否 | 日志编号 |
| `username` | VARCHAR(50) | 逻辑关联 | 否 | 操作用户名称 |
| `action` | VARCHAR(100) | - | 否 | 操作类型 |
| `detail` | VARCHAR(255) | - | 是 | 操作详情 |
| `create_time` | DATETIME | - | 是 | 记录时间 |

---

### 图文件路径

- 图4.2：[fig4-2-data-module-flow.png](/C:/graduationProject/project/model/thesis_figures/fig4-2-data-module-flow.png)
- 图4.3：[fig4-3-model-module-flow.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-model-module-flow.png)
- 图4.4：[fig4-4-detection-module-flow.png](/C:/graduationProject/project/model/thesis_figures/fig4-4-detection-module-flow.png)
- 图4.5：[fig4-5-result-module-flow.png](/C:/graduationProject/project/model/thesis_figures/fig4-5-result-module-flow.png)
- 图4.6：[fig4-6-traffic-module-flow.png](/C:/graduationProject/project/model/thesis_figures/fig4-6-traffic-module-flow.png)
- 图4.7：[fig4-7-er-concept-design.png](/C:/graduationProject/project/model/thesis_figures/fig4-7-er-concept-design.png)
