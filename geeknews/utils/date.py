import os
from datetime import datetime, timedelta

class GeeknewsDate:
    
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

    def __str__(self):
        return self.joined_path

    @classmethod
    def now(cls):
        n = datetime.now()
        return cls(n.year, n.month, n.day)
    
    @property
    def formatted(self, sep=''):
        return f"{self.year:02d}{sep}{self.month:02d}{sep}{self.day:02d}"
    
    @property
    def joined_path(self):
        components = map(lambda x: str(x), [self.year, self.month, self.day])
        return os.sep.join(components)
    
    @property
    def seconds_until_next_day(self):
        dt_now = datetime.now()
        dt_this_day = self.get_datetime()
        dt_next_day = dt_this_day + timedelta(days=1)
        delta = dt_next_day - dt_now
        return delta.seconds
    
    def get_datetime(self):
        return datetime(
            year=self.year, 
            month=self.month, 
            day=self.day
        )
    
    def get_next_date(self):
        dt_this_day = self.get_datetime()
        dt_next_day = dt_this_day + timedelta(days=1)
        return GeeknewsDate(
            year=dt_next_day.year,
            month=dt_next_day.month,
            day=dt_next_day.day,
        )
    
    def get_preview_date(self):
        # if date is 1 hour remaining to next day, then preview next date
        if self.seconds_until_next_day < 3600:
            return self.get_next_date()
        else:
            return self
    
    @classmethod
    def test_date(cls):
        return cls(2025, 1, 9)
    
