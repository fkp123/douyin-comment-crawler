# 抖音评论 SQLite 分析查询合集
# 使用方法：
#   1. 用 DB Browser for SQLite 打开 comments.db
#   2. 切到"执行 SQL"标签页
#   3. 把下面任意一段 SQL 粘进去，点▶运行（快捷键 F5 或 Ctrl+Enter）
#   4. 多条 SQL 之间已用 ; 分隔，可一起粘贴运行，结果会分多个面板显示
#
# 表结构回顾：
#   comments(cid, aweme_id, text, create_time, digg_count, reply_count,
#            user_id, user_nickname, user_sec_uid, ip_label,
#            parent_cid, reply_to_cid, crawl_time)
#   - cid: 评论ID(主键)
#   - parent_cid: 父评论ID，为空=一级评论，非空=二级回复
#   - create_time: 评论时间戳(秒)，需用 datetime() 转换


-- ============================================================
-- 一、基础统计
-- ============================================================

-- 1. 总评论数、一级评论数、二级评论数
SELECT
    COUNT(*)                                          AS 总评论数,
    SUM(CASE WHEN parent_cid = '' THEN 1 ELSE 0 END)  AS 一级评论数,
    SUM(CASE WHEN parent_cid != '' THEN 1 ELSE 0 END) AS 二级评论数
FROM comments;

-- 2. 按视频分组统计（爬了多个视频时有用）
SELECT
    aweme_id       AS 视频ID,
    COUNT(*)       AS 评论数,
    SUM(digg_count) AS 总点赞数,
    ROUND(AVG(digg_count), 1) AS 平均点赞
FROM comments
GROUP BY aweme_id
ORDER BY 评论数 DESC;

-- 3. 点赞数统计（最大/最小/平均/总和）
SELECT
    MAX(digg_count)  AS 最高点赞,
    MIN(digg_count)  AS 最低点赞,
    ROUND(AVG(digg_count), 2) AS 平均点赞,
    SUM(digg_count)  AS 总点赞
FROM comments;


-- ============================================================
-- 二、热门评论
-- ============================================================

-- 4. 点赞最多的 20 条评论
SELECT
    user_nickname        AS 昵称,
    ip_label             AS IP属地,
    digg_count           AS 点赞数,
    text                 AS 评论内容,
    datetime(create_time, 'unixepoch', 'localtime') AS 评论时间
FROM comments
WHERE parent_cid = ''
ORDER BY digg_count DESC
LIMIT 20;

-- 5. 回复数最多的 20 条评论（争议度/讨论度）
SELECT
    user_nickname AS 昵称,
    reply_count   AS 回复数,
    digg_count    AS 点赞数,
    text          AS 评论内容
FROM comments
WHERE parent_cid = ''
ORDER BY reply_count DESC
LIMIT 20;

-- 6. 既有高赞又有高回复的评论（最热门讨论）
SELECT
    user_nickname AS 昵称,
    digg_count    AS 点赞数,
    reply_count   AS 回复数,
    (digg_count + reply_count * 3) AS 热度,
    text          AS 评论内容
FROM comments
WHERE parent_cid = ''
ORDER BY 热度 DESC
LIMIT 20;


-- ============================================================
-- 三、地域分析
-- ============================================================

-- 7. 各省份评论数 TOP10
SELECT
    ip_label    AS 省份,
    COUNT(*)    AS 评论数,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM comments WHERE ip_label != ''), 2) AS 占比百分比
FROM comments
WHERE ip_label != ''
GROUP BY ip_label
ORDER BY 评论数 DESC
LIMIT 10;

-- 8. 各省份平均点赞数（哪的人评论更受欢迎）
SELECT
    ip_label             AS 省份,
    COUNT(*)             AS 评论数,
    ROUND(AVG(digg_count), 1) AS 平均点赞,
    MAX(digg_count)      AS 最高点赞
FROM comments
WHERE ip_label != '' AND parent_cid = ''
GROUP BY ip_label
HAVING 评论数 > 10
ORDER BY 平均点赞 DESC
LIMIT 15;


-- ============================================================
-- 四、时间分析
-- ============================================================

-- 9. 按天统计评论数（评论时间趋势）
SELECT
    date(create_time, 'unixepoch', 'localtime') AS 日期,
    COUNT(*)  AS 评论数,
    SUM(digg_count) AS 当日总点赞
FROM comments
WHERE create_time > 0
GROUP BY 日期
ORDER BY 日期;

-- 10. 按小时统计评论数（哪个时段评论最活跃）
SELECT
    strftime('%H', create_time, 'unixepoch', 'localtime') AS 小时,
    COUNT(*) AS 评论数
