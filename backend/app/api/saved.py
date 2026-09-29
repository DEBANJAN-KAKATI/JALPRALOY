"""Saved places. In-memory for now — TODO: persist in the saved_places table and
evaluate them after every forecast run (see docs/08_ALERTS_CAP.md)."""
import uuid

import h3
from fastapi import APIRouter, HTTPException

from app.schemas import SavedPlace, SavedPlaceIn

router = APIRouter(prefix="/saved-places", tags=["saved places"])
_STORE: dict[str, SavedPlace] = {}


@router.get("", response_model=list[SavedPlace])
def list_places():
    return list(_STORE.values())


@router.post("", response_model=SavedPlace, status_code=201)
def add_place(place: SavedPlaceIn):
    sp = SavedPlace(**place.model_dump(), id=uuid.uuid4().hex[:12], h3=h3.latlng_to_cell(place.lat, place.lon, 9))
    _STORE[sp.id] = sp
    return sp


@router.delete("/{place_id}", status_code=204)
def delete_place(place_id: str):
    if _STORE.pop(place_id, None) is None:
        raise HTTPException(404)
