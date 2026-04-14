# 校园通知信息聚合系统 - 数据库设计总结

## 1. 设计原则

- 结构尽量简单，字段职责明确。
- 订阅关系、用户提醒设置、通知内容与标签三者分层保存。
- 优先保证查询与后续扩展方便，而不是把多种职责压进同一张表。

---

## 2. 当前核心表

当前项目主要围绕以下几张表展开：

- `notifications`
  - 保存 OA 抓取到的通知主数据
  - 保存通知的人群筛选标签
- `attachments`
  - 保存通知附件基础信息
  - 不再保存附件下载地址
- `users`
  - 保存用户基础信息
  - 保存用户级提醒开关与刷新周期
- `subscriptions`
  - 只保存“用户是否订阅某个发布单位”的关系
- `notification_delivery_log`
  - 保存邮件和小程序投递记录
- `audience_keyword_rules`
  - 保存人群筛选关键词规则
- `audience_department_rules`
  - 保存人群筛选部门规则
- `crawl_job_log`
  - 保存抓取任务日志

---

## 3. `notifications` 表

### 3.1 表职责

`notifications` 是通知主表，用于保存：

- OA 通知原始主数据
- 正文内容
- 发布时间与发布单位
- 人群筛选结果

### 3.2 主要字段

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `id` | `INT` | 自增主键 |
| `news_id` | `VARCHAR(64)` | 通知唯一业务 ID |
| `title` | `VARCHAR(255)` | 通知标题 |
| `category` | `VARCHAR(50)` | 通知分类 |
| `fragment_id` | `VARCHAR(64)` | 栏目或来源片段 ID |
| `publish_time` | `DATETIME` | 发布时间 |
| `publish_department` | `VARCHAR(100)` | 发布单位 |
| `content_html` | `LONGTEXT` | 原始 HTML 正文 |
| `content_text` | `LONGTEXT` | 纯文本正文 |
| `detail_url` | `VARCHAR(500)` | 原始详情链接 |
| `view_count` | `INT` | 阅读次数 |
| `first_seen_time` | `DATETIME` | 首次入库时间 |
| `last_seen_time` | `DATETIME` | 最近一次抓取到该通知的时间 |
| `crawl_time` | `DATETIME` | 本轮抓取时间 |

### 3.3 人群筛选字段

当前通知人群筛选已支持三类：

- 本科生
- 研究生
- 教职工

对应字段如下。

本科生：

- `audience_undergraduate`
- `audience_undergraduate_rule_version`
- `audience_undergraduate_rule_detail`

研究生：

- `audience_graduate`
- `audience_graduate_rule_version`
- `audience_graduate_rule_detail`

教职工：

- `audience_staff`
- `audience_staff_rule_version`
- `audience_staff_rule_detail`

字段语义统一为：

- `audience_xxx`
  - `1` 表示命中该类人群
  - `0` 表示未命中
- `audience_xxx_rule_version`
  - 当前命中的规则版本
  - 目前统一为 `v1`
- `audience_xxx_rule_detail`
  - JSON 明细
  - 记录总分、是否命中、命中的关键词规则和部门规则

### 3.4 索引说明

- `news_id` 唯一索引
- `title` 普通索引
- `publish_time` 普通索引
- `publish_department` 普通索引
- `content_text` 全文索引

---

## 4. `attachments` 表

### 4.1 表职责

`attachments` 用于保存附件基础信息，仅供前端展示附件名称、格式、大小。

当前设计已明确：

- 不保存附件下载地址
- 不保存附件预览地址
- 不再尝试让小程序直接下载 OA 附件

### 4.2 主要字段

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `id` | `INT` | 自增主键 |
| `news_id` | `VARCHAR(64)` | 关联通知 |
| `file_id` | `VARCHAR(100)` | OA 附件 ID |
| `filename` | `VARCHAR(255)` | 附件名称 |
| `extension` | `VARCHAR(20)` | 附件后缀 |
| `size` | `BIGINT` | 附件大小 |
| `crawl_time` | `DATETIME` | 抓取时间 |

### 4.3 约束说明

- `(news_id, file_id)` 唯一约束
- `news_id` 外键关联 `notifications.news_id`

---

## 5. `users` 表

