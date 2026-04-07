from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Device
from ..models import utc_now
from ..schemas import DeviceRead, DeviceRegister


router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.last_seen_at.desc())))


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceRegister, db: Session = Depends(get_db)) -> Device:
    device = db.scalar(select(Device).where(Device.name == payload.name))
    if device:
        device.hostname = payload.hostname
        device.platform = payload.platform
        device.is_server = payload.is_server
        device.last_seen_at = utc_now()
    else:
        device = Device(**payload.model_dump())
        db.add(device)
    db.commit()
    db.refresh(device)
    return device
