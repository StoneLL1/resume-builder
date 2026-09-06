# 模板选择阶段（阶段 B）：启动画廊并获取用户选择

> 读取时机：Agent 判断素材与内容稿充分后（判据见 SKILL.md）。
> 本文路径均相对当前 skill 根目录；`<项目目录>` 指用途目录的绝对路径。
> 在 skill 根目录执行以下命令，或使用脚本绝对路径；脚本按自身位置定位模板等资源。

## 1. 事前准备（运行时与原版字体）

服务与渲染只依赖 Python 3（标准库）和 typst 可执行文件。首次使用先检查：

```bash
# Windows（检查；不带 -Check 则安装缺失项）
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -Check

# macOS
bash scripts/bootstrap.sh --check

# 通用（输出 JSON，Agent 可解析）
python scripts/bootstrap_runtime.py --check --json
```

- 安装走国内镜像可设 `RESUME_BUILDER_DOWNLOAD_MIRROR`，下载固定版本并校验 SHA-256，全部装到用户级目录，不需要管理员权限。
- typst 查找顺序：环境变量 `RESUME_BUILDER_TYPST` → 用户级缓存目录的 `bin/typst(.exe)`（bootstrap 安装位置，Windows 为 `%LOCALAPPDATA%\resume-builder\bin\`）→ 系统 PATH。
- 重复运行 bootstrap 不会重复下载已就位的依赖。原版系统字体依赖见 `assets/runtime-NOTICES.md`；缺失时保持模板不变，先解决准确字体依赖。

## 2. 执行顺序（固定，勿颠倒）

1. 告知用户："即将打开模板画廊，请选择一套模板，我会自动继续。"
2. **后台**启动本地服务——它会打开浏览器进入画廊：
   ```bash
   python scripts/serve.py "<项目目录>"
   ```
   - 只监听 `127.0.0.1`；默认端口 8765，被占时自动顺延尝试；随机会话令牌已注入 URL。
   - serve 启动时读取现有 `work/session.json` 恢复会话（模板选择、换模板、编辑中都会正确接续）；没有则从 gallery 阶段新建。
   - 需要不自动开浏览器的场景（如远程）加 `--no-open`。
3. **阻塞**等待用户选择（这一步必须在用户操作页面**之前**就位）：
   ```bash
   python scripts/wait_for_event.py "<项目目录>"
   ```
   - 默认等待 `template_selected` / `template_change_requested` / `editing_done` 三类；只等选择可加 `--types template_selected`。
   - **只等"新"事件**（以启动时刻为基线，不回放历史）。
   - stdout 输出一行 JSON 事件对象（人读信息在 stderr）：`{"seq":n,"type":"template_selected","data":{"template_id":"..."}}`。
   - 退出码：0 = 等到事件；124 = 超时（默认 3600s，`--timeout` 调整，0 为无限）；1 = 错误。

用户在画廊点「确认模板」→ 浏览器写入 `template_selected` 事件、阶段自动切到 `generating`（页面显示"生成中"等待页），wait_for_event 退出并交还控制权。

## 3. 画廊说明（回答用户疑问用）

- 中文、英文各 9 套。模板列表上方居中显示 Apple 风格的圆角玻璃态语言分段按钮，含滑动选中底托、键盘左右键 / Home / End 与减少动态效果支持。
- 中文 tab：OrangeX4、skyzh/chicv、JinBridger/chicv-cn、resume-ng、Miku、Qianxi、UniqueCV、Habaneraa、SweetGargamel 的原版排版库。英文 tab：5 个 RenderCV 主题、Basic Resume、ImpreCV、Modern CV、Index CV；Harvard 标记为「纯黑白」。
- `gallery_language` 决定分类，`languages` 决定内容兼容性：中文模板仅支持 `zh`，英文模板仅支持 `en`。本阶段不适配双语；旧 bilingual 项目须先确定中文或英文内容，再选择匹配模板。
- 预览来自对应实际模板：优先使用固定上游版本的原始预览图，须在 manifest 的 `preview_source` 标明路径与校验值；仅有 PDF 时栅格化其第 1 页。不得用中文示例生成英文卡片，不得用改写版预览冒充原版。
- 切 tab 只改变浏览分类，保留每组的临时选择；确认时提交模板和目标 `language_mode`。浏览不会改写或翻译简历。跨语言确认后 Agent 先处理内容语言，再排版检查。
- 清单、上游来源、许可证见 `assets/templates/registry.md`；每套模板目录含 LICENSE 与 ATTRIBUTION.md。
- **模板必须由用户选**，Agent 不替用户决定，也不催促；用户犹豫时可以按用途给倾向性建议（如 ATS 场景建议单栏），但最终选择权在用户。

## 4. 恢复场景（skill 再次被调用）

- 服务还在跑：直接执行 §2 第 3 步等待即可。
- 服务已关、且用户此前已选过模板：`python scripts/wait_for_event.py "<项目目录>" --history` 立即返回最近一条未消费的匹配事件（注意核对 `type` 与 `data.template_id`），然后重启服务继续阶段 C。

## 5. 拿到选择结果之后

事件 `data.template_id` 是用户选定的模板 ID，`data.language_mode` 是目标内容语言；服务将后者保存在 `session.selected_language`。Agent 完成对应语言的内容精修后，一起写入 `resume.json.meta.template_id` / `language_mode`。旧事件缺少语言字段时沿用现有内容语言并检查模板能力。读取
`references/rendering-stage.md`（连同 `references/data-contract.md`）继续阶段 C。
