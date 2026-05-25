# 4.3 核心功能模块详细设计 — 流程图绘制说明

> 本文档描述8个功能模块流程图的节点和连线，可在 draw.io 中参照绘制。
> 约定：`[开始/结束]` 用椭圆，`[处理步骤]` 用圆角矩形，`◇ 判断` 用菱形，`[DB: ...]` 用圆柱形。

---

## 图4.3 登录认证与权限控制模块流程

```
[开始: 用户访问系统]
    │
    ▼
[显示登录页面 / GET /api/auth/me 检查会话]
    │
    ├── 会话有效 ──► [加载系统主页 + 按role加载菜单]
    │
    └── 会话无效
          │
          ▼
    [输入用户名和密码]
          │
          ▼
    [POST /api/auth/login 提交登录]
          │
          ▼
    ◇ 验证用户名和密码？
    ├── 失败 ──► [返回401错误提示] ──► 回到[显示登录页面]
    │
    └── 成功
          │
          ▼
    [写入Session: user_id, username, role]
          │
          ▼
    [DB: operation_log 写入登录日志]
          │
          ▼
    [进入系统主页]
          │
          ▼
    ◇ 角色判断？role?
    ├── admin ──► [加载管理员视图：完整菜单+管理功能]
    │
    └── user  ──► [加载普通用户视图：检测/结果/历史]
          │
          ▼
    [用户执行各类操作]
          │
          ▼
    ◇ 每次API请求：Session有效？
    ├── 有效 ──► [执行请求，返回数据]
    │
    └── 失效 ──► [返回401，跳转登录页] ──► 回到[显示登录页面]
          │
          ▼
    [结束]
```

---

## 图4.4 系统首页与统计展示模块流程

```
[开始: 用户登录后进入首页]
    │
    ▼
[GET /api/dashboard 前端发起统计请求]
    │
    ▼
◇ Session & 角色校验？
├── 未授权 ──► [返回401/403] ──► 回到开始
│
└── 已授权
      │
      ▼
[调用 build_dashboard_stats()]
      │
      ▼
◇ 角色 == admin？
├── 是 ──► [全局查询：无user_id过滤]
│
└── 否 ──► [个人查询：WHERE user_id = current_user]
      │
      ▼
[DB: detect_record → 样本总数/正常数/攻击数]
      │
      ▼
[DB: attack_result → GROUP BY attack_type 攻击类型分布]
      │
      ▼
[DB: alarm_log → 告警数量统计]
      │
      ▼
[DB: detect_record → GROUP BY DATE(detect_time) 每日趋势]
      │
      ▼
[聚合统计 → 组装JSON响应]
      │
      ▼
[前端渲染：统计卡片 + ECharts饼图(攻击分布) + ECharts折线图(趋势) + 最近记录列表 + 最近告警列表]
      │
      ▼
[结束]
```

---

## 图4.5 数据上传与检测任务模块流程

> 建议分两列画：左列为前端同步部分，右列为后台异步线程。

