# 架构例外台账（唯一合法入口）

> 说明：任何架构例外都必须登记在本文件的 JSON 台账中；口头约定无效。

## 允许例外场景白名单

- `prod-hotfix`：线上止血。
- `external-dependency-constraint`：外部依赖硬约束。
- `short-term-perf-stopgap`：短期性能止血。
- `compatibility-temp-patch`：兼容性临时补丁。

## 明确禁止

- 为了赶工。
- 为了图方便。
- 个人偏好或习惯。

## 固定审批链

- `moduleOwner`：模块 Owner。
- `architectureOwner`：架构 Owner。
- `reviewerOnDuty`：当班 Reviewer。

## 固定回收要求

- `expiryDate`：到期日（默认不超过生效后 14 天）。
- `recycleOwner`：回收负责人。
- `recycleCriteria`：回收验收条件。
- `recyclePr`：回收 PR（未完成可填 `TBD`，回收时必须替换为真实 PR 链接或编号）。

## 固定模板字段

每条记录必须是以下字段集合（不可缺省、不可改名）：

- `id`
- `status`（`draft` / `active` / `recycled` / `expired`）
- `scenario`
- `impactBoundary`
- `moduleOwner`
- `architectureOwner`
- `reviewerOnDuty`
- `effectiveDate`（`YYYY-MM-DD`）
- `expiryDate`（`YYYY-MM-DD`）
- `recycleOwner`
- `recycleCriteria`
- `recyclePr`

## 例外台账（仅允许修改下方 JSON）

<!-- ARCH_EXCEPTIONS_JSON_START -->
```json
[]
```
<!-- ARCH_EXCEPTIONS_JSON_END -->
