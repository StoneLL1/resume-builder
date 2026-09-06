#import "@preview/fontawesome:0.5.0" as fa
// 小标题的蓝色
#let cv-blue = rgb(56, 115, 192)
// 日期的灰色
#let gray = rgb(128, 128, 128)

#let en-font = "New Computer Modern"
#let cn-font = "Source Han Serif SC"
#let cn-italic-font = "KaiTi"

#let font-list = (en-font, cn-font)
#let italic-font-list = (en-font, cn-italic-font)

#let project(
  name: "",
  body,
  font-list: font-list,
  italic-font-list: italic-font-list,
) = {
  // 标题
  set document(title: name)
  // 页边距设定
  set page(
    paper: "a4",
    numbering: none,
    margin: (top: 2cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  )
  set text(
    font: font-list,
    lang: "zh",
    region: "cn",
  )
  
  set par(
    justify: true,
    linebreaks: "optimized",
    leading: 0.8em
  )
  // 行间距
  // show par: set block(spacing: 1em)
  // 段间距
  
  show emph: it => [
    #set text(font: italic-font-list)
    #it
  ]
  show heading.where(level: 1): it => block(width: 100%)[
    #it
    #place(dy: 0.3em, left)[#line(length: 100%, stroke: 0.7pt + cv-blue)]
  ]
  show heading: set block(spacing: 0.72em)
  // 设置标题（名字）字体
  align(center)[
    #block(text(weight: 400, 2.4em, name))
  ]
  
  body
}

// 日期
#let date-style(y) = {
  set text(fill: gray)
  y
}

// 个人信息
#let info(phone: "", email: "", github: "") = {
  set align(center)
  grid(columns: 3, column-gutter: 5pt)[
    #fa.fa-phone() #phone
  ][
    #fa.fa-envelope() #email
  ][
    #fa.fa-github() #github
  ]
}

// 教育背景
#let education(
  school: [],
  major: [],
  degree: [],
  date: [],
  grade: [],
  English: [],
  body,
) = {
  [
    *#school*
    #h(10pt)#major
    #h(10pt)#degree
    #h(1fr) #date-style(date)
    
    #grade
    #h(10pt)#English
  ]
  body
}

#let prize(data) = {
  let cells = ()
  for d in data {
    cells.push(strong(d.at("game", default: "")))
    cells.push(strong(d.at("grade", default: "")))
    cells.push(date-style(d.at("date", default: "")))
  }
  [
    #v(-0.4em)
    #table(
      columns: (1fr, 1fr, auto),
      inset: (x: 0pt, y: 0.4em),
      stroke: none,
      ..cells,
    )
    #v(-0.4em)
  ]
}

// 项目经历
#let proj-exps(exps) = {
  let cells = ()
  for exp in exps {
    cells.push(strong(exp.at("name", default: [])))
    cells.push(strong(exp.at("type", default: [])))
    cells.push(date-style(exp.at("date", default: [])))
    cells.push(
      table.cell(
        colspan: 3,
        [
          #if "tech" in exp [
            #emph(exp.tech)
            #linebreak()
          ]
          #exp.at("description", default: [])
        ],
      ),
    )
  }
  [
    #v(-0.4em)
    #table(
      columns: (auto, 1fr, auto),
      column-gutter: 1em,
      inset: (x: 0pt, y: 0.4em),
      stroke: none,
      ..cells,
    )
    #v(-0.4em)
  ]
}