```
═══════════════════════════════════════════════════════════════════════════
  前端 / 同步部分                              后台异步线程
═══════════════════════════════════════════════════════════════════════════

[开始: 进入上传检测页]
    │
    ▼
[选择检测模型(从已激活模型)]
    │
    ▼
[选择CSV文件]
    │
    ▼
◇ .csv后缀?
├──否──► [提示仅支持CSV]──►回到[选择CSV文件]
│
└──是
    │
    ▼
[POST /api/detect/upload
 提交文件 + model_id]
    │
    ▼
[save_dataset():
 ·时间戳重命名
 ·写入uploads/目录]
    │
    ▼
[DB: dataset_info 登记]
    │
    ▼
[count_csv_rows() 统计行数]
    │
    ▼
[DB: detection_task
 status='queued'
 total_rows=样本数
 processed_rows=0]
    │
    ▼
[DB: operation_log 记录]
    │
    ├──────────────────────────► [后台线程启动]
    │                            _run_detection_task()
    │                                │
    ▼                                ▼
[立即返回响应:              [更新 task.status='running']
 {task_id, status:'queued'}]        │
    │                                ▼
    ▼                            [run_detection():
[前端开始定时轮询                  ·创建 detect_record
 GET /api/tasks/<id>                ·ModelService 加载模型]
 更新进度条]                            │
    │                                ▼
    │                            [分块读取CSV
    │                             predict_file_in_chunks()
    │                             每块5000行]
    │                                │
    │                                ▼
    │                            [预处理每块数据:
    │                             ·列名清洗
    │                             ·删非特征列(Flow ID/IP/Port等)
    │                             ·无穷值→空值
    │                             ·缺失值→列均值填充
    │                             ·Z-Score标准化(mean/std)]
    │                                │
    │                                ▼
    │                            [批量模型推理
    │                             UniversalIDSModel.forward()
    │                             CNN → LSTM → Attention → FC
    │                             batch_size=1024]
    │                                │
    │                                ▼
    │                            [Softmax → argmax →
    │                             判定 BENIGN / 具体攻击类型
    │                             计算 risk_level:
    │                               confidence≥0.9 → high
    │                               confidence≥0.75 → medium
    │                               其余 → low]
    │                                │
    │                                ▼
    │                            [非BENIGN样本 → 生成AlarmLog
    │                             结果缓冲到内存列表
    │                             result_buffer[]
    │                             alarm_buffer[]]
    │                                │
    │                                ▼
    │                            ◇ 缓冲区≥DB_BATCH_SIZE(2000)?
    │                            ├──是──► [bulk_insert_mappings
    │                            │         批量写入attack_result
    │                            │         批量写入alarm_log
    │                            │         清空缓冲区]
    │                            │              │
    │                            └──否──► [继续累积]──┘
    │                                │
    │                                ▼
    │                            [进度回调:
    │                             更新task.processed_rows
    │                             前端轮询感知进度变化]
    │                                │
    │                                ▼
    │                            ◇ 全部样本处理完成?
    │                            ├──否──► 回到[分块读取CSV]
    │                            │
    │                            └──是
    │                                  │
    │                                  ▼
    │                            [flush剩余缓冲区]
    │                                  │
    │                                  ▼
    │                            [更新detect_record:
    │                             sample_count/normal_count
    │                             /attack_count]
    │                                  │
    │                                  ▼
    │                            [DB: task.status='completed'
    │                             task.record_id=记录ID
    │                             task.message='检测完成']
    │                                  │
    │                                  ▼
    │                            [DB: operation_log 完成日志]
    │
    ▼
[前端轮询检测到 status='completed']
    │
    ▼
[自动跳转 → 检测结果详情页]
    │
    ▼
[结束]
```

---

## 图4.6 检测结果与历史记录模块流程

```
[开始: 进入检测结果页面]
    │
    ▼
[GET /api/records 请求记录列表]
    │
    ▼
◇ 角色 == admin？
├── user  ──► [WHERE user_id = 当前用户]
│
└── admin ──► [返回全部记录]
    │
    ▼
[DB: detect_record JOIN user
 按detect_time降序查询]
    │
    ▼
[DB: 统计每条记录的 alarm_log 数量]
    │
    ▼
[前端渲染记录列表:
 源文件 | 样本数 | 攻击数 | 检测时间 | 状态 | 操作者]
    │
    ├──► [搜索框: 输入关键词 → 前端filteredRecords实时过滤]
    │
    ▼
[点击某条记录]
    │
    ▼
[GET /api/records/<id> 请求详情]
    │
    ▼
[DB: 查询DetectRecord + 关联AttackResult列表
 attack_type | risk_level | confidence | src_ip | dst_ip]
    │
    ▼
[前端渲染详情页:
 ·摘要卡片(样本总数/正常数/攻击数/模型名)
 ·攻击结果明细表格]
    │
    ▼
◇ 管理员操作？
├── 否 ──► [结束]
│
└── 是
      │
      ▼
    [DELETE /api/records/<id>
     删除检测记录]
      │
      ▼
    [事务内执行:
     ·DELETE attack_result WHERE record_id=x
     ·DELETE alarm_log WHERE record_id=x
     ·UPDATE detection_task SET record_id=NULL
     ·DELETE detect_record WHERE id=x
     ·INSERT operation_log]
      │
      ▼
    [刷新记录列表] ──► 回到[GET /api/records]
```

---

## 图4.7 告警管理模块流程

