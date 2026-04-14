# Java API Contract Notes

## 目的

该文档用于约束 Java 版接口输出与当前 Python 版接口保持一致，避免小程序切换后出现字段兼容性问题。

## 当前已确认的返回规则

- 顶层响应统一为：
  - `code`
  - `message`
  - `data`
- 字段命名当前按 Python 版保持 `camelCase`
  - 例如：`newsId`、`publishTime`、`lastNotificationCheckAt`
- 大多数业务时间字段当前按 Python 版返回到分钟：
  - `yyyy-MM-dd HH:mm`
- 运行态时间字段通常保留到秒：
  - 例如管理员触发任务状态中的 `lastStartedAt`、`lastFinishedAt`
- `lastSync` 当前为：
  - `HH:mm`
- 某些接口存在“按场景省略字段”的行为：
  - `GET /api/users/settings` 返回 `hasUser`
  - `POST /api/users/settings` 不返回 `hasUser`
  - `GET /api/admin/crawler/config` 返回 `updatedKeys`
  - `POST /api/admin/crawler/config` 不返回 `updatedKeys`

## 联调脚本

使用 [java_api_parity_checks.ps1](/d:/AiCoding/Trae/codex/oa_notification_project/test/java_api_parity_checks.ps1) 对 Python/Java 接口做字段集对比。

示例：

```powershell
cd d:\AiCoding\Trae\codex\oa_notification_project\test
.\java_api_parity_checks.ps1 `
  -PythonBaseUrl "http://127.0.0.1:8000" `
  -JavaBaseUrl "http://127.0.0.1:8080" `
  -UserEmail "3307180168@qq.com" `
  -NewsId "可选的真实newsId"
```

## 下一步建议

- 增加“值格式”校验，而不只是字段集合校验
- 对时间字段做正则比对
- 对错误响应体做 Python/Java 并排对比
