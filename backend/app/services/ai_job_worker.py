import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ai_job import AIJob
from app.models.post import Post
from app.models.report import Report


logger = logging.getLogger(__name__)


class AIJobWorker:
    def __init__(
        self,
        upload_folder: Path,
        process_report: Callable[[int, str | None], bool],
        poll_interval: float = 0.5,
    ) -> None:
        self.upload_folder = upload_folder
        self.process_report = process_report
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="bluesignal-ai-job-worker",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=30)
            if self._thread.is_alive():
                logger.warning("AI job worker did not stop before the shutdown timeout")

    def _run(self) -> None:
        retry_delay = 1.0
        while not self._stop_event.is_set():
            try:
                job = self._claim_next_job()
            except SQLAlchemyError:
                logger.exception("Failed to claim an AI report job")
                self._stop_event.wait(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)
                continue
            retry_delay = 1.0
            if job is None:
                self._stop_event.wait(self.poll_interval)
                continue

            job_id, report_id, image_filename = job
            image_path = str(self.upload_folder / image_filename) if image_filename else None
            try:
                succeeded = self.process_report(report_id, image_path)
            except Exception:
                logger.exception("AI job %s failed unexpectedly", job_id)
                succeeded = False
            self._finish_job(job_id, report_id, succeeded)

    def _claim_next_job(self) -> tuple[int, int, str | None] | None:
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=30)
        with SessionLocal() as db:
            job = db.scalar(
                select(AIJob)
                .where(
                    or_(
                        AIJob.status == "queued",
                        and_(
                            AIJob.status == "processing",
                            AIJob.locked_at < stale_before,
                        ),
                    )
                )
                .order_by(AIJob.created_at, AIJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            if job.status == "processing" and job.attempts >= 3:
                job.status = "failed"
                job.locked_at = None
                job.last_error = "Worker lease expired"
                self._mark_report_failed(db, job.report_id)
                db.commit()
                return None

            job.status = "processing"
            job.attempts += 1
            job.locked_at = datetime.now(timezone.utc)
            db.commit()
            return job.id, job.report_id, job.image_filename
    def _finish_job(self, job_id: int, report_id: int, succeeded: bool) -> None:
        try:
            with SessionLocal() as db:
                job = db.get(AIJob, job_id)
                if job is None:
                    logger.error("AI job %s disappeared while processing", job_id)
                    return
                job.status = "completed" if succeeded else "failed"
                job.locked_at = None
                job.last_error = None if succeeded else "Report analysis failed"
                if not succeeded:
                    self._mark_report_failed(db, report_id)
                db.commit()
        except SQLAlchemyError:
            logger.exception("Failed to finalize AI report job %s", job_id)

    @staticmethod
    def _mark_report_failed(db: Session, report_id: int) -> None:
        report = db.get(Report, report_id)
        if report is None:
            return
        post = db.get(Post, report.post_id)
        if post is None or post.status != "processing":
            return
        report.verified = False
        report.ai_summary = "AI processing failed. Please review this report manually."
        post.status = "processing_failed"
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_notify('bluesignal_changes', 'refresh')"))
