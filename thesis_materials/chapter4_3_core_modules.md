# 4.3 核心功能模块详细设计

结合系统前端页面结构和后台接口实现，本文将系统功能划分为登录认证与权限控制、系统首页与统计展示、数据上传与检测任务、检测结果与历史记录、告警管理、模型管理与性能评估、实时流量监测和用户管理等八个功能模块。各模块在功能上既相互独立，又通过统一的检测流水线和数据库架构实现协作，共同构成系统完整的业务功能体系。系统整体功能模块划分如图4.2所示。

图4.2：`fig4-14-function-module-diagram.png`

## 4.3.1 登录认证与权限控制模块

登录认证与权限控制模块是系统的入口模块，负责完成用户身份认证、角色识别与会话权限控制。该模块采用基于 Flask Session 的服务端会话机制，通过 `login_required` 和 `admin_required` 两个装饰器函数实现对 API 接口的分级保护。

用户访问系统时，前端首先调用 `GET /api/auth/me` 接口检查当前会话状态。若会话有效，则直接进入系统主页并根据角色信息加载对应的菜单和功能页面；若会话无效或已过期，则跳转至登录页面。用户在登录页面输入用户名和密码后，前端通过 `POST /api/auth/login` 接口提交认证信息。后端接收到登录请求后，首先从 `user` 表中查询匹配的用户记录，再通过 Werkzeug 提供的 `pbkdf2:sha256` 算法对输入密码与数据库中存储的密码哈希值进行比对校验。若校验失败，则返回 401 错误提示"用户名或密码错误"；若校验成功，则将 `user_id`、`username` 和 `role` 写入 Flask Session，同时向 `operation_log` 表中插入一条登录操作日志记录。

在权限控制方面，系统区分管理员（admin）和普通用户（user）两类角色。普通用户仅能执行上传检测、结果查看和历史记录查询等基础功能；管理员在此基础上还拥有告警管理、模型管理、流量监测和用户管理等更高权限的访问能力。每次 API 请求到达后端时，`login_required` 装饰器首先校验 Session 中是否存在 `user_id`，若不存在则返回 401 状态码并要求前端跳转至登录页；`admin_required` 装饰器在 `login_required` 基础之上进一步检查 `role` 字段是否为 `admin`，若角色不符则返回 403 状态码。对于检测结果、告警数据等与用户相关的数据查询，系统通过 `current_user_filters` 函数实现角色维度的数据隔离：管理员可以查看全平台所有数据，普通用户仅能查看与自身 `user_id` 相关联的数据记录。模块流程如图4.3所示。

图4.3：`fig4-3-login-auth.png`

## 4.3.2 系统首页与统计展示模块

系统首页与统计展示模块是用户登录后的首个功能界面，用于集中展示入侵检测平台的整体运行概况。该模块通过 `GET /api/dashboard` 接口获取聚合统计数据，前端再将返回的结构化数据渲染为统计卡片、ECharts 折线图和攻击类型分布图等多种可视化形式。

后端在 `build_dashboard_stats` 函数中完成统计数据的集中采集与聚合计算。该函数首先根据当前用户角色决定数据查询范围：若为管理员角色，则对所有 `detect_record`、`attack_result` 和 `alarm_log` 表执行全局聚合查询；若为普通用户角色，则在上述查询中通过 `WHERE user_id = current_user_id` 条件进行过滤，确保普通用户仅能看到自身相关的统计数据。随后，函数依次从数据库中获取以下统计指标：系统用户总数（仅管理员可见）、数据集数量、检测记录总数、告警总数、全部样本/攻击/正常样本累计值、攻击类型分布（通过 `GROUP BY attack_type` 聚合）、近期每日攻击趋势（按日期维度汇总），以及最近五条检测记录和最近五条告警信息。

前端接收到数据后，在页面顶部以卡片形式展示记录总数、告警总数、累计检测样本数和累计检出攻击数等关键指标；在页面中部通过 ECharts 饼图展示攻击类型分布情况，通过折线图展示近期攻击趋势变化；在页面底部以列表形式展示最近的检测记录和告警信息。管理员与普通用户在首页看到的数据范围不同，该设计在保证管理员能够把握平台全局运行状况的同时，也满足了普通用户查看个人工作统计的需求。模块流程如图4.4所示。

