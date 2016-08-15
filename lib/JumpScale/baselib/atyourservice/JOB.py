from JumpScale import j
import traceback
import colored_traceback

from multiprocessing import Process, Queue

colored_traceback.add_hook(always=True)

import pygments.lexers
from pygments.formatters import get_formatter_by_name


modulecache = {}


def loadmodule(name, path):
    key = path
    if key in modulecache:
        return modulecache[key]
    parentname = ".".join(name.split(".")[:-1])
    sys.modules[parentname] = __package__
    mod = imp.load_source(name, path)
    modulecache[key] = mod
    return mod


class Job():
    """
    is what needs to be done for 1 specific action for a service
    """

    def __init__(self):
        self.logger = j.atyourservice.logger

    def _str_error(self, error):
        out = ''
        formatter = pygments.formatters.Terminal256Formatter(
            style=pygments.styles.get_style_by_name("vim"))

        if error.__str__() != "":
            out += "\n*TRACEBACK*********************************************************************************\n"
            # self.logger.error("\n*TRACEBACK*********************************************************************************\n")

            lexer = pygments.lexers.get_lexer_by_name("pytb", stripall=True)
            tb_colored = pygments.highlight(error.__str__(), lexer, formatter)
            print(tb_colored)
            out += tb_colored

        # self.logger.error("\n\n******************************************************************************************\n")
        out += "\n\n******************************************************************************************\n"
        return out

    def run(self):
        # for parallelized runs
        try:
            self.result = self.service.runAction(self.runstep.action)
            self.logger.debug('running stepaction: %s' % self.service)
            self.logger.debug('\tresult:%s' % self.result)
            self.result_q.put(self.result)
        except Exception as e:
            self.logger.debug(
                'running stepaction with error: %s' % self.service)
            self.logger.debug('\tresult:%s' % self.result)
            self.logger.debug('\error:%s' % self._str_error(e))
            self.error_q.put(self._str_error(e))
            self.result_q.put(self.result)
            raise e

    def execute(self):
        # for squential runs
        try:
            self.result = self.service.runAction(self.runstep.action)
        except Exception as e:
            if j.actions.last:
                j.actions.last.print()
                self.result = j.actions.last.str
            else:
                self._print_error(e)
                self.result = e.__str__()
            self.state = "ERROR"
            self.runstep.state = "ERROR"
            self.runstep.run.state = "ERROR"
            return False
        self.state = "OK"
        return True

    def __repr__(self):
        out = "runstep action: %s!%s (%s)\n" % (
            self.service.key, self.name, self.state)
        if self.service_model != "":
            out += "model:\n%s\n\n" % j.data.text.indent(self.service_model)
        if self.service_hrd != "":
            out += "hrd:\n%s\n\n" % j.data.text.indent(self.service_hrd)
        if self.source != "":
            out += "source:\n%s\n\n" % j.data.text.indent(self.source)
        return out

    __str__ = __repr__
