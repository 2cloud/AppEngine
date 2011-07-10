from google.appengine.api import prospective_search
from google.appengine.ext import db
import timestamp

import logging


class StatsRecord(db.Model):
    event = db.StringProperty()
    timestamp = db.DateTimeProperty()
    value = db.StringProperty()


def record(key, value, stamp=False):
    record = StatsRecord(event=key, value=value)
    if not stamp:
        stamp = timestamp.now()
    record.timestamp = stamp
    logging.info("Firing stats off. Event: %s" % key)
    prospective_search.match(record, result_task_queue='stats')
