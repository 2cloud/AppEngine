from google.appengine.api import prospective_search
from google.appengine.ext import db
from datetime import datetime

import logging


class StatsRecord(db.Model):
    event = db.StringProperty()
    timestamp = db.DateTimeProperty()
    value = db.StringProperty()


def record(key, value, timestamp=False):
    record = StatsRecord(event=key, value=value)
    if not timestamp:
        timestamp = datetime.now()
    record.timestamp = timestamp
    logging.info("Firing stats off. Event: %s" % key)
    prospective_search.match(record, result_task_queue='stats')
