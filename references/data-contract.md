# resume.json 数据契约（v2，schema_version = 1）

本文档是 resume-builder v2 数据层的唯一权威描述。Agent（对话侧）与网页编辑器
共同读写同一份 `resume.json`，双方都必须遵守本契约。实现见
`scripts/resume_model.py`，校验 CLI 见 `scripts/validate_project.py`。

- 单一事实源：`<项目目录>/resume.json`。
- 保存语义：校验通过才写盘；原子写入；后保存者生效（不实现冲突合并）。
- 所有用户文本**只能**携带两种行内格式（见 §5），其余按纯文本处理。

---

## 1. 顶层结构

```jsonc
{
  "schema_version": 1,                    // 固定 1；契约升级时递增
  "meta":     { ... },                    // 简历定位与排版目标（§2）
  "basics":   { ... },                    // 姓名与联系方式（§3）
  "sections": [ ... ]                     // 有序板块列表（§4）
}
```

## 2. meta

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `purpose` | string | ✅ | `job` \| `competition` \| `academic` |
| `target_position` | string | ✅ | 目标岗位/方向，非空。用于 Agent 写作定位与导出文件名 |
| `language_mode` | string | ✅ | `zh` \| `en` \| `bilingual`（语义见 §6） |
| `page_target` | int | ✅ | `1` 或 `2`。实际页数由渲染决定，超出时 Agent 负责精简 |
| `template_id` | string | ✅ | 非空，对应 `assets/templates/<id>/`（registry.md 为准） |

## 3. basics

画廊分类 `gallery_language` 属于模板 manifest，不是简历内容字段。中文模板仅支持 `zh`，英文模板仅支持 `en`；不做跨语言或双语模板适配。用户确认跨语言选模板时，选择事件携带 `language_mode`，Agent 处理实际正文后才更新 meta；切 tab 本身不修改 JSON。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 非空。中文或主显示名 |
| `name_en` | string | — | 历史可选拉丁字母名；当前单语内容整理到 name，见 §6 |
| `headline` | string | — | 一行头衔（如「后端开发 · 校招候选人」） |
| `contacts` | array | — | 联系方式，有序，模板按序单行渲染 |

`contacts[]` 条目：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 稳定 ID（§7），如 `contact-phone` |
| `type` | string | ✅ | `phone` \| `email` \| `link` \| `location` \| `custom` |
| `label` | string | — | 展示前缀（如「电话：」）。无 label 则只渲染 value |
| `value` | string | ✅ | 非空。`link` 类型建议裸域名形式（`github.com/xxx`），不要带 `https://` 前缀 |

约束：`type=phone` 最多一个（导出文件名取第一个 phone）。

## 4. sections 与 entries

`sections` 是非空有序数组，顺序即渲染顺序（Agent 按写作指南决定）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 稳定 ID（§7），如 `sec-education` |
| `type` | string | ✅ | `education` \| `experience` \| `project` \| `skill` \| `award` \| `custom` |
| `title` | string | ✅ | 板块显示标题，非空，由 Agent 撰写（如「实习经历」） |
| `entries` | array | — | 有序经历列表，可为空（如纯 custom 板块标题下无条目的场景不存在——校验要求条目非空，见下） |

`entries[]` 条目：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 稳定 ID（§7），如 `edu-1` |
| `title` | string | — | 条目标题（机构/项目名），模板**无条件埋点**（空字符串也有热区） |
| `subtitle` | string | — | 副标题（专业/角色），空字符串 = 不渲染 |
| `date` | string | — | 时间段，格式自由但全简历统一（建议 `2024.06 – 2024.12`） |
| `location` | string | — | 地点，空字符串 = 不渲染 |
| `bullets` | array | — | 有序 bullet 列表 |

约束：entry 至少要有 `title/subtitle/date/location` 之一非空**或** `bullets`
非空，否则校验拒绝（完全空的条目没有可渲染内容）。

`bullets[]` 条目：`{ "id": "exp-1-b1", "text": "..." }`，`text` 非空。
Bullet 顺序即渲染顺序；网页编辑器支持同板块内增删与排序。

## 5. 行内格式（受限 Markdown）

所有用户文本字段（title、subtitle、bullets.text、headline、contacts 的
label/value、name）支持且仅支持：

| 写法 | 渲染为 | 说明 |
|---|---|---|
| `**文字**` | **文字**（加粗） | 用于关键词强调；写作指南约束使用频率 |
| `[文字](https://…)` | 链接 | 用于项目地址等。URL 内不能包含右括号或空白 |

- 不支持列表、标题、代码块、图片、表格等其他 Markdown 语法。
- 未配对的 `*`、`[`、`]` 等按字面渲染（转义层保证，见 §9）。
- 其余任何字符（含 CJK、emoji、数学符号）按原文渲染。

## 6. 语言模式

`meta.language_mode` 决定**排版行为**，不要求维护平行翻译字段：

