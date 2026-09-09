# PC Web Design

## Source of truth

- Status: Active
- Last refreshed: 2026-08-24
- Primary product surfaces: PC Web 答题端、PC Web 管理端、Web 专属嵌字笔记
- Supporting architecture: [`docs/WEB_ARCHITECTURE_ZH.md`](docs/WEB_ARCHITECTURE_ZH.md)
- Evidence reviewed:
  - [`README.md`](README.md)
  - [`miniprogram/pages/index/index.wxml`](miniprogram/pages/index/index.wxml) 与 [`index.wxss`](miniprogram/pages/index/index.wxss)
  - [`miniprogram/pages/level/level.wxml`](miniprogram/pages/level/level.wxml) 与 [`level.wxss`](miniprogram/pages/level/level.wxss)
  - [`miniprogram/pages/quiz/quiz.wxml`](miniprogram/pages/quiz/quiz.wxml) 与 [`quiz.wxss`](miniprogram/pages/quiz/quiz.wxss)
  - `miniprogram/pages/admin*` 下的登录、题库、题目编辑、详情和设置页面
  - [`miniprogram/images/hero-title-hanzipen.png`](miniprogram/images/hero-title-hanzipen.png)
- Evidence limits: 仓库中没有设计稿、截图基线或既有 Web 组件；本文件以当前小程序源码和标题资产为视觉事实，以已确认的 PC 使用场景为布局依据。

本文件是 PC Web 实现与评审的设计合同。实现中若出现与本文件冲突的设计决策，应先更新本文件，再修改界面。

## Brand

- Personality: 温暖、安静、亲切，带有手写课堂和纸张卡片的轻松感；专业但不严肃。
- Trust signals: 清楚显示当前难度、题号、保存状态和提交结果；管理员操作反馈明确；破坏性操作可预期且可取消。
- Existing signatures to preserve:
  - 米白底色和陶土橙主操作色。
  - 白色圆角卡片、暖色浅边框和克制阴影。
  - 首页继续使用现有手写标题图片，不用运行时字体仿制。
  - “新手级 / 熟练级 / 挑战级”、星级难度、A–D 圆形选项标记和当前中文文案。
- Avoid:
  - 紫蓝色 SaaS 后台、纯黑科技风或冷灰企业后台。
  - 到处使用毛玻璃、渐变、悬浮球、彩色图标和装饰性动画。
  - 把 PC 页面做成居中的放大手机壳。
  - 在答题页显示会泄露正确答案的信息。

## Product goals

- Goals:
  - 为偏好 PC 的用户提供与小程序一致的匿名答题体验。
  - 利用横屏宽度，让题图和操作同时可见，减少上下滚动。
  - 让管理员用键盘和鼠标高效地逐题录入、预览和维护题库。
  - Web 与小程序共享业务规则和数据，但允许 Web 使用更适合桌面的信息架构。
  - 提供由管理员上传标题、说明和难度维护的嵌字笔记卡片。
- Non-goals:
  - 不做用户注册、用户中心、跨设备成绩历史或排行榜。
  - 不做批量 Excel/ZIP 导入。
  - 不在 Web 管理端维护管理员账号。
  - 不在前端静态配置嵌字笔记；内容从公开 API 读取。
  - 首版不做暗色主题、SSR、复杂仪表盘或可自定义布局。
- Success signals:
  - 1280px 及以上宽度下，单题的题图、题干、选项和主导航无需整页纵向来回滚动。
  - 管理员在题目编辑页不离开当前页即可看到接近答题端的实时预览。
  - 只使用键盘可以完成登录、选难度、答题、提交和题目编辑保存。
  - 在 200% 浏览器缩放和减少动态效果设置下，功能仍完整可用。

## Personas and jobs

- Primary personas:
  - PC 答题用户：无需注册，可选填写昵称后完成一次短练习并查看错题解析。
  - 题库管理员：多个独立账号、权限相同，主要在 PC 上逐题录入和维护。
  - 运维人员：通过服务器命令管理管理员账号，不进入产品 UI。
