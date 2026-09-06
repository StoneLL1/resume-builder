#import "upstream/layout.typ" as upstream
#import "upstream/theme.typ": original-theme
#import "english-bindings.typ": render-english
#let render(resume) = original-theme(resume.basics.at("name-plain"), render-english(resume, upstream, "rendercv-moderncv"))
