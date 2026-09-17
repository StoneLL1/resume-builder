# 排版阶段（阶段 C / E）：模板适配、渲染与检查

> 读取时机：收到 `template_selected`（阶段 C）或 `template_change_requested`
> （阶段 E）事件后。此时 `session.json` 处于 `generating`，等待页向用户显示
> "生成中"——完成本文流程前不要切阶段。
> 写 `resume.json` 之前**必须**先读 `references/data-contract.md`（字段、ID、
> 行内格式、保存语义的权威描述）。本文路径相对 skill 根目录。

## 1. 第二轮精修（模板相关）

对阶段 A 的模板无关内容稿做**针对所选模板**的调整——这是两阶段撰写的第二阶段：

- **信息密度**：按模板风格（单栏密排 / 双栏 / 侧栏）调整每板块条目数与 bullet 长度。
- **条目顺序**：相关性排序微调（指南 Step 5 的结论不变，只做版面层面的微调）。
- **断行**：长 bullet 在模板版心宽度下的自然断点，避免一行挂两三个字。
- **页数**：目标 `page_target`（1 或 2），正式简历**不得超过 2 页**。

精修仍受写作指南约束：参照指南 §4 写清个人动作与证据，不机械补齐公式；措辞改动若涉及事实，回 claim-map 核对。

## 2. 写入 resume.json

- 结构、字段、ID 规则、受限行内格式（`**加粗**` 与 `[文字](url)`）见 data-contract.md；实现层校验在 `scripts/resume_model.py`。
- **`meta.template_id` 必须写入用户选定的模板 ID**：选择事件只写进 `session.json`，resume.json 里的 `meta.template_id` 是 Agent 的职责，漏写则渲染仍用旧模板。
- **同步目标语言**：读取选择事件的 `data.language_mode`（或 `session.selected_language`）。跨语言选择时先翻译 / 精修正文与标题并核对事实，再同时写入 `meta.language_mode`。只改语言标记不会翻译内容。中文原版模板仅支持 `zh`，英文模板仅支持 `en`；沿用原版字体与排版。
- 中文模板的修改限于内容、明确配置和兼容性修复；不要另写一套类似版式代替 `upstream/layout.typ`。
- 渲染会自动校验数据结构，正常流程无需另跑校验命令；需要单独定位数据错误时使用：
  ```bash
  python scripts/validate_project.py "<项目目录>"
  ```

## 3. 渲染

下文 `python` 指 bootstrap 输出的实际解释器绝对路径。Windows 可用 `powershell -ExecutionPolicy Bypass -File scripts/run.ps1 render "<项目目录>" --json`；macOS 可用 `bash scripts/run.sh render "<项目目录>" --json`。

首次使用某模板前，运行 `scripts/bootstrap_runtime.py --template <模板ID> --check --json`，缺开放字体时去掉 `--check` 安装；系统字体缺失需合法安装或由用户重选。不要在渲染服务和手动命令中同时编译。

- **服务在跑（正常情况）**：直接保存 resume.json 即可——服务监听文件 mtime 自动重渲染，渲染完浏览器自动刷新。Agent 不需要手动触发。
- 手动渲染 / 服务没跑（排错、CI）：
  ```bash
  python scripts/render.py "<项目目录>" --json
  ```
  输出 JSON 含实际页数、输出文件路径；Typst 编译错误会被格式化成中文提示（错误内容 + 位置）。

每次成功结果的 `build_dir` 指向 `<项目目录>/work/build/<revision>/`。`work/build/current.json` 指向当前成功版本，`work/render-result.json` 记录最近一次尝试（包括失败）。版本目录包含：`page-{n}.svg`（真实渲染预览）、`resume.pdf`、`layout-map.json`（点击热区，契约见 data-contract.md §8）。这些是中间产物，不是交付物。

## 4. 当前简历检查

首次生成、换模板或渲染环境变化后，查看全部页面；普通编辑后，只复核变化的内容和受影响的页面，包括分页变化波及的后续页。同一版本已检查通过，且内容、模板与渲染环境未变时，导出沿用检查结果；无法确认时查看最新页面。

1. **事实**：新增或改写的事实对照 claim-map——只有 ✅ 内容，无 ❓/⛔ 混入；已核对且未改变的事实不重查。
2. **表达**：确认改写后仍清楚呈现个人动作与证据，没有引入空话、重复或夸大，不重复给整份简历打分。
3. **排版**：打开需检查页面的 `build_dir/page-{n}.svg` 看实际图像（工具不能显示 SVG 时转为 PNG）。先看整页是否饱满均衡、重点突出，有无大块空白或第二页只剩几行；再看文字是否重叠、越界、缺字，标题是否与正文分离、断行是否零碎。不能仅凭编译成功或页数正确判断排版完成。
4. **页数与取舍**：实际页数符合约定的 `meta.page_target` 且 ≤ 2。超页或局部拥挤时，先删重复、精简措辞、合并同类信息，再取舍弱相关内容，保留核心成果和理解它所需的上下文。沿用上游字号与间距；内容量与模板不匹配时，向用户说明并建议调整页数或重选模板。
5. ATS 关注点（用户在意时）：PDF 文本可选中复制（渲染层已保证，抽查即可）。

页面明显过空时，回查素材中尚未表达的、已确认且相关的职责、方法、取舍或交付物。补充应增加有用信息或让事实更容易理解，不靠拉长句子、重复成果、堆技能或添加空泛自评凑行数。没有值得补充的内容，就保留自然留白。

发现明显版面问题就调整内容、重新渲染并复查受影响页面。以内容清楚、版面舒展饱满为完成标准，不追求机械填满每一行，也不为细微差异反复改写。

## 5. 完成放行

```bash
python scripts/session.py "<项目目录>" set-stage editor --note "排版检查完成"
```

浏览器无需手动刷新，会自动从等待页切到编辑器。然后读 `references/editor-stage.md`。

## 6. 阶段 E：用户在编辑器里换模板

用户点「切换模板」并选新模板 → `template_change_requested` 事件 → 阶段自动回 `generating`（页面回等待页）。Agent 侧：

1. `python scripts/wait_for_event.py "<项目目录>"`（默认三事件并等即可）。
2. 按 §1–§4 适配新模板并检查全部页面：不同模板的密度、断行、页数结论不通用，**不允许套用新模板直接放行**；未改动的事实无需重新核对。
3. 更新 `meta.template_id` 为新模板 ID；若目标语言变化，同时完成 §2 的内容语言处理。
4. 渲染检查通过后同样 `set-stage editor` 放行。

## 7. 排错

- 渲染失败先读取 `work/render-result.json` 和 `work/render-error.log`；页面展示完整错误并保留上次成功预览。服务健康时用页面重试，不要另起第二个编译进程。确认服务已经停止后才手动 `render.py --json`。
- Windows 接受 UTF-8（有/无 BOM）及带 BOM 的 UTF-16 JSON，推荐 UTF-8。保存采用同目录临时文件替换，避免写半截文件。
- Typst 每条命令默认最多 30 秒，超时会终止并显示原因；必要时设置 `RESUME_BUILDER_TYPST_TIMEOUT`（最大 300 秒），不要靠无限重试掩盖字体或模板错误。
- `generating` 且 JSON 仍是旧模板时，先完成当前选择的模板/语言适配；重试不会用旧模板绕过阶段检查。
- 模板能力对账（语言模式 / 页数目标不符）会在选择与渲染两处被拦（409 / RenderError），换能力匹配的模板或改 meta。