- User jobs:
  - 快速开始一次合适难度的字形练习。
  - 清楚判断当前题目、已选答案和剩余进度。
  - 查看得分以及真正答错的题目解析。
  - 高效新增、修改、删除、检索题目并确认最终显示效果。
  - 调整出题策略、字体快捷项和查看历史提交。
- Key contexts of use:
  - 中国大陆用户，PC 横屏为主，常见宽度 1280–1920px。
  - 浏览器可能处于学校或组织网络，同一公网 IP 下可能有多个用户。
  - 图片由外部图床加载，网络延迟或图片失效必须有明确降级状态。

## Information architecture

### Public navigation

公开端不设置常驻复杂导航。左上角品牌标识返回首页；右上角显示昵称入口。主要路由：

| Route | Screen | Primary action |
| --- | --- | --- |
| `/` | 首页 | 开始识字挑战 |
| `/levels` | 难度选择 | 选择新手级、熟练级或挑战级 |
| `/quiz/:attempt` | 答题 | 选择答案并进入下一题 |
| `/result/:attempt` | 结果 | 查看错题或再答一次 |
| `/font-reference` | 嵌字笔记 | 卡片式展示，按星级筛选与标题搜索，点击放大 |
| `/admin/login` | 管理员登录 | 账号密码登录 |

管理员入口保留在首页次要区域，不与“开始识字挑战”竞争视觉优先级。

### Admin navigation

管理端采用固定左侧导航，不保留移动端“管理首页 → 更多管理”的卡片中转层。登录后默认进入题库：

1. 题库
2. 新增题目
3. 出题策略
4. 字体快捷项
5. 提交记录
6. 配置迁移
7. 退出登录

账号创建、停用、恢复和改密不出现在导航中，由服务器 CLI 负责。

### Content hierarchy

- 每个页面只设一个主要动作。
- 页面标题说明“这里是什么”，紧邻的说明文字解释“可以做什么”。
- 主操作位于内容流末端或右上工具栏；破坏性操作不与主操作并列成同色按钮。
- 列表先提供检索和状态，再呈现数据；空状态直接提供下一步。

## Layout specifications

### Shared desktop frame

- Page background: `#FFF9F0`。
- Public content max-width: `1280px`；左右安全边距 `clamp(24px, 4vw, 64px)`。
- Admin content max-width: `1440px`；侧栏 `232px`，主区最小 `720px`。
- 默认使用 12 列网格、`24px` gutter。
- 页面首屏垂直留白不少于 `40px`，主要区块间距 `32px`。

### Home

首页使用“左侧内容与入口、右侧角色插图”的两区结构，不把移动端卡片简单拉宽：

```text
┌──────────────────────────────────────────────────────────────┐
│ 品牌                                                     昵称 │
│                                                              │
│  砂糖橘的秘密小课堂       [画师 Q 版角色插图]                 │
│  [现有手写标题图片]                                           │
│  观察图片……                                                   │
│  ┌──────────────────┐                                         │
│  │ 开始识字挑战   → │                                         │
│  ├──────────────────┤                                         │
│  │ 嵌字小本本     → │                                         │
│  └──────────────────┘                                         │
│  提交后会自动评分……                                           │
└──────────────────────────────────────────────────────────────┘
```

- 左侧约 52–55%，依次放品牌眉题、标题图、简短说明、两个入口和评分提示；标题图片最大宽度 `620px`。
- 右侧约 45–48%，完整展示画师提供的 Q 版角色图，不额外叠加图标、气泡或装饰卡片。
- 答题入口为陶土橙主卡片，嵌字小本本为白色次卡片；沿用现有无前置图标、右侧文字箭头的样式。
- `1023px` 以下切换为单列；平板端保持标题与说明 → 两个入口 → 评分提示 → Q 版角色图的顺序。
- 手机端通过响应式网格调整为标题与说明 → Q 版角色图 → 两个入口 → 评分提示；角色图使用内容区约 `92%` 宽度并居中展示，入口卡片适度收紧，优先让常见手机首屏同时看到完整角色图和两个入口。

