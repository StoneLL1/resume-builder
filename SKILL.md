---
name: resume-builder
description: 中文简历制作流水线：为求职 / 比赛 / 升学新建、完善或重组中文简历，覆盖选模板→收集→筛选→撰写→XeLaTeX 编译单页 PDF→按用途归档，强调事实可溯源、不编造。触发词：简历、resume、CV、投简历、改简历。
---

# Resume Builder — 中文简历制作流水线

## 适用场景
用户要为某个具体目标（求职岗位 / 比赛 / 升学）制作中文简历，或要把不同用途的简历分文件夹管理。

## 能力边界（不做什么）
本 skill 只做**中文（或双语）1–2 页求职 / 比赛 / 升学简历**。明确不做：
- 求职信 / cover letter / 推荐信
- 作品集 / 个人主页 / PPT
- 多页学术 CV（教职、博后申请那种带完整 publications 的长简历）
- 非简历文档（周报、研究计划 RP 等）

遇到以上需求，明示用户超出范围，另寻工具。

## 核心原则
- **先选模板**：模板来自 [awesome-resume-for-chinese](https://github.com/dyweb/awesome-resume-for-chinese) 合集。动手前**先提示用户选择**，不默认替用户决定。
- **目标决定取舍**：每份简历围绕一个明确的「背景 + 目的」，与目标无关的经历果断舍弃并说明理由。
- **事实可溯源（重点）**：每条写入简历的内容都要有来源；高危信息缺失就**阻塞提问**，不脑补、不偷偷删除、不擅自升级措辞（如把"参与"写成"主导"）。
- **迁移性重包装**：非对口经历挖掘可迁移能力（科研→建模、工具开发→工程能力），用目标领域语言重新表述。**重包装 ≠ 编造**，必须有事实支撑。
- **提问驱动完善**：信息缺口分优先级提问补全；用户说"跳过 / 不用"就不再追问。
- **零敏感信息泄露**：本 skill 文件中不得出现任何真实个人数据；示例一律占位符 / 脱敏匿名（见 `example/`）。
- **单页优先**：求职 / 比赛简历默认控制为一页。

## 事实与防幻觉（claim 追溯）
为防止编造，每份简历在 `<用途>/work/claim-map.md` 维护一张**轻量三列表**，贯穿收集→撰写全过程：

| 简历内容 | 来源 | 状态 |
|---|---|---|
| 某某大学 某专业本科 | 原 PDF / 用户口述 | ✅ 已确认 |
| Qlib A股因子回测 年化 X% | （待用户给出） | ⛔ 缺失阻塞 |
| 某某公司 实习 | 用户确认 | ✅ 已确认 |
| 高数成绩 | 用户说不写 | ➖ 已省略 |

**四态：**
- ✅ **已确认** — 可写入简历
- ❓ **待确认** — 暂不写入，等用户确认后再用
- ⛔ **缺失阻塞** — 高危且缺失，**必须先问清楚才能动笔**
- ➖ **已省略** — 经用户同意不写

**高危类目**（这些项要么确认、要么经用户同意省略，绝不猜、绝不偷删）：
身份信息 · 学历 / 学校 · 雇主 / 公司 · 时间日期 · 论文 / 专利 · 量化数字（绩效、规模、排名、star 数）· ATS / 照片取舍

**规则：**
- 撰写**只能用「已确认」事实**；高危项处于「缺失阻塞」时，先提问解决再写。
- 凡高危类目的省略，须用户明确同意并记为「已省略」。
- 不脑补、不擅自升级或泛化措辞。

## 九步流程

### 1. 选择模板（最先做）
模板源自 [awesome-resume-for-chinese](https://github.com/dyweb/awesome-resume-for-chinese) 合集。**先把对照表给用户选**：

| 模板 | 仓库 | 特点 | 适用 |
|---|---|---|---|
| **billryan/resume** ⭐推荐 | github.com/billryan/resume | 单栏简洁，无照片默认 | 求职 / 比赛 / 升学通用 |
| Deedy-Resume-for-Chinese | github.com/dyweb/Deedy-Resume-for-Chinese | 双栏高密度 | 应届求职 |
| resume-ng | github.com/fky2015/resume-ng | 高信息密度 + 美学 | 信息量大的简历 |
| liweitianux/resume | github.com/liweitianux/resume | 中英双语 | 双语简历 |
| luooofan/resume | github.com/luooofan/resume | billryan 改良 | 通用 |
| resume-template-postgraduate | github.com/kodyyu1126/Chinese-resume-template-postgraduate | 考研复试专用 | 升学 |

> 求职场景若对方用 ATS（招聘系统）筛选，优先选**单栏、无表格、无照片**的模板（billryan / luooofan），避免双栏或复杂排版被解析错。
> 非 LaTeX 路线（合集也有）：Markdown 类（pandoc 渲染）、Typst（`OrangeX4/Chinese-Resume-in-Typst`）。选这些则工具链换 pandoc / typst，不用 xelatex。

**选定后统一拉取**：无论选哪个（含 billryan），先 `git clone` 对应仓库到工作区（如 `templates/<name>/`），读其 README 与 `.tex`/`.cls` 摸清命令，再进入后续步骤。若工作区已有该模板文件夹（如 `resume-0.1.0/`），可直接复用、不必重复 clone。后续撰写/排版以 billryan 为例，换模板按所选模板适配。

### 2. 收集
读取基础信息（PDF / 粘贴文字 / 口述）。PDF 用 `pdfplumber` 提取——Windows GBK 报错需：
```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```
整理成 `<用途>/work/信息整理.md`（素材库），并**同步初始化 `<用途>/work/claim-map.md`**，把已知事实按四态登记。

### 3. 确认目标
明确「背景 + 目的」：求职（什么岗位）/ 比赛（什么赛题方向）/ 升学。决定第 4 步取舍与第 6 步关键词侧重。**目标不清先问清楚再动笔**。

### 4. 信息筛选
按目标挑相关项、舍弃无关项。给用户一张「保留 vs 舍弃」对照表并说明理由。**高危项若缺失，在 claim-map 标为 ⛔ 缺失阻塞**。

### 5. 缺口提问
针对缺口分优先级（⭐⭐⭐ / ⭐⭐ / 次要）**批量**提问，优先解决 ⛔ 缺失阻塞 项：
- 优先问能显著提升含金量的硬信息（绩效数字、对口项目、数理基础、技能深度）。
- **量化 > 形容词**：引导给数字（年化、夏普、排名、规模、star 数）。
- 用户说"没有 / 跳过"就接受，把该项记为 ➖ 已省略，不反复追问。
- 用户每答一条，及时更新 claim-map 状态。

### 6. 设计撰写（以 billryan 为例）
**只能动用 claim-map 中 ✅ 已确认 的事实。** 参照 `example/resume-example.tex`，命令：
- 姓名/联系方式：`\name{}` + `\basicInfo{}`；图标 fontawesome（`\faGraduationCap` `\faFlask` `\faBriefcase` `\faCogs` `\faHeartO` `\faUsers` `\faInfo`；联系方式 `\phone{}` `\email{}` `\github[显示]{url}`）。
- 经历：`\datedsubsection{标题}{日期}` + `\role{角色}{备注}` + `\begin{itemize}` 成果导向 bullet。
- 技能 / 荣誉：itemize 或 `\datedline{条目}{日期}`。

**经历撰写公式**（决定含金量，完整公式表与改写示例见 `references/writing-guide.md` 第一节）：每条必须**量化**（规模 / 比例 / 排名 / star 数，**裸描述 ≈ 没写**）；用 **STAR / 场景化五步法 / 三要素**（覆盖"做了什么 + 怎么做 + 结果"）；关键数据与关键词**加粗**、动词开头、每条 ≤ 2 行。

**结构与排序**：基本信息（**只写四样**：姓名 / 电话 / 邮箱 / 求职岗位）→ 教育（倒序）→ 自我评价（可选，仅当有 JD 强相关卖点时写，宽泛优点不如不写）→ 经历 → 项目 → 技能/证书。优先级 **实习 > 项目 = 科研 > 校园**；最新在前；**与目标最相关的经历可提前**，不严格按时间。

### 7. 编译单页（billryan 工具链）
引擎 **XeLaTeX**（`xelatex resume.tex`，勿用 pdflatex），成功判据为日志含 `Output written on resume.pdf (1 page)`。中文字体、单页排版（`\geometry` / `\titlespacing`）、预览渲染与排错的**完整代码块见 `references/compile-guide.md`**。要点：超一页先收紧间距 / 砍经历，**不缩字号**。

**交付前检查清单（编译通过、投递前逐条打勾，全绿再交付；详版见 `references/writing-guide.md`）**：
- [ ] 一页纸、最多两种字体/颜色，黑白上下结构、对齐、留白合理
- [ ] 求职岗位明确写了一个（不是"都可以"）
- [ ] 基本信息：姓名 + 电话 + 邮箱 +（求职岗位）
- [ ] 每段经历都有量化数据，关键词已加粗
- [ ] 与目标无关的经历已删除或缩减为一句
- [ ] 无错别字、无技术/专业名词拼写错误（至少通读 3 遍）
- [ ] 写上去的经历与技能面试都能讲清、数据经得起追问

### 8. 按用途归档（work / output 分离）
每个用途一个**独立可编译**文件夹，分最终交付与中间产物：
```
<用途>/
├── resume.tex          ← 最终交付（源文件）
├── resume.pdf          ← 最终交付（编译产物）
├── preview.jpg         ← 预览
├── resume.cls / fonts / fontawesome …  ← 模板依赖（复制自带）
└── work/               ← 中间产物（轻量工作区）
    ├── 信息整理.md     ← 素材库
    └── claim-map.md    ← 事实追溯表
```
- 做法：把所选模板文件夹整个复制为目标文件夹，再覆盖其中的 `resume.tex`。
- **原始模板文件夹（`resume-0.1.0/` 等）始终保持不变**——任何产物只进用途文件夹。
- 编译中间文件（`.aux` / `.log` / `.out`）编译后清理，保留 `.pdf`。交付以 `resume.pdf` 为准，不单独交付源文件。

**对外投递命名**：源文件保持 `resume.tex` / `resume.pdf`，但**投递副本**重命名为 `姓名-目标岗位-电话.pdf`（示例 `张三-后端开发-138-xxxx-xxxx.pdf`），别叫"我的简历.pdf"。投递用 PDF 不用 Word。

### 9. 迭代
按反馈或新信息更新对应用途文件夹的 `resume.tex`（并同步 claim-map），重新编译，再发预览。
- **事实阻塞** → 回到收集 / 提问补全；
- **措辞 / 模板问题** → 回到撰写；
- **LaTeX 报错** → 直接修，不涉及新事实时无需回流。

**新增用途**：复制模板文件夹 → 改名 → 编辑 `resume.tex` → 编译。

## 信息安全（硬性要求）
- 本 skill 目录、`example/`、以及任何"模板 / 示例 / 流程"文件中，**不得出现真实姓名、电话、邮箱、学校、公司等个人数据**。一律占位符：`{{姓名}}`、`(+86) 138-xxxx-xxxx`、`example@mail.com`、`某某大学`、`xx 科技有限公司`。
- 用户真实数据只存在于其自己的用途文件夹简历中，**不回灌进 skill**。

## 常见坑
- 终端 Unicode/GBK 错误 → 输出包一层 UTF-8（见第 2 步）。
- 中文不显示 → 确认 `\usepackage{xeCJK}` + 上述系统字体，且引擎是 xelatex。
- **非 Windows 报 `Cannot find font SimSun`** → 换本地等价字体（macOS Songti SC / Heiti SC / STFangsong；Linux Noto CJK），完整对照见 `references/compile-guide.md`。
- fontawesome 图标变方框 → 确认 `fonts/fontawesome` 与 `fontawesome.sty` 在同目录（复制模板时带上）。
- 超一页 → 先收紧 `\titlespacing` 与边距，再砍最不相关的经历，不缩字号。
- 换了非 billryan 模板 → 该模板 `.cls`/命令不同，务必先读它的 README 和示例 `.tex` 再写。
- **编造陷阱** → 凡是 claim-map 里不是 ✅ 已确认 的内容，尤其高危类目，一律不写入；宁可留空提问。
