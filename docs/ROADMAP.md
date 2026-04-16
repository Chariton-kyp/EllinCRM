# EllinCRM — Roadmap

The engineering foundation is done (green CI, professional license, security
hardening, production-grade test suite). This file tracks the **marketing-
and reach-focused** follow-ups that make the project meaningfully more
useful as a portfolio piece.

All three items are deliberately **post-v1.0** — they need time, money, or a
separate workflow and shouldn't block day-to-day engineering work.

---

## ⏳ Planned

### 1. Live demo deployment

**What.** A single public URL that visitors can click and interact with
without having to clone and run Docker locally. E.g.:

- Frontend → Vercel (free tier, excellent Next.js support).
- Backend → Railway / Fly.io / Render (~5–10 EUR/month for a small worker
  with Postgres and enough RAM for EmbeddingGemma, or cloud-managed pgvector).
- Alternatively, the full stack on the existing OVH VPS (already sized right
  per `CLAUDE.md`).

**Why.** The single biggest conversion lever for an AI portfolio piece: a
one-click demo turns "interesting GitHub readme" into "I just used it". The
existing screenshots carry weight only up to a point.

**Watch-outs.**

- Cost control — the chat agent calls Claude Sonnet; rate limit anonymous
  users hard (e.g. 5 queries / IP / day).
- Data freshness — seed with the 25 bundled dummy records; make clear the
  demo is read-only for uploads.
- Secrets hygiene — deploy secrets go into the hosting platform's secrets
  manager, never into the repo. The existing `SecretStr` migration keeps
  them hidden from stack traces in hosted logs.

**Success signal.** README badge at the top linking to the live URL; a
"demo" link that opens the dashboard pre-populated.

---

### 2. Demo video embedded in the README

**What.** A 3–5 minute walkthrough recorded in Greek, uploaded to YouTube,
and embedded at the very top of the README (just under the title, above the
screenshots).

**Why.** Chariton is comfortable on camera (per `CLAUDE.md`); 18–20 videos
already recorded. Moving video from "future YouTube channel" to "pinned at
the top of the portfolio repo" compounds reach: GitHub visitors, LinkedIn
posts referencing the repo, and YouTube SEO all point at the same asset.

**Scope.** Cover the four talking points already documented in
`CLAUDE.md → DEMO VIDEO TALKING POINTS`:

1. Local SLM runs on the server (EmbeddingGemma).
2. Hybrid RAG explained in 60s.
3. Multi-model architecture (right model for each task).
4. Greek-first NLP and human-in-the-loop review.

**Distribution follow-up.**

- Main recording → YouTube (long form).
- Same recording cut into 15–60 s Reels → Instagram, LinkedIn.
- LinkedIn post with the GitHub repo link and 2–3 of the Reels.

**Watch-outs.**

- The live demo (Item 1) should ideally exist first — the video becomes
  much more compelling if it ends with "and you can try it yourself at
  crm.ellinai.com" rather than "clone it from GitHub".

---

### 3. `CHANGELOG.md` + release discipline

**What.** A Keep-a-Changelog-style top-level file, updated on every tagged
release, starting from the (already shipped) `v1.0.0`. Each version's
section lists **Added / Changed / Fixed / Security** buckets with a 1-line
per-commit summary.

**Why.** Low-effort, high-legitimacy signal. It says "this is not a
weekend project — it is maintained". Works in tandem with the existing
GitHub Releases page (each release gets both a tag and a CHANGELOG entry
that links to it).

**Scope.**

1. Backfill `[1.0.0] — 2026-04-15` from the commit history between the
   initial commit and the v1.0.0 release tag.
2. Keep `[Unreleased]` at the top; move items under the next version when
   a tag is cut.
3. Add a line to `docs/User_Manual.md` (or `CONTRIBUTING.md` if that gets
   created) pointing future contributors at this convention.

**Automation option.** `git-cliff` or `release-drafter` can seed the
changelog from conventional commits, which the repo already uses
(`chore(ci):`, `feat(chat):`, `fix(extractors):` …). Worth enabling when
the project picks up a second contributor.

---

## How to use this file

- When you start one of these items, create a dedicated branch
  (`feat/demo-deploy`, `docs/demo-video`, `docs/changelog`) and reference
  this roadmap entry in the PR description.
- When one ships, move its section from **Planned** to **Done** (with the
  date and the PR that closed it) instead of deleting the text — it then
  doubles as a portfolio-relevant changelog in its own right.
- If priorities change, edit freely; this is intentionally a living
  document, not a commitment.
