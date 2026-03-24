import os
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore


DATA_DIR = os.path.expanduser("~/.youtubeautomation")
DB_PATH = os.path.join(DATA_DIR, "jobs.db")


class PostScheduler:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{DB_PATH}")}
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        self._started = False

    def start(self):
        if not self._started:
            self.scheduler.start()
            self._started = True

    def schedule_post(
        self,
        post_func,
        product_id: str,
        platforms: list[str],
        run_at: datetime,
        **kwargs,
    ) -> str:
        self.start()
        job = self.scheduler.add_job(
            post_func,
            "date",
            run_date=run_at,
            kwargs={
                "product_id": product_id,
                "platforms": platforms,
                **kwargs,
            },
            id=f"post_{product_id}_{int(run_at.timestamp())}",
            replace_existing=True,
        )
        return job.id

    def list_scheduled(self) -> list[dict]:
        self.start()
        jobs = self.scheduler.get_jobs()
        result = []
        for job in jobs:
            result.append(
                {
                    "id": job.id,
                    "next_run": str(job.next_run_time),
                    "kwargs": job.kwargs if hasattr(job, "kwargs") else {},
                }
            )
        return result

    def cancel(self, job_id: str) -> bool:
        self.start()
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown()
            self._started = False
