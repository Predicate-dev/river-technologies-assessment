# Engagement context

This is a timed 8-hour consulting take-home. Client: Apex Ridge Capital
(fictional hedge fund). Deliverables are (1) a working prototype,
(2) a technical approach doc for the client's engineers, (3) a one-page
solution brief for the client's managing partner (non-technical).

## How to work with me here

- I am on a hard clock. Bias toward the smallest thing that works
  end to end. Never propose a refactor unless it unblocks a deliverable.
- Before writing code for anything non-trivial, state the approach in
  2-4 bullets and wait for my go-ahead. Do not silently pick an
  architecture.
- When you hit an ambiguity in the client's requirements, STOP and add
  it to `NOTES/questions.md` instead of guessing. I have limited
  consultation windows with the client and I batch questions.
- Log every meaningful decision and tradeoff to `NOTES/decisions.md`
  as we go: what I chose, what I rejected, why. One or two lines each.
  These become the technical doc. Do not let this go stale.
- Log anything I deliberately cut to `NOTES/descoped.md` with a
  one-line reason.
- Working code beats complete code. If something is going long, tell me
  and offer a narrower version.
- No new dependencies without asking. No scaffolding I did not request.
- Tests: cover the data-correctness path and the ugly edge cases only.
  Skip tests for glue and I/O.

## Style
- Direct. No preamble, no "great question", no summaries of what you
  just did unless I ask.
