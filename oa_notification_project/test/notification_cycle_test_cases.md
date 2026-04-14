# 通知刷新周期测试用例

更新时间：2026-04-08

## 1. 测试目标

验证以下业务规则是否成立：

- OA 爬虫仍为全局统一抓取
- 用户刷新周期只影响“多久检查一次该用户是否有新通知”
- 已到周期且有新通知时，系统为用户生成投递记录并发送提醒
- 已到周期但没有新通知时，系统不发送提醒
- 未到周期时，系统不重复检查、不重复提醒
- 未订阅部门的新通知不会投递给该用户

## 2. 测试前提

测试用户：

- 邮箱：`3307180168@qq.com`

已确认当前订阅规则：

- `enable_email = 1` 为默认开启
- `enable_wechat = 1` 表示已授权
- `enable_wechat = 0` 表示未授权或拒绝

建议先确认：

- `users.notification_refresh_interval_minutes`
- `users.last_notification_check_at`
- `subscriptions`
- `notification_delivery_log`

## 3. 场景清单

### 场景 A

名称：已到通知周期，但没有新的通知，用户不收到提醒

前置条件：

- 用户已订阅若干部门
- 这些订阅部门下没有晚于 `last_notification_check_at` 的通知
- 将 `last_notification_check_at` 手动调整为早于当前时间 60 分钟以上

执行步骤：

1. 运行投递任务
2. 观察终端输出
3. 查询 `notification_delivery_log`

预期结果：

- `checked_users > 0`
- `matched_notifications = 0`
- `created_email_delivery_records = 0`
- `created_miniapp_delivery_records = 0`
- 用户不收到提醒

当前状态：

- 已通过

### 场景 B

名称：已到通知周期，且有新的通知，用户收到提醒

前置条件：

- 用户已订阅部门存在新通知
- 新通知的 `publish_department` 命中该用户订阅关系
- 新通知的 `first_seen_time / crawl_time / publish_time` 晚于 `last_notification_check_at`
- 将 `last_notification_check_at` 手动调整为早于当前时间 60 分钟以上

执行步骤：

1. 在已订阅部门下插入一条新通知
2. 运行投递任务
3. 查询 `notification_delivery_log`
4. 核对邮件或小程序提醒结果

预期结果：

- `checked_users > 0`
- `matched_notifications > 0`
- 至少产生 1 条 `email` 或 `miniapp` 投递记录
- 邮件通道可成功发送时，`successful_deliveries > 0`

当前状态：

- 已通过

本轮联调样例：

- 命中通知：`TEST_SUB2_c67ed0e50b`
- 发布单位：`科学研究管理部`
- 结果：
  - `email` 投递记录 1 条，状态 `success`
  - `miniapp` 投递记录 1 条，状态 `pending`

主流程自动发送补充验证：

- 命中通知：`TEST_AUTO_MP_135f4eb9`
- 发布单位：`科学研究管理部`
- 结果：
  - `email` 投递记录 1 条，状态 `success`
  - `miniapp` 投递记录 1 条，状态 `success`
  - `miniapp.provider_message_id` 已写入

结论：

- 当前 `oa_delivery_main.py` 已不只是生成 `miniapp` 投递记录
- 主投递流程会自动调用微信订阅消息发送接口
- `miniapp` 记录会根据实际发送结果更新为：
  - `success`
  - 或 `failed`
- `pending` 仅表示“已入投递队列但尚未执行发送”

### 场景 C

名称：未到通知周期，且没有新的通知，用户不收到提醒

前置条件：

- 刚完成一次投递检查
- 用户的 `last_notification_check_at` 已被更新为当前时间附近

执行步骤：

1. 立即再次运行投递任务
2. 观察终端输出
3. 查询 `notification_delivery_log`

预期结果：

- `checked_users = 0`
- `matched_notifications = 0`
- 不生成新的投递记录
- 用户不收到提醒

当前状态：

- 已通过

### 场景 D

名称：已到通知周期，但新通知属于未订阅部门，用户不收到提醒

前置条件：

- 插入一条新通知
- 该通知的 `publish_department` 不在当前用户订阅列表中

执行步骤：

1. 将 `last_notification_check_at` 调早
2. 插入未订阅部门通知
3. 运行投递任务
4. 查询 `notification_delivery_log`

预期结果：

- 该通知不会产生该用户的投递记录
- 用户不收到提醒

当前状态：

- 已通过

本轮联调样例：

- 未命中通知：`TEST_UNSUB_06ad81e7f8`
- 发布单位：`UNSUB_DEPT_TEST`
- 结果：
  - 未生成任何投递记录

## 4. 推荐核对 SQL

查看用户状态：

```sql
SELECT
  id,
  email,
  notification_refresh_interval_minutes,
  last_notification_check_at
FROM users
WHERE email = '3307180168@qq.com';
```

查看用户订阅：

```sql
SELECT
  s.id,
  s.target_value,
  s.status
FROM subscriptions s
INNER JOIN users u
  ON u.id = s.user_id
WHERE u.email = '3307180168@qq.com'
ORDER BY s.id ASC;
```

查看投递记录：

```sql
SELECT
  id,
  news_id,
  channel,
  recipient,
  status,
  error_msg,
  sent_at,
  created_at
FROM notification_delivery_log
ORDER BY id DESC
LIMIT 20;
```

## 2026-04-10 补测结论

### 场景 1：关闭邮箱提醒后，不生成 `email` 投递记录

测试方式：

- 将测试用户 `3307180168@qq.com` 设置为：
  - `users.email_notifications_enabled = 0`
  - `users.miniapp_notifications_enabled = 1`
- 使用该用户真实已订阅部门人工插入一条新通知
- 将该用户调整为“已到刷新周期”
- 执行一次按用户周期检查的投递入队逻辑

测试结果：

- `checked_users = 1`
- `matched_notifications = 1`
- `email_records_created = 0`
- `miniapp_records_created = 1`
- 该测试通知对应投递记录仅生成：
  - `miniapp / pending`

结论：

- 关闭邮箱提醒后，系统不会生成 `email` 投递记录。

### 场景 2：关闭小程序提醒后，不生成 `miniapp` 投递记录

测试方式：

- 将测试用户 `3307180168@qq.com` 设置为：
  - `users.email_notifications_enabled = 1`
  - `users.miniapp_notifications_enabled = 0`
- 使用该用户真实已订阅部门人工插入一条新通知
- 将该用户调整为“已到刷新周期”
- 执行一次按用户周期检查的投递入队逻辑

测试结果：

- `checked_users = 1`
- `matched_notifications = 1`
- `email_records_created = 1`
- `miniapp_records_created = 0`
- 该测试通知对应投递记录仅生成：
  - `email / pending`

结论：

- 关闭小程序提醒后，系统不会生成 `miniapp` 投递记录。

### 场景 3：未订阅部门有新消息时，不生成任何投递记录

测试方式：

- 将测试用户 `3307180168@qq.com` 设置为：
  - `users.email_notifications_enabled = 1`
  - `users.miniapp_notifications_enabled = 1`
- 选择一个该用户未订阅的发布单位，人工插入一条新通知
- 将该用户调整为“已到刷新周期”
- 执行一次按用户周期检查的投递入队逻辑

测试结果：

- `checked_users = 1`
- `matched_notifications = 0`
- `email_records_created = 0`
- `miniapp_records_created = 0`
- 该测试通知对应投递记录：
  - 无

结论：

- 未订阅部门即使存在新消息，也不会为该用户生成任何投递记录。