图4.4：`fig4-3-dashboard.png`

## 4.3.3 数据上传与检测任务模块

数据上传与检测任务模块是系统最核心的业务模块，负责完成从 CSV 文件上传、后台异步检测到结果写回数据库的完整处理链路。该模块采用后台线程异步执行的方式，有效解决了大文件检测时前端界面长时间阻塞的问题。

用户进入上传检测页面后，首先需要从当前已启用的模型中选择目标检测模型。系统通过 `get_model_for_detection` 函数解析检测所使用的模型：若用户指定了具体模型 ID，则优先使用指定模型；否则使用当前激活模型；若系统中无激活模型，则回退至配置文件 `MODEL_PATH` 所指向的默认模型文件。用户选择 CSV 文件后，前端对文件后缀进行初步检查，仅允许 `.csv` 格式的数据文件进入上传流程。

前端通过 `POST /api/detect/upload` 接口以 `multipart/form-data` 格式提交文件和模型 ID。后端接收到请求后，首先通过 `allowed_file` 函数再次校验文件后缀，确保安全性。校验通过后，`save_dataset` 函数对原始文件名添加时间戳前缀以避免同名覆盖，调用 `secure_filename` 进行安全文件名生成，将文件保存至 `uploads/` 目录，并通过 `count_csv_rows` 统计样本行数。随后，系统将文件元信息登记到 `dataset_info` 表，并创建一条 `detection_task` 记录，初始化任务状态为 `queued`，记录总行数 `total_rows` 及已处理行数 `processed_rows=0`。

任务记录创建完成后，后端立即启动一个后台守护线程执行 `_run_detection_task` 函数，同时向前端返回任务 ID 和当前状态。前端在收到响应后，通过定时轮询 `GET /api/tasks/<task_id>` 接口跟踪任务进度，在页面上以进度条形式实时展示已处理行数百分比。

后台线程的执行过程如下：首先将任务状态更新为 `running`；然后调用 `run_detection` 函数进入核心检测流程。`run_detection` 函数首先创建一条 `detect_record` 记录作为本次检测的统计容器，再通过 `ModelService.predict_file_in_chunks` 方法对 CSV 文件进行分块检测。每个数据块经过列名清洗、非特征列剔除、缺失值列均值填充、Z-Score 标准化等预处理步骤后，送入 PyTorch 模型进行批量推理。推理结果中的每条样本根据预测标签被分类为 BENIGN（正常）或具体攻击类型，对于非 BENIGN 样本同步生成对应的告警日志。为提高数据库写入效率，检测结果和告警信息分别缓冲在内存列表中，当缓冲区大小达到 `DB_BATCH_SIZE`（默认 2000 条）阈值时通过 `bulk_insert_mappings` 批量写入 `attack_result` 和 `alarm_log` 表。每处理完一个数据块，后台线程通过回调函数更新任务记录的 `processed_rows` 字段，供前端轮询获取进度。

全部样本处理完成后，系统更新 `detect_record` 表中的样本总数、正常流量数量和攻击流量数量等统计信息，将任务状态更新为 `completed` 并关联检测记录 ID，同时向 `operation_log` 表写入任务完成日志。前端轮询检测到任务状态变为 `completed` 后，自动跳转至检测结果详情页面。模块流程如图4.5所示。

图4.5：`fig4-3-upload-detection.png`

## 4.3.4 检测结果与历史记录模块

检测结果与历史记录模块用于实现检测记录的列表展示、详情查看、关键词搜索和管理操作，是用户获取和分析入侵检测结果的主要界面。该模块将结果展示与历史查询合并在同一视图下，用户无需在多个页面之间切换即可完成从记录浏览到详情分析的完整流程。

