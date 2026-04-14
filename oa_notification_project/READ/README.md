# OA 通知项目说明

更新时间：2026-04-06

## 1. 项目概述

本项目面向广东工业大学 OA 通知系统，目标是实现“校园通知信息汇聚系统”的后端抓取、数据库入库、提醒分发和小程序展示能力。

当前已经形成的主链路为：

`OA 抓取 -> MySQL 入库 -> 任务日志 -> 邮件提醒 -> 后端 API -> 小程序展示`

当前项目目录中最主要的入口如下：

- `oa_notification_project/oa_crawler_main.py`
  - 单轮抓取或定时抓取主入口
- `oa_notification_project/oa_api_main.py`
  - 后端接口服务入口
- `oa_notification_project/oa_delivery_main.py`
  - 提醒与投递链路入口

---

## 2. 当前已实现功能

### 2.1 抓取能力

已实现：

- OA 首页会话初始化
- 三个栏目抓取
- 列表页分页抓取
- 详情页解析
- 正文 HTML 与纯文本提取
- 附件元数据提取
- 抓取频率延时控制
- 中断后保存

当前抓取的核心字段包括：

- `news_id`
- `title`
- `publish_time`
- `publish_department`
- `category`
- `content_html`
- `content_text`
- `detail_url`
- `view_count`

附件当前只保留元数据：

- `file_id`
- `filename`
- `extension`
- `size`

说明：

- 当前不保存附件下载地址
- 当前不在小程序中直接下载附件

### 2.2 数据库存储

已实现：

- 自动初始化数据库和表结构
- 通知去重入库
- 附件去重入库
- 抓取任务日志记录
- 订阅与投递相关表结构

当前使用的核心表：

- `notifications`
- `attachments`
- `crawl_job_log`
- `users`
- `subscriptions`
- `notification_delivery_log`

### 2.3 调度与日志

已实现：

- 单轮抓取
- 定时抓取
- 限定轮数测试
- 抓取任务日志记录

`crawl_job_log` 当前可记录：

- 开始时间
- 结束时间
- 状态
- 抓取条数
- 入库条数
- 错误信息

### 2.4 邮件提醒

已实现：

- SMTP 配置接入
- 基于新增通知发送邮件
- 基于订阅结构的投递模型
- 邮件发送成功/失败回写

### 2.5 后端 API

已实现：

- `GET /health`
- `GET /api/notifications`
- `GET /api/notification-detail`

### 2.6 小程序

已实现：

- 首页展示真实通知列表
- 点击通知进入详情页
- 详情页展示标题、部门、时间、分类
- 详情页展示正文内容
- 详情页展示正文图片
- 详情页展示附件名称
- 分享、收藏、复制原文链接

附件交互当前为：

- 点击附件名称时复制当前通知原文链接
- 提示用户到 OA 原页面下载附件

通知已读状态当前设计为：

- 只在小程序本地存储已读状态
- 不写入后端数据库
- 不支持跨设备同步
- 不和用户体系、提醒体系联动
- 仅用于当前设备上的阅读状态展示

---

## 3. 当前数据库模型说明

### 3.1 `notifications`

用于保存通知主体数据，主要字段包括：

- `news_id`
- `title`
- `publish_time`
- `publish_department`
- `content_html`
- `content_text`
- `detail_url`
- `first_seen_time`
- `last_seen_time`
- `crawl_time`

### 3.2 `attachments`

用于保存附件元数据，不保存附件文件本体，也不保存附件下载地址。

当前字段包括：

- `news_id`
- `file_id`
- `filename`
- `extension`
- `size`
- `crawl_time`

### 3.3 `crawl_job_log`

用于保存抓取与调度执行记录。

### 3.4 `users`

用于保存订阅用户基础信息。

### 3.5 `subscriptions`

用于保存用户订阅规则。

### 3.6 `notification_delivery_log`

用于保存“每个用户、每个渠道、每条通知”的投递流水。

---

## 4. 如何运行

### 4.1 运行抓取

```powershell
python .\oa_notification_project\oa_crawler_main.py
```

作用：

- 抓取 OA 通知
- 入库 MySQL
- 记录任务日志

### 4.2 启动 API

```powershell
python -B .\oa_notification_project\oa_api_main.py
```

作用：

- 提供通知列表接口
- 提供通知详情接口
- 为小程序提供数据

### 4.3 运行提醒链路

```powershell
python .\oa_notification_project\oa_delivery_main.py
```

作用：

- 选择待投递通知
- 匹配订阅用户
- 生成投递记录
- 发送邮件

---

## 5. 如何检查运行结果

### 5.1 控制台日志

重点关注：

- `Program started`
- `MySQL connection test passed`
- `Fetch notifications finished`
- `Notifications saved`
- `Attachments saved`
- `Notification API server started`

### 5.2 数据库表

重点查看：

- `notifications`
- `attachments`
- `crawl_job_log`
- `notification_delivery_log`

示例 SQL：

```sql
SELECT id, job_type, status, started_at, finished_at, message
FROM crawl_job_log
ORDER BY id DESC
LIMIT 20;
```

```sql
SELECT news_id, title, publish_department, publish_time
FROM notifications
ORDER BY id DESC
LIMIT 20;
```

```sql
SELECT news_id, file_id, filename, extension, size
FROM attachments
ORDER BY id DESC
LIMIT 20;
```

---

## 6. 当前待实现功能

当前尚未完成的内容包括：

- 更完善的增量抓取策略验证
- 邮件失败自动重试
- 小程序提醒渠道
- 用户/订阅管理接口
- 搜索接口
- 收藏持久化到数据库
- 更完整的小程序功能页
- 服务常驻部署能力

---

## 7. 当前结论

截至目前，项目已经具备较完整的后端和展示基础能力，能够支撑：

- OA 通知抓取
- 数据入库
- 定时执行
- 邮件提醒
- API 提供数据
- 小程序展示真实通知详情

目前最适合下一步继续推进的方向是：

1. 补全用户订阅管理
2. 完成小程序提醒链路
3. 增强 API 与搜索功能

---
