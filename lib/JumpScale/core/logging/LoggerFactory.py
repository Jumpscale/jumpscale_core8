from JumpScale import j

from JSLogger import JSLogger
from Filter import ModuleFilter, JobFilter
import time
import logging
import re
import sys
def embed():
    return "embed" in sys.__dict__

if not embed():
    import logging.handlers
from colorlog import ColoredFormatter
import os


FILE_FORMAT = '%(asctime)s - %(pathname)s:%(lineno)d - %(levelname)-8s - %(message)s'
CONSOLE_FORMAT = '%(cyan)s[%(asctime)s]%(reset)s - %(filename)-20s:%(lineno)-4d:%(name)-30s - %(log_color)s%(levelname)-8s%(reset)s - %(message)s'

# Modes
PRODUCTION = 0  # use NullHander, let the application configure the logging
DEV = 10  # use predefine handlers for console and file.

_mode_to_name = {
    PRODUCTION: "PRODUCTION",
    DEV: "DEV"
}
_name_to_mode = {
    "PRODUCTION": PRODUCTION,
    "DEV": DEV
}


SILLY = 4
logging.addLevelName(SILLY, "SILLY")


def silly(self, msg, *args, **kws):
    self._log(SILLY, msg, args, **kws)

logging.Logger.silly = silly


class Handlers():

    def __init__(self):
        self._fileRotateHandler = None
        self._consoleHandler = None
        self._memoryHandler = None
        self._all = []

    @property
    def fileRotateHandler(self, name='jumpscale'):
        if self._fileRotateHandler is None:
            if not j.sal.fs.exists("%s/log/" % j.dirs.VARDIR):
                j.sal.fs.createDir("%s/log/" % j.dirs.VARDIR)
            filename = "%s/log/%s.log" % (j.dirs.VARDIR, name)
            formatter = logging.Formatter(FILE_FORMAT)
            fh = logging.handlers.TimedRotatingFileHandler(
                filename, when='D', interval=1, backupCount=7, encoding=None, delay=False, utc=False, atTime=None)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            self._fileRotateHandler = fh
            self._all.append(self._fileRotateHandler)
        return self._fileRotateHandler

    @property
    def consoleHandler(self):
        if self._consoleHandler is None:
            formatter = LimitFormater(
                fmt=CONSOLE_FORMAT,
                datefmt="%a%d %H:%M",
                reset=True,
                log_colors={
                    'DEBUG':    'cyan',
                    'INFO':     'green',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'red,bg_white',
                },
                secondary_log_colors={},
                style='%',
                lenght=37
            )
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)
            self._consoleHandler = ch
            self._all.append(self._consoleHandler)
        return self._consoleHandler

    @property
    def memoryHandler(self):
        if self._memoryHandler is None:
            self._memoryHandler = logging.handlers.MemoryHandler(capacity=10000)
            self._all.append(self._memoryHandler)
        return self._memoryHandler


