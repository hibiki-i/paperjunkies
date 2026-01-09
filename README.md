## Paperjunkies

Streamlit web app backed by Supabase (Postgres + Auth).

### Prereqs

- Python 3.10+
- Supabase project with the existing schema:
  - `profiles`, `references`, `posts`, `post_terms`

### Configure

Provide Supabase connection values via environment variables or Streamlit secrets.

Environment variables:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

Optional (useful for local dev or server-side inserts):

- `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS; keep private)
- `SUPABASE_ACCESS_TOKEN` (JWT for RLS-protected access)

Auth (app assumes you are authenticated):

- Set `SUPABASE_USER_ID` to your `auth.users.id` UUID for local development, OR
- Set `st.session_state['user_id']` from your auth integration.

The `profiles` table must already contain a row for that UUID.

### Install

If you're using `uv`:

1. `uv sync`

### Run

- `streamlit run app.py`

### Theme (optional)

Streamlit supports app theming via `.streamlit/config.toml`.

- Edit `.streamlit/config.toml` and uncomment the `[theme]` section to set `primaryColor`, background colors, and typography.

Pages:

- Timeline: post reads by pasting a BibTeX entry (must include `abstract`)
- Dashboard: semantic trends + time-of-day reading patterns (personal/team views)
