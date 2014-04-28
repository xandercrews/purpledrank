__author__ = 'achmed'

import datetime
import logging

import pytz.reference
# dateutil has odd package naming so we hint to the IDEA inspector
# noinspection PyUnresolvedReferences
import dateutil.tz


class ISO8601Formatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self.created_timezone = kwargs.pop('created_timezone', pytz.reference.utc)
        # TODO created time converter like formatTime has
        super(ISO8601Formatter, self).__init__(*args, **kwargs)

    # NOTE created is a string when you use this formatter
    def format(self, record):
        if hasattr(record, 'created'):
            record.isocreated = datetime.datetime.fromtimestamp(record.created, self.created_timezone).isoformat()

        return super(ISO8601Formatter, self).format(record)

    @classmethod
    def factory(cls, *args, **kwargs):
        return ISO8601Formatter(*args, **kwargs)
