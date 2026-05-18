# TGC Pricing Engine — Supabase Database

Multi-tenant PostgreSQL schema with Row Level Security for The Gracious Collection Pricing Engine.

## Architecture

```
tenants (1) ──< properties (1) ──< room_types
                              ──< occupancy_snapshots
                              ──< rate_recommendations
                              ──< bookings
                              ──< guests
user_profiles  ── links auth.users → tenants + role
market_signals ── NO tenant_id, shared aggregate (no RLS)
```

### Roles
| Role | Own tenant | All tenants |
|---|---|---|
| `inn_owner` | Full CRUD + settings | — |
| `inn_manager` | Read + create recs/bookings, no settings | — |
| `shg_admin` | — | Full CRUD |
| `shg_analyst` | — | Read only |

## Setup (Supabase)

### 1. Create Supabase project
New project at [supabase.com](https://supabase.com). Note your project URL and anon/service keys.

### 2. Run migrations in order

Open **Supabase Dashboard → SQL Editor** and run each file:

```
database/migrations/001_schema.sql     # Tables + indexes
database/migrations/002_auth_rls.sql   # RLS policies + JWT hook
database/migrations/003_functions.sql  # provision_tenant()
```

### 3. Register the custom JWT hook

**Dashboard → Auth → Hooks → Custom Access Token Hook**
- Enable hook
- Select schema: `public`
- Select function: `custom_access_token_hook`

This injects `tenant_id` and `app_role` into every JWT so RLS policies can read them.

### 4. Seed Anchorage 1770 demo data

```sql
-- SQL Editor
\i database/seed/anchorage_1770.sql
-- or paste contents directly
```

Generates:
- Tenant `anchorage-1770-demo` with Anchorage 1770 Inn property
- 4 room types (Waterfront Suite, Waterview Suite, Garden View Room, Cottage Room)
- ~2,920 daily occupancy snapshots (2 years, Beaufort SC seasonal model)
- ~350–450 synthetic bookings (90-day window + 30 days ahead)
- 24 months of Beaufort/Lowcountry market signals

### 5. Create the owner's auth account

After seeding, create the owner's Supabase Auth user either via Dashboard or:

```js
const { data } = await supabase.auth.admin.createUser({
  email: 'jwilliams8559@gmail.com',
  password: 'your-secure-password',
  email_confirm: true,
})

// Link to tenant
await supabase.rpc('link_user_to_tenant', {
  p_user_id: data.user.id,
  p_tenant_id: '<tenant_id from seed output>',
  p_role: 'inn_owner'
})
```

## Adding a new tenant

```sql
-- Generic (creates placeholder room types)
SELECT provision_tenant(
  'My Inn Name',
  'my-inn-slug',          -- unique slug, used in URLs
  'owner@myinn.com',
  'starter'               -- plan_tier: starter | professional | enterprise
);

-- Then after auth.signUp:
SELECT link_user_to_tenant('<user_uuid>', '<tenant_uuid>', 'inn_owner');
```

## RLS Test

Verifies multi-tenant isolation with 5 suites (29 assertions):

```bash
psql $DATABASE_URL -f database/tests/test_rls.sql
```

Or paste into Supabase SQL Editor. The entire test runs inside a transaction and **rolls back** — no permanent test data is written. Expected output:

```
suite               | test_name                                 | expected | actual | result
A: Alpha inn_owner  | sees own property (count=1)               | 1        | 1      | ✓ PASS
A: Alpha inn_owner  | cannot see Beta property (count=0)        | 0        | 0      | ✓ PASS
...
ALL 29 RLS TESTS PASSED — tenant isolation is working correctly.
```

## Environment variables

```bash
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...    # server-side only, never expose to browser
```

```python
# config/database.py — add Supabase client
from supabase import create_client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
```

## Schema decisions

**Why `tenant_id` on every row?** Denormalized for RLS performance — policy expressions hit a single indexed column rather than joining through the property hierarchy.

**Why no RLS on `market_signals`?** Fully anonymized aggregate data (no property or guest info). All authenticated users can read it; no writes from tenants.

**Why `email_encrypted` + `email_hash`?** Encrypt at application layer with pgcrypto for GDPR compliance; store SHA-256 hash for O(1) dedup lookups without decrypting the full dataset.

**Why `provision_tenant` is SECURITY DEFINER?** Tenant creation must bypass RLS (no JWT context during provisioning). The function is called from trusted server-side code only, never directly from client JWTs.
