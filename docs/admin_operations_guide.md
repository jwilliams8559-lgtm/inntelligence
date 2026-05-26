# INNtelligence Admin Operations Guide — For Jim Williams

*Internal · The Gracious Collection. Not for distribution to clients.*

This is your operating manual for running INNtelligence: onboarding clients, keeping them
healthy, and the technical runbook for Railway + Supabase.

---

## 1. Adding a New Client

**Workflow:** Management Console → **+ Onboard New Property** (or **Add New Client**).

1. Enter: **property name, owner name, owner email, plan tier, city, state**.
2. Click **Create + send welcome**. The system:
   - Creates a **Supabase auth user** with a generated temporary password
     (`role: inn_owner`, `pending_onboarding: true`, plan tier in `app_metadata`).
   - Provisions the **tenant record** (DB `provision_tenant()` function, else inserts the row).
   - Sends the **welcome email via SendGrid** with login URL + temp password + scheduling link.
3. The modal shows the **temp password** — copy it somewhere safe in case the email is delayed.
4. Schedule the **onboarding call** (Calendly link is in the welcome email).

**Plan tiers:** Starter $399 · Professional $699 · Enterprise $1,200 · Premium $2,400 ·
Founding Member (free 6 months → $699).

> Admin access is gated to `tgc_admin`. Your account (`jwilliams8559@gmail.com`) is always treated
> as admin via the email allowlist, even if a JWT claim is missing.

---

## 2. Conducting an Onboarding Call (90-minute agenda)

- **0–10 — Welcome & overview.** Confirm property details. Set expectations: by the end they'll
  have live, reviewable rate recommendations.
- **10–25 — PMS connection.** ResNexus API key or Cloudbeds OAuth. Kick off the 2-year history
  sync early so it finishes during the call. If no PMS, set expectation of demo data.
- **25–35 — Competitor confirmation.** Review auto-discovered comps. Confirm Tier 1, prune bad
  results, add any they know are missing. Sanity-check for private residences.
- **35–45 — Room configuration review.** Confirm room types, bathroom types, and especially the
  **min/max guardrails** — this is where their comfort lives.
- **45–55 — Autopilot setup.** Recommend Balanced autopilot on standard rooms, Manual on top suites
  for the first weeks. Explain guardrails and the weekly report.
- **55–80 — First recommendations walkthrough.** Open the Rate Calendar together. Explain a green
  premium, a rose discount, an event date, a gap night. Approve a few rates live so they feel it.
- **80–90 — Q&A and next steps.** Book the first monthly strategy call. Point them to the Setup
  Guide and Training Manual.

---

## 3. Monitoring Client Health

**Management Console metrics to watch:**
- **Pending approvals** climbing week over week → they're not engaging; reach out.
- **Sync status** not "synced" → PMS connection problem; fix before it erodes trust.
- **Last login** going stale (7+ days) → proactive check-in.

**Signs a client isn't engaging:** recommendations piling up unapproved, Autopilot left off on
every room, no campaign sends. A short "anything I can help price this week?" email usually
re-activates them.

---

## 4. Troubleshooting Client Issues

- **PMS sync failures:** re-check API key / re-authorize OAuth; confirm API permissions on their
  PMS user; check sync logs (Railway logs / Supabase). Re-trigger sync from Settings.
- **Rate publishing errors:** confirm the room is Autopilot-enabled; confirm channel-manager auth;
  check the rate isn't clamped by guardrails.
- **Competitor data issues:** remove bad discoveries (closed/residential); add known comps
  manually; widen/narrow the discovery radius.
- **Auth problems:** use the Supabase dashboard or the password-reset flow (see §7) to issue a new
  temporary password; confirm the user's `role`/`tenant_id` claims are set.

---

## 5. Monthly Client Strategy Calls (agenda template)

1. **Review last month's performance** — RevPAR, ADR, occupancy vs last year; Autopilot lift.
2. **Upcoming demand periods** — festivals/events in the next 60–90 days; confirm minimum stays.
3. **Pricing strategy adjustments** — tune base/min/max or Autopilot confidence based on results.
4. **Feature questions & feedback** — what's working, what's confusing, what they wish it did.

Keep it to 30 minutes. End with one concrete action you'll each take before next month.

---

## 6. Founding Member Program Management

- **Data quality scores:** track each founding member's data completeness (PMS connected, history
  synced, competitors confirmed). Higher quality = better benchmarks for everyone.
- **Testimonials at 90 days:** once they've seen documented results, request a testimonial — they're
  most enthusiastic right after their first strong festival weekend.
- **Convert to paid at 6 months:** the free period rolls to **$699/month (Professional)**. Send a
  heads-up at month 5 with their documented ROI to make the conversion easy.
- **Case study process:** at the testimonial stage, capture before/after RevPAR + ADR and a quote.
  Anonymize first; name once they're comfortable.

Target: **3–5 founding members.** Track them in the Management Console founding-members panel.

---

## 7. Railway and Supabase Operations

**Deploy updates (Railway builds the JSX app + Flask):**
```bash
git push origin dev                 # back up work
git checkout production && git merge dev && git push origin production   # deploy
git checkout dev
```
Railway runs `nixpacks.toml`: installs deps, `cd dashboard && npm run build`, then
`gunicorn app:app`. Confirm the watched branch in Railway → Settings → Source.

**Check logs:** Railway → service → **Deployments / Logs**. Flask logs auth failures, SendGrid
results, and sync warnings at WARNING level.

**Reset a user password:** Supabase → Authentication → Users → select user → **Send password
recovery** (or "Reset password"). Or have them use **Forgot password** on the login screen, which
calls `/api/auth/reset-password` → Supabase recover.

**Required Railway env vars:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`,
`ELEVENLABS_API_KEY`, `SENDGRID_API_KEY`, `APP_PUBLIC_URL`, `WELCOME_FROM_EMAIL`, `CALENDLY_URL`.
(`PORT` is injected by Railway.)

**Database backup verification:** Supabase takes automated daily backups (Project → Database →
Backups). Periodically confirm a recent backup exists; before any schema migration, take a manual
backup first.

**Auth modes:** with Supabase env set, the dashboard **requires login**. With those vars unset
(e.g., local UI work), the app runs in **open/demo mode** so you can browse without a session.

---

*Internal operations doc — INNtelligence by The Gracious Collection.*
