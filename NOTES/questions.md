# Open questions for the client

## Window 1 (asked before schema lock)

1. **KREF classification.** ~~Brief calls it a BDC; it is a mortgage REIT~~
   **RESOLVED (Window 1), pending CIO confirmation of the peer list itself.**
   Partner chose (b): keep KREF, populate what maps, explicit caveat in the
   output that it is a REIT and net return is not apples-to-apples. Partner
   will not finalise unilaterally — the CIO put KREF on the list, so any
   scope-down comes from him. Treat as provisional; do not hard-code a drop.
   - **Follow-up I owe the partner (answered in-window):** it is not one
     failure mode, it splits by row. See NOTES/decisions.md "KREF row-level
     mapping".
   - **CLOSED:** partner chose blank + stated reason on the three net-return
     rows. "A blank with an explanation is defensible to the board. A filled
     cell with the wrong definition is not." No TSR substitution.
   - Partner is taking 1a and 1c to the CIO in one conversation. Neither
     blocks the build.
   - **1a. What is KREF on the list FOR? — ASKED, partner does not know.**
     CIO set the peer list before the partner was looped in and did not walk
     through it name by name. Partner's *guess* (explicitly not from the CIO):
     KREF appears in the same LP conversations Apex does — allocators holding
     both private credit and CRE debt — so the CIO tracks it as an alternative
     the LPs are seeing, not as a performance comparable. If that guess is
     right the escalation resolves in favour of what is already being built:
     leverage / distribution yield / fees are exactly the right rows and the
     three blank return cells cost nothing. NOT BLOCKING — build proceeds.
   - **1c. NEW, and bigger than KREF: what is each of the four on the list
     for?** Nobody on the client side has stated the selection criteria for
     ANY peer; KREF merely exposed it. If the names were chosen for different
     reasons, a single 8-metric table is the wrong shape for at least one of
     them. Partner is meeting the CIO anyway — one extra sentence, no extra
     window.
   - **1b. Rule, not a ruling.** KREF is not a one-off — GBDC is a BDC on
     10-K/10-Q, not N-CSR, so its fee and return bases differ from the interval
     funds too. Does the CIO want to set the policy once (metric absent for a
     peer => blank + reason, never a substituted near-metric), or adjudicate
     cell by cell each quarter? The first is a system; the second is the manual
     process they are paying to remove.
2. **Fiscal-year misalignment. RESOLVED (Window 1).** As-reported, with the
   as-of date rendered *on the cell*, not in footnote 1. Partner accepted the
   argument that a half-aligned row (recomputable for CCLFX/TAKIX from N-PORT
   monthlies, not for GBDC/KREF) is worse than an honest as-reported one.
   - **Staleness: hard line at six months.** Older than that => cell blank,
     carrying the as-of date of the last available figure. Blanks are not
     empty; they carry provenance.
   - **Cost asymmetry, stated by the partner and now governing the whole
     confidence model:** last year a misread basis point on a *leverage ratio*
     reached a board presentation and was caught only afterwards. That incident
     is why this engagement exists. "A blank cell generates a question I can
     answer. A confident wrong number generates a question I cannot, and it
     follows me." System is to be conservative: flag uncertainty, suppress when
     stale, never fill a cell to avoid a gap.
3. **Share class.** Deck footnote 3 says institutional for CCLFX/TAKIX.
   N-PORT gives fund-level returns cheaply; class-level needs narrative
   parsing. Hard requirement or is labelled fund-level acceptable?
   - Default if unanswered: fund-level, clearly labelled.
4. **Conflict presentation.** Resolved single value + appendix conflict log,
   or both values in-cell?
   - Default if unanswered: resolved value in-cell, conflict log appendix.
5. **LLM / compliance.** Constraint on sending public EDGAR text to a
   third-party model? API key available or must run key-free?
   - Default if unanswered: LLM optional, deterministic fallback always works.

Bonus if time: what does a wrong number cost vs. a blank cell? (calibrates
the confidence threshold for suppression)

## Window 2 (mid-build, after pipeline runs)

**PARKED — drafted at close of window 1, not sent. Lead with this.**

Turnaround on a scope change, per open item. Four of five are config-level by
construction, not luck:
- *Apex column basis:* already renders through the same path as the peers with
  basis marked unconfirmed. His answer is a label change plus re-enabling the
  derived comparisons. Minutes.
- *CCLFX fund-level fallback:* built as a switch, currently off. Toggle.
- *KREF's purpose:* one entry in the fund registry, whether it stays, moves
  section, or comes off.
- *Compliance / LLM:* specified but unbuilt, so approval later is net-new work
  with zero rework. Costs nothing either way.