### 5.1 表职责

`users` 表当前承担两类职责：

- 保存用户基础信息
- 保存用户级通知提醒设置

### 5.2 主要字段

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `id` | `INT` | 自增主键 |
| `username` | `VARCHAR(100)` | 用户名 |
| `email` | `VARCHAR(255)` | 邮箱 |
| `wechat_openid` | `VARCHAR(128)` | 微信 OpenID |
| `email_notifications_enabled` | `TINYINT` | 邮件提醒开关 |
| `miniapp_notifications_enabled` | `TINYINT` | 小程序提醒开关 |
| `notification_refresh_interval_minutes` | `INT` | 提醒刷新周期 |
| `last_notification_check_at` | `DATETIME` | 上次检查通知时间 |
| `status` | `TINYINT` | 用户状态 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### 5.3 当前业务规则

- `email_notifications_enabled`
  - `1` 表示开启邮件提醒
  - `0` 表示关闭邮件提醒
- `miniapp_notifications_enabled`
  - `1` 表示开启小程序提醒
  - `0` 表示关闭小程序提醒
- `notification_refresh_interval_minutes`
  - 当前允许值：`1 / 5 / 30 / 60`
  - 默认值：`60`
- 用户修改刷新周期后：
  - 同步重置 `last_notification_check_at = 当前时间`

### 5.4 当前相关接口

- `GET /api/users/settings`
- `POST /api/users/settings`

---

## 6. `subscriptions` 表

### 6.1 表职责

`subscriptions` 表当前只表示：

“某个用户是否订阅了某个发布单位”

它不再负责保存邮件或小程序渠道开关。

### 6.2 主要字段

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `id` | `BIGINT` | 自增主键 |
| `user_id` | `INT` | 关联用户 |
| `target_type` | `VARCHAR(32)` | 当前固定为 `department` |
| `target_value` | `VARCHAR(100)` | 发布单位名称 |
| `status` | `TINYINT` | 是否有效 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### 6.3 当前业务规则

- 只有用户主动订阅某个发布单位时，才写入 `subscriptions`
- 系统不会根据通知表自动灌入全量部门订阅
- 一个用户可以订阅多个发布单位
- `status = 1` 表示有效订阅
- `status = 0` 表示取消订阅或无效

### 6.4 当前相关接口

- `GET /api/subscriptions/departments`
- `POST /api/subscriptions/department`
- `POST /api/subscriptions/batch`

### 6.5 当前明确废弃的旧口径

以下旧字段和旧说法已废弃，不应继续引用：

- `subscriptions.enable_email`
- `subscriptions.enable_wechat`
- “订阅表同时控制订阅关系和渠道开关”

---

## 7. `notification_delivery_log` 表

### 7.1 表职责

保存通知投递记录，用于追踪：

- 哪个用户
- 哪条通知
- 通过哪个渠道
- 当前发送状态如何

### 7.2 主要字段

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `id` | `BIGINT` | 自增主键 |
| `news_id` | `VARCHAR(64)` | 通知 ID |
| `user_id` | `INT` | 用户 ID |
| `subscription_id` | `BIGINT` | 命中的订阅关系 |
| `job_id` | `BIGINT` | 关联抓取任务 |
| `channel` | `VARCHAR(32)` | `email` / `miniapp` |
| `recipient` | `VARCHAR(255)` | 接收人 |
| `status` | `VARCHAR(32)` | `pending` / `success` / `failed` |
| `retry_count` | `INT` | 重试次数 |
| `error_msg` | `TEXT` | 失败原因 |
| `provider_message_id` | `VARCHAR(128)` | 外部服务消息 ID |
| `sent_at` | `DATETIME` | 发送成功时间 |
| `last_attempt_at` | `DATETIME` | 最近尝试发送时间 |

### 7.3 当前状态说明

- `pending`
  - 已生成投递记录，但尚未真正发出
- `success`
  - 已发送成功
- `failed`
  - 已执行发送，但发送失败

---

## 8. 人群规则表

### 8.1 `audience_keyword_rules`

用于保存关键词规则，字段包括：

- `audience_type`
- `rule_scope`
- `keyword`
- `weight`
- `status`
- `rule_version`

