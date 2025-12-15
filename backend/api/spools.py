from fastapi import APIRouter, HTTPException

from db import get_db
from models import Spool, SpoolCreate, SpoolUpdate

router = APIRouter(prefix="/spools", tags=["spools"])


@router.get("", response_model=list[Spool])
async def list_spools():
    """Get all spools."""
    db = await get_db()
    return await db.get_spools()


@router.get("/{spool_id}", response_model=Spool)
async def get_spool(spool_id: str):
    """Get a single spool."""
    db = await get_db()
    spool = await db.get_spool(spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spool not found")
    return spool


@router.post("", response_model=Spool, status_code=201)
async def create_spool(spool: SpoolCreate):
    """Create a new spool."""
    db = await get_db()
    return await db.create_spool(spool)


@router.put("/{spool_id}", response_model=Spool)
async def update_spool(spool_id: str, spool: SpoolUpdate):
    """Update an existing spool."""
    db = await get_db()
    updated = await db.update_spool(spool_id, spool)
    if not updated:
        raise HTTPException(status_code=404, detail="Spool not found")
    return updated


@router.delete("/{spool_id}", status_code=204)
async def delete_spool(spool_id: str):
    """Delete a spool."""
    db = await get_db()
    if not await db.delete_spool(spool_id):
        raise HTTPException(status_code=404, detail="Spool not found")