- *CIO's leverage definition:* THE EXCEPTION. Regulatory vs. economic, and
  whether KREF's non-recourse securitisation and repo are in or out, changes
  per-filer extraction. Half a day, not minutes. Tell him to chase this answer
  first — and note it is the same metric as his board incident, which is not a
  coincidence: it is ambiguous in exactly the way that produces a wrong number.

On his scope-flex signal (funds and metrics may grow):
- Cheap already, via the config-driven registry, *within a filer type already
  handled* (BDC / interval fund / mortgage REIT).
- Deliberately did NOT build a plugin system on a rumour — cost with no certain
  payoff on this clock.
- Two real cliffs to put in his head: (1) a new entity type, or any fund with
  no EDGAR presence, has no source — a scoping conversation, not an engineering
  one; (2) any new metric living in narrative prose rather than structured data
  is gated behind the same compliance answer blocking the LLM path. Fees are
  the example he already has: prose, not tagged data. **The scope question and
  the compliance question are the same question, and he did not appear to
  realise it.** That makes compliance more load-bearing than it looks.

**Carried to the CIO by the partner (he will not decide these unilaterally):**
- **A. Peer-list intent.** What is KREF on the list for, and what is each of the
  four on the list for? Determines whether one table is the right shape.
- **B. CCLFX institutional cadence gap.** Class-level data is semi-annual at
  best; CCLFX's March FYE leaves two windows a year with no institutional
  figure under six months old (next one projected early-to-late Dec 2026). Is a
  current *fund-level* figure with an explicit basis marker acceptable as a
  named fallback for CCLFX specifically? Partner's own preference is the blank
  (a PM catching a mismatch with footnote 3 is the exact failure he is buying
  this system to prevent) but he says the call is the CIO's. Build proceeds on
  blank + NOT_YET_FILED label; fallback is additive if the CIO wants it.
- **C2. CIO's leverage definition.** Added by the partner at window close, not
  previously on the list. Regulatory vs. economic basis; whether KREF's
  non-recourse securitisation/repo is in or out. This is the ONLY open item
  that implies real rework rather than a config change — it is per-filer
  extraction work, not a toggle.
- **C. Compliance (Q5).** Written answer on third-party model use, timeline in
  days. LLM path descoped from the prototype meanwhile.
**Not yet asked — both concern the Apex column itself. Every rule agreed so
far governs the peers; the anchor of the comparison has never been defined.**
- **D. RESOLVED: anchor is the reporting quarter, not the run date.** Apex Q4
  2025, period end 2025-12-31. Staleness = anchor - period_end; a source is
  eligible if period_end <= anchor, regardless of when it was filed (TAKIX's
  N-CSR for 2025-12-31 was filed 2026-02-27 and is point-in-time correct for a
  Q4 2025 deck prepared today). CORRECTED 2026-08-31: an earlier version of this note claimed the cadence
  gap did not bite the Q4 2025 deck. It does. Four CCLFX cells blank on
  stale_beyond_limit in the current run -- the 1Y, 3Y and 5Y returns and the
  distribution yield -- all against the N-CSR for period 2025-03-31, which is
  275 days behind the anchor. CIO item B is live for THIS deck, not a future
  one, and the partner should not be told otherwise. Original note follows.
  NOTE: this largely dissolves CIO item B for
  *this* deck — CCLFX's N-CSRS for 2025-09-30 is three months inside the
  anchor. The cadence gap is real but bites future quarters, not Q4 2025. Tell
  the partner so he does not escalate it as urgent. Original framing: The staleness rule is anchored ambiguously.
  Apex's own data ends Q4 2025 (period 2025-12-31) — eight months before
  today's run date of 2026-08-31. Anchored on the run date, Apex's own column
  blanks under its own rule while the peers populate (CCLFX/TAKIX N-PORT run to
  2026-06-30), i.e. the peers look fresher than Apex. Anchored on the Apex
  quarter being reported, everything is consistent and almost nothing blanks.
  Almost certainly the latter, but it is a one-line answer that changes every
  suppression decision in the output, so it gets asked rather than assumed.
- **E. OPEN, HARD BLOCK on anything referencing the Apex column.** Partner does
  not know the share class or whether the net return is net of both fees or
  management only; explicitly instructed: do not assume institutional, do not
  assume fully net. Confirmation promised by end of week. Original framing: Which share class, and net of which
  fees? He has just made institutional a hard requirement for CCLFX/TAKIX
  because a blended number flatters the competitor. If Apex's own net return is
  blended or struck on a different basis, the same distortion is present at the
  reference point and every peer comparison inherits it. Apex CSV shows a
  single mgmt fee 1.25 / incentive 12.50 / hurdle 6.00 with no class label.

