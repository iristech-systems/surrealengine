from surrealengine import (
    Document, StringField, IntField, FloatField, DateTimeField,
    create_connection, BooleanField
)
import datetime

# Define a document model
class Task(Document):
    """Task document model for demonstrating sync API."""

    title = StringField(required=True)
    description = StringField()
    priority = IntField(min_value=1, max_value=5, default=3)
    completed = BooleanField(default=False)
    due_date = DateTimeField()
    estimated_hours = FloatField(min_value=0.1)

    class Meta:
        collection = "tasks"
        indexes = [
            {"name": "task_priority_idx", "fields": ["priority"]},
            {"name": "task_completed_idx", "fields": ["completed"]}
        ]

def main():
    # Connect to the database using the sync API
    connection = create_connection(
        url="ws://localhost:8001/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,
        async_mode=False  # This is the key parameter for using sync API
    )

    # Use the connection as a context manager
    with connection:
        print("Connected to SurrealDB using sync API")

        # Create the table and indexes
        try:
            Task.create_table_sync()
            print("Created task table")
        except Exception as e:
            print(f"Table might already exist: {e}")
        
        try:
            Task.create_indexes_sync()
            print("Created task indexes")
        except Exception as e:
            print(f"Indexes might already exist: {e}")

        # Create tasks
        task1 = Task(
            title="Complete project documentation",
            description="Write comprehensive documentation for the SurrealEngine project",
            priority=4,
            due_date=datetime.datetime.now() + datetime.timedelta(days=7),
            estimated_hours=8.5
        )

        task2 = Task(
            title="Fix bugs in query module",
            description="Address reported issues in the query module",
            priority=5,
            due_date=datetime.datetime.now() + datetime.timedelta(days=2),
            estimated_hours=4.0
        )

        task3 = Task(
            title="Plan next release",
            description="Define features for the next release",
            priority=3,
            due_date=datetime.datetime.now() + datetime.timedelta(days=14),
            estimated_hours=2.0
        )

        # Save tasks using sync API
        task1.save_sync()
        task2.save_sync()
        task3.save_sync()
        print(f"Created tasks: {task1.title}, {task2.title}, {task3.title}")

        # Query tasks using sync API
        all_tasks = Task.objects.all_sync()
        print(f"All tasks: {[task.title for task in all_tasks]}")

        # Query with filter
        high_priority_tasks = Task.objects.filter_sync(priority__gte=4).all_sync()
        print(f"High priority tasks: {[task.title for task in high_priority_tasks]}")

        # Get a single task
        single_task = Task.objects.get_sync(id=task1.id)
        print(f"Retrieved single task: {single_task.title}")

        # Update a task
        task2.completed = True
        task2.save_sync()
        print(f"Updated task '{task2.title}' - completed: {task2.completed}")

        # Refresh a task from the database
        task2.refresh_sync()
        print(f"Refreshed task from database: {task2.title} - completed: {task2.completed}")

        # Count tasks
        total_tasks = Task.objects.count_sync()
        completed_tasks = Task.objects.filter_sync(completed=True).count_sync()
        print(f"Task statistics: {completed_tasks} of {total_tasks} tasks completed")

        # Clean up - delete all tasks
        for task in Task.objects.all_sync():
            task.delete_sync()

        print("Cleaned up all tasks")

if __name__ == "__main__":
    main()
