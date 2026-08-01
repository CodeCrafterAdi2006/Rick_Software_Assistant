# Task Tracker

`task-tracker` is a lightweight Python package for managing tasks, project priorities, and status tracking.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from task_tracker.core import TaskManager, TaskStatus

manager = TaskManager()
task = manager.add_task("Implement login authentication", priority=1)
manager.update_status(task.id, TaskStatus.IN_PROGRESS)

print(manager.get_task(task.id))
```

## Running Tests

```bash
pytest
```
