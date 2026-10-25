# -*- coding: utf-8 -*-
"""
查询 / 导出已抓取的评论数据
用法：
    python query.py                  # 查看统计
    python query.py export csv       # 导出为 CSV
    python query.py list <aweme_id>  # 查看某视频的评论
"""
import sys
import csv

import config
from db import get_conn


def stats():
    """统计信息"""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
        videos = conn.execute(
            "SELECT COUNT(DISTINCT aweme_id) AS n FROM comments"
        ).fetchone()["n"]
        print(f"数据库: {config.DB_PATH}")
        print(f"视频数: {videos}")
        print(f"评论总数: {total}")
        print()

        if videos:
            print("各视频评论数:")
            rows = conn.execute(
                "SELECT aweme_id, COUNT(*) AS n FROM comments GROUP BY aweme_id ORDER BY n DESC"
            ).fetchall()
            for r in rows:
                print(f"  {r['aweme_id']}: {r['n']} 条")


def list_comments(aweme_id: str, limit: int = 50):
    """列出某视频的评论"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM comments WHERE aweme_id = ? ORDER BY create_time DESC LIMIT ?",
            (aweme_id, limit),
        ).fetchall()
        print(f"视频 {aweme_id} 的评论（最多 {limit} 条）：\n")
        for r in rows:
            tag = "[回复]" if r["parent_cid"] else ""
            print(f"{tag}{r['user_nickname']}({r['ip_label']}): {r['text']}")
            print(f"  点赞:{r['digg_count']}  回复:{r['reply_count']}  cid:{r['cid']}")
            print()


def export_csv(path: str = "comments.csv"):
    """导出为 CSV"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM comments ORDER BY aweme_id, create_time").fetchall()
        if not rows:
            print("数据库为空，无数据可导出")
            return

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            for r in rows:
                writer.writerow(r)

        print(f"已导出 {len(rows)} 条到 {path}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "export" and sys.argv[2] == "csv":
        export_csv()
    elif len(sys.argv) >= 3 and sys.argv[1] == "list":
        list_comments(sys.argv[2])
    else:
        stats()
