# Explorer 取证节流附录（数值与阈值）

规则正文以 Step 2「Playwright MCP 取证契约」为准，本文件只收数值与阈值，不重复说明性文字。

红线：**只降低取证与上下文开销，不改变证据标准**——禁止为省 Token 启用 `evaluate` / `get_page_source` 类工具，`fact` 仍只能来自可见文本与交互行为。

## 一、工具白名单（只读探索最小集）

探索阶段只启用下列工具，其余一律不调用：

| 用途 | 工具 | 备注 |
| --- | --- | --- |
| 导航 | `playwright_navigate` | 含 URL 变更 |
| 取证（主） | `playwright_get_visible_text` | 优先于截图 |
| 取证（辅） | `playwright_screenshot` | 默认关闭，见预算表 |
| 交互 | `playwright_click` / `playwright_fill` / `playwright_select` / `playwright_hover` / `playwright_press_key` | 单一动作原则 |
| 状态佐证 | `playwright_console_logs` | 仅辅助，不作业务结论 |

禁用（含省 Token 目的也不得启用）：`playwright_evaluate` / `playwright_get_page_source`（违反「只观察、不获取 DOM」边界）、`playwright_upload_file` 及写操作类（越权风险）、`playwright_save_as_pdf` 等高开销无关工具。MCP 客户端支持工具过滤时，在配置层只挂载白名单工具；不支持时在提示层自我约束。

## 二、取证预算（硬性）

每个页面（同一 URL + 同一角色态）的取证预算：

| 项 | 上限 | 超限处置 |
| --- | --- | --- |
| 取证次数 | 3 次（入口确认 / 动作后 / 补采） | 第 4 次起须说明为何前次证据不足 |
| 单次可见文本 | 1500 Token（约 3000 字） | 用 `scripts/trim_visible_text.py` 裁剪 |
| 截图 | 0 次（默认） | 仅快照不足以取证的布局/纯图标/toast 场景启用，每页 ≤ 1 |
| 单页面总计 | 4000 Token | 超出即收口该页，缺口登记为 `candidate` |

取证前三问：① 这条 REC 需要证明什么主张？② 现有上下文（上一步取证/已写盘 REC）是否已能证明？③ 能否只取证目标区块而非整页？

## 三、度量与降级

每条 REC 取证后记录一次量级（可选字段 `取证预算：`）：`文本约 X Token / 截图 N 次 / 取证 M 次`。单页超出预算时按序降级：

1. 停止截图
2. 取证文本预算下调至 800 Token
3. 该页收口，未覆盖部分登记 `candidate`/`blocked` 并说明「受取证预算限制」

严禁为省 Token 而降低证据标准：不得因为裁剪丢失关键反馈文案，不得用推断补齐未取证内容——缺失一律登记缺口。
