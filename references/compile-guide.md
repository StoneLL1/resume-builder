# 编译速查（resume-builder 配套）

> SKILL.md 第 7 步「编译单页」的完整版：XeLaTeX 工具链、中文字体、单页排版、预览与排错。

## 引擎
- **XeLaTeX**：`xelatex resume.tex`（**勿用 pdflatex**，中文与 fontawesome 会挂）。
- 成功判据：日志含 `Output written on resume.pdf (1 page)`。

## 中文字体（Windows 自带，开箱可编译）
```latex
\usepackage{xeCJK}
\setCJKmainfont[BoldFont=SimHei, ItalicFont=KaiTi]{SimSun}
\setCJKsansfont{SimHei}
\setCJKmonofont{FangSong}
```
> 不依赖 Adobe 字体。

### 非 Windows 字体替换
SimSun/SimHei/KaiTi/FangSong 是 Windows 专有；其它系统须换本地等价字体，否则报 `Cannot find font` 编译失败。

**macOS**（系统自带）：
```latex
\setCJKmainfont{Songti SC}
\setCJKsansfont{Heiti SC}    % 或 PingFang SC
\setCJKmonofont{STFangsong}  % 仿宋等价；或 Kaiti SC
```

**Linux**（先装 Noto CJK，如 `sudo apt install fonts-noto-cjk`）：
```latex
\setCJKmainfont{Noto Serif CJK SC}
\setCJKsansfont{Noto Sans CJK SC}
\setCJKmonofont{Noto Sans Mono CJK SC}
```

## 单页排版（收紧边距与标题间距）
```latex
\geometry{top=0.5in, bottom=0.4in}
\titlespacing*{\section}{0cm}{*1.0}{*1.0}
\titlespacing*{\subsection}{0cm}{*1.0}{*0.5}
```
**超一页**：先收紧 `\titlespacing` 与边距，再精简 bullet、合并或下移次要经历；**不缩字号**。

## 渲染预览发用户
```bash
pdftoppm -jpeg -r 130 resume.pdf preview && cp preview-1.jpg preview.jpg
```

## 排错速查
见 SKILL.md「常见坑」（终端 GBK 报错、中文不显示、fontawesome 变方框、超一页、非 billryan 模板适配）。
