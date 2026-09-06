#let delimiter = " | "
#import "@preview/cuti:0.2.1": show-cn-fakebold

#let array-to-str(a, delimiter: delimiter) = {
   a.join(delimiter)
}

#let resume-contacts(contact) = {
   set align(center)
   array-to-str(contact)
}
//用来说自己可以啥时候到岗的
#let time-info(content)={
  set align(center)
  text(size: 12pt, content)
}

#let item-list(key, value) = {
  // 使用就是传入一个键值对来处理
  // 例如 item-list(
  //   ("编程语言","C/C++、Python、Java"))
  // 渲染结果就是 strong{编程语言} ： C/C++、Python、Java
  strong(key) + "：" + value
}
// The project function defines how your document looks.
// It takes your content and some metadata and formats it.
// Go ahead and customize it to your liking!
#let project(title: "", author: (), times: none, contacts: (), body) = {
  // Set the document's basic properties.
  set document(author: author.name, title: title)
  set page(
    /// Margins of the page
  margin: (
    top: 1.2cm,
    bottom: 0.5cm,
    left: 1cm,
    right: 1cm,
  ),
  )

  // set text(font: "Linux Libertine", lang: "en")
  // set text(font: ("Times New Roman", "STKaiti"), lang: "zh")
  show: show-cn-fakebold
  set text(font: ("Times New Roman", "STKaiti"), lang: "zh")

// show strong: it => text(font: "Noto Sans CJK SC", weight: 700, it.body)
// show heading: it => text(font: "Noto Sans CJK SC", weight: 800, it.body)

  align(center)[
    #block(text(weight: 1000, 1.7em, strong(author.name)))
    #if times != none {
      v(-4pt)
      time-info(times)
    }
    #v(-4pt)
    #resume-contacts(contacts)
  ]

  // Main body.
  set par(justify: true)

  body
}

#let format-date(date) = {
  if type(date) == datetime [date.display()] 
  else if type(date) == str and date.len() == 0 [今] 
  else if type(date) == str {
    date
  } else {
    // todo panic
  }
}

#let resume-date(start, end: "") = {
  if start == "" and end == "" {
    "" 
  } else {
    format-date(start) + " " + $dash.en$ + " " + format-date(end)
  }
}

#let resume-item(left:"", right:"", body) = {
  text(size: 11pt, place(end, right))
  text(size: 11pt, left)
  linebreak()
  body
}

#let resume-education(university: "", gpa: "", school: "", start: "", end: "", body) = {
  let left = (university, school, gpa)
  let right = resume-date(start, end: end);
  
  resume-item(
    left: array-to-str(left),
    right: right,
    body
  )
}

#let resume-work(company: "", duty: "", start: "", end: "", body) = {
  let left = (strong(company), duty)
  let right = resume-date(start, end: end)

  resume-item(
    left: array-to-str(left),
    right: right,
    body
  )
}

#let resume-project(title: "", description: "", start: "", end: "", body) = {
  let left-items = (strong(title), description)
  let left = array-to-str(left-items)
  let right = resume-date(start, end: end)

  resume-item(
    left: left,
    right: right,
    body
  )
}

#let resume-section(title) = {
  v(-5pt)
  heading(level: 2, title)
  line(length: 100%)
  v(-2pt)
}
