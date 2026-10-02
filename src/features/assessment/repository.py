"""Read and append assessment versions. Callers commit."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.assessment_reports import AssessmentReport, AssessmentVersion


async def get_report(session: AsyncSession, case_id: UUID) -> AssessmentReport | None:
    return await session.scalar(select(AssessmentReport).where(AssessmentReport.case_id == case_id))


async def current_version(session: AsyncSession, report: AssessmentReport) -> AssessmentVersion | None:
    return await session.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.report_id == report.id,
            AssessmentVersion.version == report.current_version,
        )
    )


async def append_version(
    session: AsyncSession,
    report: AssessmentReport,
    *,
    payload: dict,
    source: str,
    status: str,
    edited_by: UUID | None,
) -> AssessmentVersion:
    """Supersede the open draft, then store the next version."""
    previous = await current_version(session, report)
    if previous is not None and previous.status == "DRAFT":
        previous.status = "SUPERSEDED"
    version_no = 1 if previous is None else report.current_version + 1
    if previous is None and report.current_version:
        version_no = report.current_version
    row = AssessmentVersion(
        report_id=report.id,
        version=version_no,
        status=status,
        source=source,
        payload=payload,
        edited_by=edited_by,
    )
    session.add(row)
    report.current_version = version_no
    report.status = status
    await session.flush()
    return row
