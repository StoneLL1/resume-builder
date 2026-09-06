// Data bindings only. Layout, headings and entries are provided by the upstream libraries.
#let editable(id, kind, body, anchor: "block", edge: "left") = {
  let marked = [
    #context metadata((kind: kind, id: id, phase: "start", page: here().page(), x: here().position().x, y: here().position().y, size: text.size, anchor: "block", edge: "left"))#body#context metadata((kind: kind, id: id, phase: "end", page: here().page(), x: here().position().x, y: here().position().y, size: text.size, anchor: "block", edge: "left"))
  ]
  // Keep metadata inside the aligned content, including centered headers and placed dates.
  if kind == "bullet" { block(width: 100%, breakable: false, marked) }
  else { box(marked) }
}
#let present(value) = value != none and value != "" and value != []
#let field(entry, key, anchor: "inline", edge: "left") = {
  let value = entry.at(key, default: none)
  if key == "title" or present(value) {
    editable(entry.id + "." + key, "text", if value == none { [] } else { value }, anchor: anchor, edge: edge)
  }
}
#let bullets(entry) = {
  for b in entry.at("bullets", default: ()) {
    // Each list owns its content; markers remain inside the individual item.
    list(block(breakable: false, editable(b.id, "bullet", b.text)))
  }
}
#let subtitle(entry) = {
  let parts = ()
  for key in ("subtitle", "location") {
    if present(entry.at(key, default: none)) { parts.push(field(entry,key)) }
  }
  parts.join(" · ")
}
#let section-label(section, mode) = editable(section.id, "section-title", section.title)
#let metrics(latin-only: false) = context {
  for (script, sample) in (("latin", [A]), ("cjk", [中])) {
    if latin-only and script == "cjk" { continue }
    for size in (8pt,9pt,9.9pt,10pt,10.5pt,11pt,12pt,13pt,13.2pt,14pt,14.4pt,15pt,16pt,17pt,18pt,19.25pt,20pt,22pt,24pt,26.4pt) {
      let one = measure(block(width: 100%,text(size: size,sample)))
      let two = measure(block(width: 100%,text(size: size)[#sample#linebreak()#sample]))
      metadata((kind: "_metrics",script: script,size: size,pitch: two.height - one.height,lh: one.height))
    }
  }
}
#let render-with(resume, upstream, style) = {
  let basics = resume.basics
  let mode = resume.meta.at("language-mode", default: "zh")
  let name = editable("basics.name", "text", basics.name)
  let headline = if present(basics.at("headline",default: none)) { editable("basics.headline","text",basics.headline) } else { [] }
  let contacts = basics.contacts.map(c => editable(c.id,"contact",{
    if present(c.label) { [#c.label：] }
    c.value
  },anchor: "inline"))
  let config = if style == "habaneraa" { upstream.setup-styles(font-size:12pt, element-spaciness:1.30) } else { none }
  let body = {
    metrics()
    if style not in ("orange-chinese", "habaneraa", "sweet-gargamel") and present(headline) {
      align(center, headline)
    }
    for section in resume.sections {
      let label = section-label(section,mode)
      if style in ("resume-ng", "sweet-gargamel") { upstream.resume-section(label) }
      else if style == "miku" {
        let icons = (education:"mortarboard.svg",experience:"seedling.svg",project:"telescope.svg",skill:"darts.svg",award:"football.svg",custom:"curl.svg")
        upstream.section([#upstream.titleemj(icons.at(section.type,default:"curl.svg")) #label])
      }
      else if style == "qianxi" {
        let icons = (education:"education",experience:"internship",project:"project",skill:"skill",award:"award",custom:"project")
        upstream.section-header(title:label,icon:"icons/"+icons.at(section.type,default:"project")+".svg")
      }
      else if style == "orange-chinese" {
        let icons = (education:"fa-graduation-cap",experience:"fa-work",project:"fa-code",skill:"fa-wrench",award:"fa-award",custom:"fa-building-columns")
        heading(level:2,[#upstream.icon("icons/"+icons.at(section.type,default:"fa-code")+".svg",fill:rgb("#26267d")) #label])
      }
      else {
        heading(level: if style in ("uniquecv","habaneraa") {1} else {2},label)
        if style in ("chicv","chicv-cn") { upstream.chiline() }
      }
      for entry in section.entries {
        let title = field(entry,"title",anchor:"block")
        let date = field(entry,"date",edge:"right")
        let sub = subtitle(entry)
        let details = bullets(entry)
        if style == "orange-chinese" {
          if section.type == "education" {
            upstream.sidebar(date,[#strong(title) · #sub #details])
          } else if section.type == "skill" {
            upstream.sidebar(with-line:false,strong(title),[#sub #date #details])
          } else {
            upstream.item(strong(title), sub, upstream.date(date))
            details
          }
        } else if style in ("resume-ng", "sweet-gargamel") {
          upstream.resume-item(left: strong(title),right: date)[#sub #details]
        } else if style == "miku" {
          upstream.datedsubsection(strong(title),date)
          if present(sub) { sub; parbreak() }
          details
        } else if style == "qianxi" {
          let points = entry.bullets.map(b=>block(breakable:false,editable(b.id,"bullet",b.text)))
          if section.type == "education" {
            upstream.educations(((school:title,major:sub,degree:[],date:date),),show-section:false)
            details
          } else if section.type == "experience" {
            upstream.internships(((company:title,jobtitle:sub,date:date,points:points),),show-section:false)
          } else if section.type == "award" {
            upstream.awards(((name:[#title #sub],date:date),),show-section:false)
            details
          } else if section.type == "skill" {
            upstream.skills(((name:title,desc:sub),),show-section:false)
            date
            details
          } else {
            upstream.projects(((name:title,url:"",date:date,desc:sub,points:points),),show-section:false)
          }
        } else if style == "uniquecv" {
          if section.type == "education" {
            upstream.education(school:title,major:field(entry,"subtitle"),degree:field(entry,"location"),date:date,details)
          } else if section.type == "award" {
            upstream.prize(((game:title,grade:sub,date:date),))
            details
          } else {
            upstream.proj-exps(((name:title,type:sub,date:date,description:details),))
          }
        } else if style == "habaneraa" {
          (config.resume-entry)(title:title,subtitle:sub,date:date,details)
        } else {
          // chicv's original document uses strong title + flexible space + date.
          [#strong(title) #h(1fr) #date #linebreak()#field(entry,"subtitle") #h(1fr) #field(entry,"location") #details]
        }
      }
    }
  }
  if style == "orange-chinese" {
    let infos = basics.contacts.zip(contacts).map(((c,value)) => {
      let icons = (phone:"fa-phone",email:"fa-envelope")
      if c.type in icons { (content:value,icon:upstream.icon("icons/"+icons.at(c.type)+".svg",fill:rgb("#26267d"))) } else { (content:value,) }
    })
    upstream.resume(header-center:false,[#heading(level:1,name)#upstream.info(color:rgb("#26267d"),..infos)],headline,body)
  } else if style in ("chicv","chicv-cn") {
    upstream.document-style([#heading(level:1,name)#contacts.join(" | ")#body])
  } else if style == "resume-ng" {
    upstream.project(author:(name:name),contacts:contacts,body)
  } else if style == "sweet-gargamel" {
    upstream.project(author:(name:name),times:if present(headline){headline}else{none},contacts:contacts,body)
  } else if style == "miku" {
    let items = (:)
    let rest = ()
    for (c,value) in basics.contacts.zip(contacts) {
      if c.type in ("email","phone") { items.insert(c.type,value) } else { rest.push(value) }
    }
    upstream.project(title:name,author:(email:items.at("email",default:[]),phone:items.at("phone",default:[]),home:[],github:rest.join(" · "),linkin:[]),body)
  } else if style == "qianxi" {
    upstream.cv(name:name,contacts:contacts,body)
  } else if style == "uniquecv" {
    upstream.project(name:name)[#align(center,contacts.join(" · "))#body]
  } else if style == "habaneraa" {
    (config.resume-header)(author:name,contacts-display:contacts,basic-info:if present(headline){(headline,)}else{()},body)
  }
}
