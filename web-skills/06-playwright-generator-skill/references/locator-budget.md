# Generator Locator 实测节流附录（数值与阈值）

规则正文以 Step 2「定位器来源与强制验证」为准，本文件只收数值与阈值，不重复说明性文字。
**目标**：用最少 MCP 操作与最低 Token 成本，拿到 generator 必需的真实语义 locator。

**红线**：只降低实测与上下文开销，**不改变「必须实测、禁止猜测」的硬门禁**——禁止为省成本启用 `evaluate` / `get_page_source` 原始 DOM 工具；`# 实测命中` 仍只能来自 accessibility 语义快照或最小交互探测确认。

## 一、工具白名单（locator 采集最小集）

采集阶段只启用下列工具，其余一律不调用：

| 用途 | 工具 | 备注 |
| --- | --- | --- |
| 导航 | `playwright_navigate` | 含 URL 变更；稳定 URL 直达，不层层点击进入 |
| 取证（主） | `playwright_snapshot`（accessibility 语义树） | 首选取数方式，产出 `role/name/text/placeholder` → 语义 locator |
| 交互探测（兜底） | `playwright_click` / `playwright_fill` / `playwright_hover` / `playwright_press_key` | 仅入口发现触发条件启用（图标/隐藏/placeholder 盲区） |
| 状态佐证 | `playwright_console_logs` | 仅辅助，不作定位依据 |

禁用（含省成本目的也不得启用）：`playwright_evaluate` / `playwright_get_page_source`（原始 DOM，违反边界且产出脆弱选择器）、`playwright_upload_file` 及写操作类、`playwright_save_as_pdf` 等高开销无关工具。MCP 客户端支持工具过滤时，在配置层只挂载白名单工具；不支持时在提示层自我约束。

## 二、实测预算（硬性）

每个页面/状态（同一 URL + 同一角色态）的实测预算：

| 项 | 上限 | 超限处置 |
| --- | --- | --- |
| 快照次数 | 1 次（单页单快照抽取全部所需 locator） | 第 2 次起须说明为何前次快照不足 |
| 单页取证 | ≤ 1 次 `navigate` + 1 次 `snapshot` | 同页跨场景/跨页面类复用，不重复 |
| 交互探测（兜底） | 0 次（默认） | 仅入口发现触发条件启用，每页 ≤ 2 次 |
| 截图 | 0 次（默认） | 仅入口发现兜底需视觉回读时启用，每域 ≤ 1 |
| 单页上下文 | 原始快照落盘后只留 `页面 → [语义 locator]` | 超出即收口该页 |

**实测前三问**：① 这个 locator 是否被阶段 0 `locator 需求表` 列为必要？② 是否已在同页已采集快照中命中（指纹去重）？③ 能否只从该页快照抽取而非触发额外操作？

## 三、去重指纹与缓存

- **指纹** = `URL + 角色态`（+ 必要的查询条件，如列表默认查询）。指纹未变则**引用已落盘的 `spec/evidence/locators-<页>.json`**，不重新 `navigate` / `snapshot`。
- 维护「已采集页面 + 角色态」清单即为范围防护，缓存是其副产品：分页/筛选/搜索只验证目标范围内必要的一个代表状态，不做无目的全排列。
- 登录态页面通过一次 `logged_in_page` 会话共享，避免每页重复登录。

## 四、度量与降级

每条页面采集后记录一次量级（可选字段 `实测预算：`）：`快照 N 次 / 交互探测 M 次 / 落盘路径`。单页超出预算时按序降级：

1. 停止交互探测与截图；
2. 该页收口，未在快照中确认的必要 locator 登记 `blocked` / `待补测` 并说明「受实测预算限制」。

**严禁为省成本降低证据标准**：不得因裁剪丢失关键控件/容器定位，不得用推断补齐未实测 locator——缺失一律登记缺口，回交用户/testcase 补齐。
