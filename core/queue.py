"""
Job Queue Management Module
"""
import logging
import json
import os
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Callable, List
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str
    input_path: str
    output_path: str
    settings: dict
    state: str = JobState.PENDING.value
    progress: float = 0.0
    error_message: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    added_at: str = ""

    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        return cls(**data)

class QueueManager:
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.config/vconv")
        self.config_dir = config_dir
        self.queue_file = os.path.join(config_dir, "queue.json")
        self.jobs: List[Job] = []
        self._lock = threading.Lock()
        self._load_queue()

    def add_job(self, job: Job) -> str:
        with self._lock:
            self.jobs.append(job)
        self._save_queue()
        return job.id

    def add_jobs_from_files(self, files: List[tuple], settings: dict) -> List[str]:
        job_ids = []
        with self._lock:
            for i, (inp, outp) in enumerate(files):
                job = Job(id=f"job_{datetime.now().timestamp()}_{i}", input_path=inp, output_path=outp, settings=settings)
                self.jobs.append(job)
                job_ids.append(job.id)
        self._save_queue()
        return job_ids

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            for i, job in enumerate(self.jobs):
                if job.id == job_id:
                    self.jobs.pop(i)
                    self._save_queue()
                    return True
        return False

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            for job in self.jobs:
                if job.id == job_id:
                    return job
        return None

    def get_jobs_by_state(self, state: JobState) -> List[Job]:
        with self._lock:
            return [j for j in self.jobs if j.state == state.value]

    def update_job_state(self, job_id: str, state: JobState, **kwargs):
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.state = state.value
                for k, v in kwargs.items():
                    if hasattr(job, k):
                        setattr(job, k, v)
                if state == JobState.RUNNING and not job.started_at:
                    job.started_at = datetime.now().isoformat()
                elif state in [JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED]:
                    job.completed_at = datetime.now().isoformat()
        self._save_queue()

    def get_next_pending_job(self) -> Optional[Job]:
        with self._lock:
            for job in self.jobs:
                if job.state == JobState.PENDING.value:
                    return job
        return None

    def reorder_job(self, job_id: str, new_position: int):
        with self._lock:
            if new_position < 0 or new_position >= len(self.jobs):
                return False
            for i, job in enumerate(self.jobs):
                if job.id == job_id:
                    self.jobs.pop(i)
                    self.jobs.insert(new_position, job)
                    self._save_queue()
                    return True
        return False

    def clear_completed(self):
        with self._lock:
            self.jobs = [j for j in self.jobs if j.state not in [JobState.COMPLETED.value, JobState.CANCELLED.value, JobState.FAILED.value]]
        self._save_queue()

    def clear_all(self):
        with self._lock:
            self.jobs.clear()
        self._save_queue()

    def get_queue_summary(self) -> dict:
        summary = {'total': len(self.jobs), 'pending': 0, 'running': 0, 'completed': 0, 'failed': 0, 'cancelled': 0}
        for job in self.jobs:
            summary[job.state] += 1
        return summary

    def update_progress(self, job_id: str, progress: float):
        job = self.get_job(job_id)
        if job:
            job.progress = progress
            self._save_queue()

    def _save_queue(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            data = {'jobs': [j.to_dict() for j in self.jobs], 'saved_at': datetime.now().isoformat()}
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    def _load_queue(self):
        if not os.path.exists(self.queue_file):
            return
        try:
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
                self.jobs = [Job.from_dict(j) for j in data.get('jobs', [])]
            logger.info(f"Loaded {len(self.jobs)} jobs from queue")
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")

    def can_resume(self) -> bool:
        return any(j.state == JobState.PENDING.value for j in self.jobs)

    def cancel_all(self):
        for job in self.jobs:
            if job.state in [JobState.PENDING.value, JobState.RUNNING.value]:
                job.state = JobState.CANCELLED.value
                job.completed_at = datetime.now().isoformat()
        self._save_queue()