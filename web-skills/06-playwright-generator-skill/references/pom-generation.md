# POM 用例生成详细说明（generator · Step 2）

> 本文件是 `SKILL.md` 中「Step 2：POM 用例生成」的详细附录。**仅在执行 POM 用例生成模式时按需阅读**；框架初始化模式无需加载本文件，以节省上下文。

### Step 2：核心操作执行（POM 用例生成 — 消费 testcase.md + 页面对象 + 测试用例 + 三步顺序）
**输入：消费 testcase.md**（唯一业务规格）：符合格式的 per-module `<PROJECT_DIR>/spec/<模块>.testcase.md`，仅含纯测试用例（字段：用例编号、所属模块、用例标题、优先级、前置条件、测试步骤、预期结果、测试数据、就绪状态，零证据）。Generator 按模块读取对应文件，**仅消费其中标注的「可生成场景」（见规则 1）**；定位线索（选择器）由 Generator 在真实页面经可见 HTML 抽取 / 受控 `evaluate` 只读探查实测获取，不来自 testcase.md。

生成前必做：用 Glob 扫描 `spec/*.testcase.md`，列出本 feature 的全部模块文件；每个文件对应一个待生成功能模块。无 testcase 文件时停止并报告。

读取与实现遵守以下规则：

> 下文「**可生成场景**」统指 testcase.md 中标注 `确定性 + READY` 的场景，以及经用户明确确认生成的 `NEEDS_CONFIRMATION` / `BLOCKED` / 探索性场景（定义见规则 1）。

1. testcase.md 是唯一业务规格；生成范围为其中明确标注 `确定性 + READY` 的场景，以及经用户明确确认生成的 `NEEDS_CONFIRMATION` / `BLOCKED` / 探索性场景（含「保留」小节）。`NEEDS_CONFIRMATION` / `BLOCKED` / 探索性场景生成前需询问用户是否生成可运行用例；未经用户明确确认，不得生成可运行用例，也不得自行提升其状态。
2. 页面、动作、步骤顺序、角色、测试数据、断言谓词/预期值及清理边界，必须已在对应 READY 场景中提供；**定位线索不来自 testcase.md**（前序不提供），由本阶段在真实页面用 Playwright MCP 可见 HTML 抽取 / 受控 `evaluate` 只读探查实测获取（按本 Skill「定位器来源与强制验证」的两阶段法）。缺少任何生成必需信息（除定位线索外）时停止该场景并交回 testcase 修订，不得从其他来源推断或补写。
3. 保留并**透传** testcase.md 给出的**用例 ID（`<模块名>-<实际业务名>`，如 `登录认证-登入成功`）、优先级、就绪状态**作为追溯元数据；生成的每个 `test_` 方法必须以该用例 ID 显式标注，确保代码与 `<模块>.testcase.md` 一一对应、可反向追溯。testcase.md 不含证据线索（REC/§/测试点），如需追溯证据见独立的 `testcase-evidence.md`，Generator 不依赖该文件。testcase.md 内部有缺漏、冲突时，交回 testcase 修订。
4. 不从 testcase.md 之外自行扩展场景；只有「可生成场景」可生成（定义见上文）。
5. 不新增 testcase.md 未提供的 selector、断言文案、数据值、角色、状态转换或业务步骤。代码语法、POM 结构及 locator 实现方式可按本 Skill 和现有框架约定完成，但不得改变业务含义。
6. READY 条目不保证 locator、fixture、环境或用例可运行。按代码审核及 `pytest --collect-only` 门禁验证；实际页面运行只能在后续明确授权的执行阶段进行。

