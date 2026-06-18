"""Identity listing/detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from chatmaster.identities.loader import IdentityNotFound, get_registry

router = APIRouter(prefix="/api/identities", tags=["identities"])


@router.get("")
async def list_identities():
    return get_registry().list_public()


@router.get("/{identity_id}")
async def get_identity(identity_id: str):
    try:
        get_registry().get(identity_id)  # validates existence
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")
    # Return the public projection for this single identity.
    for pub in get_registry().list_public():
        if pub.id == identity_id:
            return pub
    raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")
