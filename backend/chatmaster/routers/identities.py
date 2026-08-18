"""Database-backed identity/persona endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from chatmaster.core.auth import get_current_workspace_id
from chatmaster.db.session import get_db
from chatmaster.identities.schema import IdentityCreate, IdentityDetail, IdentityOut, IdentityUpdate
from chatmaster.identities.service import (
    IdentityNotFound,
    create_identity,
    duplicate_identity,
    get_identity_model,
    list_identity_models,
    set_archived,
    to_detail,
    to_out,
    update_identity,
)

router = APIRouter(prefix="/api/identities", tags=["identities"])


@router.get("", response_model=list[IdentityOut])
async def list_identities(
    include_archived: bool = Query(False),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return [
        to_out(item)
        for item in list_identity_models(
            db,
            workspace_id=workspace_id,
            include_archived=include_archived,
        )
    ]


@router.get("/{identity_id}", response_model=IdentityDetail)
async def get_identity(
    identity_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return to_detail(
            get_identity_model(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                include_archived=True,
            )
        )
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")


@router.post("", response_model=IdentityDetail)
async def post_identity(
    body: IdentityCreate,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return to_detail(create_identity(db, workspace_id=workspace_id, payload=body))


@router.put("/{identity_id}", response_model=IdentityDetail)
async def put_identity(
    identity_id: str,
    body: IdentityUpdate,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return to_detail(
            update_identity(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                payload=body,
            )
        )
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail="Identity not found") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{identity_id}/archive", response_model=IdentityDetail)
async def archive_identity(
    identity_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return to_detail(
            set_archived(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                archived=True,
            )
        )
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail="Identity not found") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{identity_id}/restore", response_model=IdentityDetail)
async def restore_identity(
    identity_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return to_detail(
            set_archived(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                archived=False,
            )
        )
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail="Identity not found") from None


@router.post("/{identity_id}/duplicate", response_model=IdentityDetail)
async def clone_identity(
    identity_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return to_detail(duplicate_identity(db, workspace_id=workspace_id, identity_id=identity_id))
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail="Identity not found") from None