**1. 页面对象 `pages/<page>_page.py`（一页一类，按 READY 场景中交接的页面拆分）**：
- **拆分依据**：testcase.md 可生成场景中交接的页面及路径；每个页面对应一个独立文件。Generator 不打开 REC 源文件。例：`HomePage` → `pages/home_page.py`。跨页公共元素（header 搜索、导航、公共弹层等）归 `components/` 下的组件类单独成文件，由相关页面对象在内部组合/继承消费，测试文件不直接引用组件类；组件类同样继承 `BasePage`，不混入具体页面业务逻辑。**禁止**把多个页面塞进一个 `page.py`。
- 每个类 `class <PageName>(BasePage)`，继承框架初始化生成的 `BasePage`，`from base.base_page import BasePage`。
- 定位器稳定性分三档，按优先级取最稳一档（与「首选稳定属性 → 次选语义组合 → 末选结构层级」原则一致，禁止跨档跳级取易碎定位器）：
  - **① 首选·稳定属性**（全局唯一、随样式/布局不变、浏览器原生优化最快）：站点刻意提供的测试契约属性 `data-test` / `data-testid` / `test-id`（React/Vue 等生态常见，Playwright `get_by_test_id` 原生支持，并可经 `testIdAttributeName` 配置统一识别），以及全局唯一的 DOM 元素 `id`（须确认页面内唯一，否则降级或加父容器 scope）。一律用 `get_by_test_id` / `page.locator("[data-test='x']")` / `page.locator("#x")`；`data-test*` 属性不暴露在 accessibility 快照，须经 `playwright_get_visible_html`（只读已渲染元素）或受控 `evaluate` 读取，读到后只产出契约级 locator，严禁复制结构路径。**首选前提=全局唯一**：`--check-locators` 的阶段1唯一性硬门禁（`locator.count()==1`）即此前提的强制校验，非唯一 `id` 不得入首选档。
  - **② 次选·语义化属性组合**（可读、与业务语义直接绑定）：表单元素优先 `name`（`get_by_label` / `get_by_placeholder` / 按 `name` 取）；超链接优先 `get_by_role("link", name=...)`（稳定可访问名），链接名稳定且非 i18n 敏感时可用 `link_text` / `partial_link_text`；通用控件用 `role+name`。i18n 敏感文案须先 `switch_locale` 强制基线再断言，不得直接以翻译文案作定位/断言锚点。
  - **③ 末选·结构/层级**（最脆，默认禁用）：禁止绝对 XPath（`/html/body/...`）、禁止 `tag:nth-child(n)` 位置索引长链、禁止复制浏览器开发者工具生成的层级路径。仅当无任何稳定属性/语义属性可用、且经 `--check-locators` 显式评审放行时才允许极简、稳定的结构选择器，并须 `# 唯一` 标注。