当前 `rule_scope` 主要包括：

- `title`
- `category`
- `content_text`

### 8.2 `audience_department_rules`

用于保存部门映射规则，字段包括：

- `audience_type`
- `department_name`
- `weight`
- `status`
- `rule_version`

### 8.3 当前判定方式

当前采用“多信号打分 + 阈值命中”的规则机制：

- 标题命中关键词加分
- 分类命中关键词加分
- 正文命中关键词加分
- 发布单位命中部门规则加分
- 达到阈值后写入通知表的人群标签字段

当前这套规则是可解释的，因为命中明细会保存在：

- `audience_undergraduate_rule_detail`
- `audience_graduate_rule_detail`
- `audience_staff_rule_detail`

---

## 9. 当前通知投递的数据库判断逻辑

当前是否给某用户发送某通知，依赖以下几类数据共同决定：

1. `users`
   - 是否开启邮件提醒
   - 是否开启小程序提醒
   - 是否到达刷新周期
2. `subscriptions`
   - 是否订阅了该发布单位
3. `notifications`
   - 该发布单位是否有新通知

当前统一逻辑为：

- 是否生成 `email` 投递记录，只看 `users.email_notifications_enabled`
- 是否生成 `miniapp` 投递记录，只看 `users.miniapp_notifications_enabled`
- 是否命中订阅关系，只看 `subscriptions`
- 是否属于新通知，结合：
  - `notifications.first_seen_time`
  - `notifications.crawl_time`
  - `notifications.publish_time`
  - `users.last_notification_check_at`

---

## 10. 当前设计结论

后续所有接口说明、文档说明、测试说明，均应统一按以下口径理解：

- 通知内容与人群标签在 `notifications`
- 附件展示信息在 `attachments`
- 用户提醒开关与刷新周期在 `users`
- 用户订阅发布单位关系在 `subscriptions`
- 投递过程记录在 `notification_delivery_log`

不再继续使用以下旧口径：

- `subscriptions.enable_email`
- `subscriptions.enable_wechat`
- “订阅表既保存关系又保存渠道开关”

---

## 11. 管理员爬虫配置与接口说明

### 11.1 `crawler_runtime_config` 表

该表用于保存“当前生效的全局爬虫运行参数”。

设计特点：

- 不是历史版本表，而是当前配置表。
- 每个 `config_key` 只有一条记录。
- 管理员保存配置时，直接覆盖该 `config_key` 当前值。

主要字段：

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `config_key` | `VARCHAR(64)` | 配置项名称，主键 |
| `config_value` | `VARCHAR(255)` | 当前配置值 |
| `config_type` | `VARCHAR(32)` | 值类型，如 `bool` / `int` / `float` |
| `description` | `VARCHAR(255)` | 配置说明 |
| `updated_at` | `DATETIME` | 最后更新时间 |

### 11.2 当前可配置字段

`SCHEDULER_ENABLED`

- 含义：是否开启全局自动调度。
- 使用场景：管理员决定系统是否按周期自动抓取 OA。
- 典型值：
  - `true`：开启自动调度
  - `false`：关闭自动调度，仅支持手动抓取

`SCHEDULER_INTERVAL_MINUTES`

- 含义：自动调度执行间隔，单位分钟。
- 使用场景：控制全局爬虫“多久抓一次”。
- 典型值：
  - `0.5`
  - `1`
  - `5`
  - `30`

`SCHEDULER_MAX_RUNS`

- 含义：当前调度进程最多执行多少轮。
- 使用场景：开发联调时限制调度循环次数，防止无限运行。
- 典型规则：
  - `> 0`：执行到指定次数后停止
  - `<= 0`：视为不限次数

`MAX_RECORDS`

- 含义：单次抓取最多保留多少条通知。
- 使用场景：限制单次抓取规模，避免一次抓取过多数据。

`REQUEST_DELAY_MIN`

- 含义：单次请求之间的最小等待时间，单位秒。
- 使用场景：降低请求频率，避免对 OA 站点造成过高压力。

`REQUEST_DELAY_MAX`

- 含义：单次请求之间的最大等待时间，单位秒。
- 使用场景：与 `REQUEST_DELAY_MIN` 共同组成随机请求延迟区间。

