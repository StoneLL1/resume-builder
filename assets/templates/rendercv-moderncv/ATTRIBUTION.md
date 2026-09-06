# RenderCV · ModernCV — 来源与接入说明

上游：[https://github.com/rendercv/rendercv](https://github.com/rendercv/rendercv)

固定 commit：`1d4b87bc427e4cf61c0ef49623c971b0e2224708`；入口来源：`src/rendercv/renderer/rendercv_typst/lib.typ`。

许可证：MIT，原文 / 状态见 LICENSE。上游作者、版权声明与依赖许可保持原文。

本地 template.typ 直接导入 upstream/layout.typ；原始源码与校验值见 manifest.source_files，完整接入差异见 upstream/changes.patch。RenderCV 另有主题原文与 theme.changes.patch。接入仅用于结构化内容、可编辑标记、可选字段与 Typst API 兼容，保持原字体与排版参数，不做跨语言或双语适配。

原版字体：Fontin / Font Awesome 7 Free / Font Awesome 7 Brands。开放字体从固定清单安装；系统字体使用本机合法安装版本，不再分发。上游未声明的字体保持原生默认设置。

画廊使用上游 `examples/John_Doe_ModerncvTheme_CV.pdf` 原始预览 的第 1 页栅格图。 来源、原文件与显示文件 SHA-256 见 manifest.preview_source。不会把上游示例人物、照片或联系方式注入用户简历。上游可选照片能力保留，当前 JSON 接入未提供照片字段。