前端通过 `GET /api/records` 接口获取检测记录列表。后端查询 `detect_record` 表并按 `detect_time` 降序排列，同时通过 ORM 关系映射关联查询 `user` 表获取操作者用户名。对于每条记录，后端还会统计其关联的 `alarm_log` 记录数量，以标识该检测是否"存在告警"或"正常完成"。查询结果经 `serialize_record` 函数序列化为 JSON 格式后返回前端。前端将数据渲染为记录列表表格，展示源文件名、样本总数、攻击数量、检测时间、操作者和检测状态等字段。用户可在页面上方的搜索框中输入文件名、记录编号或时间等关键词，前端通过计算属性 `filteredRecords` 对已加载的列表数据进行实时客户端过滤，无需额外发起后端请求。

当用户点击某条记录时，前端通过 `GET /api/records/<record_id>` 接口获取该记录的详细信息。后端不仅返回 `detect_record` 的基本统计字段，还关联查询该记录下的全部 `attack_result` 记录，返回每条攻击样本的攻击类型、风险等级、置信度、源 IP 地址和目的 IP 地址等字段。前端在详情页中以摘要卡片和攻击结果明细表格的组合形式展示这些数据，便于用户快速了解一次检测任务中的攻击流量组成和分布情况。

对于管理员角色，该模块还提供了检测记录删除功能。管理员可通过 `DELETE /api/records/<record_id>` 接口删除某条检测记录，后端在同一个事务中先级联删除该记录关联的所有 `attack_result` 和 `alarm_log` 数据，再将相关 `detection_task` 中的 `record_id` 引用置空，最后删除记录本身并写入操作日志。模块流程如图4.6所示。

图4.6：`fig4-3-results-history.png`

## 4.3.5 告警管理模块

告警管理模块用于集中管理入侵检测过程中自动生成的异常流量告警信息，将检测结果进一步转化为可用于安全运维的事件处置工单。该模块仅对管理员开放。

在检测任务执行过程中，当模型判定某条流量样本为攻击类型时，系统会同步生成一条告警记录写入 `alarm_log` 表，内容包括告警描述（如"Detected DDoS attack from 192.168.1.100"）、告警级别（与攻击样本的风险等级一致）和初始处理状态（`unprocessed`）。告警信息与检测记录之间通过 `record_id` 外键关联，确保每条告警均可追溯到具体的检测任务和原始流量数据。

管理员进入告警中心后，前端通过 `GET /api/alarms` 接口获取告警列表。后端对 `alarm_log` 表与 `detect_record` 表进行 JOIN 查询，筛选出源文件名为 `traffic_` 前缀的在线流量监测告警记录，并按创建时间降序排列。接口支持分页查询和状态筛选参数：管理员可通过 `status` 参数按 `unprocessed`（未处理）、`processed`（已处理）或 `ignored`（已忽略）三种状态过滤告警记录，通过 `page` 和 `page_size` 参数控制分页。前端将返回的告警列表渲染为带分页控件的表格，并支持在告警列表中直接点击跳转到对应的检测详情页面。

管理员可根据实际处置情况，通过 `PATCH /api/alarms/<alarm_id>` 接口更新告警状态。后端在接收更新请求时，首先校验新状态值是否在允许的枚举范围内，然后执行状态更新并将操作记录写入 `operation_log` 表。通过该模块，管理员能够将检测系统与安全运维流程对接，实现对告警事件的闭环处理。模块流程如图4.7所示。

图4.7：`fig4-3-alarm-management.png`

## 4.3.6 模型管理与性能评估模块

模型管理与性能评估模块用于维护系统所接入的深度学习模型信息，包括模型注册、激活切换、删除管理和性能指标查看等功能。该模块仅对管理员开放，是保障系统模型可扩展性和可维护性的关键入口。

管理员进入模型管理页面后，前端通过 `GET /api/models` 接口获取所有已注册模型的信息列表，同时返回当前激活模型的 ID。后端查询 `model_info` 表，按 `is_active` 降序（激活模型排在首位）和 `create_time` 降序排列，并将每条记录序列化为包含模型名称、路径、类型、各项评价指标（准确率、精确率、召回率、F1 分数、误报率、漏报率、推理时延）、数据格式说明、所需字段列表和启用状态的 JSON 对象。前端将这些信息渲染为模型列表表格，并标识出当前激活模型。

