---
name: weread-planner
description: 微信读书管理与规划 — 帮助用户制定阅读目标与计划、管理书架/书单、跟踪阅读进度、分析阅读数据并生成可视化报告与仪表盘。当用户提出"制定阅读计划""规划今年读什么""管理我的书架/TBR""跟踪阅读进度""生成阅读报告/年度总结""我的阅读数据可视化"等需求时使用本 skill；与 weread-skills（微信读书助手，负责搜索/笔记/原始统计）互补，本 skill 侧重规划、管理与分析。
version: 1.0.0
---

# 微信读书管理与规划 (WeRead Planner)

帮助用户把"想读"变成"读完"：从目标设定、书单规划、进度跟踪，到数据分析和可视化报告的全流程管理方法。

本 skill 与 `weread-skills`（微信读书助手）互补：

- `weread-skills` 负责**取数**：搜索书籍、查看书架、读取笔记划线、拉取原始阅读统计（时长/天数/偏好）。
- `weread-planner`（本 skill）负责**规划与管理**：基于目标制定计划、组织书单、跟踪进度、把原始数据转化为洞察、生成可读的报告与仪表盘。

当用户需要原始数据时，先调用 `weread-skills` 取数，再用本 skill 的方法加工。若用户已自行提供数据（截图、导出的 JSON/CSV、手动记录），直接进入规划/分析流程。

## 何时使用

- 制定阅读目标：年/月/周目标、主题挑战、书单规划
- 管理书架与 TBR：想读/在读/已读分类、书单整理、去重与优先级排序
- 跟踪进度：对比计划 vs 实际、剩余量估算、读完时间预测
- 分析数据：阅读时长趋势、类型分布、完成率、阅读节奏
- 生成产出：阅读计划文档、月度/年度阅读报告、HTML 可视化仪表盘

## 核心能力

### 1. 制定阅读目标与计划

根据用户的可用时间、目标数量、兴趣主题生成可执行的阅读计划。

工作流：

1. 收集输入：每日/每周可用阅读时长、目标周期（如 2026 全年）、目标数量（如 30 本）、关注的类别或主题、当前书架中的待读清单。
2. 参考 `references/planning_methods.md` 选择规划框架（SMART 目标、年→月→周拆解、按页数/时长估算、主题轮换策略）。
3. 用 `assets/reading_plan_template.md` 中的结构产出计划文档（Markdown）。
4. 给出可调整的节奏建议（如每周读完 0.6 本 ≈ 每月 2.5 本），并提示风险（过满/过松）。

### 2. 管理书架与书单 (TBR)

将"想读"清单结构化为可执行的书单。

工作流：

1. 从 `weread-skills` 的 `/shelf/sync` 获取书架，或读取用户提供的书单。
2. 按状态分层：想读 (TBR) / 在读 / 已读；按主题、难度、篇幅打标签。
3. 排序优先级：结合用户目标、书籍篇幅、阅读难度、主题连贯性给出阅读顺序建议。
4. 识别"僵尸书单"（长期未动、与当前目标无关），建议归档或移除。

### 3. 跟踪阅读进度

对比计划与实际，给出偏差与预测。

工作流：

1. 从 `references/data_model.md` 定义的 reading-log 结构读取用户的进度记录（书名、开始/结束日期、总页数、已读页数、累计时长）。
2. 计算完成率、剩余页数/时长、按当前速度预测读完日期。
3. 对比阶段目标（如"本季度应读 8 本"），输出偏差与追赶建议。

### 4. 分析阅读数据与生成报告

把原始统计转化为可读的洞察。

工作流：

1. 取数：调用 `weread-skills` 的 `/review/readingdata`（阅读统计）与 `/shelf/sync`，或读取用户提供的 reading-log。
2. 按 `references/data_model.md` 规整为统一结构。
3. 计算维度：月度时长趋势、类型/主题分布、平均单本时长、连续阅读天数、完成率。
4. 产出月度/年度阅读报告（Markdown，套用 `assets/reading_plan_template.md` 的报告章节）。

### 5. 生成可视化仪表盘

将 reading-log 渲染为自包含的 HTML 仪表盘（含图表，无需联网）。

工作流：

1. 确认用户有结构化 reading-log（JSON 或 CSV，字段见 `references/data_model.md`）。
2. 运行 `scripts/reading_dashboard.py`：

   ```bash
   python scripts/reading_dashboard.py --input reading_log.json --output dashboard.html
   # CSV 输入同样支持：--input reading_log.csv
   # 可选：--title "我的 2026 阅读仪表盘" --year 2026
   ```

3. 用 `preview_url` 打开生成的 `dashboard.html` 供用户查看。
4. 脚本零依赖（仅标准库），离线可用；图表用内联 SVG/Canvas 绘制。

## 数据模型

所有规划与分析基于统一的 reading-log 结构，详见 `references/data_model.md`。核心字段：`book_id`、`title`、`author`、`status`(want/reading/finished)、`category`、`total_pages`、`read_pages`、`start_date`、`finish_date`、`minutes`、`rating`。

若用户仅有零散信息（如"刚读完三体，约 30 小时"），先补全为上述结构再分析。

## 引用文件

- `references/planning_methods.md` — 规划方法论与框架（SMART、拆解、估算、节奏）
- `references/data_model.md` — reading-log 数据结构与技术说明
- `assets/reading_plan_template.md` — 阅读计划 / 月度 / 年度报告的输出模板
- `scripts/reading_dashboard.py` — reading-log → HTML 仪表盘生成器

## 输出规范

- 计划与报告一律采用 Markdown，套用 `assets/reading_plan_template.md` 的章节结构，便于用户直接存档。
- 时间戳展示为 `YYYY-MM-DD`；阅读时长展示为"X 小时 Y 分钟"；页数用"已读/总页"形式。
- 仪表盘为离线 HTML，不依赖任何外部 CDN。
- 给出建议时标注假设（如默认阅读速度 30 页/小时），方便用户校正。