- `zh`：仅用于中文分类，使用所选上游原版的字体与排版，不追加英文标题。
- `en`：仅用于英文分类，使用原版字体、大小写规则与排版。
- `bilingual`：只保留旧数据读取能力。当前正式模板不支持该模式，须由 Agent 先将内容整理为 zh 或 en，并同步 meta；不能仅改标记。

`name_en` 是历史可选字段，当前新建单语简历使用 `name` 作为展示姓名。恢复旧数据时应将拟展示的姓名整理到 name，不自动翻译或补造英文姓名。生成器内部的 `name-plain` 仅供上游 PDF 元数据和姓名格式函数使用，不是新的用户字段。

上游字体不能由数据层统一覆盖。skyzh/chicv 原文未指定 CJK 字体，保留 Typst 原生默认行为；其他模板使用各自声明的原字体。

## 7. 稳定 ID 规则

- 格式：`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`（字母数字开头，≤64 字符，
  允许 `-` 和 `_`）。
- **全局唯一**：contacts、sections、entries、bullets 的所有 ID 共用一个
  命名空间，重复即校验失败。
- **生命周期内不变**：ID 是热区映射（layout-map.json）、Agent diff、网页
  编辑定位的锚。改文案不改 ID；删除条目后其 ID 不复用。
- 命名建议（非强制）：板块 `sec-<类型>`，条目 `<板块缩写>-<序号>`（edu-1、
  exp-2），bullet `<条目ID>-b<序号>`，联系方式 `contact-<type>`。
- 派生 ID：模板对 entry 子字段使用 `<entryID>.title` / `.subtitle` /
  `.date` / `.location`；因此用户自定义 ID 里避免再使用 `.`（格式规则已排除）。

## 8. layout-map.json 契约（渲染产物，只读）

`scripts/render.py` 渲染后生成 `work/build/<revision>/layout-map.json`：

```jsonc
{
  "schema_version": 1,
  "pages": 1,
  "page_sizes": { "1": { "width": 595.28, "height": 841.89 } },  // pt，A4
  "fields": [
    { "id": "edu-1-b1", "kind": "bullet", "page": 1,
      "x": 41.5, "y": 190.2, "width": 551.8, "height": 11.4 }   // pt
  ]
}
```

- `kind`：`text` \| `contact` \| `section-title` \| `bullet` \| `entry`。
- `entry` 热区 = 条目全部子字段矩形并集（点击条目空白处选中整条）；编辑器
  命中多个热区时**取最小命中面积**。
- 坐标系：页面左上为原点，单位 pt，与 SVG `viewBox` 1:1（前端换算
  `scale = 显示宽 / page_sizes.width`）。
- bullet 热区通栏（宽 = 版心宽），便于点击行尾空白。
- 字段跨页时拆成两条记录（同 ID，不同 page）。
- 生成算法（anchor 换算、悬空兜底、同行中点切分）见 `scripts/render.py`
  坐标段注释；模板适配必须保持该埋点契约。

## 9. 安全与保存语义

- **Typst 注入防护**：所有用户文本经 `typst_escape` 转义 Typst 特殊标点
  （`\` `"` `'` `#` `$` `_` `[` `]` `(` `)` `@` `<` `>` `~` `+` `-` `/`
  `=` `*` 及反引号）。用户数据只能产生文字，不可能注入 Typst 代码或标记；
  链接 URL 走 Typst 字符串字面量转义。
- **生成物**：`work/build/<revision>/resume-data.typ` 由 `resume_data_literal()` 从
  resume.json 自动生成，禁止手改。
- **原子保存**（`save_resume`）：先校验 → 写同目录临时文件 → fsync →
  `os.replace`。中途断电/崩溃要么旧文件完好、要么新文件完整，不会出现
  半截 JSON。
- **损坏数据不覆盖有效内容**：校验失败抛 `ResumeModelError`（含中文行号
  与修复提示），原文件字节不变。load 端同样给出可展示的错误信息。
- **后保存者生效**：Agent 与网页并发修改不做合并，谁的保存晚谁生效；双方
  通过文件监听感知对方变更（网页侧，Batch 5）。

## 10. 校验清单（`resume_model.validate`）

1. 顶层是对象，`schema_version == 1`。
2. meta 五字段齐全且取值合法。
3. basics.name 非空；contacts 数组内条目结构合法；phone ≤ 1。
4. sections 非空数组；每段 type/title 合法。
5. entry 子字段类型正确且条目非空；bullet text 非空。
6. 全部 ID 格式合法且全局唯一。

CLI：`python scripts/validate_project.py <项目目录> [--strict]`，
退出码 0/1；渲染（`render.py`）内部强制同一套校验。

## 11. 导出命名

正式导出文件名：`姓名-目标岗位-电话.pdf`。
电话缺失时为 `姓名-目标岗位.pdf`；Windows 非法文件名字符替换为 `-`
（`resume_model.export_filename`）。
