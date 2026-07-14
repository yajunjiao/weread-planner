# 阅读数据模型 (Reading Log Data Model)

本文件定义规划与分析统一使用的 `reading-log` 结构。所有脚本（`scripts/reading_dashboard.py`）与模板均依赖此结构。用户提供的零散数据应先规整为本结构再处理。

## 1. reading-log 条目字段

reading-log 是一组书籍记录的集合，每条记录代表一本书的阅读情况。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `book_id` | string | 否 | 微信读书 bookId（来自 `weread-skills` 搜索/书架），用于回链 |
| `title` | string | 是 | 书名 |
| `author` | string | 否 | 作者 |
| `status` | enum | 是 | `want`(想读) / `reading`(在读) / `finished`(已读) |
| `category` | string | 否 | 主题类别，如 小说/历史/科技/商业/传记/自我提升 |
| `total_pages` | int | 否 | 总页数（无则用 `total_words ÷ 500` 估算） |
| `total_words` | int | 否 | 总字数（微信读书常用口径，可替代页数） |
| `read_pages` | int | 否 | 已读页数（在读时 < total_pages） |
| `start_date` | string | 否 | 开始日期 `YYYY-MM-DD` |
| `finish_date` | string | 否 | 读完日期 `YYYY-MM-DD`（仅 finished） |
| `minutes` | int | 否 | 该书累计阅读分钟数 |
| `rating` | int | 否 | 评分 1-5（仅 finished） |
| `note_count` | int | 否 | 笔记/划线数量 |
| `deep_link` | string | 否 | 微信读书深度链接（来自 `weread-skills` 回包） |

字段换算规则：

- 仅给 `total_words` 时：`total_pages = round(total_words / 500)`。
- 进度百分比：`read_pages / total_pages`（reading 状态）。
- 若 `minutes` 缺失但有 `read_pages`：用默认 30 页/小时回填估算时长。

## 2. JSON 格式示例

```json
{
  "meta": {
    "owner": "用户昵称",
    "year": 2026,
    "goal_books": 30
  },
  "books": [
    {
      "book_id": "book_abc123",
      "title": "人类简史",
      "author": "尤瓦尔·赫拉利",
      "status": "finished",
      "category": "历史",
      "total_pages": 440,
      "read_pages": 440,
      "start_date": "2026-01-03",
      "finish_date": "2026-01-20",
      "minutes": 880,
      "rating": 5,
      "note_count": 32,
      "deep_link": "https://weread.qq.com/web/bookDetail/..."
    },
    {
      "title": "三体",
      "status": "reading",
      "category": "小说",
      "total_pages": 302,
      "read_pages": 120,
      "start_date": "2026-02-01",
      "minutes": 240
    }
  ]
}
```

## 3. CSV 格式

表头与字段一一对应，一行一本书：

```csv
book_id,title,author,status,category,total_pages,read_pages,start_date,finish_date,minutes,rating,note_count
,人类简史,尤瓦尔·赫拉利,finished,历史,440,440,2026-01-03,2026-01-20,880,5,32
,三体,,reading,小说,302,120,2026-02-01,,240,,
```

`scripts/reading_dashboard.py` 同时支持 JSON（`books` 数组）与 CSV（自动映射表头）两种输入。

## 4. 聚合指标（脚本计算）

仪表盘脚本基于上述字段自动计算：

- **完成率** = finished 数量 / (finished + reading + want) 总数
- **月度时长趋势** = 按 `finish_date` 或累计 `minutes` 归集到月份
- **类别分布** = 按 `category` 统计本数 / 时长 / 页数
- **平均单本时长** = finished 的 `minutes` 均值
- **连续阅读天数 (streak)** = 基于每日 `minutes` 分布的去重日期最长连续段（需更细粒度数据时退化为展示总天数）
- **目标进度** = finished 数量 / `meta.goal_books`（若提供）

## 5. 与 weread-skills 的数据对接

当用户通过 `weread-skills` 取数时，映射规则：

- 书架 `/shelf/sync` → 生成 `want`/`reading` 状态条目（含 `book_id`、`title`、`deep_link`）。
- 阅读统计 `/review/readingdata` → 补充 `minutes`、`finish_date`、月度分布。
- 笔记 `/user/notebooks` → 补充 `note_count`。
- 所有 Unix 时间戳按 `weread-skills` 规范转为 `YYYY-MM-DD` 再写入本结构。