- **禁用会命中多节点的属性/结构选择器（strict mode 多匹配违规根因）**：`a[href=...]`、后代 `x a`、`a:has-text(...)`、`tag.class` 等按属性/类/文案模糊匹配的选择器极易一对多——同一目标 URL 常同时存在「页头文字链 + CTA 按钮」等多个节点（如 `/user/register.html` 命中「注册」与「立即注册」）。当可见 HTML/快照中出现「同 href / 同 class / **同一可见文案多次**」的多个节点（如多步骤向导两处 "Proceed to checkout"），必须改用 `data-test` 契约级 locator（`[data-test='x']`）唯一区分，**不得**用 `get_by_text(<文案>)` 消歧（同名文案无法区分）。`get_by_text` 的文本参数须传**纯文案串**（如 `get_by_text("Favorites")`），**严禁**传入 `"text=Favorites"` 这类带 `text=` 前缀的 locator 串（那是 `page.locator("text=...")` 的写法，塞给 `get_by_text` 永远零命中）。
- **定位器来源与强制验证（杜绝猜测，硬性规则）**：真实页面上**精确 locator 的实测采集是本阶段的唯一职责与硬性环节**（前序均不提供任何定位线索）。本阶段采集严格遵循 `references/locator-budget.md`，以 **`playwright_get_visible_html` 可见 HTML 抽取为主**、**accessibility 语义快照为辅**，必要时用**受控 `evaluate` 只读探查**读取 `data-test`/`id`/`name` 属性与可见性/异步时序（详见 `locator-budget.md` 白名单）。优先提取站点自带的测试契约属性（`data-test` / `data-testid` / `test-id`）映射为 `get_by_test_id` / `page.locator("[data-test='x']")` / `page.locator("#x")`；可见 HTML 与快照给出的 `role/name/text/placeholder` 映射为语义 locator；**禁用 `get_page_source` 全文档原始 DOM**（token 爆炸且诱导脆弱结构选择器）。每个 locator 在页面中确认命中（`count()>0` 或可见）后写入，注释 `# 实测命中：<选择器说明>`（如 `# 实测命中：data-test=product-title 商品标题`）。testcase.md **不含定位线索字段**，不得从其臆造或"原样沿用"选择器；前序任何阶段都未提供选择器，故本阶段必须实测。

  **采集两阶段（先静态圈定，再按页单快照实测，最少操作）**：
  - **阶段 0 · 静态推导「必要 locator 集合」（零 MCP）**：遍历本模块全部「可生成场景」，**只从「测试步骤」与「预期结果/断言」解析**所需控件与断言锚点——`点击X`→X 的定位、`fill Y`→Y、`select Z`→Z；断言中的结果集→结果容器、计数/页数→计数/分页元素、状态/错误文案→文本锚点、空态→空结果区。合并去重为 `locator 需求表：{页面/状态, 控件语义名, 用途(动作/断言), 来源场景}`。**凡 testcase 未提及的元素一律不采集**；结构型容器（结果/分页/空态）仅在断言明确需要时才列入，不臆造。此表不开浏览器即定死采集范围，是降本核心。（此表属步骤解析推理，最终选择器一律以阶段 1 实测为准，不得凭步骤文案臆造。）
  - **阶段 1 · 按页/状态分组 + 单快照实测 + 去重指纹 + 逐级提成**：把需求表按「页面/状态」聚类，导航次数 ≈ **不同页面/状态数**（而非场景数×控件数）。每页/状态流程：**① `navigate` → ② 先等异步就绪**（`wait_for_content()`，即 READY_LOCATOR/内容锚点）**再**取快照（SPA 的 XHR 元素须渲染完才在 DOM，否则漏采）→ **③ 单次 `playwright_get_visible_html`（post-async）**解析候选契约属性 `data-test`/`data-testid`/`test-id`/唯一 `id` 及 `name`/`aria-label`/`placeholder`/`role`/`title`/`alt` + **单次 accessibility 快照**补语义；同页跨场景/跨页面类**复用同一次快照与 locator**（去重指纹 = `URL + 角色态`，指纹不变则引用已采集结果，不重复导航/快照）。登录态页面（书架/个人中心/充值/阅读等）共用一次 `logged_in_page` 登录会话；能用稳定 URL 直达的（如 `/login`、列表页）直接 `navigate`，不层层点击进入。原始快照**落盘为 `spec/evidence/locators-<页>.json`**，上下文只保留 `页面 → [语义locator]` 清单，不滞留原始快照（上下文收口）。
    - **逐级提成算法（每个需求控件取最高可用档）**：① 契约属性命中且唯一 → `get_by_test_id(name)`（id 唯一则 `#id`）；② 否则 `name`/`aria-label`/`role+name`/`link_text`（稳定且非 i18n）→ 语义 locator；③ 否则可见文本（**i18n 文案须先 `switch_locale` 到已知基线再读**，记录 `locale`）→ `get_by_text`；④ 皆无 → 触发阶段 2 最小交互探测兜底，仍无则登记缺口回交。**命中即停**，记录最终 `tier`、所选元素**可达的最高档** `max_tier` 与 `demand_id`；契约属性一律 `get_by_test_id`（conftest 配 `testIdAttributeName` 覆盖多种属性名），避免手写 `[data-test='x']` 拼错。
    - **批量唯一性校验（一次操作替代 N 次 `count()`）**：本页全部候选 selector 用一次受控 `evaluate` 跑 `arg.reduce((m, s) => (m[s] = document.querySelectorAll(s).length, m), {})`，仅 `==1` 放行；`>1` 按①回流精炼（优先 data-test 契约级 / 加父容器 scope），`==0` 回页面重查。唯一者注释补 `# 唯一`。
  - **阶段 1 唯一性硬门禁（杜绝多匹配）**：以阶段 1 的**批量 `evaluate`**（`document.querySelectorAll(sel).length == 1`）为强制校验手段，每个 locator 在写入前**必须**通过；`count() > 1` 即为「多匹配违规」，须精炼到唯一（优先改用 `data-test` 契约级 locator，或按可见文案 `name` 区分、加父容器层级限定）后再写；`count() == 0` 为「未命中违规」，须回页面重查节点。已确认唯一的 locator 在注释补 `# 唯一` 标识（供 `--check-locators` 放行，否则按多匹配风险判错）。
  - **阶段 1 就绪时序硬门禁（杜绝早返回）**：`READY_LOCATOR` 与"内容断言锚点"必须是 **XHR/AJAX 完成后才出现的元素**，不得选向导静态标签、页头常驻文案等"导航即存在"的外壳元素（如购物车页选商品行 `product-title` 而非向导标题 `Cart`）。多步骤向导/折叠面板中"存在但隐藏"的按钮（如 `offsetParent` 为空），须用受控 `evaluate` 复核其可见性，断言"可见"须以真正可见元素为准；可用 `playwright_expect_response` 在采集期确认关键接口已返回，作为就绪锚点的事实依据。
  - **阶段 2 · 入口发现兜底（仅触发条件启用）**：纯图标按钮、隐藏文本、仅有 placeholder 的输入框在语义树不可见时，用**最小交互探测**（hover/点击暴露）或区域截图兜底确认存在后再取 locator；仅在触发条件启用，**不每页盲做**，避免额外操作。

  **采集证据契约（机械审计依据）**：每页采集结束须落盘 `spec/evidence/locators-<页>.json`，结构如下（供 `run_generator.py --audit-locators` 校验"按步骤/不冗余/不猜测/稳定可靠/**档位未降级**"）：`tier` 必须为该元素**可达的最高档**（`max_tier`）；若页面本有 `data-test`/`id` 却落到 `text`/结构级，审计将判"档位降级"告警。

  ```json
  {
    "page": "cart",
    "fingerprint": "URL + 角色态",
    "operations": [
      {"tool": "navigate", "detail": "/checkout"},
      {"tool": "get_visible_html", "selector": "..."},
      {"tool": "click", "detail": "提交订单", "escalation_reason": "错误框仅提交后渲染"}
    ],
    "locators": [
      {"name": "PRODUCT_TITLE", "selector": "[data-test='product-title']",
       "tier": "contract", "max_tier": "contract", "demand_id": "cart.product_title",
       "unique": true, "ready_async": false, "locale": "en",
       "evidence": "# 实测命中：商品行标题"}
    ]
  }
  ```
  字段约束：`tier` ∈ {contract, semantic, text}（structural 禁用），且 **`tier` 必须等于 `max_tier`**（该元素可达的最高档：contract > semantic > text）——二者不一致即"档位降级"，`--audit-locators` 告警；`max_tier` 为逐级提成算法实际可达的最高档；`locale` 记录该 locator 采集时的语言基线（i18n 文案级定位须先 `switch_locale` 强制基线再采集）；`demand_id` 须回溯阶段 0 需求表（需求表落盘为 `spec/evidence/locator-demands-<模块>.json`）；`evidence` 非空即等价于代码内 `# 实测命中`；`operations` 中每次超额/交互须带 `escalation_reason`（完整性优先的有界放宽）。

  **实测前置与硬门禁（不变）**：
  1. **步骤/断言描述定位**：优先依据阶段 0 `locator 需求表` 在对应页快照实测定位并命中。
  2. **结构型/必需但未描述的元素**：结果容器、分页、当前页、空结果区、计数容器、弹层等"结构型"定位器，按阶段 0 需求表（断言需要才列入）在对应页快照查证节点并提取，注释 `# 实测命中`。
  3. **实测前置条件：BASE_URL 与登录凭据来自用户指令或项目资料**：MCP 实测需要可访问的真实页面。生成前取得 `BASE_URL` 与**登录账号的用户名及密码**——优先采用用户指令显式给出的，否则从项目资料读取；需登录才能访问的页面，本阶段用该凭据在 MCP 会话内登录后再采集其 locator（复用 `logged_in_page` 会话）。凭据仅用于本次 MCP 定位会话，**绝不写入任何生成文件、conftest、日志或截图**；运行期仍由 `credentials` fixture 经环境变量/命令行注入。
  4. **必须产出真实 locator，禁止占位、禁止推迟到自愈阶段**：本阶段对 testcase.md 中**每个**「可生成场景」涉及的页面，都必须完成快照实测并写入真实选择器（注释 `# 实测命中`）。**不得**生成 `TODO_VERIFY` 占位符，**不得**把 locator 采集推迟到 code-review / Healer 阶段。若用户指令与项目资料均缺少 `BASE_URL` 或某场景所需登录凭据，导致无法 MCP 访问对应页面，则**停止该场景并报告缺什么**（交回用户/testcase 补齐），不以猜测值或占位符蒙混，也不留待后续自愈补测。