### Level selection

- 左侧 4 列：标题、题目数量说明和返回入口。
- 右侧 8 列：三张难度卡纵向排列；每张显示单字图标、标题、副标题和箭头。
- Hover 只提升 `2px` 并增强阴影；选中/按下立即缩放至 `0.985`。
- 不展示管理员配置的具体权重，避免让用户承担策略细节。

### Quiz

答题页以左右布局为核心：

```text
┌──────────────────────────────────────────────────────────────┐
│ ← 退出练习        新手级 · 第 3 / 10 题       进度条          │
├──────────────────────────────┬───────────────────────────────┤
│ 第 3 题 · ★★★                │ A  选项文本                    │
│ 请选择以下……                 │ B  选项文本                    │
│                              │ C  选项文本                    │
│ ┌──────────────────────────┐ │ D  选项文本                    │
│ │         题目图片          │ │                               │
│ │      点击查看原图         │ │ [上一题]             [下一题] │
│ └──────────────────────────┘ │                               │
└──────────────────────────────┴───────────────────────────────┘
```

- 左侧 7 列：题号、星级、题干和图片；图片容器最大高度 `min(62vh, 620px)`。
- 右侧 5 列：选项、上一题/下一题或提交按钮；在视口内 sticky，但不遮挡页脚。
- 选项最小高度 `64px`，整行可点击；A–D 标记保持圆形。
- 选择后立刻更新边框、底色和标记，不等待网络请求。
- 支持 `A`–`D` 或 `1`–`4` 选择、左右方向键换题；焦点在输入控件中时不触发快捷键。
- 未完成全部题目时，“提交”保持可点击但触发就地提示缺少的题号；不要只用 disabled 状态隐藏原因。
- 离开未提交答题不需要确认；答题页底部提供“重新开始本次练习”，清除本地进度后回到难度选择。

### Result and wrong-answer review

- 左侧 4 列：分数、答对数量、难度、昵称和“再答一次”。
- 右侧 8 列：只展示错题；一次查看一题，保留题图、用户选择、正确答案和统一解析。
- 全对时右侧显示简洁完成状态，不制造虚假的错题内容。
- 正确使用绿色 `#39864A`，错误使用深红 `#B5483F`，同时配合文字和图标，不只依赖颜色。

### Font reference

- 嵌字笔记是 Web 专属公开页面，内容由管理员维护。
- 左侧 `280px` 缩略图/标题列表，右侧展示当前大图和说明。
- 图片条目来自 TypeScript 静态配置：`id`、`title`、`thumbnailUrl`、`imageUrl`、可选 `description`。
- 支持标题关键词过滤；条目很少时不增加分类、标签和后台 CRUD。
- 点击大图使用原生 `<dialog>` 打开查看器；`Esc` 关闭，焦点返回触发元素。

### Admin shell

