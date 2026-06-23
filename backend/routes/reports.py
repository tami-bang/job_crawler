from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.services.report_service import (
    ReportMailConfigError,
    send_report_email,
    validate_email_address,
)


router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportJob(BaseModel):
    score: int | float = 0
    company: str = ""
    title: str = ""
    location: str = ""
    career: str = ""
    employment_type: str = ""
    deadline: str = ""
    matched_keywords: str = ""
    reason: str = ""
    url: str = ""

    def as_report_row(self) -> dict:
        return {
            "score": self.score,
            "company": self.company,
            "job_title": self.title,
            "location": self.location,
            "career": self.career,
            "employment_type": self.employment_type,
            "deadline": self.deadline,
            "matched_keywords": self.matched_keywords,
            "reason": self.reason,
            "job_url": self.url,
        }


class EmailReportPayload(BaseModel):
    email: str
    jobs: list[ReportJob] = Field(default_factory=list, max_length=500)


@router.post("/email")
def send_email_report(payload: EmailReportPayload):
    try:
        validate_email_address(payload.email)
        send_report_email(payload.email, [job.as_report_row() for job in payload.jobs])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ReportMailConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"sent": True}
