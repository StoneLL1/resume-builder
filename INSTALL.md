# Install resume-builder

resume-builder 不挑 agent——Claude Code、Codex、OpenClaw、Hermes 都能用。整个仓库根目录就是 skill 文件夹本身（`SKILL.md` 在根目录），用的是标准的 AgentSkills `SKILL.md` 格式。任何能读 skill 的 agent 都能加载它。

下面这套流程你不用手动照着敲——把文末那句 "fetch and follow" 丢给你的 agent，它自己拉这份文档、按里面的步骤装好。

## 支持的 agent

- Claude Code
- Codex
- OpenClaw
- Hermes
- 其它能读 `SKILL.md`、或能按指令拉取并执行安装的 agent

## 模板不随仓库走

仓库里没有几百 M 的字体和模板依赖。skill 运行时按你选的模板，从 [awesome-resume-for-chinese](https://github.com/dyweb/awesome-resume-for-chinese) 现拉对应仓库。所以安装只管把 skill 文件夹放到位。

## 各 agent 的 skill 目录

| Agent | 默认 skill 目录 |
|---|---|
| Claude Code | `~/.claude/skills`（用户级）或项目 `.claude/skills/` |
| Codex | `~/.codex/`（通过 `AGENTS.md` 接入） |
| OpenClaw | 该 agent 配置的 skill 目录（runner 自检或问用户） |
| Hermes | 该 agent 配置的 skill 目录（runner 自检或问用户） |

目录拿不准的时候，agent 会自己探测 runner 配置，或直接问你，不硬猜。

## 依赖

| 依赖 | 是否必需 | 用途 |
|---|---|---|
| `xelatex`（TeX Live / MiKTeX） | 必需 | 编译出最终的单页 PDF |
| 运行时模板 | 运行时拉取 | skill 按所选模板 `git clone` 对应仓库 |

## 安装步骤

1. 把仓库 clone 到目标 agent 的 skill 目录下：
   `git clone https://github.com/StoneLL1/resume-builder.git <skill目录>/resume-builder`
2. 确认 `xelatex --version` 能跑。没有就装一个带 XeLaTeX 的 TeX 发行版。
3. 让 agent 读 `resume-builder/SKILL.md`，然后说一句"帮我写简历"试试。

## PowerShell 示例

```powershell
$SkillDir = "<你的 agent skill 目录绝对路径>"
git clone https://github.com/StoneLL1/resume-builder.git "$SkillDir\resume-builder"
xelatex --version   # 没有就: winget install --id MiKTeX.MiKTeX -e --accept-package-agreements --accept-source-agreements
```

## POSIX 示例

```sh
SKILL_DIR="<你的 agent skill 目录绝对路径>"
git clone https://github.com/StoneLL1/resume-builder.git "$SKILL_DIR/resume-builder"
xelatex --version   # macOS: brew install --cask mactex-no-gui ; Linux: sudo apt-get install -y texlive-xetex texlive-lang-chinese
```

## Copy/Paste：丢给 agent 自己装

把下面这段原样粘给 OpenClaw / Hermes / Codex / Claude Code 任一 agent：

```text
Fetch and follow instructions from:
https://raw.githubusercontent.com/StoneLL1/resume-builder/main/INSTALL.md
```

## 简单验证

装完让 agent 跑一次：给它一句"用占位符数据生成一份示例单页简历 PDF"。能编译出 1 页 PDF、日志里含 `Output written on resume.pdf (1 page)`，就算装好了。
