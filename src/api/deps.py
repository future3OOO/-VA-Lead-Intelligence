from uuid import UUID

from fastapi import Header, HTTPException

from db.session import get_session as _get_session


async def require_workspace(x_workspace_id: str = Header(...), x_api_key: str = Header(...)) -> UUID:
    from config.settings import Settings

    settings = Settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        return UUID(x_workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid workspace ID") from exc


get_session = _get_session
