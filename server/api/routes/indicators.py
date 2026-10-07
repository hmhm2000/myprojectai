"""Indicator definitions and values (computed in the backend; the chart only draws them)."""
import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import get_current_user
from core.errors import BadRequest
from indicators.base import REGISTRY
from indicators.service import compute_indicator
from services.candle_service import candle_service

router = APIRouter(prefix="/api/indicators", tags=["indicators"], dependencies=[Depends(get_current_user)])


class ParamOut(BaseModel):
    name: str
    type: str
    default: float | int | str
    min: Optional[float] = None
    max: Optional[float] = None


class OutputOut(BaseModel):
    name: str
    plot: str
    color: Optional[str] = None


class IndicatorOut(BaseModel):
    id: str
    name: str
    pane: str
    description: str
    params: list[ParamOut]
    outputs: list[OutputOut]
    levels: list[float]


class IndicatorValuesOut(BaseModel):
    indicator: str
    params: dict
    time: list[int]
    closed: list[bool]
    outputs: dict[str, list[Optional[float]]]


@router.get("", response_model=list[IndicatorOut])
def list_indicators():
    return [
        IndicatorOut(id=i.id, name=i.name, pane=i.pane, description=i.description, levels=i.levels,
                     params=[ParamOut(**p.__dict__) for p in i.params],
                     outputs=[OutputOut(**o.__dict__) for o in i.outputs])
        for i in REGISTRY.values()
    ]


@router.get("/{indicator_id}/values", response_model=IndicatorValuesOut)
def indicator_values(
    indicator_id: str,
    symbol: str = Query(...),
    interval: str = Query("1h"),
    start: int = Query(..., description="Unix seconds - first candle (inclusive)"),
    end: Optional[int] = Query(None, description="Unix seconds - last candle; default now"),
    params: str = Query("{}", description='JSON, e.g. {"length": 14}'),
):
    try:
        raw = json.loads(params)
        if not isinstance(raw, dict):
            raise ValueError
    except ValueError:
        raise BadRequest("indicators.invalid_param", "params must be a JSON object", param="params")
    now = time.time()
    result = compute_indicator(candle_service, indicator_id, raw, symbol.strip().upper(), interval,
                               start, end or int(now), now)
    return IndicatorValuesOut(indicator=result.indicator_id, params=result.params, time=result.time,
                              closed=result.closed, outputs=result.outputs)
