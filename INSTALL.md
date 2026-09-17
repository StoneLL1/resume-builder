# Install resume-builder

> 本文供执行安装的 Agent 读取。收到用户的安装请求后，自行完成环境探测、获取文件、部署 skill、准备依赖和验证；不要把下面的步骤原样转交给用户手动执行。

`resume-builder` 使用标准的 Agent Skills `SKILL.md` 格式。目标是让当前 Agent 能发现并加载它，且本地 Python、Typst 和开放字体通过运行时检查。写作流程见 [SKILL.md](SKILL.md)，产品介绍见 [README.md](README.md)。

## 1. 探测环境与安装位置

先检查当前操作系统、CPU 架构、Agent 类型、已配置的 skill 搜索路径，以及是否已安装同名 skill。优先使用用户指定的位置或当前环境明确配置的目录，不凭空猜测 runner 路径。

| Agent | 可使用的 skill 目录 |
|---|---|
| Codex | 用户级 `~/.agents/skills/`，或项目级 `.agents/skills/`；以当前环境实际加载配置为准。 |
| Claude Code | 用户级 `~/.claude/skills/`，或项目级 `.claude/skills/`。 |
| OpenClaw / Hermes | 读取该 Agent 的 runner 配置，使用其中的 skill 目录。 |
| 其他 Agent | 使用其支持的 Agent Skills 搜索路径或显式文件加载机制。 |

