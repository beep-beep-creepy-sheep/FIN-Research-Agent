from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from finresearch.repositories.data_quality import DataQualityRepository


router = APIRouter()


@router.get("/summary")
def data_quality_summary() -> dict[str, object]:
    return DataQualityRepository().summary()


@router.get("/issues")
def list_data_quality_issues(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    return DataQualityRepository().list(status=status, limit=limit)


@router.get("/issues/{issue_id}")
def get_data_quality_issue(issue_id: int) -> dict[str, object]:
    issue = DataQualityRepository().get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail={"code": "data_quality_issue_not_found"})
    return issue