新增模型时，管理员可通过 `POST /api/models` 接口以表单或 JSON 格式提交模型元数据，主要包括模型名称、模型文件路径、模型类型、六项性能指标、模型描述、数据格式说明和所需特征字段列表等字段。管理员还可以选择上传 `.pth` 模型权重文件，系统在接收后将文件保存至 `uploads/models/` 目录。在保存模型记录之前，后端首先校验模型文件路径是否指向实际存在的文件，防止无效模型被注册到系统中；其次检查是否存在相同路径的模型记录，避免重复注册；最后检查是否需要将该模型设置为激活状态——若管理员勾选"设为当前启用模型"或系统当前无任何激活模型，则调用 `set_active_model` 函数执行原子性激活操作：先取消所有其他模型的激活状态，再将新模型设置为唯一激活模型。这种"唯一激活模型"的单例设计保证了系统中所有检测任务和流量监测始终使用明确的、统一的模型版本，避免模型版本混用导致的检测结果不一致问题。

激活切换方面，管理员可通过 `POST /api/models/<model_id>/activate` 接口将任意已注册模型设置为当前激活模型。该接口同样会执行上述原子性激活逻辑。删除模型时，系统首先检查该模型是否已被检测任务或检测记录引用，若存在引用关系则阻止删除以防止数据孤岛；若无引用关系，则允许删除。删除后若被删模型原本为激活状态，系统会自动将最近创建的模型设置为新的激活模型，确保系统中始终存在一个可用模型。

性能评估功能集成在模型管理视图内。管理员查看某个模型的性能指标时，系统展示该模型的 Accuracy、Precision、Recall、F1 分数、误报率（FPR）、漏报率（FNR）和推理时延等指标。此外，系统还支持通过 `ModelService` 在测试集上重新执行模型评估，评估结果缓存至 `artifacts/evaluation_metrics.json` 文件，后续查看时可直接从缓存读取，避免重复计算。模块流程如图4.8所示。

图4.8：`fig4-3-model-management.png`

## 4.3.7 实时流量监测模块

实时流量监测模块是系统区别于普通离线检测平台的核心扩展功能，用于实现在线网络流量采集、流量特征提取、列名规范化映射和自动入侵检测的完整闭环。该模块基于 Scapy 和 Python cicflowmeter 实现了不依赖外部 Java 运行时的纯 Python 流量处理链路，仅对管理员开放。

流量监测功能由 `TrafficMonitorService` 单例服务类统一管理。该服务维护一个后台守护线程 `_run_loop`，按照可配置的轮询间隔周期性地执行抓包、提取和送检流程。管理员首先需要通过 `PATCH /api/traffic-monitor/config` 接口配置抓包网卡，系统将配置持久化到 `artifacts/traffic_monitor_settings.json` 文件中以确保服务重启后配置不丢失。管理员可以通过 `GET /api/traffic-monitor/interfaces` 接口获取当前环境可用的网卡列表，该接口通过 Scapy 的 `conf.ifaces` 自动发现网络接口并过滤有效接口名称。

管理员通过 `POST /api/traffic-monitor/start` 接口启动监测线程后，系统进入周期性扫描状态。每个扫描周期包含以下四个阶段：

(1) **抓包阶段**：系统通过 Scapy 的 `sniff` 函数在指定网卡上捕获指定时长（默认 60 秒）的网络流量，支持通过 BPF 过滤器（如 `tcp`）对抓包范围进行限定。捕获到的原始数据包以 PCAP 格式写入 `uploads/traffic_flows/pcap/` 目录，文件名包含时间戳标识。

(2) **特征提取阶段**：系统调用 Python cicflowmeter 的 `FlowSession` 类读取 PCAP 文件，逐包处理并聚合成 CIC 流量特征。与早期版本依赖 Java 版 CICFlowMeter 的 JAR 包方式相比，Python cicflowmeter 的集成方式消除了对 Java 运行时的依赖，简化了环境部署复杂度。提取后的原始特征 CSV 以 cicflowmeter 原生字段名输出。