- 业务方法封装原子操作，内部调 `self.click/fill/get_text`（继承自 BasePage，自带日志与 `allure.step`）。
- **定位与断言全部封装在页面对象（用例层零 Playwright API）**：
  - locator（`page.locator`/`get_by_role`/`get_by_text` 等）**只允许出现在页面对象方法内**；测试用例文件内禁止任何原始定位 API。
  - 页面对象提供**状态读取方法**：`xxx_text() -> str` / `xxx_count() -> int` / `is_xxx() -> bool`，返回纯 Python 值供用例 `assert`，读取前内部必须完成等待。
  - 或提供**断言封装方法**：`expect_xxx(...)`，内部用 `playwright.sync_api.expect`（自带自动重试等待），用例直接调用。
  - URL/title 断言同样封装为页面对象方法（如 `current_url()`），用例不直接访问 `page.url`/`page.title()`。
- **等待与导航（硬性规范）**：
  - **页面打开只用基类 `goto()`（基于 `URL_PATH`），禁止 `open()`**：框架 `BasePage` 仅提供 `goto()`，未定义 `open()`；生成代码若调用 `open()` 会在运行时抛 `AttributeError`。测试模板（`seed_test.py.template`）与页面模板（`seed_page.py.template`）均已统一为 `goto()`；无参 `goto()` 走类级 `URL_PATH`，传 `path` 可覆盖。`goto()` 会等待子类声明的 `READY_LOCATOR` 就绪，且该等待非致命（兼容客户端守卫路由重定向），无需在用例内重复等待。
  - **异步内容就绪：用「内容就绪锚点」代替 networkidle（硬性规范）**：JS 渲染应用（含轮询/流式）几乎永远不会 `networkidle`，依赖 `wait_for_load_state("networkidle")` 会随机超时，一律禁用。改用**内容就绪锚点**：子类声明 `READY_LOCATOR`（或业务方法内用具体结果锚点，如列表 `a.card`/数据行/分页容器），触发 AJAX 后 `wait_for_selector(锚点)` 或 `locator.wait_for()` 等待其出现。基类 `wait_for_ready()` / `wait_for_content()` 已封装该逻辑，超时**仅告警不阻断**（兼容无数据的空结果页）；`load` 事件不等于数据就绪，读取方法内部必须先 `wait_for_content()`。
  - **动画容器交互：触发→等可见→点选项→验证（硬性规范）**：下拉/弹层/右键菜单多有 CSS 动画，立即点击选项会被动画吞掉点击。一律走基类 `open_and_click(trigger, option, container=…, outcome_text=…)`：触发后等容器/选项 `visible` 并短停顿再点，点击后按可观测结果（文案/元素变化）验证，未达成自动重试。页面对象不得对容器内的选项直接裸 `click()`。
  - **停用态断言：祖先回退（通用启发式）**：断言控件禁用/可用时，先看控件自身 `disabled` 属性；部分 UI 把禁用态挂在**包裹元素**上（按钮/链接自身无 `disabled`），此时用基类 `is_disabled()` 向上查祖先 class 含 `disabled`，不得只查自身而漏判。
  - **本地化文本断言：先强制区域基线（通用规范）**：凡断言界面文案/标签（尤其随语言变化的导航项/按钮），断言前必须用基类 `switch_locale(code, toggle=…, option=…, expected_text=…)` 将界面切到已知区域（动画安全 + 结果验证 + 重试），消除默认区域波动对断言的影响。具体触发器/选项定位器与期望文案由各页对象按真实 DOM 实测提供，框架不写死任何语种或文案。
  - **严格区分「真实导航」与「原地 JS 刷新/分页」，二者等待方式不同**：真实导航才用 `expect_navigation` 包裹点击（链接 `href` 指向真实 URL、`location.href` 赋值、表单 `action` 提交、`location.reload()`）；不确定时方法提供 `wait_for_navigation: bool = False` 参数。原地 JS 刷新 / 分页 / 筛选重渲染（`href="javascript:;"`、AJAX 列表、组件库分页、`search()` 类 JS 函数）**绝不**包 `expect_navigation`——这类点击不触发 Playwright 导航事件，包裹会直接超时失败；正确做法：点击后等**内容就绪锚点**重渲染。分页/筛选/搜索类方法默认**不**带 `wait_for_navigation`，并在 docstring 标注「JS 原地更新」。
  - **`target="_blank"` 链接用 `context.expect_page()` 捕获新页**：方法提供 `new_tab: bool = False` 参数，捕获 popup 并 `wait_for_load_state()` 后**返回新 page**；用例对返回的新 page 构造对应页面对象再断言（页面对象构造函数须支持传入任意 page 实例）。
  - **断言按真实 DOM 层级取容器**：目标文本分布在兄弟节点时（如 `<i>标签：</i><em id="value">内容</em>单位`）按共同父级整体定位断言，不得假设文本集中在单一元素。
  - **计数类断言要剔除表头/非数据行**：列表 `tbody#resultList tr`（表头在 `thead`，不计入）vs 裸 `table tr`（会把表头算成 1 行导致「0 结果」误判为有结果）。结果容器选择器必须经过实测，不得用含糊的 `table tr` 做计数。
  - **避免依赖站点数据分布的"值变化"断言**：不用"筛选后首行书名应变化"这类受数据波动影响的断言；优先状态类断言（选中态 class、存在性、计数 ≥1）。具体数字/页数断言仅在 testcase.md 明确给定且该值稳定时才用，否则改为「总页数可解析为数字且 ≥1」这类稳定断言。
  - **断言文本须以实测为准、保留大小写与空白**：断言文案（尤其全大写标签、带空格的短语）必须沿用定位实测期观察到的**真实渲染文本**（含大小写），不得凭常规大小写或空格假设改写；i18n 文案须先经 `switch_locale` 强制基线后再比对。
  - **`wait_for_function` 的 JS 片段一律用命名参数**：生成任何 `page.wait_for_function("…", arg)` 时，箭头函数必须写成 `arg => …` 形式；**禁止**在箭头函数内使用 `arguments[0]`（箭头函数没有 `arguments` 对象，会静默失败）。需要多参数时显式写成 `(a, b) => …`。