- **F. NEW (build finding). Do fee terms go stale?** The six-month rule blanks
  GBDC's management fee, but 1.0% is the rate *in force* under the current
  effective advisory agreement -- it is not a point-in-time measurement the way
  a NAV or a leverage ratio is. Under a flat 183-day rule a live, correct fee
  rate renders as a blank. Proposal: exempt the three fee-terms metrics
  (management fee, incentive fee, hurdle) from hard staleness and let the
  continuous freshness factor discount them instead; keep the hard rule for
  every measured quantity. One-line answer, changes ~6 cells. Not assumed --
  the partner set the six-month line and this is a carve-out from it.
- **G. NEW (build finding). Superseded rates in the source.** GBDC's 10-K
  states "the base management fee rate was reduced from 1.375% to 1.0%" and
  "incentive fee rates were reduced from 20.0% to 15.0%" -- both the old and
  the current figure sit in the same sentence. We resolve to the current rate
  and flag it. Worth telling the partner explicitly: this is the exact shape of
  the misread that caused his board incident, and it is now a named, tested
  case rather than a matter of analyst attention.

## Window 3 CLOSED — outcomes

All four carried items resolved in-window; nothing on the escalation list is
still with the client except two she owes by date.

- **1. Leverage definition. RESOLVED.** Both bases, rendered as two separate
  rows (regulatory, economic). KREF: non-recourse securitisation out, repo in.
  Per-filer extraction work, ~half a day. Unblocks TAKIX's blank leverage cell.
- **2. Apex column basis. RESOLVED.** Institutional, net of both management and
  incentive fees. `APEX_BASIS_CONFIRMED` flips; peer deltas re-enable.
- **3. Fee-clock sign-off. RESOLVED.** Client accepts the weaker, true claim:
  "no amendment disclosed through <date>". Already the implemented wording.
- **4. Cell-by-cell source review. RETURNED, and its conclusion corrected.**
  See NOTES/decisions.md -- six of the eight reviewed cells are already
  EDGAR-populated; nothing moved to structural. Client is re-running the
  question against the 13 expanded-metric cells, which is where the ceiling
  question actually lives.
- **11. Coverage acceptability. RESOLVED.** 26 of 36 with every blank attributed
  is presentable. "A blank with a reason is a defensible position. What I cannot
  defend is a blank that looks like a system failure."

### Still owed by the client (dated)

- **Weighted average spread definition** -- all-in yield vs spread over
  benchmark. From the PMs, this week. Extraction is per-filer table work
  regardless of which she picks.
- **House Word template, fonts, logo** -- promised same day.
- **Analyst answer on the 13 expanded-metric cells** -- no date given.

### Still open, not blocking

- **5. Do the PMs want to author metric definitions themselves?** Workflow
  preference, never answered. Option (b) exists either way.
- **Peer-list intent (Window 1, 1a/1c) and policy-vs-adjudication (1b).** Went
  to the CIO with the leverage question; only leverage came back.

## Window 3 (final) — the full list

Ordered by cost of guessing wrong. Everything below genuinely needs her; nothing
here can be resolved by building.

### ALL CLOSED — Window 3 delivered everything outstanding

Nothing below is open. Retained as the record of what was asked and answered.

**Closed in Window 3:** the CIO's leverage ruling (both bases; KREF non-recourse
securitisation out, repo in; two display rows, her words: "a single row with a
basis note is exactly the kind of thing a tired reader misses"); the Apex column
basis (institutional, net of both management and incentive fees); the analyst
sourcing review; the fee-clock label; superseded-rate labelling; NAV footnote
wording; custom-metric authorship (we write the definitions); weighted average
spread NOT authorised pending a definition; Word house template to follow.

**One thing her confirmation did not cover, and the system now says so.** She
confirmed her column's share class and fee treatment. That unblocks returns,
fees and yield. It does not say which leverage basis her single unlabelled
`leverage_ratio_dte` column uses, and leverage is regulatory-vs-economic rather
than a share-class question. Peers now report two bases differing by more than a
factor of two (CCLFX 0.32x regulatory vs 0.79x economic), so her leverage delta
is withheld and the cell carries "leverage basis unconfirmed". This is the last
open basis question in the system and it was never asked, because it only became
visible once leverage split into two rows.

### Carried over — she owes these (ALL NOW DELIVERED)

1. **CIO's leverage definition.** Regulatory vs. economic, and whether KREF's
   non-recourse securitisation and repo are in scope. TAKIX's leverage cell is
   blank and stays blank. The only open item implying per-filer extraction work
   rather than a config change, and the same metric class as the board incident.