### 11.3 为什么 `GET /api/admin/crawler/config` 返回的是“最新配置”

当前不是通过某个“是否最新”的状态字段来判断，而是通过表结构保证：

- `crawler_runtime_config` 以 `config_key` 为主键
- 每个配置项始终只有一条记录
- 这条记录里的 `config_value` 就是当前最新值

如果要看最后一次修改时间，可以看 `updated_at`。

### 11.4 管理员爬虫接口

`GET /api/admin/crawler/config`

- 使用场景：管理员进入爬虫管理页时，读取当前全局配置。
- 返回内容：当前各配置项的最新值。
- 作用：前端展示当前运行参数。

`POST /api/admin/crawler/config`

- 使用场景：管理员修改配置后点击保存。
- 作用：更新 `crawler_runtime_config` 中对应配置值。
- 当前校验逻辑包括：
  - `schedulerIntervalMinutes > 0`
  - `maxRecords > 0`
  - `requestDelayMin >= 0`
  - `requestDelayMax >= 0`
  - `requestDelayMin <= requestDelayMax`

`POST /api/admin/crawler/run`

- 使用场景：管理员手动发起一次抓取，不等待调度。
- 作用：后台线程触发一次 `run_once()`。
- 当前不是完整任务编排中心，只是最小版手动执行入口。
- 该接口只负责抓取任务，不负责触发通知投递。

`GET /api/admin/crawler/jobs`

- 使用场景：管理员查看最近任务执行情况。
- 作用：读取 `crawl_job_log` 最近记录，供前端列表展示。

`GET /api/admin/crawler/job-detail`

- 使用场景：管理员查看某一条任务的完整详情。
- 作用：按 `jobId` 读取单条 `crawl_job_log`。

### 11.5 配置保存后的生效逻辑

管理员保存配置后，并不是直接修改 `config.py` 文件，而是走下面这条链路：

1. 前端调用 `POST /api/admin/crawler/config`
2. 后端把配置写入 `crawler_runtime_config`
3. 后端调用 `apply_crawler_runtime_config()`
4. `apply_crawler_runtime_config()` 从数据库读取当前配置
5. 再把这些值同步到当前 Python 进程内存中的 `config` 模块变量，例如：
   - `config.SCHEDULER_ENABLED`
   - `config.SCHEDULER_INTERVAL_MINUTES`
   - `config.MAX_RECORDS`
   - `config.REQUEST_DELAY_MIN`
   - `config.REQUEST_DELAY_MAX`

这样做的含义是：

- 数据库存的是“配置源”
- `config` 模块存的是“当前进程真正正在使用的运行参数”
- `apply_crawler_runtime_config()` 就是把数据库最新值加载进当前进程

### 11.6 如何区分管理员手动执行和自动调度

不建议用运行态内存文案 `lastMessage` 作为正式判断依据。

当前推荐使用 `crawl_job_log` 中的这两个字段判断：

`job_type`

- `manual`
- `scheduled`
- `scheduler_boot`
- `delivery_only`

`trigger_mode`

- `single`
- `scheduler`
- `after_crawl`

判断方式：

- 管理员手动点击“立即抓取”
  - `job_type = manual`
  - `trigger_mode = single`
- 自动调度触发的抓取
  - `job_type = scheduled`
  - `trigger_mode = scheduler`
- 抓取结束后串行触发的统一投递
  - `job_type = delivery_only`
  - `trigger_mode = after_crawl`

### 11.7 当前抓取任务与通知任务的职责边界

当前系统已明确拆分为两套独立逻辑：

抓取任务：

- 只负责抓取 OA 通知
- 只负责通知、附件入库
- 只负责记录抓取日志
- 不负责判断是否给用户发送通知

通知任务：

- 独立于抓取任务运行
- 根据 `users.notification_refresh_interval_minutes` 判断哪些用户到期
- 根据 `subscriptions` 和 `notifications` 判断用户应收到哪些通知
- 再分别执行邮件和小程序发送

因此：

- `oa_crawler_main.py` 只做抓取
- `oa_delivery_main.py` 只做通知检查与发送
- 管理员点击 `POST /api/admin/crawler/run` 时，只会新增抓取任务记录，不会自动追加投递任务记录
