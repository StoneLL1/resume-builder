# 当前模板注册表

中文与英文各 9 套。全部直接接入上游原版，中文仅 zh、英文仅 en；不相互适配，暂不提供双语模板。原字体、字号、纸张与排版参数保持上游设置。

## 中文模板

| ID | 名称 / 来源 | 固定版本 | 许可 | 原版字体 |
|---|---|---|---|---|
| `orange-chinese` | [Chinese Resume · OrangeX4](https://github.com/OrangeX4/Chinese-Resume-in-Typst) | `d2f85d4e63bf` | NOASSERTION | IBM Plex Serif、IBM Plex Mono、Noto Serif CJK SC |
| `chicv` | [Chi CV · 原版](https://github.com/skyzh/chicv) | `ab26f3d340ce` | MIT AND CC0-1.0 | Libertinus Serif、Linux Biolinum、CJK 沿用原生默认 |
| `chicv-cn` | [Chi CV · 中文版](https://github.com/JinBridger/chicv-cn) | `ecc6e73c9588` | NOASSERTION | Linux Biolinum O、Noto Serif CJK SC |
| `resume-ng` | [Resume NG](https://github.com/fky2015/resume-ng-typst) | `bc2d5ce0299b` | MIT | Noto Serif CJK SC |
| `miku` | [Miku CV](https://github.com/ice-kylin/typst-cv-miku) | `cca877aa3a86` | WTFPL | KpRoman、KpSans、Segoe UI Emoji、Source Han Serif SC、Source Han Sans SC |
| `qianxi` | [cv.typ · Qianxi](https://github.com/qianxi0410/cv.typ) | `05b6a604ae34` | MIT | LXGW WenKai |
| `uniquecv` | [Unique CV](https://github.com/gaoachao/uniquecv-typst) | `17927a9f7f67` | NOASSERTION | New Computer Modern、Font Awesome 6 Free Solid、Font Awesome 6 Brands、Source Han Serif SC、KaiTi |
| `habaneraa` | [Habaneraa · 一页简历](https://github.com/habaneraa/typst-resume-one-page) | `98aea62a4f37` | MIT | New Computer Modern、Noto Sans CJK SC、Noto Serif CJK SC、Source Han Sans SC、Source Han Serif SC |
| `sweet-gargamel` | [SweetGargamel · 中文简历](https://github.com/SweetGargamel/typst-resume-template) | `c57ebe3ddc64` | MIT | Times New Roman、STKaiti |

## 英文模板

| ID | 名称 / 来源 | 固定版本 | 许可 | 原版字体 |
|---|---|---|---|---|
| `rendercv-classic` | [RenderCV · Classic](https://github.com/rendercv/rendercv) | `1d4b87bc427e` | MIT | Source Sans 3、Font Awesome 7 Free、Font Awesome 7 Brands |
| `rendercv-moderncv` | [RenderCV · ModernCV](https://github.com/rendercv/rendercv) | `1d4b87bc427e` | MIT | Fontin、Font Awesome 7 Free、Font Awesome 7 Brands |
| `rendercv-harvard` | [RenderCV · Harvard](https://github.com/rendercv/rendercv) · 纯黑白 | `1d4b87bc427e` | MIT | XCharter、Font Awesome 7 Free、Font Awesome 7 Brands |
| `rendercv-ink` | [RenderCV · Ink](https://github.com/rendercv/rendercv) | `1d4b87bc427e` | MIT | EB Garamond、Font Awesome 7 Free、Font Awesome 7 Brands |
| `rendercv-opal` | [RenderCV · Opal](https://github.com/rendercv/rendercv) | `1d4b87bc427e` | MIT | Lato、Font Awesome 7 Free、Font Awesome 7 Brands |
| `basic-resume` | [Basic Resume](https://github.com/stuxf/basic-typst-resume-template) | `e7b02372015a` | Unlicense | New Computer Modern |
| `imprecv` | [ImpreCV](https://github.com/jskherman/imprecv) | `8d0a4c506c68` | Apache-2.0 | Libertinus Serif |
| `modern-cv` | [Modern CV](https://github.com/ptsouchlos/modern-cv) | `ff9c6164fa63` | MIT | Source Sans 3、Roboto、Font Awesome 7 Free、Font Awesome 7 Brands |
| `culemann-index` | [Index CV](https://github.com/davidculemann/typst-templates) | `cdc2313f5794` | MIT-0 | Roboto |

## 预览与迁移

画廊列表上方居中为 Apple 风格的圆角玻璃态中英文分段按钮；切换浏览不改正文，每组记忆选择。18 张画廊图均来自固定版本上游原图或原 PDF 的第 1 页，manifest 记录来源与校验值；不再展示统一脱敏内容的重渲染图。

旧自绘 / 退役模板不再接受选择。原版源文件在各目录 upstream/original/，接入差异在 upstream/*.patch。旧项目换到原版后必须重新检查事实、实际页数和布局；旧 bilingual / name_en 字段先整理为当前单语内容。

Harvard 提供原版纯黑白选项；Ink 保留原版紫墨配色，Basic Resume 保留作者示例的蓝色配色。系统字体依赖与开放字体来源见 [运行时说明](../runtime-NOTICES.md)。未提供明确许可证的三个指定中文仓库标记 NOASSERTION，详见各 LICENSE-STATUS.md。