(3) **列名规范化阶段**：由于 cicflowmeter 输出的字段名称（如 `src_ip`、`tot_fwd_pkts`、`fwd_pkt_len_mean`）与模型训练时使用的 CIC-IDS2017 标准列名（如 `Source IP`、`Total Fwd Packets`、`Fwd Packet Length Mean`）不一致，系统在送检前执行 `_normalize_python_cicflowmeter_csv` 过程。该过程通过一个包含 78 个映射关系的字段字典 `PYTHON_CICFLOWMETER_FIELD_MAP`，将 cicflowmeter 的原始字段名逐列转换为 CIC-IDS2017 标准列名。同时，系统为每条流计算 `Flow ID` 标识，并补齐模型所需的全部 80 个特征列，确保在线提取的数据与训练数据在特征空间上严格对齐。

(4) **自动检测与归档阶段**：规范化后的 CSV 文件被放入 `inbox` 目录，系统调用 `run_detection` 函数使用当前激活模型对该文件执行入侵检测。检测完成后，攻击结果和告警信息写入数据库，PCAP 文件和 CSV 文件分别归档至 `pcap_archive` 和 `archive` 目录。系统更新监测状态中的已处理计数（`processed_count`）和最近处理时间等统计信息。若 CSV 文件无有效数据行（空流量），系统直接归档该文件并累计空特征计数（`empty_feature_count`），不执行检测流程。

一轮扫描完成后，若管理员未通过 `POST /api/traffic-monitor/stop` 接口发出停止指令，系统等待轮询间隔（默认 10 秒）后自动进入下一轮扫描。停止指令通过线程安全的事件标志 `_stop_event` 实现，确保监测线程能够安全退出。前端通过定时轮询 `GET /api/traffic-monitor` 接口获取监测实时状态，以状态面板的形式展示运行状态、最近抓包时间、最近提取时间、已处理文件数量、最近错误信息等关键状态指标。模块流程如图4.9所示。

图4.9：`fig4-3-traffic-monitor.png`

## 4.3.8 用户管理模块

用户管理模块用于维护系统中的用户账号信息和角色配置，是平台多用户协作和权限管理的基础支撑模块。该模块仅对管理员开放，提供用户的增删改查等完整管理功能。

管理员进入用户管理页面后，前端通过 `GET /api/users` 接口获取系统中所有用户的列表。后端查询 `user` 表并按创建时间降序排列，返回用户编号、用户名、角色和创建时间等字段。前端将数据渲染为用户管理表格，管理员可在此表格基础上执行各项管理操作。

新增用户时，管理员填写用户名、密码和角色（admin 或 user）信息后，前端通过 `POST /api/users` 接口提交 JSON 数据。后端在保存之前执行三项校验：检查用户名是否为空、检查角色值是否在 `admin` 和 `user` 枚举范围内、检查用户名是否已存在于数据库中。三项校验通过后，系统使用 `pbkdf2:sha256` 算法对明文密码进行哈希处理后存入 `user` 表，并写入操作日志。编辑用户时，管理员可修改用户名、角色或重置密码，前端通过 `PATCH /api/users/<user_id>` 接口提交变更。后端同样执行用户名唯一性校验（排除当前用户的 ID），并在用户更新自己的信息时同步刷新 Session 中的用户名和角色字段。删除用户时，系统首先检查被删除用户是否为当前登录的管理员本人，若是则阻止删除以防止误操作；其次检查该用户是否已在系统中拥有检测记录，若存在则阻止删除以保证数据完整性。两项检查均通过后，系统执行删除操作并记录操作日志。模块流程如图4.10所示。

图4.10：`fig4-3-user-management.png`

---

## 图文件对应关系

- 图4.2：[fig4-14-function-module-diagram.png](/C:/graduationProject/project/model/thesis_figures/fig4-14-function-module-diagram.png)
- 图4.3：[fig4-3-login-auth.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-login-auth.png)
- 图4.4：[fig4-3-dashboard.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-dashboard.png)
- 图4.5：[fig4-3-upload-detection.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-upload-detection.png)
- 图4.6：[fig4-3-results-history.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-results-history.png)
- 图4.7：[fig4-3-alarm-management.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-alarm-management.png)
- 图4.8：[fig4-3-model-management.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-model-management.png)
- 图4.9：[fig4-3-traffic-monitor.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-traffic-monitor.png)
- 图4.10：[fig4-3-user-management.png](/C:/graduationProject/project/model/thesis_figures/fig4-3-user-management.png)
