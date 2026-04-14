-- 测试数据 SQL
-- 说明：
-- 1. 执行前请确认数据库为 oa_notifications
-- 2. 测试用户默认使用 3307180168@qq.com

-- 1. 查询测试用户
SELECT
  id,
  email,
  notification_refresh_interval_minutes,
  last_notification_check_at
FROM users
WHERE email = '3307180168@qq.com';


-- 2. 查询当前订阅部门
SELECT
  s.id,
  s.target_value,
  s.status
FROM subscriptions s
INNER JOIN users u
  ON u.id = s.user_id
WHERE u.email = '3307180168@qq.com'
ORDER BY s.id ASC;


-- 3. 将用户检查时间调早，便于测试“已到通知周期”
UPDATE users
SET last_notification_check_at = DATE_SUB(NOW(), INTERVAL 70 MINUTE)
WHERE email = '3307180168@qq.com';


-- 4. 查询最近测试通知
SELECT
  id,
  news_id,
  title,
  publish_department,
  first_seen_time,
  crawl_time
FROM notifications
WHERE news_id LIKE 'TEST_%'
ORDER BY id DESC;


-- 5. 查询最近测试通知的投递记录
SELECT
  d.id,
  d.news_id,
  d.channel,
  d.recipient,
  d.status,
  d.error_msg,
  d.sent_at,
  d.created_at
FROM notification_delivery_log d
WHERE d.news_id LIKE 'TEST_%'
ORDER BY d.id DESC;


-- 6. 删除测试通知对应投递记录
DELETE FROM notification_delivery_log
WHERE news_id LIKE 'TEST_%';


-- 7. 删除测试通知
DELETE FROM notifications
WHERE news_id LIKE 'TEST_%';


-- 8. 再次确认清理结果
SELECT
  id,
  news_id,
  title
FROM notifications
WHERE news_id LIKE 'TEST_%';