```
[开始: 管理员进入告警中心]
    │
    ▼
[GET /api/alarms?page=1&page_size=20&status=all]
    │
    ▼
[DB: alarm_log JOIN detect_record
 WHERE source_file LIKE 'traffic_%'
 按create_time降序 分页查询]
    │
    ▼
[前端渲染告警列表 + 分页控件:
 告警内容 | 告警级别 | 状态 | 创建时间]
    │
    ├──► [按状态筛选:
    │     unprocessed | processed | ignored
    │     切换筛选条件 → 重新GET /api/alarms]
    │
    ▼
◇ 管理员操作？
├── 仅浏览 ──► [结束]
│
├── 更新状态
│     │
│     ▼
│   [PATCH /api/alarms/<id>
│    body: {"status": "processed"}]
│     │
│     ▼
│   ◇ 状态值合法？
│   │  (unprocessed/processed/ignored)
│   ├──否──► [返回400错误]
│   │
│   └──是
│         │
│         ▼
│   [DB: 更新alarm_log.status
│    写入operation_log]
│         │
│         ▼
│   [刷新告警列表]
│
└── 查看详情
      │
      ▼
    [跳转到对应检测记录详情页
     通过record_id关联]
      │
      ▼
    [结束]
```

---

## 图4.8 模型管理与性能评估模块流程

```
[开始: 管理员进入模型管理页]
    │
    ▼
[GET /api/models
 获取所有模型 + active_model_id]
    │
    ▼
[DB: model_info
 按is_active降序, create_time降序]
    │
    ▼
[前端渲染模型列表:
 名称 | 类型 | 准确率 | F1 | 是否启用 | 操作按钮]
    │
    ▼
◇ 管理员操作？
│
├── 新增模型
│     │
│     ▼
│   [填写表单:
│    model_name/path/type
│    6项指标/description
│    dataset_format/required_columns
│    上传.pth文件(可选)
│    勾选is_active]
│     │
│     ▼
│   [POST /api/models]
│     │
│     ▼
│   ◇ 校验模型文件路径存在？
│   ├──否──► [返回错误: 文件不存在]──►回到表单
│   │
│   └──是
│         │
│         ▼
│   ◇ 首个模型 或 勾选激活？
│   ├──是──► [set_active_model():
│   │         取消所有其他模型激活
│   │         设置当前模型为唯一激活]
│   │
│   └──否──► [直接保存]
│         │
│         ▼
│   [DB: INSERT model_info
│    写入operation_log]
│         │
│         ▼
│   [刷新列表]
│
├── 激活切换
│     │
│     ▼
│   [POST /api/models/<id>/activate]
│     │
│     ▼
│   [set_active_model() 原子切换]
│     │
│     ▼
│   [DB: operation_log] → [刷新列表]
│
├── 删除模型
│     │
│     ▼
│   ◇ 有检测任务/记录引用此模型？
│   ├──是──► [提示: 有依赖，无法删除]
│   │
│   └──否
│         │
│         ▼
│   [DELETE /api/models/<id>]
│         │
│         ▼
│   [若删除的是激活模型 →
│    自动激活最近创建的模型]
│         │
│         ▼
│   [DB: operation_log] → [刷新列表]
│
└── 查看性能指标
      │
      ▼
    [展示模型指标卡片:
     Accuracy | Precision | Recall | F1
     FPR | FNR | Inference_Latency]
      │
      ▼
    [可选: ModelService.evaluate()
     在测试集上重新评估 → 缓存到artifacts/]
      │
      ▼
    [结束]
```

---

## 图4.9 实时流量监测模块流程

> 建议分两列画：左列为配置与启动，右列为后台监测循环。

