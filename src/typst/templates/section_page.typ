// Section title page - same formatting as cover. Call: section-page(grad-date, count, build)

#let section-page(grad-date, count, build) = [
  #let pat = "10010110100101101001011010010110"
  #let pat-len = 24
  #let cols = 96
  #let rows = 110
  #let mono = "Liberation Mono"
  #let cyan = rgb("#00bcd4")
  #let gray = rgb("#525252")
  #let light-gray = rgb("#e8e8e8")
  #let subtitle = [GreyHat #h(0.3em) — #h(0.3em) Georgia Tech Cybersecurity Club]

  #set grid.cell(breakable: false)

  #set page(
    fill: gray,
    background: [
      #block(width: 100%, height: 100% - 0.33in, inset: 0pt, clip: true, breakable: false)[
        #grid(
          columns: cols,
          column-gutter: 0pt,
          row-gutter: 4pt,
          inset: 0pt,
          align: center,
          ..range(cols * rows).map(i => {
            let row = int(i / cols)
            let col = calc.rem(i, cols)
            let t = row / (rows - 1)
            let a = t * t
            let alpha = 0.02 + 0.98 * a
            let phase = calc.rem(col * 7, pat-len)
            let stride = 2 + calc.rem(col, 4)
            let idx = calc.rem(phase + row * stride, pat-len)
            let digit = pat.at(int(idx))
            text(size: 10pt, font: mono, fill: rgb(0, 188, 212, (alpha * 100) * 1%))[#digit]
          })
        )
      ]
    ]
  )

  #pagebreak(weak: true)

  #place(top + right, dx: 0.5in, dy: -0.5in)[
    #image("grey_hat_hat_small_400x400.png", width: 1.4in)
  ]

  #place(top + left, dx: -0.5in, dy: -0.5in)[
    #text(size: 9pt, font: mono, fill: cyan)[greyhat#"\u{0040}"gt:~#"\u{0024}" resumebook #"\u{002D}\u{002D}"section "#grad-date"]
    #linebreak()
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[#subtitle]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Resumes: #count]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Build: #build]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Contact: greyhat.gt#"\u{0040}"gmail.com]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Privacy: recruiting use only; do not redistribute]
    #linebreak()
    #linebreak()
    #text(size: 9pt, font: mono, fill: cyan)[greyhat#"\u{0040}"gt:~#"\u{0024}" ]
    #text(size: 9pt, font: mono, fill: cyan)[▌]
  ]

  #align(center)[
    #v(1.5in)
    #text(size: 36pt, weight: "bold", font: mono, fill: white)[#grad-date]
    #v(0.35em)
    #text(size: 16pt, font: mono, fill: light-gray)[#subtitle]
  ]
]
