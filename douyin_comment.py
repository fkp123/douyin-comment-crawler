# -*- coding: utf-8 -*-
"""
抖音视频评论爬虫
=================
- 输入：抖音视频分享链接（长链 / 短链均可）
- 输出：SQLite 数据库 comments.db
- 依赖：requests、gmssl

原理：
    1. 抖音 web 端评论接口为
       https://www.douyin.com/aweme/v1/web/comment/list/        （一级评论）
       https://www.douyin.com/aweme/v1/web/comment/list/reply/  （二级评论/回复）
    2. 接口需要 a_bogus 签名参数，用本地 abogus.py 生成（纯 Python 实现，无需浏览器）
    3. 需要 Cookie（至少 ttwid），从浏览器复制
    4. 通过 cursor 翻页，has_more 判断是否结束
    5. 绕过系统代理（s.trust_env = False），避免代理导致 SSL 报错
"""
import time
import re
import random
import logging

import requests

from abogus import ABogus

import config
import db

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("douyin")


class DouyinCommentCrawler:
    # 评论接口
    COMMENT_API = "https://www.douyin.com/aweme/v1/web/comment/list/"
    REPLY_API = "https://www.douyin.com/aweme/v1/web/comment/list/reply/"

    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False  # 绕过系统代理，避免代理导致 SSL/连接失败
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Cookie": config.COOKIE,
                "Referer": "https://www.douyin.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        # 本地签名生成器
        self.abogus = ABogus(config.USER_AGENT)

    # ------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------
    @staticmethod
    def parse_aweme_id(video_url: str) -> str:
        """
        从视频链接中解析出 aweme_id
        支持：
          https://www.douyin.com/video/7312345678901234567
          https://www.douyin.com/discover?modal_id=7312345678901234567
          https://v.douyin.com/xxxxxxx/  (短链，会自动跟随重定向)
        """
        # 先尝试直接正则匹配纯数字 ID（一般 19 位）
        m = re.search(r"/(\d{15,})(?:/?$|\?)", video_url)
        if m:
            return m.group(1)

        m = re.search(r"modal_id=(\d+)", video_url)
        if m:
            return m.group(1)

        # 短链：发一次请求跟随重定向，从最终 URL 提取
        if "v.douyin.com" in video_url or "iesdouyin.com" in video_url:
            log.info("检测到短链，正在解析重定向...")
            try:
                resp = requests.get(
                    video_url,
                    headers={"User-Agent": config.USER_AGENT},
                    allow_redirects=True,
                    timeout=10,
                )
                final_url = resp.url
                log.info("重定向至: %s", final_url)
                m = re.search(r"/(\d{15,})", final_url)
                if m:
                    return m.group(1)
            except Exception as e:
                log.error("短链解析失败: %s", e)

        raise ValueError(f"无法从链接解析视频ID: {video_url}")

    @staticmethod
    def _ts_ms() -> int:
        """当前毫秒时间戳"""
        return int(time.time() * 1000)

    @staticmethod
    def _ms_token() -> str:
        """从 Cookie 中提取 msToken"""
        m = re.search(r"msToken=([^;]+)", config.COOKIE)
        return m.group(1) if m else ""

    def _sign(self, params: dict) -> dict:
        """
        用本地 abogus.py 给请求参数生成 a_bogus 签名
        返回补充了 a_bogus 之后的完整参数字典

        :param params: 业务参数字典（不含 a_bogus）
        """
        a_bogus = self.abogus.generate_a_bogus(params)
        params["a_bogus"] = a_bogus
        return params

    def _request(self, url: str, base_params: dict) -> dict:
        """
        带签名的 GET 请求，返回 JSON
        :param url: 接口地址
        :param base_params: 不含签名的业务参数
        """
        # 补充公共参数
        params = dict(base_params)
        params.setdefault("device_platform", "webapp")
        params.setdefault("aid", "6383")
        params.setdefault("channel", "channel_pc_web")
        params.setdefault("version_code", "170400")
        params.setdefault("version_name", "17.4.0")
        params.setdefault("pc_client_type", "1")
        params.setdefault("cookie_enabled", "true")
        params.setdefault("screen_width", "1920")
        params.setdefault("screen_height", "1080")
        params.setdefault("browser_language", "zh-CN")
        params.setdefault("browser_platform", "Win32")
        params.setdefault("browser_name", "Chrome")
        params.setdefault("browser_version", "120.0.0.0")
        params.setdefault("web_route", "detail")

        ms_token = self._ms_token()
        if ms_token:
            params["msToken"] = ms_token

        # 签名
        params = self._sign(params)

        # 请求（带重试）
        for attempt in range(1, config.MAX_RETRY + 1):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                # 抖音风控返回 {"status_code": 0} 但无 comments，或直接报错
                if data.get("status_code") not in (0, None):
                    log.warning("接口返回异常 status_code=%s", data.get("status_code"))
                return data
            except Exception as e:
                log.warning("请求失败(%d/%d): %s", attempt, config.MAX_RETRY, e)
                if attempt < config.MAX_RETRY:
                    time.sleep(2 * attempt + random.random())
                else:
                    raise
        return {}

    # ------------------------------------------------------------
    # 评论解析
    # ------------------------------------------------------------
    @staticmethod
    def _parse_comment(raw: dict, aweme_id: str, parent_cid: str = "",
                       reply_to_cid: str = "") -> dict:
        """把接口返回的单条评论 JSON 转成数据库字典"""
        user = raw.get("user", {}) or {}
        return {
            "cid": str(raw.get("cid", "")),
            "aweme_id": aweme_id,
            "text": raw.get("text", "").replace("\x00", ""),
            "create_time": raw.get("create_time", 0),
            "digg_count": raw.get("digg_count", 0),
            # 注意：新接口真实回复数在 reply_comment_total，reply_count 始终为0
            "reply_count": raw.get("reply_comment_total")
                           or raw.get("reply_count", 0),
            "user_id": str(user.get("uid", "")),
            "user_nickname": user.get("nickname", ""),
            "user_sec_uid": user.get("sec_uid", ""),
            "ip_label": raw.get("ip_label", ""),
            "parent_cid": parent_cid,
            "reply_to_cid": reply_to_cid,
        }

    # ------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------
    def fetch_comments(self, aweme_id: str):
        """爬取一级评论"""
        log.info("=" * 60)
        log.info("开始爬取视频 %s 的一级评论", aweme_id)
        log.info("=" * 60)

        cursor = 0
        total = 0
        empty_page_count = 0
        buffer = []          # 内存缓冲区，攒够 BATCH_INSERT_SIZE 再批量写入
        batch_size = config.BATCH_INSERT_SIZE

        def flush():
            """把缓冲区里的评论写入数据库"""
            if not buffer:
                return
            db.save_comments(buffer)
            log.info("  💾 写入数据库 %d 条（缓冲区已清空）", len(buffer))
            buffer.clear()

        while True:
            # 达到上限（按数据库实际存量判断，断点续爬时也精确）
            if config.MAX_COMMENTS:
                db_total = db.get_comment_count(aweme_id)
                if db_total >= config.MAX_COMMENTS:
                    log.info("数据库已有 %d 条，达到上限 %d，停止",
                             db_total, config.MAX_COMMENTS)
                    break

            params = {
                "aweme_id": aweme_id,
                "cursor": cursor,
                "count": config.COMMENT_COUNT_PER_PAGE,
                "item_type": "0",
                "insert_ids": "",
                "whale_cut_token": "",
                "cut_version": "1",
                "rcFT": "",
            }

            try:
                data = self._request(self.COMMENT_API, params)
            except Exception as e:
                log.error("一级评论请求失败: %s", e)
                break

            comments = data.get("comments") or []
            if not comments:
                empty_page_count += 1
                if empty_page_count >= 2:
                    log.info("连续空页，认为已到末尾")
                    break
                # 有时返回空但有 has_more，再试一次
                if not data.get("has_more"):
                    log.info("无更多评论")
                    break
                cursor = data.get("cursor", cursor + config.COMMENT_COUNT_PER_PAGE)
                time.sleep(config.SLEEP_TIME)
                continue

            empty_page_count = 0

            # 转换，放入缓冲区
            parsed = [
                self._parse_comment(c, aweme_id) for c in comments
            ]
            buffer.extend(parsed)
            total += len(parsed)
            log.info("第 %d 页: 获取 %d 条，累计 %d 条（待写入 %d 条）",
                     cursor // config.COMMENT_COUNT_PER_PAGE + 1,
                     len(parsed), total, len(buffer))

            # 攒够一批就写入
            if len(buffer) >= batch_size:
                flush()

            # 爬取二级评论
            if config.FETCH_REPLY:
                for c in parsed:
                    if c["reply_count"] and c["reply_count"] > 0:
                        try:
                            self.fetch_replies(aweme_id, c["cid"])
                        except Exception as e:
                            log.warning("爬取二级评论失败 cid=%s: %s", c["cid"], e)

            # 翻页
            if not data.get("has_more"):
                log.info("无更多评论，结束")
                break

            cursor = data.get("cursor", cursor + config.COMMENT_COUNT_PER_PAGE)
            time.sleep(config.SLEEP_TIME + random.random())

        # 循环结束，把缓冲区里剩余的写入数据库
        flush()
        log.info("一级评论爬取完成，共 %d 条", total)
        return total

    def fetch_replies(self, aweme_id: str, comment_id: str):
        """爬取某条一级评论下的二级回复"""
        cursor = 0
        count = 0

        while True:
            if count >= config.MAX_REPLY_PER_COMMENT:
                break

            params = {
                "item_id": aweme_id,
                "comment_id": comment_id,
                "cursor": cursor,
                "count": config.COMMENT_COUNT_PER_PAGE,
                "item_type": "0",
                "insert_ids": "",
                "whale_cut_token": "",
                "cut_version": "1",
                "rcFT": "",
            }

            data = self._request(self.REPLY_API, params)
            comments = data.get("comments") or []
            if not comments:
                break

            parsed = []
            for c in comments:
                # 二级评论的 reply_to_cid 通常在 reply_id 字段
                reply_to = str(c.get("reply_id", ""))
                parsed.append(
                    self._parse_comment(c, aweme_id,
                                        parent_cid=comment_id,
                                        reply_to_cid=reply_to)
                )
            db.save_comments(parsed)
            count += len(parsed)

            if not data.get("has_more"):
                break

            cursor = data.get("cursor", cursor + config.COMMENT_COUNT_PER_PAGE)
            time.sleep(config.SLEEP_TIME + random.random())

        if count:
            log.info("  └ 二级评论 cid=%s: %d 条", comment_id, count)
        return count

    def run(self, video_url: str = None):
        """主入口"""
        url = video_url or config.VIDEO_URL
        log.info("目标视频: %s", url)

        # 校验 Cookie
        if not config.COOKIE or "粘贴" in config.COOKIE:
            log.error("请先在 config.py 中填写 Cookie！")
            return

        # 解析视频ID
        aweme_id = self.parse_aweme_id(url)
        log.info("解析到 aweme_id = %s", aweme_id)

        # 初始化数据库
        db.init_db()

        # 爬取
        try:
            self.fetch_comments(aweme_id)
        except KeyboardInterrupt:
            log.info("用户中断，已保存的数据保留在数据库中")
        finally:
            n = db.get_comment_count(aweme_id)
            log.info("=" * 60)
            log.info("完成！视频 %s 共保存 %d 条评论到 %s", aweme_id, n, config.DB_PATH)
            log.info("=" * 60)


if __name__ == "__main__":
    crawler = DouyinCommentCrawler()
    crawler.run()