- **禁止猜测选择器清单（Generator 头号错误源，硬性约束）**：以下类别的选择器**极容易凭常见命名猜错**，必须全部经 Playwright MCP 真实页面实测命中（可见 HTML 抽取 / 受控 `evaluate` 只读探查，注释 `# 实测命中：…`），**不允许** `TODO_VERIFY` 占位或推迟到自愈阶段：
  - **分页/页码**：`#pages`、`.current`、`.active`、按文本 `a:has-text("下一页")` 等常见猜测都不可信；真实结构常为组件库分页链接（如 `a.<lib>-next`），必须实测。
  - **结果/列表容器**：业务自定义 id（如 `#resultList`）与裸 `table tr` 等含糊写法；必须实测确认容器 id / 数据行是否含表头。
  - **详情/字段容器**：业务自定义 id（如 `#detailPanel`）等整块容器；字段取值应定位到具体节点（如 `td.name a`），不得假设整块文本。
  - **弹层/对话框**：组件库自定义类（如 `.modal`），需实测确认具体类名。
  - **「总页数/当前页」文本**：不得假设出现在某固定元素；应实测定位（不同组件库取总页数方式不同）。
  - **同名可见文案多匹配**：同一可见文案在页面出现多次（如向导多步骤的 "Proceed to checkout"），`get_by_text` 无法区分；必须用 `data-test` 契约级 locator 唯一锁定，禁止用 `get_by_text(<文案>)` 消歧。
  - **`get_by_text` 误用 `text=` 前缀**：`get_by_text("text=Favorites")` 把 `text=` locator 串当纯文案传入，永远零命中；文本参数只传纯文案，需要 `text=` 选择器时用 `page.locator("text=...")`。
  - **易变实体 ID（产品/订单/用户等）**：到达页面所用的实体 ID（如商品 URL `…/product/<id>`）会随 demo 数据重置而变化，属事实上的易碎 locator；不得硬编码，须提供按稳定属性（商品名/订单号）从列表页动态解析当前有效 ID 的方法（如 `_resolve_id_by_name`）。
  - 识别信号：任何**未标 `# 实测命中`、又非 `get_by_role`/`get_by_label`/`get_by_placeholder`/`get_by_test_id` 等稳定定位**的 CSS id/class 选择器，若属于上述类别，即为「疑似未验证猜测」。`run_generator.py --check-locators` 会扫描 `pages/*.py`，将未实测的疑似项（含 `TODO_VERIFY` 占位）**视为错误**报告，必须由本阶段补 MCP 实测消除，不得放行到后续阶段。`--check-locators` 另扫描「疑似多匹配选择器」（`a[href=...]`、`:has-text(`、后代 `] a`、以及 `get_by_text("text=...")` 这类 `text=` 前缀误用）：即使已标 `# 实测命中`（只证明存在、不证明唯一），只要未显式标 `# 唯一`（采集期已用 `count()==1` 验证）即判为错误，须改用语义按名定位或补 `# 唯一` 标注。READY_LOCATOR 若为"导航即存在"的外壳标签（如 `text=Cart`）亦判为疑似早返回锚点，须改为 XHR 后出现的元素。
