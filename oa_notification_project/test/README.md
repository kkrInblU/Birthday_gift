# 测试目录说明

本目录用于集中存放 OA 通知项目的测试资料，包括：

- 测试用例文档
- PowerShell 测试脚本
- 数据库造数与查询脚本

当前文件说明：

- `notification_cycle_test_cases.md`
  - 通知刷新周期与投递场景测试用例
- `api_settings_tests.ps1`
  - 用户刷新周期设置接口测试脚本
- `test_data_sql.sql`
  - 数据库测试数据准备、重置、结果查询 SQL

建议使用顺序：

1. 先启动后端 API 与投递脚本运行环境
2. 用 `api_settings_tests.ps1` 验证用户设置接口
3. 用 `test_data_sql.sql` 准备或核对数据库测试数据
4. 对照 `notification_cycle_test_cases.md` 执行完整场景测试

当前已覆盖的核心场景：

- 已到通知周期，但没有新的通知，用户不收到提醒
- 已到通知周期，且有新的通知，用户收到提醒
- 未到通知周期，且没有新的通知，用户不收到提醒
