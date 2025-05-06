# Placeholder for scheduling posts

import time
import os
from datetime import datetime, timezone, timedelta
from common.google_sheets import GoogleSheetsClient
import logging

logger = logging.getLogger(__name__)

class SchedulePost:
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client
        self.workflow_interval = int(os.getenv('WORKFLOW_INTERVAL_MINUTES', '60'))
        logger.info(f"Initialized SchedulePost with {self.workflow_interval} minute interval")

    def wait_and_post(self, row_id: int, post_func, *args, **kwargs):
        """Wait until scheduled time and then post."""
        # Fetch the row to get schedule_ts
        rows = self.sheets_client.get_rows()
        row = next((r for r in rows if r.get('id') == row_id), None)
        if not row or not row.get('schedule_ts'):
            raise ValueError('No schedule_ts found for row_id')
        schedule_ts = row['schedule_ts']
        # Parse schedule_ts (assume ISO format)
        scheduled_time = datetime.fromisoformat(schedule_ts).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        wait_seconds = (scheduled_time - now).total_seconds()
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        # Call the post function
        return post_func(*args, **kwargs)

    def schedule_workflow(self, workflow_func):
        """Schedule the workflow to run at regular intervals.
        
        Args:
            workflow_func: The workflow function to schedule
            
        Returns:
            datetime: The next scheduled run time
        """
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(minutes=self.workflow_interval)
        logger.info(f"Scheduled next workflow run for: {next_run}")
        return next_run

    def get_next_run_time(self):
        """Get the next scheduled run time for the workflow.
        
        Returns:
            datetime: The next scheduled run time
        """
        now = datetime.now(timezone.utc)
        return now + timedelta(minutes=self.workflow_interval)

    def should_run_now(self, last_run_time: datetime) -> bool:
        """Check if the workflow should run now based on the last run time.
        
        Args:
            last_run_time (datetime): The last time the workflow ran
            
        Returns:
            bool: True if the workflow should run now
        """
        if not last_run_time:
            return True
            
        now = datetime.now(timezone.utc)
        time_since_last_run = now - last_run_time
        return time_since_last_run.total_seconds() >= (self.workflow_interval * 60)


 