class LoggerFactory:

    def __init__(self):
        self.__jslocation__ = "j.logger"
        self.root_logger_name = 'j'
        self.handlers = Handlers()

        self.PRODUCTION = PRODUCTION
        self.DEV = DEV
        self._quiet = False

        self.logging = logging.getLogger(self.root_logger_name)
        # self.logging.addHandler(logging.NullHandler())

    def test(self):

        logger = self.get("loggerTest")

        self.enableConsoleMemHandler()

        logger.info("a test")

    def testPerformance(self):
        logger = self.get("loggerTest")

        self.enableMemHandler()

        def perftest(logger):
            print("start perftest logger")
            start = time.time()
            nr = 30000
            for i in range(nr):
                logger.info("this is an info message")
                # self.getActionObjFromMethod(test)
            stop = time.time()
            print("nr of logs per sec:%s" % int(nr / (stop - start)))

        perftest(logger)

        # FOLLOWING PROVES THAT THE LOOKING FOR FILE & PATH INFO IS THE SLOWING DOWN FACTOR
        # j.tools.performancetrace.profile("perftest(logger)", globals=locals())  # {"perftest": perftest}

    def init(self, mode, level, filter=[]):
        self.set_mode(mode.upper())
        self.set_level(level)
        if filter:
            self.handlers.consoleHandler.addFilter(ModuleFilter(filter))
            self.handlers.consoleHandler.addFilter(JobFilter())

    def get(self, name=None, new=False):
        """
        Gets the logger of Jumpscale.

        @param name str: not used only for backward compatibility.
        """
        if new is False:
            name = self.root_logger_name
        logger = logging.getLogger(name)

        return logger

    def set_quiet(self, quiet):
        self._quiet = quiet

    def set_mode(self, mode):
        if j.data.types.string.check(mode):
            if mode in _name_to_mode:
                mode = _name_to_mode[mode]
            else:
                raise j.exceptions.Input("mode %s doesn't exist" % mode)

        if mode == self.PRODUCTION:
            self._enable_production_mode()
        elif mode == self.DEV:
            self._enable_dev_mode()

    def set_level(self, level):
        """
        level 0 to 10
        10 being most verbose (need to verify this)
        """
        for handler in self.handlers._all:
            handler.setLevel(level)

    def log(self, msg=None, level=logging.INFO, category="j"):
        logger = j.logger.get(category)
        logger.log(level, msg)

    def enableMemHandler(self):
        self.logging.handlers = []
        # self.logging.propagate = True
        self.logging.addHandler(self.handlers.memoryHandler)

    def enableConsoleHandler(self):
        self.logging.handlers = []
        # self.logging.propagate = True
        self.logging.addHandler(self.handlers.consoleHandler)

    def enableConsoleMemHandler(self):
        self.logging.handlers = []
        # self.logging.propagate = True
        self.logging.addHandler(self.handlers.memoryHandler)
        self.logging.addHandler(self.handlers.consoleHandler)

    def _enable_production_mode(self):
        self.logging.handlers = []
        self.logging.addHandler(logging.NullHandler())
        # self.logging.propagate = True

    def _enable_dev_mode(self):
        logging.setLoggerClass(JSLogger)
        self.logging.setLevel(logging.DEBUG)
        self.logging.propagate = False
        logging.lastResort = None
        self.enableConsoleHandler()
        self.logging.addHandler(self.handlers.fileRotateHandler)

    def __fileRotateHandler(self, name='jumpscale'):
        if not j.sal.fs.exists("%s/log/" % j.dirs.VARDIR):
            j.sal.fs.createDir("%s/log/" % j.dirs.VARDIR)
        filename = "%s/log/%s.log" % (j.dirs.VARDIR, name)
        formatter = logging.Formatter(FILE_FORMAT)
        fh = logging.handlers.TimedRotatingFileHandler(
            filename, when='D', interval=1, backupCount=7, encoding=None, delay=False, utc=False, atTime=None)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        return fh

    def __consoleHandler(self):
        formatter = LimitFormater(
            fmt=CONSOLE_FORMAT,
            datefmt="%a%d %H:%M",
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%',
            lenght=37
        )
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        return ch

    def __redisHandler(self, redis_client=None):
        if redis_client is None:
            self.redis_client = j.core.db


class LimitFormater(ColoredFormatter):

    def __init__(self, fmt, datefmt, reset, log_colors, secondary_log_colors, style, lenght):
        super(LimitFormater, self).__init__(
            fmt=fmt,
            datefmt=datefmt,
            reset=reset,
            log_colors=log_colors,
            secondary_log_colors=secondary_log_colors,
            style=style)
        self.lenght = lenght

    def format(self, record):
        if len(record.pathname) > self.lenght:
            record.pathname = "..." + record.pathname[-self.lenght:]
        return super(LimitFormater, self).format(record)
