# Placeholder for scheduling posts

import time
from datetime import datetime, timezone
from common.google_sheets import GoogleSheetsClient

class SchedulePost:
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client

    def wait_and_post(self, row_id: int, post_func, *args, **kwargs):
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


