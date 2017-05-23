from JumpScale import j
import re
import logging


class ModuleFilter:
    """ModuleFilter filter out given modules"""

    def __init__(self, modules):
        """
        modules is an iterable containing the name of the modules to filter
        """
        self.modules = modules

    def filter(self, record):
        if record.name not in self.modules:
            return True
        return False


jobpat = "job:(\w+)!"


class JobFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        found = re.findall(jobpat, msg)
        if found:
            jobid = found[0]
            record.jobid = jobid
            return True
        return False