FROM comments
WHERE create_time > 0
GROUP BY 小时
ORDER BY 小时;

-- 11. 最新 20 条评论
SELECT
    user_nickname AS 昵称,
    ip_label      AS IP属地,
    digg_count    AS 点赞数,
    datetime(create_time, 'unixepoch', 'localtime') AS 评论时间,
    text          AS 评论内容
FROM comments
WHERE parent_cid = ''
ORDER BY create_time DESC
LIMIT 20;


-- ============================================================
-- 五、用户分析
-- ============================================================

-- 12. 评论最多的用户（刷屏党）TOP20
SELECT
    user_nickname AS 昵称,
    user_id       AS 用户ID,
    COUNT(*)      AS 评论数,
    SUM(digg_count) AS 总获赞
FROM comments
WHERE user_id != ''
GROUP BY user_id
ORDER BY 评论数 DESC
LIMIT 20;

-- 13. 获赞最多的用户（人气王）TOP20
SELECT
    user_nickname AS 昵称,
    COUNT(*)      AS 评论数,
    SUM(digg_count) AS 总获赞,
    MAX(digg_count)  AS 单条最高赞
FROM comments
WHERE user_id != '' AND parent_cid = ''
GROUP BY user_id
ORDER BY 总获赞 DESC
LIMIT 20;


-- ============================================================
-- 六、内容/文本分析
-- ============================================================

-- 14. 评论长度分布
SELECT
    CASE
        WHEN length(text) <= 5   THEN '1-极短(≤5字)'
        WHEN length(text) <= 20  THEN '2-短(6-20字)'
        WHEN length(text) <= 50  THEN '3-中(21-50字)'
        WHEN length(text) <= 100 THEN '4-长(51-100字)'
        ELSE '5-超长(>100字)'
    END AS 长度区间,
    COUNT(*) AS 评论数,
    ROUND(AVG(digg_count), 1) AS 平均点赞
FROM comments
WHERE parent_cid = ''
GROUP BY 长度区间
ORDER BY 长度区间;

-- 15. 包含特定关键词的评论（把'加油'换成你要搜的词）
SELECT
    user_nickname AS 昵称,
    digg_count    AS 点赞数,
    ip_label      AS IP属地,
    datetime(create_time, 'unixepoch', 'localtime') AS 时间,
    text          AS 评论内容
FROM comments
WHERE text LIKE '%加油%'
ORDER BY digg_count DESC;

-- 16. 含 emoji/特殊符号的评论占比
SELECT
    SUM(CASE WHEN text LIKE '%[%' OR text LIKE '%【%' THEN 1 ELSE 0 END) AS 含表情符号数,
    COUNT(*) AS 总数,
    ROUND(SUM(CASE WHEN text LIKE '%[%' OR text LIKE '%【%' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 占比百分比
FROM comments;


-- ============================================================
-- 七、二级评论（回复）分析
-- ============================================================

-- 17. 二级回复数最多的父评论（哪个话题引发最多回复）
SELECT
    parent.cid           AS 父评论ID,
    parent.user_nickname AS 父评论作者,
    parent.text          AS 父评论内容,
    parent.digg_count    AS 父评论点赞,
    COUNT(child.cid)     AS 回复数
FROM comments parent
JOIN comments child ON child.parent_cid = parent.cid
GROUP BY parent.cid
ORDER BY 回复数 DESC
LIMIT 15;

-- 18. 某条评论下的所有回复（把 '替换成父评论ID' 换成实际 cid）
SELECT
    user_nickname AS 回复者,
    digg_count    AS 点赞数,
    datetime(create_time, 'unixepoch', 'localtime') AS 时间,
    text          AS 回复内容
FROM comments
WHERE parent_cid = '7688242646573892388'
ORDER BY create_time;


-- ============================================================
-- 八、数据清洗与导出辅助
-- ============================================================

-- 19. 查找重复内容（复制粘贴的评论）
SELECT
    text      AS 评论内容,
    COUNT(*)  AS 出现次数
FROM comments
WHERE text != ''
GROUP BY text
HAVING COUNT(*) > 1
ORDER BY 出现次数 DESC
LIMIT 20;

-- 20. 导出"昵称,点赞,IP,时间,内容"为CSV格式（结果可右键导出）
SELECT
    user_nickname,
    digg_count,
    ip_label,
    datetime(create_time, 'unixepoch', 'localtime') AS create_time,
    text
FROM comments
WHERE parent_cid = ''
ORDER BY digg_count DESC;
