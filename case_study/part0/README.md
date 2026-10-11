# Part 0 — my own ideas, written before touching Claude

Two research ideas, half a page each. The point of the exercise is calibrating
*my* judgment before calibrating Claude's, so both were written without model
assistance and neither was revised after seeing what Claude produced.

| File | Seed | Verdict |
|---|---|---|
| `well_posed_kalshi_draftkings.md` | **S1** | Genuinely well-posed |
| `plausible_but_flawed_mau_arr.md` | **S2** | Plausible, dies at desk review |

## Why these two

They are deliberately the *same shape*: third-party panel data used to infer a
company's reported financials. One works and one doesn't, and showing why is a
sharper display of judgment than picking two unrelated ideas.

The point isn't "alt data good / alt data bad." It's whether the panel observes
the thing that actually drives the reported number.

- **Kalshi → DraftKings**: the panel sees deposits, which map — imperfectly, and
  the write-up says so — to the revenue driver.
- **MAU → ARR**: the panel sees usage, which is *structurally decoupled* from
  billing. Seat-based ARR bills on seats contracted, not seats used.

The flawed one is also written to fail the way a smart junior fails: every step
is individually standard practice, the caveats it does raise are real and
responsible, and none of them is what kills it. It succeeds on its own terms —
which is exactly what makes the result convincing and wrong.
