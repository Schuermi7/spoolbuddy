"""API Key management endpoints."""

import hashlib
import secrets
from datetime import datetime

from db import get_db
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


# === Schemas ===


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str
    can_read: bool = True
    can_write: bool = False
    can_control: bool = False


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""

    name: str | None = None
    can_read: bool | None = None
    can_write: bool | None = None
    can_control: bool | None = None
    enabled: bool | None = None


class APIKeyResponse(BaseModel):
    """Schema for API key response (without full key)."""

    id: int
    name: str
    key_prefix: str
    can_read: bool
    can_write: bool
    can_control: bool
    enabled: bool
    last_used: int | None = None
    created_at: int


class APIKeyCreateResponse(APIKeyResponse):
    """Response when creating a key - includes full key (shown only once)."""

    key: str


# === Helper Functions ===


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        tuple: (full_key, key_hash, key_prefix)
            - full_key: The complete API key (only shown once on creation)
            - key_hash: SHA256 hash for storage and verification
            - key_prefix: First 8 characters for display purposes
    """
    # Generate a secure random API key with prefix
    full_key = f"sb_{secrets.token_urlsafe(32)}"
    # Use SHA256 for hashing (simple and fast for API key validation)
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:8]
    return full_key, key_hash, key_prefix


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    return hashlib.sha256(key.encode()).hexdigest() == key_hash


# === API Endpoints ===


@router.get("/", response_model=list[APIKeyResponse])
async def list_api_keys():
    """List all API keys (without full key values)."""
    db = await get_db()
    async with db.conn.execute(
        """
        SELECT id, name, key_prefix, can_read, can_write, can_control,
               enabled, last_used, created_at
        FROM api_keys
        ORDER BY created_at DESC
        """
    ) as cursor:
        rows = await cursor.fetchall()

    return [
        APIKeyResponse(
            id=row[0],
            name=row[1],
            key_prefix=row[2],
            can_read=bool(row[3]),
            can_write=bool(row[4]),
            can_control=bool(row[5]),
            enabled=bool(row[6]),
            last_used=row[7],
            created_at=row[8],
        )
        for row in rows
    ]


@router.post("/", response_model=APIKeyCreateResponse)
async def create_api_key(data: APIKeyCreate):
    """Create a new API key.

    IMPORTANT: The full API key is only returned in this response.
    Store it securely - it cannot be retrieved again.
    """
    full_key, key_hash, key_prefix = generate_api_key()
    created_at = int(datetime.now().timestamp())

    db = await get_db()
    cursor = await db.conn.execute(
        """
        INSERT INTO api_keys (name, key_hash, key_prefix, can_read, can_write, can_control, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (data.name, key_hash, key_prefix, data.can_read, data.can_write, data.can_control, created_at),
    )
    await db.conn.commit()
    key_id = cursor.lastrowid

    return APIKeyCreateResponse(
        id=key_id,
        name=data.name,
        key_prefix=key_prefix,
        key=full_key,  # Only returned on creation
        can_read=data.can_read,
        can_write=data.can_write,
        can_control=data.can_control,
        enabled=True,
        last_used=None,
        created_at=created_at,
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key_by_id(key_id: int):
    """Get an API key by ID."""
    db = await get_db()
    async with db.conn.execute(
        """
        SELECT id, name, key_prefix, can_read, can_write, can_control,
               enabled, last_used, created_at
        FROM api_keys WHERE id = ?
        """,
        (key_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIKeyResponse(
        id=row[0],
        name=row[1],
        key_prefix=row[2],
        can_read=bool(row[3]),
        can_write=bool(row[4]),
        can_control=bool(row[5]),
        enabled=bool(row[6]),
        last_used=row[7],
        created_at=row[8],
    )


@router.patch("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(key_id: int, data: APIKeyUpdate):
    """Update an API key."""
    # Build dynamic update query
    updates = []
    params = []

    if data.name is not None:
        updates.append("name = ?")
        params.append(data.name)
    if data.can_read is not None:
        updates.append("can_read = ?")
        params.append(data.can_read)
    if data.can_write is not None:
        updates.append("can_write = ?")
        params.append(data.can_write)
    if data.can_control is not None:
        updates.append("can_control = ?")
        params.append(data.can_control)
    if data.enabled is not None:
        updates.append("enabled = ?")
        params.append(data.enabled)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(key_id)

    db = await get_db()
    async with db.conn.execute("SELECT id FROM api_keys WHERE id = ?", (key_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="API key not found")

    await db.conn.execute(
        f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?",  # nosec B608
        params,
    )
    await db.conn.commit()

    return await get_api_key_by_id(key_id)


@router.delete("/{key_id}")
async def delete_api_key(key_id: int):
    """Delete (revoke) an API key."""
    db = await get_db()
    async with db.conn.execute("SELECT id FROM api_keys WHERE id = ?", (key_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="API key not found")

    await db.conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    await db.conn.commit()

    return {"message": "API key deleted"}


# === API Key Validation Dependency ===


async def validate_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> dict:
    """Validate API key from request headers.

    Accepts both:
    - X-API-Key: <key>
    - Authorization: Bearer <key>
    """
    api_key_value = None

    if x_api_key:
        api_key_value = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        api_key_value = authorization.replace("Bearer ", "")

    if not api_key_value:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide 'X-API-Key' header or 'Authorization: Bearer <key>'",
        )

    # Get all enabled API keys and check them
    db = await get_db()
    async with db.conn.execute(
        """
        SELECT id, name, key_hash, can_read, can_write, can_control
        FROM api_keys
        WHERE enabled = 1
        """
    ) as cursor:
        rows = await cursor.fetchall()

    for row in rows:
        key_id, name, key_hash, can_read, can_write, can_control = row
        if verify_api_key(api_key_value, key_hash):
            # Update last_used timestamp
            await db.conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE id = ?",
                (int(datetime.now().timestamp()), key_id),
            )
            await db.conn.commit()

            return {
                "id": key_id,
                "name": name,
                "can_read": bool(can_read),
                "can_write": bool(can_write),
                "can_control": bool(can_control),
            }

    raise HTTPException(status_code=401, detail="Invalid API key")


def require_permission(permission: str):
    """Dependency factory to check specific permission."""

    async def check_permission(
        x_api_key: str | None = Header(None, alias="X-API-Key"),
        authorization: str | None = Header(None),
    ):
        api_key = await validate_api_key(x_api_key, authorization)
        if not api_key.get(f"can_{permission}"):
            raise HTTPException(
                status_code=403,
                detail=f"API key does not have '{permission}' permission",
            )
        return api_key

    return check_permission
