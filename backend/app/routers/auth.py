"""GitHub OAuth authentication router."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth import create_jwt, get_current_user
from app.config import settings
from app.dependencies import DBSession
from app.models import User
from app.schemas.auth import UserResponse

logger = logging.getLogger(__name__)

# Auth endpoints don't have the /api/v1 prefix so the OAuth redirect URL is cleaner
router = APIRouter(tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/auth/github/login")
async def github_login():
    """Redirect the user to GitHub's OAuth authorization page."""
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured")

    params = {
        "client_id": settings.github_client_id,
        "scope": "read:user user:email",
    }
    url = f"{GITHUB_AUTHORIZE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return RedirectResponse(url=url)


@router.get("/auth/github/callback")
async def github_callback(db: DBSession, code: str | None = None):
    """Handle the OAuth callback from GitHub.

    Exchanges the authorization code for an access token,
    fetches the user profile, upserts the User record,
    creates a JWT session cookie, and redirects to the frontend.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Step 1: Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code != 200:
        logger.error(f"GitHub token exchange failed: {token_resp.text}")
        raise HTTPException(
            status_code=502, detail="Failed to authenticate with GitHub"
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        error = token_data.get("error_description", "Unknown error")
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    # Step 2: Fetch user profile and primary email
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(GITHUB_USER_URL, headers=auth_headers)

        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=502, detail="Failed to fetch GitHub profile"
            )

        # Fetch emails from /user/emails and pick the primary one
        emails_resp = await client.get(GITHUB_USER_EMAILS_URL, headers=auth_headers)

    gh_user = user_resp.json()
    github_id = gh_user["id"]
    username = gh_user["login"]

    email: str | None = None
    if emails_resp.status_code == 200:
        emails: list[dict] = emails_resp.json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = primary["email"] if primary else None

    # Fall back to the email on the public profile
    if not email:
        email = gh_user.get("email")
    avatar_url = gh_user.get("avatar_url")

    # Step 3: Upsert user
    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if user:
        # Update profile fields
        user.username = username
        user.email = email or user.email
        user.avatar_url = avatar_url
    else:
        user = User(
            github_id=github_id,
            username=username,
            email=email,
            avatar_url=avatar_url,
        )
        db.add(user)

    await db.flush()
    await db.refresh(user)

    logger.info(f"User authenticated: {username} (github_id={github_id})")

    # Step 4: Create JWT and set cookie
    token = create_jwt(user.id)

    # Cross-site (e.g. Netlify frontend ↔ Fly.dev backend) requires
    # Secure=True + SameSite=None for cookies to be sent on fetch() calls
    is_production = settings.frontend_url.startswith("https")

    response = RedirectResponse(url=f"{settings.frontend_url}/spaces", status_code=302)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=settings.jwt_expiry_hours * 3600,
        path="/",
    )
    return response


@router.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(request: Request, db: DBSession):
    """Get the currently authenticated user."""
    user = await get_current_user(request, db)
    return UserResponse.model_validate(user)


@router.post("/api/v1/auth/logout")
async def logout():
    """Clear the session cookie."""
    is_production = settings.frontend_url.startswith("https")
    response = RedirectResponse(url=f"{settings.frontend_url}/login", status_code=302)
    response.delete_cookie(
        "session",
        path="/",
        secure=is_production,
        samesite="none" if is_production else "lax",
    )
    return response
