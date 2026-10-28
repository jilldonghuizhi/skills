# Generator Locator 实测节流附录（数值与阈值）

规则正文以 Step 2「定位器来源与强制验证」为准，本文件只收数值与阈值，不重复说明性文字。
**目标**：用最少 MCP 操作与最低 Token 成本，拿到 generator 必需的真实语义 locator。

**红线**：**必须 locator 的完整性优先于 token 节流**——阶段 0 需求表列为「必须」的 locator，未实测命中前不得因省 token 而跳过；token 节流是**可调软目标**，仅在完整性满足后优化。`# 实测命中` 来自可见 HTML 抽取、受控 `evaluate` 只读探查，以及为暴露动态 DOM 所需的**有界定点交互探测**（见下方白名单）；`get_page_source` 等全文档原始 DOM 工具因 token 爆炸且诱导脆弱结构选择器，始终禁用，放宽亦不包含它。

## 一、工具白名单（locator 采集最小集）

采集阶段只启用下列工具，其余一律不调用：

| 用途 | 工具 | 备注 |
| --- | --- | --- |
| 导航 | `playwright_navigate` | 含 URL 变更；稳定 URL 直达，不层层点击进入 |
| 取证（主） | `playwright_get_visible_html` | 首选取数方式，产出已渲染元素的 `role/name/text/placeholder` 及 `data-test` 属性 → 语义/契约级 locator |
| 取证（辅） | `playwright_get_visible_text` | 仅可见文本，用于确认文案存在，不单独成 locator |
| 只读探查（兜底层） | `playwright_evaluate`（只读） | 仅读 `data-test`/`id`/`name` 属性、查 `offsetParent`/`getComputedStyle` 可见性、轮询异步就绪；**禁止**写操作、全文档返回、复制结构路径 |
| 交互探测（兜底） | `playwright_click` / `playwright_fill` / `playwright_hover` / `playwright_press_key` | 仅入口发现触发条件启用（图标/隐藏/placeholder 盲区） |
| 状态佐证 | `playwright_console_logs` | 仅辅助，不作定位依据 |
| 网络就绪佐证 | `playwright_expect_response` | 采集期确认关键 XHR 已返回，作为异步就绪锚点的事实依据 |

禁用（含省成本目的也不得启用）：`playwright_get_page_source`（全文档原始 DOM，token 爆炸且诱导 `div:nth-child(n)` 等脆弱结构选择器）、`playwright_upload_file` 及写操作类、`playwright_save_as_pdf` 等高开销无关工具。`playwright_evaluate` 仅限上述只读探查；MCP 客户端支持工具过滤时，在配置层仅挂载白名单与受控 `evaluate`，其余不挂载。

## 二、实测预算（硬性）

每个页面/状态（同一 URL + 同一角色态）的实测预算：

| 项 | 上限 | 超限处置 |
| --- | --- | --- |
| 可见 HTML 抽取次数 | 1 次（单页单抽取取全部所需 locator） | 第 2 次起须说明为何前次抽取不足 |
| 单页取证 | ≤ 1 次 `navigate` + 1 次 `playwright_get_visible_html` | 同页跨场景/跨页面类复用，不重复 |
| 交互探测（兜底/升级） | 0 次（默认） | 仅入口发现触发条件启用；当需求表「必须」locator 单快照未命中时**可升级**至每页 ≤ 5 次（含提交/筛选/展开以暴露动态 DOM），每次须记录 `escalation_reason` |
| 截图 | 0 次（默认） | 仅入口发现兜底需视觉回读时启用，每域 ≤ 1 |
| 单页上下文 | 原始快照落盘后只留 `页面 → [语义 locator]` | 超出即收口该页 |

**实测前三问**：① 这个 locator 是否被阶段 0 `locator 需求表` 列为必要？② 是否已在同页已采集快照中命中（指纹去重）？③ 能否只从该页快照抽取而非触发额外操作？若「必须」locator 单快照未命中，则允许触发有界升级（记录 `escalation_reason`），目标是命中而非省操作。