- 不硬编码凭据；凭据由用例经 conftest 的 `credentials` fixture 注入（命令行 `--user/--password` 优先，其次环境变量），用例内不直接读 `os.environ`。

**2. 测试用例 `tests/test_<功能>.py`（按功能模块拆分为独立类文件，一功能一类一文件）**：
- **一功能一类一文件**：每个功能模块对应**一个独立** `test_<功能>.py` 文件，文件内只含**一个** `class TestXxx`；**禁止**把多个功能 class 塞进同一个文件，也不把同一功能的场景散落为扁平测试函数。
- 文件命名：`test_<功能名>.py`，功能名为 snake_case；class 命名：`Test` + 功能名（PascalCase，与文件名对应，如 `test_home.py` → `class TestHome`）。
- `import pytest`、`import allure`、`import os`、按需 `from pages.<page>_page import <PageName>`；**测试文件只依赖页面对象，不直接 import `components` 下的组件类**。
- 用 `page` fixture（由 `tests/conftest.py` 提供，**不自建 browser/context**）。
- `@allure.feature` 标注在 **class 级**（一个功能模块一个 feature，与文件/class 一一对应），`@allure.story` 标注在 **方法级**（每个需求场景一个 story），`@allure.severity` 标注在方法级。
- 凭据：沿用 `credentials` fixture 约定（conftest 注册 `--user/--password`，命令行 > `WEB_USER`/`WEB_PASS` 环境变量 > 占位值；用例只注入不直读环境变量；未提供则占位值自然失败）。
- 断言用原生 `assert` 比较页面对象返回的纯值，或调用页面对象的 `expect_xxx()` 断言方法；原始 Playwright API 禁止出现在用例。
- **参数化用例（强化约定）**：当 testcase.md 场景标注 `[参数化]` 且含「数据矩阵」时，必须满足：**同步骤、仅输入/预期值不同的多组数据合并为一条用例**，用 `@pytest.mark.parametrize` 展开为独立测试节点，绝不逐条复制重复方法，也**严禁**在单个 `def test_*` 内用 `for row in test_data / _DATA / data[...]: ... assert` 遍历数据矩阵（该写法使所有数据行塌缩为一个节点，单行失败即整例失败，且无法单独报告、`--lf` 重跑、`-k` 选跑、Healer 自愈）。
  - **数据源与加载（硬性）**：数据矩阵落盘为 `data/<module>.yaml`（与 `test_<功能>.py` 同名；顶层以场景名为 key 的 list of dict，每行含 `row_id` 及参数/预期字段）。`pytest.mark.parametrize` 装饰器在**模块收集期**求值、**无法引用 fixture 实例**，因此数据须在**测试模块级**一次性加载（路径用 `Path(__file__)` 派生，不硬编码）：
    ```python
    import pathlib, yaml
    _DATA = yaml.safe_load((pathlib.Path(__file__).resolve().parent.parent / "data" / f"{pathlib.Path(__file__).stem}.yaml").read_text(encoding="utf-8")) or {}
    _SEARCH = _DATA.get("search", [])
    ```
    根 `conftest.py` 的 `test_data` fixture（按模块名自动加载同一 yaml）保留，供非参数化场景整体读取使用。
  - **用例形态**：`@pytest.mark.parametrize("row", [pytest.param(c, id=c["row_id"]) for c in _SEARCH])` 展开；每个参数组合携带 `row_id` 作为用例 ID，并 `@allure.title` 或 `allure.dynamic.title(f"...{row['row_id']}")` 让 Allure 每个组合独立呈现、可反向追溯到 testcase.md 的 `行ID`。**凡 `[参数化]` 场景未出现 `@pytest.mark.parametrize` 即视为生成失败**，由 `scripts/run_generator.py --check-parametrize` 拦截。
  - **用例层零 Playwright API**：`row` 仅为纯数据，步骤与断言全部走页面对象通用方法（如 `fill_credentials(row["phone"], row["password"])` / `assert_validation(row["expected"])`），不得出现 locator / get_by_ / page.url / page.title。
  - 单条参数化方法统一标注一次 `@allure.story`/`@allure.severity` 即可，每个组合经 `row_id` 自动区分。
  - **预期结果可为多字段/多类型（通用，非仅登录）**：数据矩阵每行可同时携带多个预期字段（如 `expected_msg` / `expected_count` / `expected_url`），甚至用 `expected_type` 区分「成功跳转 / 错误提示 / 状态码」等不同结果性质。页面对象断言方法按行数据分支处理（如 `assert_result(row)` 内部依据 `row.get("expected_type")` 走不同断言路径），用例层仍只传 `row`、零 Playwright API。只要各数据行**步骤一致、仅数据与预期值不同**，无论功能域（搜索/筛选/表单/校验等）均可参数化，不局限于登录。