```text
┌───────────────┬──────────────────────────────────────────────┐
│ 砂糖字形课堂   │ 题库                         搜索   ＋新增题目 │
│               ├──────────────────────────────────────────────┤
│ ● 题库         │ 筛选 / 结果数量                              │
│   新增题目     │ ┌──────────────────────────────────────────┐ │
│   出题策略     │ │ 题目行：缩略图、题干、星级、编辑、删除    │ │
│   字体快捷项   │ └──────────────────────────────────────────┘ │
│   提交记录     │ 分页                                         │
│               │                                              │
│   退出登录     │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

- 侧栏可以使用轻微半透明暖白材料；主内容卡片保持实色，禁止玻璃叠玻璃。
- 当前导航项用暖橙浅底、深色文字和左侧 3px 指示条共同表达。
- 窄屏时侧栏收为顶部按钮打开的抽屉；进入和退出沿同一路径，从左侧出现并返回左侧。

### Question list

- 默认表格/密集列表，而非移动端大卡片列表。
- 列：缩略图、题干、难度、正确答案、更新时间、操作。
- 支持题干关键词搜索和难度筛选；使用服务端分页。
- 点击行进入详情；“编辑”和“删除”是显式按钮，删除不由整行点击触发。
- 删除对话框必须显示题干摘要，并要求二次确认；删除成功后保留当前筛选和页码。

### Question editor

- 左侧 7 列为表单，右侧 5 列为 sticky 答题卡预览。
- 表单顺序：题干 → 难度 → 图片 URL/上传入口 → 选项 → 正确答案 → 解析。
- 字体快捷项紧邻当前获得焦点的选项输入区；点击后直接替换该选项并保持焦点。
- 图片上传协议未确定前，UI 使用“图片 URL + 预览”；未来上传控件替换输入方式，不改变 `imageUrl` 数据字段。
- 保存按钮固定在表单末端，并支持 `Cmd/Ctrl + S`。
- 有未保存修改时离开页面必须确认；保存期间按钮显示明确进度并防止重复提交。
- 服务端校验错误映射到对应字段，页面顶部只显示摘要，不让用户猜哪个字段失败。

### Settings and submissions

- “出题策略”“字体快捷项”“提交记录”拆为三个导航页面，不挤在同一长页。
- “配置迁移”桌面端采用 `01 导入配置 / 02 预览确认` 双栏工作区，窄屏切换为单列；标题区只保留页面标题和全量导出入口。第一栏选择完整配置或设置配置，第二栏查看只读差异预览并进行 hash 绑定确认。右上角的完整配置导出包含题库；第一栏的设置配置导出不含题库，设置导入明确保留当前题库。页面下方另设“题库导入与导出”工具，支持题库 JSON 导出和追加式导入，明确显示“仅追加 · 不覆盖”、导入统计与失败原因；不使用含义不清的 `QB` 图标或箭头装饰。
- 出题策略使用三行 × 五星的可编辑矩阵；每行显示权重合计和至少一个非零值的校验状态。
- 字体快捷项使用逐项 chip 编辑，同时保留粘贴多行文本后解析的快捷入口。
- 提交记录使用分页表格，列为昵称、分数、答对/总题数、难度、提交时间；点击行查看答题明细。
- 历史提交永久保留，但界面不一次加载全部记录。

## Design principles

- Immediate response: 所有可按控件在 `pointerdown/:active` 即提供视觉反馈；网络结果另行显示，不能让点击显得失效。
- Spatial consistency: 面板从触发它的方向出现并沿原路径消失；返回操作回到原列表状态和滚动位置。
- Desktop depth, not mobile magnification: PC 用并行信息和键盘效率，品牌语言与小程序一致但布局不照搬。
- Calm confidence: 动效用于解释状态与空间关系，不用于庆祝每次点击；成功不加彩带和弹跳。
- Forgiveness: 未保存编辑会提醒；删除只对真正不可逆操作确认；筛选和答题进度可恢复。
- Minimum machinery: 没有拖拽、惯性或重排需求，因此不引入弹簧/手势动画库。

## Visual language

### Color tokens

| Token | Value | Use |
| --- | --- | --- |
| `--color-bg` | `#FFF9F0` | 页面背景 |
| `--color-surface` | `#FFFFFF` | 卡片、表单、主内容 |
| `--color-surface-warm` | `#FFF8ED` | 选项、图片衬底、次级区域 |
| `--color-surface-accent` | `#FFF0D8` | 图标底、当前导航、提示 |
| `--color-text` | `#332718` | 主文字 |
| `--color-text-muted` | `#816E59` | 次级说明；在米白背景达到正常文字对比要求 |
| `--color-brand` | `#C96D32` | 品牌块和大面积装饰，不承载小号白字 |
| `--color-action` | `#A94F1F` | 主按钮；白字对比度高于原品牌色 |
| `--color-action-hover` | `#913F16` | 主按钮 hover/press |
| `--color-accent` | `#D97A00` | 星级、眉题、图标；仅用于大字或非文字装饰 |
| `--color-border` | `#F3E5D3` | 暖色边框 |
| `--color-success` | `#39864A` | 正确、成功 |
| `--color-danger` | `#B5483F` | 错误、删除 |
| `--color-focus` | `#7A4BD0` | 键盘焦点环；与暖色状态有明确区别 |

