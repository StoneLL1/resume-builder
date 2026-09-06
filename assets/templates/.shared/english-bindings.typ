#import "bindings.typ": editable, field, present, bullets, metrics

#let render-english(resume, upstream, style) = {
  let b = resume.basics
  let name = editable("basics.name","text",b.name)
  let headline = if present(b.at("headline",default:none)) { editable("basics.headline","text",b.headline) } else { [] }
  let contacts = b.contacts.map(c=>editable(c.id,"contact",[#{if present(c.label) { [#c.label: ] }}#c.value]))
  let body = {
    metrics(latin-only:true)
    if style.starts-with("rendercv-") {
      heading(level:1,name)
      if present(headline) { upstream.headline(headline) }
      let native-contacts = b.contacts.zip(contacts).map(((c,value))=>context {
        let icons = (phone:"phone",email:"envelope",link:"link",location:"location-dot")
        if upstream.rendercv-config.get().at("header-connections-show-icons") and c.type in icons {
          upstream.connection-with-icon(icons.at(c.type),value)
        } else { value }
      })
      upstream.connections(..native-contacts)
    }
    for s in resume.sections {
      let label = editable(s.id,"section-title",s.title)
      if style == "culemann-index" { upstream.cv-section(label) }
      else if style != "imprecv" { heading(level:if style=="modern-cv" {1} else {2},label) }
      let entries = {
        for e in s.entries {
          let title = field(e,"title")
          let sub = field(e,"subtitle")
          let date = field(e,"date")
          let location = field(e,"location")
          let details = bullets(e)
          if style.starts-with("rendercv-") {
            upstream.regular-entry([#strong(title)#if present(sub) { [ #sub] } #details],[#date #parbreak()#location])
          } else if style=="basic-resume" {
            upstream.generic-two-by-two(top-left:strong(title),top-right:date,bottom-left:sub,bottom-right:location)
            details
          } else if style=="culemann-index" {
            upstream.index-entry(title:title,subtitle:sub,dates:date,location:location,details)
          } else if style=="modern-cv" {
            upstream.resume-entry(title:title,description:sub,date:date,location:location)
            upstream.resume-item(details)
          }
        }
      }
      if style=="culemann-index" { upstream.index-body(entries) }
      else if style=="imprecv" {
        let jobs = s.entries.map(e=>(organization:field(e,"title"),location:field(e,"location"),positions:((position:field(e,"subtitle"),startDate:none,endDate:none,date-display:field(e,"date"),highlights:e.bullets.map(item=>editable(item.id,"bullet",item.text))),)))
        upstream.cvwork((work:jobs),title:label)
      } else { entries }
    }
  }
  if style.starts-with("rendercv-") { body }
  else if style=="basic-resume" { upstream.resume(author:name,accent-color:"#26428b",contacts-display:contacts)[#headline#body] }
  else if style=="culemann-index" { upstream.index-cv(author:name)[#upstream.masthead(author:name,profession:headline,contact:contacts.join(" · "))#body] }
  else if style=="modern-cv" {
    upstream.resume(author:(firstname:b.at("name-plain").split(" ").slice(0,-1).join(" "),lastname:b.at("name-plain").split(" ").last(),positions:if present(headline){(headline,)}else{()},contacts-display:contacts),description:"Resume",profile-picture:none,body)
  } else if style=="imprecv" {
    let vars = (headingfont:"Libertinus Serif",bodyfont:"Libertinus Serif",fontsize:10pt,linespacing:6pt,sectionspacing:0pt,showAddress:true,showNumber:true,showTitle:true,headingsmallcaps:false,sendnote:false)
    set page(paper:"us-letter",numbering:"1 / 1",number-align:center,margin:1.25cm)
    upstream.setrules(vars,upstream.showrules(vars,[#upstream.cvheading((personal:(name:name,titles:if present(headline){(headline,)}else{()},contacts-display:contacts)),vars)#body]))
  }
}
