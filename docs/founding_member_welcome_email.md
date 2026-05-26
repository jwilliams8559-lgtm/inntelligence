# Founding Member Welcome Email Template

*The email Jim sends to each founding member once their account is created. Replace every
`[PLACEHOLDER]` before sending. This is the same content the system sends automatically via
SendGrid on provisioning — keep them in sync.*

---

**From:** Jim Williams <jim@graciouscollection.com>
**To:** `[OWNER_EMAIL]`
**Subject:** Welcome to INNtelligence — Your account is ready

---

Dear `[FIRST_NAME]`,

Welcome to INNtelligence — and thank you for being one of our founding members. You're among
the first boutique inns to run the same caliber of revenue intelligence that the big hotel
groups pay a fortune for, built specifically for a property like **`[PROPERTY_NAME]`**.

**Your login details**

- Dashboard: `[LOGIN_URL]`  (e.g., https://app.inntelligence.app/login)
- Email: `[OWNER_EMAIL]`
- Temporary password: `[TEMP_PASSWORD]`

Please change your password right after your first sign-in.

**Schedule your onboarding call**

This is the fun part. In about 90 minutes together we'll connect your systems and get live,
reviewable rate recommendations on your screen.

👉 **Book your onboarding call:** `[CALENDLY_URL]`

**Please have these ready before our call**

1. Your **PMS login** — ResNexus API key, or your Cloudbeds login for one-click connect.
2. A short **list of your main competitors** (the 4–8 properties guests compare you to).
3. Your **base rate for each room type**, plus the lowest rate you'd ever accept and the
   highest you'd charge at peak.

That's everything — I'll handle the rest on the call.

**As a founding member, here's our promise to you**

- INNtelligence is **free for your first 6 months**, then continues at $699/month (Professional)
  — no surprises.
- A **direct line to me** whenever you need it.
- Your feedback genuinely shapes the roadmap — you're helping build this.

In return, all we ask is that you connect your PMS, join our monthly strategy calls, and — once
you've seen the results — share an honest testimonial.

I'm looking forward to getting `[PROPERTY_NAME]` pricing like a pro. Reply to this email any time,
or just grab a time on my calendar above.

Warm regards,

**Jim Williams**
Founder, INNtelligence by The Gracious Collection
📧 jim@graciouscollection.com · 📱 (404) 909-5818

*Boutique Hospitality Intelligence*

---

### Placeholders to replace
| Placeholder | Where it comes from |
|---|---|
| `[FIRST_NAME]` | Owner first name |
| `[PROPERTY_NAME]` | Inn / property name |
| `[OWNER_EMAIL]` | Login email (the address this is sent to) |
| `[TEMP_PASSWORD]` | Generated at provisioning (shown in the Add-Client modal) |
| `[LOGIN_URL]` | `APP_PUBLIC_URL` + `/login` |
| `[CALENDLY_URL]` | Your onboarding scheduling link (`CALENDLY_URL` env var) |