原小程序的 `#C96D32` 配白字不满足普通小字的 AA 对比目标，因此它保留为品牌面，交互按钮使用更深的 `#A94F1F`。

### Typography

- UI font stack: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`。
- 首页品牌标题使用现有 PNG；不得下载或假设用户安装特定字体。
- Display: `clamp(40px, 4vw, 64px)`，line-height `1.08`，letter-spacing `-0.02em`。
- Page title: `32px/1.2`, weight `700`, letter-spacing `-0.015em`。
- Section title: `22px/1.3`, weight `700`。
- Body: `16px/1.65`, weight `400`。
- UI label: `14px/1.4`, weight `600`；需要紧凑识别时 letter-spacing `0.01em`。
- 不为所有字号设置同一个 letter-spacing；字号越大越紧，小字号保持接近零。

### Spacing, shape and elevation

- Spacing scale: `4, 8, 12, 16, 24, 32, 48, 64px`。
- Input radius: `10px`；button radius: `14px`；card radius: `22–24px`；chip: `999px`。
- Card border: `1px solid var(--color-border)`。
- Card shadow: `0 12px 32px rgba(116, 72, 20, 0.07)`。
- Hover shadow: `0 16px 38px rgba(116, 72, 20, 0.11)`。
- 不用阴影代替边界；表格和密集后台优先用边框与背景层级。

### Motion

- Press feedback: `transform: scale(0.98)`，`100ms ease-out`，在按下时立即开始。
- Hover lift: `translateY(-2px)`，`160ms ease-out`；表格行只变背景，不缩放。
- Route/content change: opacity + `translateY(6px)`，`160–200ms`，可随新输入中断。
- Dialog: 从当前触发区域轻微 `scale(.98 → 1)` 与 opacity 进入，`180ms`；退出沿相反路径。
- 不给普通点击使用弹跳；只有未来出现真实甩动/拖拽交互时才评估弹簧和速度继承。
- 只动画 `transform` 和 `opacity`；避免持续循环背景与大面积视差。

### Imagery and iconography

- 题目图片和嵌字笔记卡片图是内容，不裁切关键字形；默认 `object-fit: contain`。
- 列表缩略图允许 `cover`，但点击必须可查看完整原图。
- 图标使用统一的简洁线性 SVG；不要混用 Emoji、不同线宽图标和纯文字箭头。
- 图标按钮必须有可见 tooltip 和无障碍名称。

## Components

- Existing assets to reuse:
  - `hero-title-hanzipen.png`。
  - 当前难度名称、星级和 A–D 选项语义。
  - 当前暖色配色与卡片轮廓作为 token 来源。
- New/changed components:
  - `PublicShell`, `AdminShell`, `BrandHeader`。
  - `ActionCard`, `LevelCard`, `QuizProgress`, `QuestionMedia`, `AnswerOption`。
  - `ScoreSummary`, `WrongAnswerReview`, `ImageLightbox`。
  - `AdminSidebar`, `QuestionTable`, `QuestionForm`, `QuestionPreview`。
  - `StrategyMatrix`, `FontPresetEditor`, `SubmissionTable`。
- Variants and states:
  - `AnswerOption`: default, hover, focus-visible, selected, correct, wrong, disabled。
  - `Button`: primary, secondary, quiet, danger；每种都有 hover, active, focus, loading, disabled。
  - `Card`: static, interactive, selected；只有 interactive 变换位置。
- Token/component ownership:
  - 全局颜色、字号、间距和阴影由一个 CSS token 文件拥有。
  - Element Plus 只用于后台基础控件，并通过 token 覆盖贴合品牌；公开答题组件自行实现。
  - 首版不新增第二套设计系统，不引入 Tailwind 和 CSS-in-JS。

## Accessibility

- Target standard: WCAG 2.2 AA。
- Keyboard/focus behavior:
  - 所有功能可通过键盘完成，使用明确的 `:focus-visible` 双层焦点环。
  - DOM 顺序与视觉顺序一致；两栏布局不得通过 CSS 调换阅读顺序。
  - 对话框锁定焦点，`Esc` 关闭，关闭后焦点返回触发控件。
  - 答题快捷键不得拦截输入框中的按键。
- Contrast/readability:
  - 普通文字达到 4.5:1；大字和非文字控件至少 3:1。
  - 正确/错误状态同时使用图标、文字和颜色。
  - 题目图片加载失败时显示替代文字与重试入口。
- Screen-reader semantics:
  - 页面只有一个 `h1`；分区按层级使用原生标题。
  - 答案使用 radio group 语义；题号更新通过克制的 live region 宣告。
  - 表格使用真实 `table`、表头和分页标签。
- Reduced motion and sensory considerations:
  - `prefers-reduced-motion: reduce` 下移除位移和缩放，只保留不超过 `150ms` 的淡入淡出或静态切换。
  - `prefers-reduced-transparency: reduce` 下侧栏和 sticky chrome 使用不透明暖白背景并移除 blur。
  - `prefers-contrast: more` 下提高边框与文字对比，不通过更强阴影补偿。

## Responsive behavior

| Width | Behavior |
| --- | --- |
| `>= 1440px` | 完整 PC 布局，内容最大宽度限制，避免过宽行长 |
| `1024–1439px` | 保持两栏，缩小 gutter；管理侧栏保持可见 |
| `768–1023px` | 答题上下堆叠；管理侧栏改为抽屉；表格允许横向滚动 |
| `< 768px` | 保证 Web 可用但不作为主要体验；单列、全宽按钮、44px 触控目标 |

- Desktop hover 与 focus 状态同等设计；不能把信息只放在 hover 中。
- 触摸设备不使用 hover 位移，按钮最小目标尺寸 `44 × 44px`。
- 200% 浏览器缩放时允许从两栏降为单列，不出现遮挡或水平页面滚动。

## Interaction states

- Loading: 保留页面骨架和布局，使用静态 skeleton 或明确文字；不使用无限旋转的大型 loader。
- Empty:
  - 题库为空：“还没有题目” + “新增第一道题”。
  - 提交为空：“暂无提交记录”，不显示空表格分页。
  - 嵌字笔记配置为空：说明配置缺失，不伪造示例。
- Error: 错误靠近发生位置，保留用户输入；网络错误提供重试，不自动清空表单。
- Success: 保存后显示短暂但可感知的状态，并保持页面上下文；不依赖只出现一瞬的 toast。
- Disabled: 只用于确实不可操作的状态，并配原因；校验问题优先允许触发后解释。
- Offline/slow network:
  - 答题开始失败时不进入空白页面。
  - 已在本地选择的答案不因一次请求失败丢失。
  - 提交超时后先查询答题会话状态，避免用户重试造成重复提交。
  - 外部图片失败时，题目文字和选项仍可访问。

## Content voice

- Tone: 温和、直接、具体；面向答题用户可轻松，管理端保持简洁专业。
- Terminology:
  - 固定使用“题库”“题目”“难度”“正确答案”“题目解析”“提交记录”“嵌字笔记”。
  - 不把“保存”“提交”“发布”混用；题目编辑使用“保存”，答题使用“提交答案”。
- Microcopy rules:
  - 按钮使用动作 + 对象，例如“保存题目”“提交答案”“删除题目”。
  - 错误说明发生了什么以及下一步，例如“图片加载失败，请检查图片 URL 或重试”。
  - 不使用“操作失败”“未知错误”等无法行动的单独文案。
  - 管理端删除确认必须包含题干摘要。

## Implementation constraints

- Framework/styling system: Vue 3 + TypeScript + Vite；Vue Router；Element Plus 仅用于管理端；普通样式使用 scoped CSS 和共享 CSS tokens。
- Design-token constraints: 所有新增颜色和间距先映射到现有 token；不得在组件中散落近似橙色和米白色。
- Performance constraints:
  - 首页标题图继续使用本地压缩资产。
  - 题目和对照表图片设置尺寸占位，避免布局跳动；大图按需加载。
  - 管理端组件按路由拆包；公开答题端不加载整套后台组件。
- Compatibility constraints:
  - 支持当前稳定版 Chrome、Edge、Safari 和 Firefox。
  - 主体验为 PC 横屏；Web 手机布局只保证功能完整，小程序仍是主要移动端。
  - 外部图片只允许 HTTPS；图床直链规则另行确认。
- Test/screenshot expectations:
  - 实现后至少保存 1440×900 的首页、难度、答题、结果、题库、题目编辑和嵌字笔记截图基线。
  - 额外验证 1024px、768px、200% 缩放、键盘-only、减少动态效果和图片失败状态。
  - 视觉验收先以本文件为合同；如提供正式参考图，再启动像素级视觉匹配流程。

## Open questions

- [ ] 确定 `pan.yurucamp.cn` 的上传协议、稳定直链格式、重定向和防盗链规则 / owner: 项目方 / impact: 题目编辑图片控件与迁移工具
- [ ] 提供嵌字笔记首批图片、标题和排列顺序 / owner: 项目方 / impact: `/font-reference` 卡片内容
- [ ] 确定正式 Web/API 域名及备案中转拓扑 / owner: 运维 / impact: 环境配置、CSP 和小程序合法域名
- [ ] Web 原型完成后确认 1440×900 视觉基线 / owner: 项目方 / impact: 进入正式 UI 实现与视觉验收

## 批量制题工作区（2026-09-09）

- 路由：`/admin/questions/batch`；入口位于题库和新增题目页。保留原有逐题编辑方式。
- 使用场景：电脑上从多页漫画手动框选矩形区域，一框一题，逐题判断字体与解析，分次入库。
- 工作区采用页面列表、漫画画布、当前题编辑三栏；隐藏常驻管理侧栏，保留返回题库入口。左栏 160px、右栏 320px，中间填满；左侧页面列表和各栏独立滚动。编辑栏只显示表单，不显示重复的裁图预览。
- 1200px 以下页面列表折叠；760px 以下通过漫画／当前题目切换，保证窄屏和浏览器放大时功能可达。首版主要服务桌面鼠标键盘。
- 配色沿用现有设计变量；画布使用中性灰 `#e8e7e4`，避免与白色漫画页面混淆。区域状态有文字，不能只依靠颜色。
- 区域支持连续框选、移动、四角调整、方向键微调和删除。获取画布焦点不能引起自动滚动；缩放仅改变展示，裁图按原图像素输出 PNG。
- 默认题干与二星难度沿用单题编辑；批次默认难度只影响之后新题。答案不会自动继承；选择已有字体时，当前批次上一个同字体解析作为临时建议，按 Tab 采用。修改已完成题目后必须重新确认。
- 检查页按答题端样式显示题干、题图、选项和解析，支持选择已完成题目分次入库，显示待补充和逐题结果；需要调整时通过显式“编辑区域”返回框选。待确认提交的题目锁定内容，重试相同请求；已入库题目通过题库编辑入口修改。
- 草稿和原图存入 IndexedDB，按管理员账号隔离；同批次使用浏览器锁避免多标签页覆盖。本机事务成功后才显示保存成功，失败时给出保留页面并重试的提示。
- 原图仅在本机保存；上传裁图后复用 URL，建题通过持久提交回执防重复。删除本机批次不删除已入库题目。
- 首版不包含自动识别、多区域拼图、遮挡、PDF/ZIP、跨设备草稿同步。真实样本已在隔离本地服务器和本地存储完成端到端验收；生产服务器、R2 和真实域名仍需单独验收。自动化回归继续使用合成图和模拟 API。
- 操作及验收说明：`docs/BATCH_QUESTIONS_ZH.md`。