Codex 的目录说明见 [官方文档](https://developers.openai.com/codex/skills/#where-to-save-skills)，Claude Code 见 [官方文档](https://code.claude.com/docs/en/skills)。如果当前环境已经从 `~/.codex/skills/` 加载技能，可以沿用；不要为了匹配示例再装一份同名副本。

自动安装脚本覆盖 Windows x64 / ARM64、macOS Intel / Apple Silicon。清单不包含 Linux；在不支持的平台上说明具体缺口，不把 macOS 脚本当作通用 POSIX 安装器运行。

能从本机和上下文确定的事项自行处理。只有实际缺少访问权限、安装目录无法确定等影响执行的信息时，才向用户集中询问。

## 2. 获取并确认 skill 文件

**用户提供了本地项目时，优先使用该项目。** 找到这份 `INSTALL.md` 同级的 `SKILL.md`，将其所在目录记为 `SkillSource`。

只有需要从远端获取、且用户没有指定本地副本时，才将仓库克隆到一个新的暂存目录：

```sh
git clone --depth 1 https://github.com/StoneLL1/resume-builder.git "<新的暂存目录>"
```

检查仓库根目录；若 skill 被放在子目录中，再定位到实际入口。安装前必须确认以下组件存在：

```text
SKILL.md
references/Resume-Writing-Guide-LLM.md
scripts/bootstrap.ps1
scripts/bootstrap.sh
scripts/bootstrap_runtime.py
scripts/local_io.py
scripts/run.ps1
scripts/run.sh
scripts/serve.py
scripts/render.py
assets/runtime-manifest.json
assets/templates/registry.md
assets/typst-packages/
assets/web/gallery.html
assets/web/editor.html
```

如果拉取结果缺少这些组件，先检查是否选错目录、是否漏拿文件，或用户是否已提供完整本地副本。仍无法找到时，明确报告缺失项，不把不完整安装当作成功。

## 3. 部署到当前 Agent

目标目录统一命名为 `<skill搜索路径>/resume-builder/`，其下直接包含 `SKILL.md`、`scripts/`、`references/` 与 `assets/`。

- 目标与来源是同一目录时，直接使用，不复制到自身。
- 已安装且内容一致时，复用现有目录，继续依赖检查。
- 用户要求更新且目标已有文件时，先把原目录完整备份到 **skill 搜索路径之外**，保留本地改动，再更新目标。避免两份同名 skill 同时加载。
- 完整保留模板、`upstream/` 源码、差异补丁、Typst 包及其许可证。不要只复制 `SKILL.md`，也不要在安装时重新抓取或改造模板。
- 来源是 Git 仓库时不必复制 `.git/`；开发缓存、日志、`output/` 和用户简历用途目录不属于安装内容。真实简历目录不得覆盖或删除。

下面是**目标尚不存在时**的复制命令。占位路径由你根据探测结果替换，不要求用户填写。

Windows PowerShell：

```powershell
$SkillSource = '<实际 skill 源目录绝对路径>'
$SkillTarget = '<实际 skill 搜索路径>\resume-builder'
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Get-ChildItem -LiteralPath $SkillSource -Force |
    Where-Object { $_.Name -notin @('.git', 'output', '__pycache__', '.pytest_cache', '.playwright-cli', '.upstream-cache', '.preview-build') -and $_.Name -notlike '.matrix-*' } |
    Copy-Item -Destination $SkillTarget -Recurse
Set-Location -LiteralPath $SkillTarget
```

macOS：

```bash
skill_source="<实际 skill 源目录绝对路径>"
skill_target="<实际 skill 搜索路径>/resume-builder"
mkdir -p "$skill_target"
rsync -a --exclude='.git/' --exclude='output/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --exclude='.playwright-cli/' \
  --exclude='.upstream-cache/' --exclude='.preview-build/' --exclude='.matrix-*/' \
  "$skill_source/" "$skill_target/"
cd "$skill_target"
```

执行前检查来源中的额外目录；上面的通用排除项无法自动识别所有用户用途目录。复制后再次确认入口与组件位置。

## 4. 检查并安装依赖

所有命令从已安装的 skill 根目录执行，或改用脚本绝对路径。以 [runtime-manifest.json](assets/runtime-manifest.json) 中的固定版本、下载 URL 和 SHA-256 为准。

| 依赖 | 处理方式 |
|---|---|
| Python ≥ 3.10 | 复用已有兼容版本；找不到时，由系统对应的 bootstrap 安装用户级 Python。 |
| Typst | 由 bootstrap 安装清单中的版本，当前为 0.15.1。 |
| 开放字体 | 选定模板后用 `--template <ID>` 按需安装并校验；默认安装不下载字体。`--all-fonts` 才准备全部开放字体。 |
| 模板与 Typst 包 | 已随 skill 提供，保留本地文件及许可证。 |

不需要 Node.js、npm 或 XeLaTeX；日常脚本只使用 Python 标准库，不要额外创建前端工程或运行 `pip install`。

### Windows

先检查，只有缺失时再执行安装；安装失败时读取错误，修复可自行处理的网络、路径或环境问题后重试。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -Check
# 上一步报告缺失项时执行：
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

默认缓存：`%LOCALAPPDATA%\resume-builder\`。

### macOS

```bash
bash scripts/bootstrap.sh --check
# 上一步报告缺失项时执行：
bash scripts/bootstrap.sh
```

默认缓存：`~/Library/Application Support/resume-builder/`。

记录 bootstrap 输出的 **Python 解释器绝对路径、运行时目录和 Typst 路径**。托管安装不会保证全局 `python` 命令可用，后续用实际解释器执行脚本；PowerShell 调用带空格的程序路径时使用 `&`。

### 自定义缓存与下载镜像

| 环境变量 | 用途 |
|---|---|
| `RESUME_BUILDER_HOME` | 指定运行时缓存；安装和日后启动必须使用同一个值。 |
| `RESUME_BUILDER_DOWNLOAD_MIRROR` | 下载镜像前缀，可含 `{url}`，否则在前缀后追加原始 URL；失败后回退官方地址。 |
| `RESUME_BUILDER_TYPST` | 显式指定 Typst 可执行文件。 |

Windows 脚本也支持 `-RuntimeHome`、`-Mirror`，macOS 支持 `--runtime-home`、`--mirror`。按用户配置使用镜像，不修改清单来绕过哈希校验。已有有效缓存可直接复用。

### 按需字体、统一启动与离线安装

Windows 不要求全局 `python` 可用，统一使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run.ps1 bootstrap_runtime --template orange-chinese --check --json
# 缺开放字体时，去掉 --check 安装；缺系统字体时按错误处理。
powershell -ExecutionPolicy Bypass -File scripts/run.ps1 serve "<项目目录>"
```

macOS 对应为 `bash scripts/run.sh bootstrap_runtime --template orange-chinese --check --json` 和 `bash scripts/run.sh serve "<项目目录>"`。首次 bootstrap 完成后，launcher 会读取运行时记录的解释器。自定义 RuntimeHome 必须在安装和启动时保持一致。

仅大陆网络不保证 GitHub、raw.githubusercontent.com 或海外字体站可达。本项目没有内置经过运营商验证的国内镜像；代理环境变量也不覆盖 git clone 和安装说明入口。可用完整本地发布目录 + 离线 artifacts，避免临时寻找公共代理或修改哈希。

在能够获取依赖的机器上，使用实际 Python 准备目标平台的固定文件：

```sh
python scripts/prepare_offline.py --platform windows-x64 --all-fonts --output "<离线目录>"
# 只准备一套模板时把 --all-fonts 换为 --template orange-chinese。
# 加 --list 仅列出文件名、URL、校验值，不下载。
```

将离线目录连同完整 skill 发布目录传到目标机，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -OfflineDir "<离线目录>"
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -OfflineDir "<离线目录>" -Template orange-chinese
```

macOS 使用 `bootstrap.sh --offline-dir "<离线目录>"`，并选择对应的 mac-x64/mac-arm64 artifacts。`RESUME_BUILDER_OFFLINE_DIR` 也可指定目录。离线模式只读取本地文件并核验 SHA-256，缺文件时明确失败，不会退回联网；需准备的 Python 归档已包含在清单里。系统授权字体不包含在离线包中。保留第三方许可；不要把用户真实简历放进分发包。

### 原版系统字体

基础 bootstrap 检查不包含系统字体；指定 `--template <模板ID> --check` 时会检查该模板要求的原版字体。Miku CV 需要 Segoe UI Emoji，Unique CV 需要 KaiTi，SweetGargamel 需要 Times New Roman 和 STKaiti；使用本机已合法安装的字体，不随 skill 复制分发，也不静默替换字体。

安装结果中注明尚未满足的模板字体依赖；制作简历时，只检查用户所选模板的实际渲染。完整对应关系见 [模板注册表](assets/templates/registry.md) 和 [运行时说明](assets/runtime-NOTICES.md)。

## 5. 验证安装

完成以下检查后，才能报告安装完成：

1. `SkillTarget/SKILL.md` 存在，frontmatter 的 `name` 为 `resume-builder`；当前 Agent 能发现或显式加载该文件。
2. 第 2 节的组件检查通过，`assets/templates/` 中中文与英文各有 9 套模板，预览文件齐全。
3. 用实际解释器执行基础运行时检查，退出码为 0，JSON 中 `ok` 为 `true`、`problems` 为空数组。此结果不等于所有模板字体已齐备；选定模板后必须用 `--template <ID>` 检查。

```sh
# python 代表上一步确定的实际解释器；macOS 可能是 python3 或托管路径。
python scripts/bootstrap_runtime.py --check --json
```

如果技能未被自动识别，检查实际搜索路径和同名冲突；需要新会话或重启 Agent 才能加载时，明确告知用户。

用户仅要求安装时，到此即可。需要进一步验证渲染时，在 skill 之外创建临时用途目录，读取 [数据契约](references/data-contract.md)，使用明确标注的虚构数据与字体已满足的模板生成一页简历，再执行：

```sh
python scripts/render.py "<临时用途目录>" --json
```

核对 `ok`、实际页数和生成页面，不使用用户真实资料，不声称一次渲染已验证所有模板或平台。

## 6. 简短交付，然后进入正常使用

向用户报告：**安装位置、入口是否可加载、运行时检查结果，以及仍缺少的依赖（如有）**。给出一句开始使用的示例即可，不把整套安装日志贴回去。

```text
帮我针对这个岗位做一份简历。我有一些经历，但不知道怎么写，缺什么你主动问我。
```

用户开始制作时，读取 [SKILL.md](SKILL.md)，先进入对话收集与撰写阶段：主动追问目标、职责和证据，按优先级分批补齐信息；用户说“跳过 / 没有”就接受。素材和内容充分后，才按 [模板选择流程](references/template-selection.md) 启动本地画廊并等待用户选择。

安装本身不需要启动用户简历网页，也不需要用户先提供个人信息。之后的本地服务只监听 `127.0.0.1`；打开服务日志中带会话令牌的完整 URL，选模板后的内容适配、渲染与检查继续由 Agent 执行。
