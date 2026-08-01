"""Unit tests for TaskManager core logic."""

import pytest
from task_tracker.core import TaskManager, TaskStatus


def test_add_task_success():
    manager = TaskManager()
    task = manager.add_task("Write documentation", priority=2)
    assert task.title == "Write documentation"
    assert task.status == TaskStatus.TODO
    assert task.priority == 2


def test_add_task_empty_title_raises():
    manager = TaskManager()
    with pytest.raises(ValueError, match="title cannot be empty"):
        manager.add_task("   ")


def test_get_task():
    manager = TaskManager()
    created = manager.add_task("Test get task")
    retrieved = manager.get_task(created.id)
    assert retrieved is not None
    assert retrieved.title == "Test get task"


def test_update_status():
    manager = TaskManager()
    task = manager.add_task("Fix bug")
    updated = manager.update_status(task.id, TaskStatus.IN_PROGRESS)
    assert updated.status == TaskStatus.IN_PROGRESS


def test_delete_task():
    manager = TaskManager()
    task = manager.add_task("Temporary task")
    assert manager.delete_task(task.id) is True
    assert manager.get_task(task.id) is None


def test_list_tasks_filter():
    manager = TaskManager()
    t1 = manager.add_task("Task 1")
    t2 = manager.add_task("Task 2")
    manager.update_status(t2.id, TaskStatus.COMPLETED)

    todo_tasks = manager.list_tasks(TaskStatus.TODO)
    assert len(todo_tasks) == 1
    assert todo_tasks[0].id == t1.id
