import { createClient } from '@supabase/supabase-js'

// Real Supabase Auth client. Reads Vite env vars (set in dashboard/.env.local
// and Railway). When they're absent the export is null and the app runs in
// "open / demo mode" (no login wall) — see AuthContext.
const url = import.meta.env.VITE_SUPABASE_URL
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = (url && anon)
  ? createClient(url, anon, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null

export const supabaseConfigured = !!supabase
