import os
from datetime import datetime

class GeeknewsDate:
    
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

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
    
    @classmethod
    def test_date(cls):
        return cls(2025, 1, 9)
    
