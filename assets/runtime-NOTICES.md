# Runtime notices

开放字体和运行时安装在用户级缓存，不把二进制字体打包进 skill。精确 URL、版本 / commit、归档成员和 SHA-256 见 [runtime-manifest.json](runtime-manifest.json)。原版声明的字体缺失时报告具体名称，不用其他字体替代。

- Typst 0.15.1：Apache-2.0，[上游](https://github.com/typst/typst)。
- Python 独立运行时的版本、平台和许可见清单及 [上游](https://github.com/astral-sh/python-build-standalone)。
- New Computer Modern、Libertinus Serif、DejaVu Sans Mono 随 Typst 自带。

## 下载字体

| 字体 | 许可 / 来源 |
|---|---|
| Noto Sans SC | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/notosanssc/OFL.txt) |
| Noto Serif SC | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/notoserifsc/OFL.txt) |
| Raleway | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/raleway/OFL.txt) |
| Roboto | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/roboto/OFL.txt) |
| Inter | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/inter/OFL.txt) |
| Source Sans 3 | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/sourcesans3/OFL.txt) |
| EB Garamond | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/ebgaramond/OFL.txt) |
| Lato | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/lato/OFL.txt) |
| Font Awesome 6 Free Solid | [CC-BY-4.0](https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.7.2/LICENSE.txt) |
| Font Awesome 6 Brands | [CC-BY-4.0](https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.7.2/LICENSE.txt) |
| LXGW WenKai | [OFL-1.1](https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/OFL.txt) |
| IBM Plex Serif | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/ibmplexserif/OFL.txt) |
| IBM Plex Mono | [OFL-1.1](https://raw.githubusercontent.com/google/fonts/5e35378e6bda803962ee6fd257e444a7d459660d/ofl/ibmplexmono/OFL.txt) |
| Noto Sans CJK SC | [OFL-1.1](https://raw.githubusercontent.com/notofonts/noto-cjk/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/LICENSE) |
| Noto Serif CJK SC | [OFL-1.1](https://raw.githubusercontent.com/notofonts/noto-cjk/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Serif/LICENSE) |
| KpRoman | [OFL-1.1](https://ctan.org/pkg/kpfonts-otf) |
| KpSans | [OFL-1.1](https://ctan.org/pkg/kpfonts-otf) |
| Linux Biolinum O | [OFL-1.1](https://ctan.org/pkg/libertine) |
| Linux Libertine O | [OFL-1.1](https://ctan.org/pkg/libertine) |
| XCharter | [OFL-1.1](https://ctan.org/pkg/xcharter) |
| Source Han Sans SC | [OFL-1.1](https://raw.githubusercontent.com/adobe-fonts/source-han-sans/a4f7cf94edfb9d7ffbdfc4841de276358bd7e0f2/LICENSE.txt) |
| Source Han Serif SC | [OFL-1.1](https://raw.githubusercontent.com/adobe-fonts/source-han-serif/7889f11bf31170b5d092a083b357c8c8130f89e0/LICENSE.txt) |
| Fontin | [LicenseRef-exljbris-free-font](https://www.exljbris.com/fontin.html) |
| Linux Biolinum | [OFL-1.1](https://raw.githubusercontent.com/FileEye/linuxlibertine-fonts/895fdfaa3f4ce00b20f9074651ae76f20e8a9b92/OFL-1.1.txt) |
| Font Awesome 7 Free | [OFL-1.1](https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.3.1/LICENSE.txt) |
| Font Awesome 7 Brands | [OFL-1.1](https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.3.1/LICENSE.txt) |
| Font Awesome 6 Free | [OFL-1.1](https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.7.2/LICENSE.txt) |

Fontin 使用作者提供的原始 ZIP，下载与解压文件分别核验哈希；遵循 exljbris 的免费字体许可。部分保留字体供旧项目恢复使用，不用于替换当前原版字体。

## 本机原版字体

| 字体 | 使用模板 |
|---|---|
| KaiTi | uniquecv |
| STKaiti | sweet-gargamel |
| Times New Roman | sweet-gargamel |
| Segoe UI Emoji | miku |

上述字体使用本机合法安装的 Windows / Office 版本，不随 skill 复制或再分发。macOS 也需合法安装所选模板要求的准确字体。skyzh/chicv 的原文未指定 CJK 字体，保留原生默认行为。

## Typst 包

fontawesome 0.5.0 / 0.6.0 / 0.6.2、nerd-icons 0.2.0、cuti 0.2.1、linguify 0.5.0、scienceicons 0.1.0 固定在 assets/typst-packages/preview/。原始许可证随各包保存，URL 和归档校验值见 [packages.lock.json](typst-packages/packages.lock.json)。正式渲染走本地包目录。

Font Awesome 字体按 OFL 1.1；其 SVG 图标按 CC BY 4.0，代码按 MIT。nerd-icons 按 LGPL-3.0-or-later，其他包遵循各自 LICENSE / typst.toml。
