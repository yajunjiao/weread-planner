# 微信读书管理与规划 · weread-planner

> 一个帮你在微信读书里「把想读变成读完」的 CodeBuddy Skill —— 目标规划、书架管理、进度跟踪、数据分析与可视化仪表盘，一条龙。

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CodeBuddy Skill](https://img.shields.io/badge/type-CodeBuddy%20Skill-green.svg)](https://www.codebuddy.ai)

---

## ✨ 这是什么

`weread-planner` 是微信读书的**管理与规划**插件。它不负责「找书 / 取数」（那是 `weread-skills` 微信读书助手的事），而是专注把你已有的阅读数据，加工成**可执行的计划**和**看得懂的洞察**：

- 📅 **定目标**：根据可用时间、目标数量、兴趣主题，生成年 / 月 / 周阅读计划
- 📚 **管书架**：想读 / 在读 / 已读分层，给书单排优先级，清理「僵尸书单」
- 📈 **跟进度**：计划 vs 实际偏差、剩余量估算、读完日期预测
- 🔍 **做分析**：月度时长趋势、主题分布、完成率、阅读节奏
- 📊 **出报告**：一键生成 Markdown 阅读报告 + 离线 HTML 可视化仪表盘

## 🤝 与「微信读书助手」的关系

| Skill | 角色 | 负责 |
|-------|------|------|
| `weread-skills`（微信读书助手） | **取数** | 搜索书籍、查看书架、读取笔记划线、拉取原始阅读统计 |
| `weread-planner`（本 Skill） | **规划与管理** | 制定计划、组织书单、跟踪进度、转化洞察、生成报告与仪表盘 |

> 工作流：先用 `weread-skills` 把数据拉下来，再用 `weread-planner` 加工。
> 如果你已经自己导出了数据（JSON / CSV / 截图 / 手记），也可以跳过取数，直接进分析。

## 📂 目录结构

```
weread-planner/
├── SKILL.md                       # Skill 主文件：能力说明 + 工作流
├── README.md                      # 本文件
├── references/
│   ├── planning_methods.md        # 规划方法论（SMART / 拆解 / 估算 / 排序 / 反模式）
│   └── data_model.md              # reading-log 数据结构 + 与 weread-skills 的对接
├── assets/
│   └── reading_plan_template.md   # 计划 / 月报 / 年报 三类 Markdown 输出模板
└── scripts/
    └── reading_dashboard.py       # reading-log → 离线 HTML 仪表盘（仅标准库，零依赖）
```

## 🚀 安装（作为 CodeBuddy Skill）

把整个文件夹放进 CodeBuddy 的 skills 目录即可，**用户级**或**项目级**均可：

```bash
# 用户级（跨项目可用）
cp -r weread-planner ~/.codebuddy/skills/weread-planner

# 或项目级（团队共享）
cp -r weread-planner <你的项目>/.codebuddy/skills/weread-planner
```

安装后，在 CodeBuddy 对话里直接说类似的话即可触发：

- “帮我规划今年的阅读”
- “管理我的书架 / TBR”
- “跟踪一下我的阅读进度”
- “生成一份年度阅读报告”
- “把我的读书数据做成仪表盘”

## 🛠️ 仪表盘脚本（可独立使用）

`scripts/reading_dashboard.py` 是零依赖的纯标准库脚本，不依赖 CodeBuddy 也能跑：

```bash
# JSON 输入
python scripts/reading_dashboard.py --input reading_log.json --output dashboard.html

# CSV 输入同样支持
python scripts/reading_dashboard.py --input reading_log.csv --output dashboard.html

# 可选参数
python scripts/reading_dashboard.py \
  --input reading_log.json \
  --output dashboard.html \
  --title "我的 2026 阅读仪表盘" \
  --year 2026
```

生成的 `dashboard.html` **完全自包含、不联网**、图表用内联 SVG 绘制，双击即可在浏览器打开。

### 数据格式

支持两种输入模式：

1. **聚合模式**（推荐，对接微信读书统计接口）：顶层带 `aggregates` 块，直接吃接口返回的真实汇总值（月度时长、分类时长、总时长、活跃天数）。
2. **逐书模式**（手填 / 导出）：每本书一条记录，脚本自动汇总。

核心字段（`references/data_model.md` 有完整说明）：

```json
{
  "meta": { "owner": "...", "year": 2026, "goal_books": 30 },
  "aggregates": {
    "summary": { "read_count": 71, "finished": 43, "total_minutes": 11442, "read_days": 193 },
    "monthly": { "2026-01": 199800, "2026-02": 137520 },
    "categoryMinutes": { "个人成长": 304991, "经济理财": 250212 }
  },
  "books": [ { "title": "...", "author": "...", "status": "finished", "minutes": 1104 } ]
}
```

> 时长单位：聚合模式为**秒**，逐书模式 `minutes` 为**分钟**，脚本内部会统一换算。

## 📊 真实示例

用作者本人的微信读书真实数据跑出来的 2026 半年报（截至 7 月 14 日）：

| 指标 | 数值 |
|------|------|
| 读完 | **43 本** |
| 开读 | 71 本（读完率 61%） |
| 总时长 | **190.7 小时** |
| 阅读天数 | 193 / 195 天（覆盖率 99%） |
| 主题偏好 | 个人成长 44% + 经济理财 36% |

仪表盘包含三块图表：**月度阅读时长趋势**（1 月 55.5h 持续下滑至 7 月 5.1h）、**主题分布**（按阅读时长）、以及**按时长排序的 Top 10 书单**。

报告还自动给出洞察，例如：

> 天数覆盖率 99% 说明连续性极佳，但月度时长腰斩——典型「碎片式维持」。建议设每日 25 分钟「深度阅读」下限。

## 🧩 工作流示意

```
[微信读书 App]
      │  (API: WEREAD_API_KEY)
      ▼
[weread-skills]  ───  书架 / 阅读统计  ──┐
                                        ▼
[reading_log.json / csv]  ──►  [weread-planner]
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
           阅读计划 (MD)          阅读报告 (MD)          仪表盘 (HTML)
```

## 📝 许可证

[MIT](LICENSE) —— 随意使用、修改、再分发。

## 🙏 致谢

- 数据来源于 [微信读书](https://weread.qq.com/)
- 取数能力依赖 `weread-skills`（微信读书助手）Skill
- 由 [CodeBuddy](https://www.codebuddy.ai) 的 Skill 机制驱动
