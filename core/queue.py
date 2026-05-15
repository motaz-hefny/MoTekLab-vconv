"""
Job Queue Management Module

Manages conversion job queue with states, persistence, and control.
"""

import logging
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional, Callable, List
from datetime import datetime
from enum import Enum
from pathlib import Path


logger = logging.getLogger(__name__)


class JobState(Enum):
    """Job state constants."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Conversion job container."""
    id: str
    input_path: str
    output_path: str
    settings: dict  # Conversion settings
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
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create Job from dictionary."""
        return cls(**data)


class QueueManager:
    """Manages the conversion job queue."""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.config/vconv")
        self.config_dir = config_dir
        self.queue_file = os.path.join(config_dir, "queue.json")

        self.jobs: List[Job] = []
        self.current_job_index: int = -1
        self._load_queue()

        self._progress_callback: Optional[Callable] = None

    def add_job(self, job: Job) -> str:
        """
        Add a job to the queue.

        Args:
            job: Job to add

        Returns:
            Job ID
        """
        self.jobs.append(job)
        logger.info(f"Added job {job.id} to queue: {job.input_path}")
        self._save_queue()
        return job.id

    def add_jobs_from_files(
        self,
        files: List[tuple],
        settings: dict
    ) -> List[str]:
        """
        Add multiple jobs from file list.

        Args:
            files: List of (input_path, output_path) tuples
            settings: Conversion settings

        Returns:
            List of job IDs
        """
        job_ids = []
        for i, (input_path, output_path) in enumerate(files):
            job = Job(
                id=f"job_{datetime.now().timestamp()}_{i}",
                input_path=input_path,
                output_path=output_path,
                settings=settings
            )
            job_ids.append(self.add_job(job))

        return job_ids

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue."""
        for i, job in enumerate(self.jobs):
            if job.id == job_id:
                self.jobs.pop(i)
                logger.info(f"Removed job {job_id} from queue")
                self._save_queue()
                return True
        return False

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def get_jobs_by_state(self, state: JobState) -> List[Job]:
        """Get all jobs with specific state."""
        return [job for job in self.jobs if job.state == state.value]

    def update_job_state(self, job_id: str, state: JobState, **kwargs):
        """Update job state and optional fields."""
        job = self.get_job(job_id)
        if job:
            job.state = state.value
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            if state == JobState.RUNNING and not job.started_at:
                job.started_at = datetime.now().isoformat()
            elif state in [JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED]:
                job.completed_at = datetime.now().isoformat()

            self._save_queue()

    def get_next_pending_job(self) -> Optional[Job]:
        """Get the next pending job."""
        for job in self.jobs:
            if job.state == JobState.PENDING.value:
                return job
        return None

    def get_next_job_index(self) -> int:
        """Get index of next pending job."""
        for i, job in enumerate(self.jobs):
            if job.state == JobState.PENDING.value:
                return i
        return -1

    def reorder_job(self, job_id: str, new_position: int):
        """Reorder a job in the queue."""
        for i, job in enumerate(self.jobs):
            if job.id == job_id:
                self.jobs.pop(i)
                self.jobs.insert(new_position, job)
                logger.info(f"Reordered job {job_id} to position {new_position}")
                self._save_queue()
                return True
        return False

    def clear_completed(self):
        """Remove all completed jobs from queue."""
        self.jobs = [job for job in self.jobs
                   if job.state not in [JobState.COMPLETED.value,
                                        JobState.CANCELLED.value,
                                        JobState.FAILED.value]]
        self._save_queue()

    def clear_all(self):
        """Clear entire queue."""
        self.jobs.clear()
        self._save_queue()

    def get_queue_summary(self) -> dict:
        """Get queue summary statistics."""
        summary = {
            'total': len(self.jobs),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        for job in self.jobs:
            summary[job.state] += 1
        return summary

    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates."""
        self._progress_callback = callback

    def update_progress(self, job_id: str, progress: float):
        """Update job progress."""
        job = self.get_job(job_id)
        if job:
            job.progress = progress
            if self._progress_callback:
                self._progress_callback(job_id, progress)
            self._save_queue()

    def _save_queue(self):
        """Save queue to file."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            data = {
                'jobs': [job.to_dict() for job in self.jobs],
                'current_index': self.current_job_index,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    def _load_queue(self):
        """Load queue from file."""
        if not os.path.exists(self.queue_file):
            return

        try:
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
                self.jobs = [Job.from_dict(j) for j in data.get('jobs', [])]
                self.current_job_index = data.get('current_index', -1)
            logger.info(f"Loaded {len(self.jobs)} jobs from queue")
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")

    def can_resume(self) -> bool:
        """Check if queue can be resumed."""
        return any(job.state == JobState.PENDING.value
                   for job in self.jobs)

    def cancel_all(self):
        """Cancel all pending and running jobs."""
        for job in self.jobs:
            if job.state in [JobState.PENDING.value, JobState.RUNNING.value]:
                job.state = JobState.CANCELLED.value
                job.completed_at = datetime.now().isoformat()
        self._save_queue()
        logger.info("All jobs cancelled")


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    qm = QueueManager()
    print(f"Queue loaded: {qm.get_queue_summary()}")

    # Add test job
    job = Job(
        id="test_1",
        input_path="/path/to/video.mkv",
        output_path="/path/to/video.mp4",
        settings={'encoder': 'x265', 'quality': 23}
    )
    qm.add_job(job)
    print(f"Queue after add: {qm.get_queue_summary()}")