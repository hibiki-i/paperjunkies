from __future__ import annotations

from supabase import Client, create_client
from supabase.client import ClientOptions

from .settings import Settings


def create_supabase(settings: Settings, *, access_token: str | None = None) -> Client:
    """Create a Supabase client.

    Notes:
    - If SUPABASE_SERVICE_ROLE_KEY is set, it is used for server-side inserts.
    - If SUPABASE_ACCESS_TOKEN is set, it will be attached as a Bearer token.

    This keeps the app workable both with RLS+JWT and with service-role during development.
    """

    key = settings.supabase_service_role_key or settings.supabase_anon_key

    options: ClientOptions | None = None
    token = access_token or settings.supabase_access_token
    if token:
        options = ClientOptions(headers={"Authorization": f"Bearer {token}"})

    return create_client(settings.supabase_url, key, options)
