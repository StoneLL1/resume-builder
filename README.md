# resume-builder

<p align="center">
  <img src="cover.png" alt="resume-builder" width="720">
</p>

<p align="center"><em>turn your chaos into career ✨</em></p>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)
[![Multi-Agent](https://img.shields.io/badge/Runs%20on-Codex%20%7C%20OpenClaw%20%7C%20Hermes%20%7C%20Claude-22a7cc)](#哪个-agent-都能跑)

</div>

---

写简历最难的从来不是排版。

是你明明有一堆经历，却卡在一堆更烦的问题上：这条到底写不写？那个数字我记不清了，估一个会不会被发现？我根本不是这个专业的，怎么写才不会被 HR 一秒划掉？大部分简历工具只管给你套个模板，剩下这些真正费脑子的事，全丢给你自己。

`resume-builder` 是一个 **agent 无关**的中文简历 skill——Claude Code、Codex、OpenClaw、Hermes 都能跑。它不替你编故事，也不塞你一个花哨模板了事。它把"做一份简历"拆成九步，从选模板一直带到出 PDF。但它真正跟别的不一样的地方，就一点。

**它死活不肯编。**

---

## 先说最重要的：为什么是它

### 不编造，是写进流程里的，不是口号

每一条写进简历的事实，都得有出处。skill 会给每份简历建一张小表，叫 claim-map，长这样：

| 简历内容 | 来源 | 状态 |
|---|---|---|
| 某某大学 计算机本科 | 原 PDF / 你口述 | ✅ 已确认 |
| 实习绩效 年化 X% | 还没问清楚 | ⛔ 缺失阻塞 |
| 高数成绩 | 你说不写 | ➖ 已省略 |

四种状态：**已确认**才能写进简历，**待确认**先放一边，**缺失阻塞**必须停下来问清楚，**已省略**是你拍板不要的。

学校、公司、时间日期、绩效、规模、排名、star 数——这些"高危项"，只要不是你亲口确认过的，一律先标成 ⛔，然后它就停下来等你。你不给，它不动笔。

听着挺轴。但这正好挡住了 AI 写简历最容易出的车祸：把"参与"美化成"主导"，随手编一个"提升 30%"，把别人做的项目算到你头上。这些东西笔试看不出来，一面试全露。简历是写来经得起追问的，不是写给自己爽的。

### 一个目标，一份简历

它不搞"万能简历"那套。求职、比赛、升学，每个目的一份独立、能直接编译的文件夹。跟目标无关的经历，它会让你果断删，还告诉你为什么删。手上同时投三个方向？那就三份，分别打磨。通投一份是最蠢的，这点它比你坚持。

### 给不对口的经历找活路

不是科班、想转行、经历跟岗位八竿子打不着——这种情况它不装看不见。它会把旧经历里的可迁移能力挖出来，用目标领域的语言重新讲一遍：做实验摸出来的数据分析、为方便自己写的小工具、组织社团练出来的协调能力。

但这里有条硬线：**重包装 ≠ 编造**。它只用你确认过的事实重新组织措辞，绝不凭空给你加戏。

### 写作的底气：近百篇小红书实战经验

规则好定，难的是"到底怎么把一条流水账写成 HR 愿意看完的句子"。这部分它没靠拍脑袋——配套的 `writing-guide.md` 蒸馏自小红书上近百篇高赞的简历经验帖，全是真人投递、真人面试、真人复盘出来的干货：量化怎么估、STAR 怎么落到字面上、哪些词 HR 看一眼就烦、转行的人怎么把旧经历翻译成新语言。这不是哪个模型生成的泛泛而谈，是一堆踩过坑的人总结的。

### 一页纸优先

求职、比赛简历默认压成一页。不是信条，是现实：HR 一份简历看大概三十秒，信息密度比信息量重要。一页之内把最相关的卖点全摆出来，比写满两页更难，也更有用。

### 哪个 agent 都能跑

它不绑死在 Claude 上。skill 用的是标准的 AgentSkills `SKILL.md` 格式，任何能读 skill 的 agent 都能加载——目前实测 **Claude Code、Codex、OpenClaw、Hermes** 都能跑，原理上其它符合标准的 runner 也行。安装不挑 agent：把一句"fetch and follow"丢给你的 agent，它自己拉 `INSTALL.md`、按里面的步骤装好。具体见下面[安装](#安装)。

---

## 它能干什么（九步流水线）

1. **选模板** —— 先甩一张对照表给你挑，不替你决定。默认推荐 billryan 那套单栏、无照片的，走 ATS 招聘系统不容易被解析挂。
2. **收集** —— 读你的 PDF、粘贴的文字、口头说的，整理成素材库。Windows 终端的 GBK 报错它也帮你处理掉。
3. **确认目标** —— 到底是冲哪个岗位、哪个比赛、哪所学校。这个不清，后面全是白干，所以它先问清楚再动笔。
4. **筛选** —— 按目标挑相关项、砍无关项，给你一张"保留 vs 删掉"的对照表，每条都带理由。
5. **缺口提问** —— 缺的信息分优先级、成批地问你。优先问那些能明显抬升含金量的硬货：数字、对口项目、技能深度。你说"没有 / 跳过"，它就记下来，不再追着问。
6. **撰写** —— 只动用已确认的事实。每条经历必须量化（规模、比例、排名、star 数），用 STAR 或场景化写法，关键词和数据加粗，动词开头。
7. **编译** —— XeLaTeX 出单页 PDF。Windows 自带字体开箱即编，mac / Linux 有对应的字体替换方案。
8. **归档** —— 每个用途一个独立文件夹，交付的 PDF 和中间素材分开放。原始模板始终不被动，谁也不许弄脏它。
9. **迭代** —— 按反馈改。事实缺了回收集，措辞烂了回撰写，LaTeX 报错直接修，不绕路。

---

## 它不做什么（边界很硬）

它只做中文（或双语）一到两页的求职 / 比赛 / 升学简历。下面这些，它直接告诉你超出范围，不硬上：

- 求职信、推荐信
- 作品集、个人主页、PPT
- 多页学术 CV（那种带完整 publications list 的教职 / 博后简历）
- 周报、研究计划这种非简历文档

不是做不到，是别在一个简历 skill 里指望它做。专精一件事，比啥都接、啥都半吊子强。

---

## 安装

agent 无关，任选其一。

**方法一（推荐，任何 agent 通用）：** 把下面这段原样粘给 Claude Code / Codex / OpenClaw / Hermes，它自己拉取 `INSTALL.md` 并按里面的步骤装好：

```text
Fetch and follow instructions from:
https://raw.githubusercontent.com/StoneLL1/resume-builder/main/INSTALL.md
```

**方法二（手动 clone）：** 把仓库丢进你 agent 的 skill 目录。Claude Code 的目录是 `~/.claude/skills`（或项目 `.claude/skills/`），其它 agent 的目录见 `INSTALL.md` 里的对照表。

```bash
git clone https://github.com/StoneLL1/resume-builder.git .claude/skills/resume-builder
```

装好之后跟 agent 说一句"帮我写简历"、"改简历"、"投 XX 岗位，要份简历"就行。触发词：简历、resume、CV、投简历、改简历。

前提是机器上有 XeLaTeX（装个 TeX 发行版即可，TeX Live 或 MiKTeX 都行）。详细的分 agent 目录、PowerShell / POSIX 命令、验证步骤都在 `INSTALL.md` 里。

---

## 目录结构

```
resume-builder/
├── SKILL.md                       # skill 主体：九步流程 + 全部规则
├── INSTALL.md                     # 多 agent 安装（fetch-and-follow 入口）
├── README.md                      # 你正在看的这个
├── cover.png
├── references/
│   ├── writing-guide.md           # 撰写方法论，蒸馏自近百篇小红书高赞经验帖
│   └── compile-guide.md           # XeLaTeX 编译、字体、单页排版、排错
└── example/
    └── resume-example.tex         # 一份脱敏的示例简历，照着抄结构
```

`SKILL.md` 里只有规则和流程，没有任何真实个人信息——这是刻意的。所有示例都是占位符：`{{姓名}}`、`(+86) 138-xxxx-xxxx`、`example@mail.com`、`某某大学`。你的真实数据只待在你自己的简历文件夹里，不会回灌进 skill。

---

## 模板对照

默认从 [awesome-resume-for-chinese](https://github.com/dyweb/awesome-resume-for-chinese) 合集里挑。选定时 skill 会 clone 对应仓库、读它的 README 和 `.cls`，再动手写。

| 模板 | 特点 | 适合 |
|---|---|---|
| **billryan/resume**（默认推荐） | 单栏、简洁、默认无照片 | 求职 / 比赛 / 升学通用 |
| Deedy-Resume-for-Chinese | 双栏、信息密度高 | 应届求职 |
| resume-ng | 高密度 + 好看 | 经历多的简历 |
| liweitianux/resume | 中英双语 | 双语简历 |
| luooofan/resume | billryan 的改良版 | 通用 |
| 考研复试专用模板 | 复试向 | 升学 |

> 走 ATS（招聘系统自动筛简历）的场景，认准单栏、无表格、无照片。双栏和花排版经常被解析器读错。

不喜欢 LaTeX 也行，合集里有 Markdown（pandoc 渲染）和 Typst 的路线，换了工具链 skill 也能跟着走。

---

## 两份参考文档

skill 主体尽量保持精简，重的东西拆进了 `references/`，需要时才加载：

- **`writing-guide.md`** —— 蒸馏自小红书近百篇高赞简历经验帖。涵盖撰写公式（量化铁律、STAR、场景化五步法、三要素）、结构与排序、技术岗 / 三无大学生 / 转行 / 运营 / 英文简历的分场景写法、JD 关键词匹配、排版红线、投递规范、交付前的检查清单。
- **`compile-guide.md`** —— XeLaTeX 工具链、Windows / macOS / Linux 三套中文字体方案、单页排版的边距与间距、预览渲染命令、常见报错排查。

---

## 常见坑

- 终端报 Unicode / GBK 错 —— 输出套一层 UTF-8。
- 中文不显示 —— 确认 `\usepackage{xeCJK}` 加上系统字体，且引擎是 xelatex，不是 pdflatex。
- macOS / Linux 报 `Cannot find font SimSun` —— SimSun 是 Windows 专有，换本地方案（macOS：Songti SC / Heiti SC；Linux：装 Noto CJK）。
- fontawesome 图标变方框 —— `fonts/fontawesome` 和 `fontawesome.sty` 得在同一目录，复制模板时别忘了带上。
- 超过一页 —— 先收紧间距和边距，再砍最不相关的经历，**别缩字号**。

---

## 给谁用

- 应届找工作、找实习，简历一片空白或者一团乱
- 打比赛、申请保研 / 考研复试，要做针对性简历
- 转行，旧经历不知道怎么往新方向上靠
- 就是单纯想要一份不花哨、经得起追问的单页 PDF

不适合：想要花哨设计感的（去找设计师模板）、要写英文长篇学术 CV 的、指望 AI 帮你把经历吹上天的。这三种，请出门左转。

---

## 致谢

模板来自开源社区，尤其 [billryan/resume](https://github.com/billryan/resume) 和 [dyweb/awesome-resume-for-chinese](https://github.com/dyweb/awesome-resume-for-chinese)。撰写方法论蒸馏自小红书上一批认真分享简历经验的原作者。封面那张手绘插画，是这套 skill 的脸面——"DELETE THE DEFAULT RESUME" 和 "CAFFEINE > TALENT"，大概就是它整个的脾气。

## License

MIT。
