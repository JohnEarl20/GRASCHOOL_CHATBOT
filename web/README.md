# GRA SCHOOL web app (Vercel)

This Next.js app is a separate migration target. The original Streamlit app remains in the repository and is unchanged.

## Required setup

1. Create a Supabase project and run [`supabase/schema.sql`](./supabase/schema.sql) in its SQL Editor.
2. In Vercel, import this GitHub repository and set **Root Directory** to `web`.
3. Configure these environment variables for Preview and Production:
   - `NEXT_PUBLIC_SUPABASE_URL` — Supabase project URL.
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase publishable/anon key.
   - `SUPABASE_SERVICE_ROLE_KEY` — Supabase service-role key. Keep this secret; never prefix it with `NEXT_PUBLIC_` or commit it.
4. In Supabase Auth settings, set the production site URL and add the Vercel domain to the allowed redirect URLs. Keep email confirmation enabled.
5. Promote a trusted staff account in the Supabase SQL Editor only after that account has registered:

   ```sql
   update public.profiles
   set role = 'staff'
   where student_id = 'THE_REGISTERED_STUDENT_ID';
   ```

   Registration only creates student accounts. Do not expose a role selector to visitors.

For local development, copy `.env.example` to `.env.local` and fill in the values privately. Never commit `.env.local`.

## Current migration scope

The web app currently includes Supabase email/password authentication, student profiles, saved conversations and messages, typed assistant chat, record/upload/playback-only voice input, a basic staff metrics page, and account preferences. The assistant uses an exported copy of the trained intent model and the school's ontology.

This is an initial migration slice, not yet feature parity with every Streamlit staff tool. In particular, staff live-presence/chat operations, full analytics and retraining tools, all ten advanced settings categories, and durable audio storage still need migration before replacing the Streamlit deployment.