2. **The basis of Apex's own column.** Share class, and net of which fees. Still
   blocks every peer-minus-Apex delta. Now a one-line change when it lands
   (`APEX_BASIS_CONFIRMED`) rather than new work.
3. **Fee-clock sign-off.** She asked to confirm the amendment-based clock holds
   for the other funds before production. It is built and running. Also confirm
   she accepts the weaker claim it can support: "no amendment disclosed through
   <date>", not "confirmed in force at <date>" -- a filer need not restate an
   unamended fee.
4. **Cell-by-cell source review.** Which manual-pack cells came from fund
   websites or IR pages rather than filings. The only thing that could still move
   the coverage picture, and it can only shrink scope, not grow it.

### New, from the scope update

5. **Do the PMs want to author metric definitions themselves?** Reduced by
   building: option (b) now exists. A table metric needs a row label; a prose
   metric can be declared with a regex-free `match` block (name the phrase, say
   what to take, bound the distance) that an analyst can write. `prose_patterns`
   remains for the hard cases. So the question is no longer "can they" but
   "do they want to, or would they rather send the metric to us" -- a workflow
   preference rather than a scoping decision.
6. **Weighted average spread: define it, and know it is not a config entry.**
   Zero coverage, and I checked why: GBDC's 10-K mentions the exact phrase once,
   and the numbers live in tables with per-filer structure rather than in prose.
   So this needs two things from her -- which definition she means (spread over
   benchmark vs all-in yield; they are different numbers) -- and an
   acknowledgement that extracting it is per-filer table work, not a definition
   she can add herself.
7. **RESOLVED BY BUILDING — not a question any more.** Non-accrual now ships on
   *both* bases as two metrics (0.6% cost, 0.3% fair value for GBDC). The basis
   is a render choice from data already extracted, not a blocking question.
8. **RESOLVED BY BUILDING.** Fund search now runs on EDGAR full-text search,
   which is the only SEC index that sees non-traded interval funds -- it finds
   CCLFX and returns its ticker, which the ticker files omit entirely. The
   browse-edgar endpoint that rate-limited is now a fallback, not the path.
9. **RESOLVED BY BUILDING.** `--save-peers` / `--peers` persist a peer set as
   readable JSON. Worth *telling* her the CIO can inspect the list without
   running anything, but there is nothing to decide.
10. **Does the Word document need their house template?** It is attached to a
    board deck. Currently generic Word styling. A template, fonts or a logo is
    trivial to apply and impossible to guess.

### If there is time

11. **Coverage acceptability.** Never actually answered -- she asked for the
    breakdown instead, and now has it. 26 of 36 with every blank attributed. Is
    that presentable to the board, or does the emptiness itself become the
    question?

## Window 3 (superseded — see the full list above)

- Confidence model sign-off, output format / handoff, production rollout
  assumptions for the technical doc.


## Escalated to the CIO — one batched conversation, end of week

Partner routes these; he explicitly declined to rule on them unilaterally.
Neither blocks the prototype. Both are render-time switches by design.

1. **TAKIX leverage basis — regulatory vs economic. HIGHEST PRIORITY.**
   TAKIX reports 0.00 in every N-PORT borrowing field while carrying ~$2.2bn
   total liabilities on $4.47bn net assets. The CIO has referred to the
   regulatory/economic distinction without defining it. This is the same metric
   class as the board incident, so no default is assumed. Pipeline emits all
   three constructions as flagged candidates; his answer selects one at render.
2. **CCLFX institutional-class staleness — is fund-level an acceptable *named*
   fallback?** Partner ruled blank + explanatory label, which is what is being
   built. Question to the CIO is only whether a clearly-labelled fund-level
   number is preferable to a blank for the part of each year when no
   class-level filing is under six months old (CCLFX's March FYE means the next
   class-level source lands ~Dec 2026).
3. **Carried from Window 1, still with him:** 1a (what KREF is on the list
   FOR), 1b (policy once vs. cell-by-cell adjudication), 1c (selection criteria
   for all four peers). Peer list is CIO-owned — partner flags, CIO adds/removes.

### Closed by the partner in this window
<!-- RESOLVED in Window 2: put to Lara directly and confirmed as her decisions,
     not consultant drafts. "You did not get ahead of me." No longer provisional. -->
- TAKIX unattributable class returns -> **suppress + label**, never a band.
- KREF distribution yield -> **both bases in-cell**, run-rate primary, TTM alongside.
- GBDC 5Y -> **blank + reason + actual coverage period**; never labelled 5Y.