- **跨页流程用例**：用例内按步骤顺序实例化所需页面对象，同一 `page` 实例贯穿流程，不重复造 browser。
- **功能模块拆分依据（硬性约定）**：直接映射 **per-module `<模块>.testcase.md` 文件**——每一个 `<模块>.testcase.md` 对应一个 `test_<功能>.py` / `class Test<功能>`。文件命名 `<功能名>` 由 testcase.md 的「业务模块全名」派生为 snake_case（如 登录认证 → `test_login.py`）。`@allure.feature` 标注 **class 级且保留 testcase 的「业务模块全名」**（如 `@allure.feature("浏览发现")`）。模块内每个「可生成场景」 → 一个 `test_` 方法，**必须携带 testcase.md 的「`<模块名>-<实际业务名>`」用例 ID**（如 `@allure.testcase("登录认证-登入成功")` + `@pytest.mark.caseid(...)`，docstring 首行写明该用例 ID 与场景名）；用例 ID 一律沿用 testcase.md 原值，不得自行重编或省略。跨页面场景按 testcase.md 模块文件归属；testcase.md 未说明归属时退回修订，不自行判断。
- class 内**不含 `__init__`**；共享 fixture 统一放 `tests/conftest.py`（如 `header`/`home`/`common_layer`/`logged_in_page`/`_credentials` 等），`test_data` 由框架初始化生成的项目根 `conftest.py` 提供（按模块名自动加载 `data/<module>.yaml`）；各 `test_<功能>.py` 文件**不在文件内重复定义 fixture**。
- 模块级常量若仅单功能使用可放该功能文件顶部；跨模块共享且非框架通用的**业务常量**统一放 `common/constants.py`，跨模块共享的**框架级共享常量**统一放 `config/config.yaml` 的 `web` 段；参数化数据集放 `data/`。

