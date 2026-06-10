import uuid
from datetime import datetime, timezone
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Task:
    def __init__(self, command, name=None, submitter=None):
        self.id = str(uuid.uuid4())[:8]
        self.name = name or f"task-{self.id}"
        self.command = command
        self.submitter = submitter
        self.status = TaskStatus.PENDING
        self.assigned_to = None
        self.created_at = datetime.now()
        self.started_at = None
        self.finished_at = None
        self.result = None
        self.error = None

    def start(self, worker_id: str) -> None:
        self.status = TaskStatus.RUNNING
        self.assigned_to = worker_id
        self.started_at = datetime.now(timezone.utc)

    def complete(self, result: str) -> None:
        self.status = TaskStatus.DONE
        self.finished_at = datetime.now(timezone.utc)
        self.result = result

    def fail(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(timezone.utc)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "command": self.command,
            "submitter": self.submitter,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": self.result,
            "error": self.error,
        }

    def __repr__(self):
        return f"Task({self.id}, {self.status}, cmd={self.command!r})"
