"""Core Task Manager module handling task creation, status changes, and querying."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import uuid
from task_tracker.utils import sanitize_title


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: int = 1  # 1 (low) to 5 (urgent)
    tags: List[str] = field(default_factory=list)


class TaskManager:
    """Manages an in-memory collection of tasks."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}

    def add_task(
        self,
        title: str,
        description: str = "",
        priority: int = 1,
        tags: Optional[List[str]] = None,
    ) -> Task:
        """Create and store a new task."""
        clean_title = sanitize_title(title)
        if not clean_title:
            raise ValueError("Task title cannot be empty.")

        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            title=clean_title,
            description=description,
            status=TaskStatus.TODO,
            priority=priority,
            tags=tags or [],
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by its ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List tasks, optionally filtered by status string.

        Returns all tasks if status is None.
        """
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]

    def update_status(self, task_id: str, new_status: TaskStatus) -> Task:
        """Update status of a task."""
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task with ID '{task_id}' not found.")
        task.status = new_status
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
