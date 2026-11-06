<!-- Copied verbatim from the `earnings-quotes` eval manifest (dataset v23), task success_criteria. -->

Apply a 10/10 analyst-replacement bar. Pass only if the final post could be
published to #hf-earnings-quotes without substantive edits and matches or
exceeds the gold comparison post's decision utility using evidence available in
the transcript and authorized research-tool results. "Good," "competent," or
generally accurate is a fail. A
generic earnings summary, chronological call recap, data dump, or prose that
leaves the investor to find the signal is a fail.

The human gold is a known passing answer and calibrates sufficiency for this
task. An answer identical to the gold must pass unless the trial is invalid. For
any other answer, make a true net-utility comparison between the few highest-value
decisions in each post. The gold is often longer than the generated-post target,
so never treat its topics as an additive checklist or require every useful fact
it contains. A missing gold topic can cause failure only when it is among the
gold's highest-value investment decisions and the generated post contains no
equally valuable, evidence-supported substitute. Do not fail merely because
another point, quote, risk, counterweight, or implication could be added.

For every omission-based failure, identify the concrete estimate, thesis,
action, catalyst, risk, or peer decision available from the gold but unavailable
from the generated post, and explain why the generated post's competing use of
that space has lower decision value. The counterfactual fix must specify what to
swap out within the target word budget; an additive wish list is not a valid
basis for failure. Extra analysis may improve an answer but is not required when
the generated selection is equally publishable and decision useful.

Judge the post holistically, then require excellence in every material area:
(1) investment judgment: lead with a clear bottom line, correctly rank the few
deltas that change expectations or underwriting, distinguish signal from
management framing, and resolve or sharpen the central debates; (2) content
selection: capture the key transcript-supported beat/miss quality, operating
drivers, guidance changes, forward indicators, risks, and contradictions while
omitting low-value call narration; (3) quotes: select purposeful
management quotes that best prove a change, expose a debate, or preserve useful
nuance, with faithful wording, speaker, and context; transparent ellipses and
grammatical bracket edits may pass when they preserve every material qualifier
and do not change meaning, while silent alterations or misleading splices fail;
do not reward decorative or excessive quotation; (4) factual fidelity: contain no material error,
unsupported claim, faulty calculation, invented expectation, misleading
comparison, or misattribution; (5) implications: state the useful company,
thesis, estimate, catalyst, risk, or peer read-throughs that follow from the
transcript without presenting inference as fact; and (6) writing: be concise,
specific, decisive, scannable Slack prose with density and prioritization
comparable to an elite public-markets analyst. For a generated answer, the
preferred visible channel format is one or two unheaded opening bottom-line
paragraphs, then the bold Markdown label `**What Happened?**` with literal
Unicode `•` top-level bullets whose conclusions use real Markdown bold and
four-space-indented Unicode `◦` evidence or quote bullets, then the bold
Markdown label `**Implications**` with supported company or signed-ticker
read-throughs. A format used by the task's gold is also accepted; do not fail an
otherwise publishable answer solely because the historical human post used
hyphen bullets, a title, a `Portfolio Implications` label, or a separate quote
section.
Selective bold in the opening should expose the decisive delta or
counterweight without emphasizing a whole paragraph. Nested evidence lines are
mandatory under
`**What Happened?**` only; `**Implications**` may use supported one-line bullets when claims trace to
evidence already presented in the post. For generated answers that do not use a
gold-supported layout, a report title, labeled "Bottom line," Markdown heading,
numbered themes, table, citation or source footer, or prose-only theme sections
require substantive formatting edits and therefore fail. The finished post should normally fit
in 375-450 words; more than 475 words is presumptively too long unless the
complete material guide cannot be preserved more compactly. Repetition,
overlong evidence bullets, or implications that merely restate the body fail
the writing standard.

When authorized research tools are available, require a good-faith dated
attempt to source the earnings surprise and market context: actual versus
Street and any sourced buyside expectation, new guidance versus prior or
consensus, beat-to-guide pass-through, stock reaction, valuation, and the
public or house debate. Do not require an item that was not found or was
unavailable, but failing to seek retrievable context is material when it
would change the investment conclusion. Keep company disclosure, consensus,
buyside checks, market data, house context, and inference clearly distinct.

For a historical call, treat the close of the second trading day after the
call as the external-research cutoff. Later events are hindsight and cannot
support the recap; material reliance on them is a factual-fidelity failure.

Treat the transcript and authorized research results as the evidence ceiling.
The gold may contain buyside expectations, prior work, models, or house views
absent from those sources. Do not penalize omission of unavailable context and
do not require unsupported imitation. Equivalent conclusions, quote choices,
and wording may pass when they provide equal or better decision value.
The gold is a comparison target, not factual authority: if it conflicts with the
transcript or authorized research, judge the generated post against the source
evidence and do not require it to reproduce the gold's error or unsupported claim.
This evidence-ceiling rule applies when judging a generated alternative; do not
use it to relitigate whether the accepted human gold itself should have passed.
Missing a central transcript-supported insight, debate, implication, or
purposeful quote captured by the gold is material only under the comparative
omission test above. A point absent from the gold must also clear that test
before its omission can cause a failure.

The run may use only the prompt, its declared generated system prompt and
skill/source mounts, and its declared research MCPs. Mark it invalid if the
trace shows successful access outside the recorded runtime roots, an undeclared
skill/source or MCP server, or any retrieval that identifies, quotes, or
materially reproduces the actual gold Slack post. On every fail, put
all material critiques in missing_requirements in priority order, explicitly
covering each deficient category among judgment, content selection, quotes,
factual fidelity, implications, and writing. Cite concrete omissions or
mistakes relative to the transcript and gold. The counterfactual_fix must give
a concrete revision plan that would make this specific post publishable; vague
advice is insufficient.
