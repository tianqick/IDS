# DeepIDS Graduation Project

这是一个基于 `Vue 3 + Flask API + MySQL + PyTorch` 的网络入侵检测系统，已经按前后端分离方式组织完成，适合作为毕业设计系统原型。

## 当前架构

- 前端：`Vue 3` 单页应用
- 后端：`Flask` 仅提供 `/api/*` 接口与单页入口
- 数据库：`MySQL`
- 模型推理：`PyTorch`
- 鉴权：`session` 登录态 + 密码哈希存储
- 权限：管理员与普通用户页面、接口双重区分

## 已实现功能

1. 登录与退出登录
2. 管理员 / 普通用户权限区分
3. CSV 数据上传与检测
4. 分块读取 + 分批推理 + 分批写库
5. 检测结果与历史记录查看
6. 告警中心与告警状态修改
7. 模型信息展示
8. 性能评估页面
9. 用户新增、编辑、删除
10. 仪表盘统计与图表展示

## 主要入口

- 单页前端入口：[spa.html](./app/templates/spa.html)
- Vue 应用脚本：[vue-app.js](./app/static/js/vue-app.js)
- Flask API：[api.py](./app/routes/api.py)
- 模型推理服务：[model_service.py](./app/services/model_service.py)
- 检测写库服务：[data_service.py](./app/services/data_service.py)

## 启动步骤

### 1. 创建虚拟环境

```powershell
cd c:\graduationProject\project\model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
```

推荐配置示例：

```env
SECRET_KEY=ids-system-secret-key
DATABASE_URI=mysql+pymysql://root:你的密码@127.0.0.1:3306/ids_system?charset=utf8mb4
MODEL_PATH=c:\graduationProject\project\model\1D_CNN_BiLSTM_Attn_best.pth
DATASET_DIR=c:\graduationProject\project\model\dataset
ARTIFACT_DIR=c:\graduationProject\project\model\artifacts
PREDICT_CHUNK_SIZE=5000
INFERENCE_BATCH_SIZE=1024
DB_BATCH_SIZE=2000
```

这三个参数用于大文件检测性能调优：

- `PREDICT_CHUNK_SIZE`：每次从 CSV 读取的行数
- `INFERENCE_BATCH_SIZE`：每次模型推理的 batch 大小
- `DB_BATCH_SIZE`：每次批量写入数据库的记录数

如果机器内存较小，可调低为：

```env
PREDICT_CHUNK_SIZE=2000
INFERENCE_BATCH_SIZE=256
DB_BATCH_SIZE=1000
```

### 4. 初始化 MySQL

进入 MySQL 后执行：

```sql
source c:/graduationProject/project/model/sql/init.sql;
```

### 5. 启动系统

```powershell
python app.py
```

浏览器访问：

```text
http://127.0.0.1:5000
```

## 初始化演示账号

进入登录页后，点击“初始化演示账号”按钮即可。

默认账号：

- 管理员：`admin / admin123`
- 普通用户：`user / user123`

## 模型接入说明

系统会优先使用：

- [1D_CNN_BiLSTM_Attn_best.pth](./1D_CNN_BiLSTM_Attn_best.pth)

如果该文件不存在，才会回退到：

- [best_hybrid_ids_model.pth](./best_hybrid_ids_model.pth)

当前预处理和模型结构已按你的 [v2.ipynb](./v2.ipynb) 对齐，支持：

- `CIC-IDS2017` 风格 CSV
- 特征列清洗与对齐
- 标准化
- 分块读取和批量推理

## 管理员功能

- 查看系统全部检测记录
- 查看和修改告警状态
- 查看模型信息
- 查看性能评估
- 新增用户
- 编辑用户
- 删除无关联检测记录的用户

## 普通用户功能

- 登录系统
- 上传数据并执行检测
- 查看自己的检测结果
- 查看自己的历史记录

## 目录结构

```text
model/
├── app/
│   ├── routes/
│   ├── services/
│   ├── static/
│   └── templates/
├── artifacts/
├── dataset/
├── logs/
├── sample_data/
├── sql/
├── uploads/
├── app.py
├── v2.ipynb
├── 1D_CNN_BiLSTM_Attn_best.pth
├── best_hybrid_ids_model.pth
├── requirements.txt
└── README.md
```

## 常见问题

### 1. 登录成功但页面空白

先按 `Ctrl + F5` 强刷浏览器，确保加载到新的 Vue 前端脚本。

### 2. 上传后等待较久

大文件会执行分块读取、分批推理、分批写库，等待时间属于正常现象。

### 3. MySQL 连接失败

重点检查：

- `DATABASE_URI` 中账号密码是否正确
- MySQL 服务是否启动
- `ids_system` 数据库是否已初始化

### 4. 模型加载失败

重点检查：

- `MODEL_PATH` 是否指向正确的 `.pth`
- 权重文件是否和训练结构匹配
- 训练特征列是否和当前预处理流程一致
