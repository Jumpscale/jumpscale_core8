from JumpScale import j
from JumpScale.core.errorhandling.JSExceptions import BaseJSException
import traceback


class AuthenticationError(BaseJSException):
    pass


class MethodNotFoundException(BaseJSException):
    pass


class RemoteException(BaseJSException):

    def __init__(self, message="", eco=None):
        super().__init__(message=message)
        backtrace = traceback.format_stack()[:-1]
        eco['backtrace'] = """
Remote Backtrace
-----------------

%s

================

Client BackTrace
-----------------

%s

""" % (eco['backtrace'], ''.join(backtrace))
        self.eco = eco