```
═══════════════════════════════════════════════════════════════════════════
  配置与启动                                  后台监测循环
═══════════════════════════════════════════════════════════════════════════

[开始: 管理员进入监测页]
    │
    ▼
[GET /api/traffic-monitor
 获取当前状态]
    │
    ▼
◇ 环境就绪?(pipeline_ready)
│  scapy可用 & cicflowmeter可用
│  & 网卡已配置
│
├──否──► [展示未就绪状态
│         + 操作指引]
│
└──是
    │
    ▼
[PATCH /api/traffic-monitor/config
 配置抓包网卡]
    │
    ▼
[GET /api/traffic-monitor/interfaces
 获取可用网卡列表(Scapy自动发现)]
    │
    ▼
[选择网卡(如WLAN/Ethernet)]
    │
    ▼
[POST /api/traffic-monitor/start
 启动监测线程] ──────────────► [_run_loop() 线程启动]
    │                                │
    ▼                                ▼
[前端定时轮询                    ┌─────────────────────────────────┐
 GET /api/traffic-monitor       │  每个扫描周期的四阶段:            │
 展示实时状态面板]                │                                 │
    │                            │ ① 抓包阶段                      │
    │                            │   Scapy sniff(iface,            │
    │                            │     duration=60s, filter)       │
    │                            │   → pcap/目录/traffic_xxx.pcap  │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │ ② 特征提取阶段                   │
    │                            │   Python cicflowmeter           │
    │                            │   FlowSession.process(pkt)      │
    │                            │   → 原始特征CSV                 │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │ ③ 列名规范化阶段                 │
    │                            │   _normalize_python_            │
    │                            │   cicflowmeter_csv()            │
    │                            │   78个字段映射:                  │
    │                            │   src_ip → Source IP            │
    │                            │   tot_fwd_pkts → Total Fwd...   │
    │                            │   fwd_pkt_len_mean → Fwd...     │
    │                            │   + 补齐80个CIC-IDS2017标准列    │
    │                            │   → inbox/目录/traffic_xxx.csv  │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │ ④ 检测+归档阶段                  │
    │                            │   ◇ CSV有数据行?                 │
    │                            │   ├──否──► archive空文件         │
    │                            │   │        empty_feature_count++ │
    │                            │   │                              │
    │                            │   └──是                          │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │   run_detection(csv)             │
    │                            │   使用当前激活模型                │
    │                            │   → DetectRecord+AttackResult    │
    │                            │     +AlarmLog 写入DB             │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │   PCAP → pcap_archive/          │
    │                            │   CSV  → archive/               │
    │                            │   processed_count++              │
    │                            │        │                        │
    │                            │        ▼                        │
    │                            │   更新status:                    │
    │                            │   last_scan_at                   │
    │                            │   last_capture_at                │
    │                            │   last_extract_at                │
    │                            │   last_processed_file 等         │
    │                            └────────┬────────────────────────┘
    │                                      │
    │                                      ▼
    │                            [等待轮询间隔(默认10秒)]
    │                                      │
    │                                      ▼
    │                            ◇ stop_event 被设置？
    │                            ├──否──► 回到①下一轮
    │                            │
    │                            └──是
    │                                  │
    ▼                                  ▼
[POST /api/traffic-monitor/stop     [线程安全退出]
 管理员停止监测]                         │
    │                                  ▼
    ▼                              [结束]
[展示停止状态]
```

---

## 图4.10 用户管理模块流程

```
[开始: 管理员进入用户管理页]
    │
    ▼
[GET /api/users 获取所有用户]
    │
    ▼
[DB: user表 按create_time降序]
    │
    ▼
[前端渲染用户列表:
 用户名 | 角色 | 创建时间 | 操作]
    │
    ▼
◇ 管理员操作？
│
├── 新增用户
│     │
│     ▼
│   [填写: 用户名 + 密码 + 角色(admin/user)]
│     │
│     ▼
│   [POST /api/users]
│     │
│     ▼
│   ◇ 校验: 用户名非空 + 角色合法 + 用户名不重复？
│   ├──否──► [返回错误提示]──►回到列表
│   │
│   └──是
│         │
│         ▼
│   [密码 pbkdf2:sha256 哈希]
│         │
│         ▼
│   [DB: INSERT user + operation_log] → [刷新列表]
│
├── 编辑用户
│     │
│     ▼
│   [修改: 用户名/角色/新密码(可选)]
│     │
│     ▼
│   [PATCH /api/users/<id>]
│     │
│     ▼
│   ◇ 校验同上 + 排除自身ID查重
│   ├──否──► [返回错误提示]
│   │
│   └──是
│         │
│         ▼
│   [若编辑的是当前登录用户 →
│    同步更新Session中username/role]
│         │
│         ▼
│   [DB: UPDATE user + operation_log] → [刷新列表]
│
├── 删除用户
│     │
│     ▼
│   ◇ 是当前登录管理员自己？
│   ├──是──► [提示: 不能删除自己]
│   │
│   └──否
│         │
│         ▼
│   ◇ 该用户有检测记录？
│   ├──是──► [提示: 有关联记录，无法删除]
│   │
│   └──否
│         │
│         ▼
│   [DELETE /api/users/<id>]
│         │
│         ▼
│   [DB: DELETE user + operation_log] → [刷新列表]
│
└── 浏览完毕 ──► [结束]
```