## 三、去重指纹与缓存

- **指纹** = `URL + 角色态`（+ 必要的查询条件，如列表默认查询）。指纹未变则**引用已落盘的 `spec/evidence/locators-<页>.json`**，不重新 `navigate` / `playwright_get_visible_html`。
- 维护「已采集页面 + 角色态」清单即为范围防护，缓存是其副产品：分页/筛选/搜索只验证目标范围内必要的一个代表状态，不做无目的全排列。
- 登录态页面通过一次 `logged_in_page` 会话共享，避免每页重复登录。

## 四、度量与降级

每条页面采集后记录一次量级（可选字段 `实测预算：`）：`可见 HTML 抽取 N 次 / 交互探测 M 次 / 受控 evaluate K 次 / 落盘路径`，并落盘 `spec/evidence/locators-<页>.json`（证据契约见 `pom-generation.md`）。单页采集遵循**完整性优先的有界放宽**：

1. 需求表「必须」locator 单快照未命中 → **先升级**（二次抽取 / 定点交互 / 受控 `evaluate`，记录 `escalation_reason`），直至命中或触及上限；
2. 触及上限（交互 ≤ 5 次/页、截图每域 ≤ 1）仍缺「必须」locator → 该 locator 登记 `blocked` / `待补测`，说明「受采集上限限制」，交回用户/testcase 补齐；**不得因节流跳过必需 locator，更不得猜测**。

**严禁为省成本降低证据标准**：不得因裁剪丢失关键控件/容器定位，不得用推断补齐未实测 locator——缺失一律登记缺口，回交用户/testcase 补齐。受控 `evaluate` 读取到的 `data-test`/`id` 属站点自带稳定测试契约，是合法实证（非推断），应予采用并标注 `# 实测命中`。

## 五、采集质量补充（供 generator 落地稳健交互）

- **文本类断言锚点须原样记录渲染文本**：凡断言用到的可见文案（标签、按钮、错误提示、全大写向导步骤等），在证据与代码注释中**保留真实大小写与空白**，不得按常规大小写改写；i18n 文案须记录其所属区域，供 generator 先 `switch_locale` 强制基线再比对。
- **容器内定位器须连带记录容器**：下拉/弹层/右键菜单内的选项 locator，需同时记录「打开触发器」与「容器本体」定位器，供 generator 走 `open_and_click(trigger, option, container=…)`——触发后等待容器可见再点选项，规避 CSS 动画吞点击；不得仅记选项、让用例裸 `click()`。
- **容器可见性预检**：对处于动画容器内、断言可见的元素，采集与生成阶段均应先 `wait_for(state="visible")` 于**容器**而非仅子项，再交互/断言。

## 六、获取提质（与 pom-generation.md 阶段 1 对齐）

- **快照须在异步就绪后采集**：`navigate` 后先 `wait_for_content()`（READY_LOCATOR/内容锚点）再取 `playwright_get_visible_html` 与 accessibility 快照；SPA 列表/卡片为 XHR 后渲染，导航即快照会漏采异步元素（0 卡片根因之一）。
- **逐级提成（每控件取最高可用档）**：对每个需求控件按 `contract(data-test/data-testid/test-id/唯一 id) → semantic(name/aria-label/role+name/link_text) → text` 顺序探测，命中即停；契约属性一律 `get_by_test_id(name)`（conftest 配 `testIdAttributeName` 覆盖多种属性名），不手写 `[data-test='x']`。
- **批量唯一性校验（一次 `evaluate` 替代 N 次 `count()`）**：本页全部候选 selector 一次性 `document.querySelectorAll(sel).length` 校验，仅 `==1` 放行，省去逐个 `locator.count()` 的多次 MCP 往返。
- **i18n 文案级定位须在基线下采集**：仅靠可见文案定位时，若页面有语言切换，先 `switch_locale`/`switch_language` 到已知基线再读文本，并在证据记 `locale`，避免采到默认语言波动下的文本。
