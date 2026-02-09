// Section title page - same formatting as cover. Call: section-page(grad-date, count, release, build)

#let section-page(grad-date, count, release, build) = [
  // Greyhat in ASCII binary: G r e y H a t. Per-column blanks between each letter
  #let blanks-min = 2
  #let blanks-max = 6
  #let blanks-range = blanks-max - blanks-min + 1
  #let letters = ("01000111", "01110010", "01100101", "01111001", "01001000", "01100001", "01110100")
  #let cols = 96
  #let rows = 72
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
            let n0 = blanks-min + calc.rem(col * 7, blanks-range)
            let n1 = blanks-min + calc.rem(col * 11 + 3, blanks-range)
            let n2 = blanks-min + calc.rem(col * 13 + 7, blanks-range)
            let n3 = blanks-min + calc.rem(col * 17 + 2, blanks-range)
            let n4 = blanks-min + calc.rem(col * 19 + 11, blanks-range)
            let n5 = blanks-min + calc.rem(col * 23 + 5, blanks-range)
            let n6 = blanks-min + calc.rem(col * 29 + 13, blanks-range)
            let s0 = n0
            let s1 = n0 + n1
            let s2 = s1 + n2
            let s3 = s2 + n3
            let s4 = s3 + n4
            let s5 = s4 + n5
            let s6 = s5 + n6
            let stream-len = 64 + s6
            let col-offset = calc.rem(col * 37 + calc.rem(col * col, 47) * 13 + calc.rem(col * 7, 23) * 19, 97)
            let stream-pos = calc.rem(row + col-offset, stream-len)
            let ch = (
              if stream-pos < 8 { letters.at(0).at(int(stream-pos)) }
              else if stream-pos < 8 + s0 { " " }
              else if stream-pos < 16 + s0 { letters.at(1).at(int(stream-pos - 8 - s0)) }
              else if stream-pos < 16 + s1 { " " }
              else if stream-pos < 24 + s1 { letters.at(2).at(int(stream-pos - 16 - s1)) }
              else if stream-pos < 24 + s2 { " " }
              else if stream-pos < 32 + s2 { letters.at(3).at(int(stream-pos - 24 - s2)) }
              else if stream-pos < 32 + s3 { " " }
              else if stream-pos < 40 + s3 { letters.at(4).at(int(stream-pos - 32 - s3)) }
              else if stream-pos < 40 + s4 { " " }
              else if stream-pos < 48 + s4 { letters.at(5).at(int(stream-pos - 40 - s4)) }
              else if stream-pos < 48 + s5 { " " }
              else if stream-pos < 56 + s5 { letters.at(6).at(int(stream-pos - 48 - s5)) }
              else if stream-pos < 56 + s6 { " " }
              else { letters.at(6).at(int(stream-pos - 56 - s6)) }
            )
            let vert-fade = 0.02 + 0.98 * (row / (rows - 1)) * (row / (rows - 1))
            let alpha = if ch == " " { 0 } else { vert-fade }
            let digit = if ch == " " { [ ] } else { [#ch] }
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
    #text(size: 9pt, font: mono, fill: cyan)[greyhat#"\u{0040}"gt:~#"\u{0024}" resumebook #"\u{002D}\u{002D}"info #"\u{002D}\u{002D}"section "#grad-date"]
    #linebreak()
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Greyhat Resume Book #h(0.3em) — #h(0.3em) Sponsor Edition]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Release: #release (build #build)]
    #linebreak()
    #text(size: 9pt, font: mono, fill: light-gray)[Candidates: #count]
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