**强制三步生成顺序（硬性规则，不得跳步）**：
- **前置检查（三步前必做）：文件存在性扫描**——用 Glob 扫描 `pages/*.py` 与 `tests/test_*.py`，列出已存在文件清单；**已存在文件默认不覆盖**，只补齐缺失方法/用例（方法体为 `NotImplementedError`/`pass` 的才回填）；内容发生变化时可修改；用户手改内容原则上不覆盖，冲突时报告交用户裁决；同名文件需全新建时追加版本后缀。
- **第 1 步：落所有页面类骨架**——按 testcase.md 中「可生成场景」涉及的页面创建全部 `<page>_page.py`（已存在的跳过新建，仅对缺失的页面建骨架）；每文件含 `class <PageName>(BasePage):` + docstring + **所有方法签名 + docstring**，方法体统一 `raise NotImplementedError` 或 `pass`；已存在文件若缺失方法签名只追加，签名需调整则同步修改；方法清单来源为场景中涉及该页的操作。**自检**：`py_compile` 全部骨架文件通过。
- **第 2 步：回填方法体**——逐个类、逐个方法填实现：定位器按本 Skill「定位器来源与强制验证」的两阶段法采集——阶段 0 静态推导本模块 `locator 需求表`（零 MCP）→ 阶段 1 按页/状态分组、每页仅一次 `navigate` + accessibility 快照、去重指纹复用、落盘 `spec/evidence/locators-<页>.json`；每个 locator 实测命中后写入并注释 `# 实测命中`；只回填 `NotImplementedError`/`pass` 占位方法；定位器强制验证、结构型定位器实测、禁止 `TODO_VERIFY` 占位/推迟自愈（缺 BASE_URL 或登录凭据则停止该场景并报告）。触发 AJAX 的方法点击后等**内容就绪锚点**（`wait_for_content()` / `wait_for(锚点)`），原地 JS 刷新/分页类方法不包 `expect_navigation`。**自检**：`py_compile` 全部页面对象通过；`run_generator.py --check-locators` 扫描不得报「疑似未验证猜测」（含 `TODO_VERIFY` 一律判错）；回复末尾输出「已验证定位器清单」（每个 locator 的实测选择器与 `# 实测命中` 说明），**不得**输出「待验证/占位」清单。
- **第 3 步：写测试用例**——按 testcase.md 的 per-module 文件规划拆分（每模块 → 一个 `test_<功能>.py`），文件内写**一个** `class TestXxx` + 测试方法；已存在的 `test_<功能>.py` 默认不覆盖，只补缺失「可生成场景」（断言/步骤因更新需调整时可修改）；共享 fixture 统一落 `conftest.py`（既有则补缺失、不覆盖）；跨页流程按需注入多个页面对象，同一 `page` 实例贯穿；参数化场景抽离到 `data/<功能名>.yaml`；`@allure.feature` class 级、`@allure.story`/`@allure.severity`/`@pytest.mark.ui` 方法级。**自检**：`py_compile` 全部 `test_<功能>.py` + `conftest.py` 通过 + `pytest --collect-only -q` 成功 + **用例文件零原始 Playwright API**（grep `page.locator(`/`get_by_`/`sync_api`/`page.url`/`page.title` 在 `test_<功能>.py` 内零命中）。
- **不得跳步**：未完成第 1 步全部骨架前不得回填方法体；未完成第 2 步不得写用例。每步自检失败就修到通过再下一步。
- **代码风格**：PEP 8、类型注解、`# -*- coding: utf-8 -*-`、中文注释、`pathlib.Path`、UTF-8。
