# 4.3 流程图论文版处理建议

建议正文采用“简图 + 文字解释”的方式，不把接口名、函数名、批处理大小、字段映射数量等实现细节放进流程图。图中节点控制在 5 到 8 个，节点文字控制在 4 到 10 个字左右；实现细节写在图前后的正文段落中。

已按 `流程图参考.png` 的样式生成黑白版流程图，推荐论文正文优先使用 `thesis_figures/4_3_bw_flowcharts/` 下的图片。该版本为白底、黑色边框、普通矩形处理框、菱形判断框和圆角开始/结束框，图内不含标题，适合在 Word 中通过题注统一编号。

## 正文建议保留的图

| 建议图号 | 用途 | 文件 |
| --- | --- | --- |
| 图4.3-1 | 展示系统核心模块划分 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-1-module-structure.png` |
| 图4.3-2 | 展示登录认证与权限控制 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-2-login-permission.png` |
| 图4.3-3 | 展示首页统计展示流程 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-3-dashboard-stats.png` |
| 图4.3-4 | 展示离线 CSV 上传检测主流程 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-4-offline-detection.png` |
| 图4.3-5 | 合并展示结果查看与告警处理 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-5-result-alarm.png` |
| 图4.3-6 | 展示模型管理主流程 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-6-model-management.png` |
| 图4.3-7 | 展示在线流量监测主流程 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-7-traffic-monitoring.png` |
| 图4.3-8 | 展示用户管理流程 | `thesis_figures/4_3_bw_flowcharts/fig4-3-bw-8-user-management.png` |

## 不建议放进正文的内容

- 不在流程图节点中写 `/api/...` 接口路径，正文说明即可。
- 不在节点中写具体函数名，例如 `run_detection()`、`ModelService`、`bulk_insert_mappings`。
- 不在图中写参数值，例如 `chunksize=5000`、`batch_size=1024`、`DB_BATCH_SIZE=2000`。
- 不把“字段映射、缺失值填充、Z-Score 标准化、张量重构”拆成多个节点，可合并为“数据预处理”。
- 不为每个 CRUD 操作单独画图，用户管理和模型管理各用一张主流程图即可。

## 详细图的用途

`thesis_figures/4_3_core_modules/` 下的 12 张详细图不建议放入论文正文，可作为：

- 答辩时解释系统实现细节的备用图；
- 自己检查业务逻辑是否完整的设计草图；
- 后续写第5章系统实现时的参考材料。

## 绘图脚本

论文版短图由以下脚本生成：

```powershell
.\.venv\Scripts\python.exe generate_chapter4_3_bw_flowcharts.py
```

彩色短图由以下脚本生成：

```powershell
.\.venv\Scripts\python.exe generate_chapter4_3_paper_flowcharts.py
```

详细版图由以下脚本生成：

```powershell
.\.venv\Scripts\python.exe generate_chapter4_3_current_flowcharts.py
```
