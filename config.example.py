# -*- coding: utf-8 -*-
"""
配置文件模板
使用方法：
    1. 复制本文件为 config.py  (cp config.example.py config.py)
    2. 在 config.py 中填入你自己的 Cookie 和视频链接
    3. config.py 已在 .gitignore 中，不会被上传，保护你的隐私
"""

# ========== 必填项 ==========

# User-Agent：用你浏览器的 UA，要和 Cookie 对应的浏览器一致
# 打开浏览器开发者工具 -> Network -> 任意请求 -> Headers -> user-agent 复制
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Cookie：从浏览器复制完整的 Cookie 字符串
# 关键字段：ttwid、sessionid（登录后才有）、s_v_web_id 等
# 获取方法见 README.md
COOKIE = "在这里粘贴你的Cookie"

# 要爬取的抖音视频分享链接，例如：
#   https://www.douyin.com/video/7312345678901234567
#   https://www.douyin.com/jingxuan?modal_id=7312345678901234567
#   或 https://v.douyin.com/xxxxxxx/  (短链也支持，会自动重定向解析)
VIDEO_URL = "https://www.douyin.com/video/7312345678901234567"

# ========== 可选项 ==========

# 数据库文件路径
DB_PATH = "comments.db"

# 每页评论数（抖音接口固定 20，一般不用改）
COMMENT_COUNT_PER_PAGE = 20

# 最多爬取多少条评论，0 表示不限制
MAX_COMMENTS = 0

# 是否爬取二级评论（回复）
FETCH_REPLY = False

# 二级评论每个一级评论最多爬取多少条回复
MAX_REPLY_PER_COMMENT = 50

# 批量写入阈值：内存里攒够多少条再一次性写入数据库
# 0 表示每爬完一页(20条)就写一次；2000 表示攒够2000条再写一次
BATCH_INSERT_SIZE = 2000

# 请求间隔（秒），避免太快被风控
SLEEP_TIME = 1.0

# 最大重试次数
MAX_RETRY = 3
