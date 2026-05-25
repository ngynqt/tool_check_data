import uuid
from datetime import datetime, timezone
from typing import Optional, Dict
from pydantic import BaseModel

class TaskStatus(BaseModel):
    task_id: str
    link: str
    status: str  # "queued", "processing", "completed", "failed"
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TaskTracker:
    def __init__(self):
        self._tasks: Dict[str, TaskStatus] = {}

    def create_task(self, link: str) -> str:
        task_id = str(uuid.uuid4())[:8]  # short readable UUID
        now = datetime.now(timezone.utc)
        self._tasks[task_id] = TaskStatus(
            task_id=task_id,
            link=link,
            status="queued",
            created_at=now,
            updated_at=now
        )
        return task_id

    def update_status(self, task_id: str, status: str, error: Optional[str] = None) -> None:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = status
            task.error = error
            task.updated_at = datetime.now(timezone.utc)

    def get_task(self, task_id: str) -> Optional[TaskStatus]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskStatus]:
        return list(self._tasks.values())

tracker = TaskTracker()
