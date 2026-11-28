# `#hf-earnings-quotes` format

Match this visible layout. The placeholders describe content; do not print them.
Use the literal bullet characters and indentation shown here.

```text
TICKER reported [principal result] for [reporting period], and [why it matters].
Complete the forward setup, underwriting change, and strongest counterweight in
the same dense opening paragraph.

[Optional compact scorecard paragraph when separating the numbers improves
scanning.]

**What Happened?**
• **Highest-value conclusion or financial result**
    ◦ Evidence, mechanism, qualification, or exact management quote
• **Second ranked conclusion**
    ◦ Evidence, counterevidence, and what resolves the debate
• **Remaining mandatory delta**
    ◦ Status, economics, timing, dependency, or next proof point

**Implications**
• (+) TICKER: supported positive read-through
• (-) TICKER: supported negative read-through
```

## Formatting rules

- Open directly with the ticker, reporting period, result, reaction when sourced,
  and causal bottom line. Use one or two opening paragraphs; do not print a title
  above them or label them `Bottom line`.
- Write the opening as a normal paragraph. Do not place `TICKER [period]:` on its
  own line or emphasize the entire opening sentence as a title. Sentence-level
  emphasis inside the paragraph is fine.
- Print the section labels exactly as `**What Happened?**` and
  `**Implications**` so they render in bold.
- Use `•` for every top-level bullet, four spaces plus `◦` for supporting evidence,
  and eight spaces plus `▪` only when a third level is indispensable. Do not use
  hyphen bullets or numbered themes.
- Make each top-level bullet a conclusion. Put proof, qualifications, and quotes
  beneath it instead of turning each theme into a prose paragraph.
- Use real Markdown bold (`**...**`) for each top-level conclusion and for one or
  two short phrases in the opening that carry the decisive delta or
  counterweight. Do not bold a whole opening paragraph, routine numbers, or
  quotes. Reserve `_..._` italics for an occasional exact quote.
- End each top-level `• **conclusion**` line after the bold conclusion. Do not
  place evidence on that line. Every top-level bullet must have at least one
  four-space-indented `◦` evidence or quote line beneath it.
- Put exact quotes on nested lines near the claim they prove. Italicizing a quote
  with `_..._` is optional. Do not create a separate quote section.
- Use signed read-throughs such as `(+) TICKER`, `(-) TICKER`, or `(+/-) TICKER`
  when the transcript supports a public-peer implication. Company-level estimate,
  thesis, catalyst, or risk implications may be bullets without a peer ticker.
- Do not add Markdown `#` headings, a report title, tables, citations, a `Source:`
  footer, methodology, confidence language, or a postscript unless the user asks.
- Remove every inline citation, source link, footnote, and other visible source
  notation from the finished post.

The channel varies in voice and sometimes omits `Implications` when no useful
read-through exists. Preserve that flexibility only when the section would be
empty; do not invent a peer implication to fill the template.

## Publication budget

- Keep the opening to at most three sentences and 90 words. Bold one or two short
  phrases carrying the highest-value surprise and decisive counterweight.
- Use exactly three `What Happened?` conclusions. Each gets one or two nested
  evidence lines. Use a fourth conclusion only when omitting a separate guide,
  earnings-quality, regulatory, or structural delta would change the decision.
- Use one or two compact `Implications` bullets. Each must add an estimate
  direction, thesis/action change, or differentiated peer/category consequence
  plus its proof point; do not summarize the body again.
- Spend quote space on the changed-underwriting conclusion and strongest adverse
  qualification before any management color or product narrative.

## Length and compression

Build and reconcile the content-complete draft before shortening it. Then aim for
375-450 words, with a hard maximum of 475, and keep the opening below 90 words.
This is a final editing pass, not a reason to drop required decision evidence.

Shorten sentences, combine adjacent evidence that supports the same conclusion,
and remove repetition, secondary scorecard detail, product tours, generic
background, unquantified optionality, and implications that restate the body.
Preserve the decision-changing guide delta, main leading indicator, central
counterevidence or Q&A debate, and each selected quote. Omit routine guide fields
and scorecard rows. After compression, restore any missing decision evidence and
recover space elsewhere.
