# 抖音评论爬虫

用 Python + requests + SQLite 爬取抖音视频下的评论，支持一级评论和二级回复，自动翻页、去重、批量入库。

## ✨ 特性

- 🔑 **本地生成 a_bogus 签名**，无需依赖第三方在线服务，稳定不掉链
- 📦 **纯 requests 实现**，不依赖 Selenium / Playwright / 浏览器
- 💾 **SQLite 存储**，自动去重、断点续爬
- 🔄 **批量写入**，可配置攒够 N 条再写一次，减少 IO
- 📄 **支持长链 / 短链 / 精选页链接**，自动解析视频 ID
- 📊 **附带 SQL 分析脚本**，开箱即用

## 📐 原理

抖音 web 端有公开的评论 JSON 接口：

| 接口 | 用途 |
|------|------|
| `/aweme/v1/web/comment/list/` | 一级评论 |
| `/aweme/v1/web/comment/list/reply/` | 二级回复 |

但接口需要 **`a_bogus` 签名 + Cookie** 才能访问。其中 `a_bogus` 是抖音 JS 的逆向加密算法，本项目使用 [amxsa/douyin_abogus_python](https://github.com/amxsa/douyin_abogus_python) 的纯 Python 实现（已内置，无需额外安装）。

## 📁 文件结构

```
├── douyin_comment.py     # 核心爬虫（签名、请求、翻页、批量写入）
├── abogus.py             # a_bogus 签名算法（纯 Python 实现）
├── gmssl/                # 签名算法依赖的国密库（sm3 哈希）
├── db.py                 # SQLite 数据库模块（建表、存储、去重）
├── query.py              # 查询统计 / 导出 CSV
├── config.example.py     # 配置文件模板（复制为 config.py 后填写）
├── requirements.txt      # Python 依赖
├── 分析SQL.sql           # 20 条分析查询合集（DB Browser 直接运行）
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> 只需要 `requests` 一个依赖。`gmssl` 和 `abogus` 已内置在仓库中，无需安装。

### 2. 配置

复制配置模板并填写：

```bash
cp config.example.py config.py
```

编辑 `config.py`，填入两样东西：

**① Cookie**（必填）

1. 用 Chrome/Edge 打开 https://www.douyin.com 并**登录**
2. 按 `F12` → **Network** 标签
3. 随便点开一个视频，在请求列表里找到 `comment/list` 开头的请求
4. Headers 里找 `Cookie:` 那一行，**完整复制**
5. 粘贴到 `config.py` 的 `COOKIE = "..."` 里

> 关键字段：`ttwid`、`sessionid`（登录后有）。建议登录，更稳定。

**② 视频链接**（必填）

```python
VIDEO_URL = "https://www.douyin.com/video/7312345678901234567"
```

支持以下格式：
- `https://www.douyin.com/video/7312345678901234567`
- `https://www.douyin.com/jingxuan?modal_id=7312345678901234567`
- `https://v.douyin.com/xxxxxxx/`（短链，自动重定向解析）

### 3. 运行

```bash
python douyin_comment.py
```

日志示例：

```
23:38:13 [INFO] 解析到 aweme_id = 7312345678901234567
23:38:14 [INFO] 第 1 页: 获取 20 条，累计 20 条（待写入 20 条）
23:38:16 [INFO] 第 2 页: 获取 20 条，累计 40 条（待写入 40 条）
...
23:41:17 [INFO]   💾 写入数据库 2007 条（缓冲区已清空）
23:41:30 [INFO] 一级评论爬取完成，共 238 条
```

### 4. 查看 / 导出数据

```bash
python query.py                    # 查看统计
python query.py list 7312345678901234567   # 查看某视频评论
python query.py export csv         # 导出为 comments.csv
```

也可以用 [DB Browser for SQLite](https://sqlitebrowser.org/) 直接打开 `comments.db`，配合 `分析SQL.sql` 做各种统计分析。

## ⚙️ 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `COOKIE` | — | 抖音 Cookie（必填） |
| `VIDEO_URL` | — | 视频链接（必填） |
| `MAX_COMMENTS` | 0 | 最多爬取条数，0=不限 |
| `FETCH_REPLY` | False | 是否爬取二级评论 |
| `BATCH_INSERT_SIZE` | 2000 | 攒够多少条再写入数据库 |
| `SLEEP_TIME` | 1.0 | 请求间隔（秒） |
| `MAX_RETRY` | 3 | 失败重试次数 |

## 🗄️ 数据库表结构

| 字段 | 说明 |
|------|------|
| cid | 评论ID（主键，去重用） |
| aweme_id | 视频ID |
| text | 评论内容 |
| create_time | 评论时间戳（秒） |
| digg_count | 点赞数 |
| reply_count | 回复数 |
| user_id / user_nickname / user_sec_uid | 评论者信息 |
| ip_label | IP归属地 |
| parent_cid | 父评论ID（一级为空，二级指向父评论） |
| reply_to_cid | 回复目标评论ID |
| crawl_time | 抓取时间 |

## 🔧 常见问题

**Q: 返回空数据 / 评论为空？**
A: 99% 是 Cookie 失效或不完整。重新从浏览器复制，确保含 `ttwid`。`USER_AGENT` 也要和获取 Cookie 时的浏览器一致。

**Q: SSL 连接失败 / `check_hostname` 报错？**
A: 系统开了代理导致。代码已加 `trust_env = False` 绕过系统代理，如仍失败请关闭代理软件重试。

**Q: 被风控 / 请求太频繁？**
A: 调大 `SLEEP_TIME`（默认 1 秒）。

**Q: 想爬多个视频？**
A: 修改 `douyin_comment.py` 末尾，循环调用 `crawler.run(url)`，数据库按 `aweme_id` 区分。

**Q: 页面显示评论数和爬到的不一致？**
A: 页面显示的总数含一级评论 + 二级回复。只爬一级评论时数量会少于页面显示，开启 `FETCH_REPLY = True` 可爬取二级回复。

## 📊 数据分析

项目附带 `分析SQL.sql`，包含 20 条常用分析查询，用 DB Browser for SQLite 打开 `comments.db`，在"执行 SQL"标签页粘贴运行即可：

- 热门评论排行（按点赞 / 回复 / 综合热度）
- 地域分布统计
- 评论时间趋势（按天 / 按小时）
- 用户分析（刷屏党 / 人气王）
- 评论长度分布
- 关键词搜索
- 重复内容检测

## ⚠️ 法律与合规说明

- 本工具仅用于**学习交流**，爬取的都是公开可见的评论数据
- 请勿用于商业用途、批量采集、数据倒卖
- 请遵守抖音的用户协议，控制请求频率，不要对服务器造成压力
- 使用本工具产生的一切后果由使用者自行承担

## 🙏 致谢

- [amxsa/douyin_abogus_python](https://github.com/amxsa/douyin_abogus_python) — a_bogus 签名的纯 Python 实现
- [gmssl](https://github.com/duanhongyi/gmssl) — 国密算法 Python 库（sm3 哈希）

## 📄 License

[MIT](LICENSE)
