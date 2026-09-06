#import "is-blank.typ": *

// One accent + ink + one muted grey (cv-typography-standard rule 6). The accent
// is the running section NUMBER, the section label rule, and the masthead hairline;
// ink for text, muted for meta. Default accent a restrained indigo.
#let ink = rgb("#1f2430")
#let muted = rgb("#6b7280")

// Fixed size scale from body B = 10.5pt (standard rule 2), defined ONCE.
#let display-size = 23pt // ~2.2 x B - the name (masthead)
#let subhead-size = 12pt // ~1.14 x B - the profession line
#let body-size = 10.5pt // B
#let label-size = 10pt // ~0.95 x B - section labels (uppercase + tracked)
#let number-size = 15pt // the running two-digit section index
#let meta-size = 8.6pt // ~0.82 x B - dates, location, contact, level, fine print

// The section index gutter: a fixed left column holds the two-digit number; the
// label and every entry indent past it so the number sits alone in the margin.
#let NUM-COL = 22pt
#let NUM-GUT = 12pt
#let SEC-INDENT = NUM-COL + NUM-GUT

// A document-scoped counter for the running section index (01, 02, ...). Reset at
// the top of every render so the first section is always 01.
#let index-section-counter = counter("index-cv-section")

// Document shell: set-rules + PDF metadata only. The masthead and sections are
// composed by wrapSections. Roboto is the single family (standard rule 1);
// Roboto ships regular / medium / bold (no semibold), so labels use medium.
#let index-cv(
  author: "",
  font: "Roboto",
  font-size: 10.5pt,
  paper: "a4",
  margin: 1.5cm,
  leading: 0.65em,
  lang: "en",
  body,
) = {
  let author-str = if type(author) == str { author } else { "CV" }
  set document(author: author-str, title: author-str + " - CV")

  set text(font: font, size: font-size, fill: ink, lang: lang, ligatures: false, hyphenate: false)
  set page(margin: margin, paper: paper)
  set par(justify: false, leading: leading)

  index-section-counter.update(0)

  show link: set text(fill: muted)

  body
}

// Masthead (full width): name (bold) over the profession (accent, medium, tracked)
// and a quiet contact line, closed by a thin accent hairline. Distinct from the
// numbered body: no number here, the hairline is the only rule in the header.
#let masthead(author: "", profession: "", contact: "", accent-color: "#3a3f6b") = {
  let has-name = not is-blank(author)
  let has-prof = not is-blank(profession)
  let has-contact = not is-blank(contact)
  if has-name or has-prof or has-contact {
    block(above: 0pt, below: 1.2em, breakable: false, {
      set block(spacing: 0pt)
      set par(spacing: 0pt, leading: 0.45em, justify: false)
      if has-name { text(size: display-size, weight: "bold", fill: ink, author) }
      if has-prof {
        if has-name { v(4pt) }
        text(size: subhead-size, weight: "medium", tracking: 0.4pt, fill: rgb(accent-color), profession)
      }
      if has-contact {
        if has-name or has-prof { v(7pt) }
        text(size: meta-size, fill: muted, contact)
      }
      if has-name or has-prof or has-contact { v(9pt); line(length: 100%, stroke: 0.6pt + rgb(accent-color)) }
    })
  }
}

// Section label (the signature): a big two-digit accent NUMBER in the left gutter,
// the UPPERCASE tracked label beside it over a thin accent rule. Sticky so a label
// never orphans at a page bottom. The number steps once per section.
#let cv-section(title, accent-color: "#3a3f6b") = {
  index-section-counter.step()
  block(above: 1.3em, below: 0.9em, sticky: true, {
    set block(spacing: 0pt)
    set par(spacing: 0pt, justify: false)
    grid(
      columns: (NUM-COL, 1fr),
      column-gutter: NUM-GUT,
      align: (right + bottom, left + bottom),
      context {
        let n = index-section-counter.get().first()
        text(size: number-size, weight: "bold", fill: rgb(accent-color), (if n < 10 { "0" } else { "" }) + str(n))
      },
      {
        text(size: label-size, weight: "medium", tracking: 1pt, fill: ink, upper(title))
        v(3pt)
        line(length: 100%, stroke: 0.6pt + rgb(accent-color))
      },
    )
  })
}

// Section body wrapper: indents entries past the number gutter so they align under
// the label, leaving the number alone in the margin. Inherits the ambient block spacing
// (no spacing:0pt) so the first entry keeps its natural gap below the section rule,
// matching the other templates instead of sitting flush against the divider.
#let index-body(body) = block(width: 100%, inset: (left: SEC-INDENT), body)

// Entry: semibold-ink title leads with a muted subtitle, dates right; location and
// an optional URL meta line below; then the body. Title leads with weight, not
// uppercase (standard rule 4); no mid-word hyphenation on the title line.
#let index-entry(title: "", subtitle: "", dates: "", location: "", meta: "", body) = {
  block(breakable: false, {
    set block(spacing: 0pt)
    set par(spacing: 0pt)
    block(sticky: true, breakable: false, {
      set par(justify: false)
      set text(hyphenate: false)
      grid(
        columns: (1fr, auto),
        align: (left + top, right + top),
        column-gutter: 0.75em,
        {
          if not is-blank(title) { text(weight: "medium", fill: ink, title) }
          if not is-blank(title) and not is-blank(subtitle) { text(fill: muted)[ #sym.dash.en ] }
          if not is-blank(subtitle) { text(fill: muted, subtitle) }
        },
        if not is-blank(dates) { text(size: meta-size, fill: muted, dates) } else { [] },
      )
      if not is-blank(location) {
        v(3pt)
        text(size: meta-size, fill: muted, location)
      }
      if not is-blank(meta) {
        v(3pt)
        text(size: meta-size, fill: muted, meta)
      }
    })
    if not is-blank(body) {
      v(3.5pt)
      block(spacing: 0pt, { set text(fill: ink); body })
    }
  })
}

// Language row: language left, level muted right.
#let index-language(language: "", level: "") = {
  grid(
    columns: (1fr, auto),
    align: (left + horizon, right + horizon),
    column-gutter: 0.6em,
    language,
    if not is-blank(level) { text(size: meta-size, fill: muted, level) } else { [] },
  )
}
