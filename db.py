# -*- coding: utf-8 -*-
"""
SQLite 数据库模块
负责评论数据的存储、去重、查询
"""
import sqlite3
from contextlib import contextmanager

import config


# 建表 SQL
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS comments (
    cid           TEXT PRIMARY KEY,            -- 评论ID
    aweme_id      TEXT,                        -- 视频ID
    text          TEXT,                        -- 评论内容
    create_time   INTEGER,                     -- 评论时间戳(秒)
    digg_count    INTEGER DEFAULT 0,           -- 点赞数
    reply_count   INTEGER DEFAULT 0,           -- 回复数
    user_id       TEXT,                        -- 用户ID
    user_nickname TEXT,                        -- 用户昵称
    user_sec_uid  TEXT,                        -- 用户sec_uid
    ip_label      TEXT,                        -- IP归属地
    parent_cid    TEXT,                        -- 父评论ID（一级评论为空，二级评论指向其父评论）
    reply_to_cid  TEXT,                        -- 回复的目标评论ID（二级评论用）
    crawl_time    TEXT DEFAULT (datetime('now','localtime'))  -- 抓取时间
);

CREATE INDEX IF NOT EXISTS idx_aweme_id   ON comments(aweme_id);
CREATE INDEX IF NOT EXISTS idx_parent_cid ON comments(parent_cid);
"""


@contextmanager
def get_conn():
    """获取数据库连接的上下文管理器，自动提交/关闭"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库，创建表"""
    with get_conn() as conn:
        conn.executescript(_INIT_SQL)


def save_comment(comment: dict):
    """
    保存一条评论到数据库，已存在则忽略（根据 cid 去重）

    :param comment: 评论字典，字段需与表结构对应
    """
    sql = """
    INSERT OR IGNORE INTO comments
        (cid, aweme_id, text, create_time, digg_count, reply_count,
         user_id, user_nickname, user_sec_uid, ip_label, parent_cid, reply_to_cid)
    VALUES
        (:cid, :aweme_id, :text, :create_time, :digg_count, :reply_count,
         :user_id, :user_nickname, :user_sec_uid, :ip_label, :parent_cid, :reply_to_cid)
    """
    with get_conn() as conn:
        conn.execute(sql, comment)


def save_comments(comments: list):
    """批量保存评论"""
    if not comments:
        return
    sql = """
    INSERT OR IGNORE INTO comments
        (cid, aweme_id, text, create_time, digg_count, reply_count,
         user_id, user_nickname, user_sec_uid, ip_label, parent_cid, reply_to_cid)
    VALUES
        (:cid, :aweme_id, :text, :create_time, :digg_count, :reply_count,
         :user_id, :user_nickname, :user_sec_uid, :ip_label, :parent_cid, :reply_to_cid)
    """
    with get_conn() as conn:
        conn.executemany(sql, comments)


def get_comment_count(aweme_id: str = None) -> int:
    """查询已保存的评论数量"""
    with get_conn() as conn:
        if aweme_id:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM comments WHERE aweme_id = ?", (aweme_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()
        return row["n"]


def cid_exists(cid: str) -> bool:
    """判断某条评论是否已存在（用于去重提前结束翻页）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM comments WHERE cid = ? LIMIT 1", (cid,)
        ).fetchone()
        return row is not None
