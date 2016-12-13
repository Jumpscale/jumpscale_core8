from JumpScale import j


app = j.tools.cuisine._getBaseAppClass()

# TODO: is this still correct, maybe our docker approach better, need to check


class CuisineJSAgent(app):

    NAME = 'jsagent'

    def build(self):
        raise NotImplementedError()

    def install(self, start=False, gid=1, ctrl_addr='', ctrl_port=4444, ctrl_passwd='', reset=False):
        """
        gid: grid ID
        ctrl_addr: IP address of the controller
        ctrl_port: listening port of the controller
        ctrl_passwd: password of the controller
        """
        if reset is False and self.isInstalled():
            return

        self.cuisine.core.dir_ensure('$JSAPPDIR')
        self.cuisine.core.file_link('$CODEDIR/github/jumpscale/jumpscale_core8/apps/jsagent', '$JSAPPDIR/jsagent')
        if start is True:
            self.start(gid, ctrl_addr, ctrl_port, ctrl_passwd)

        return

    def start(self, gid, ctrl_addr, ctrl_port=4444, ctrl_passwd=''):
        """
        gid: grid ID
        ctrl_addr: IP address of the controller
        ctrl_port: listening port of the controller
        ctrl_passwd: password of the controller
        """
        cmd = "jspython jsagent.py --grid-id %d --controller-ip %s --controller-port %d" % (gid, ctrl_addr, ctrl_port)
        if ctrl_passwd is not None and ctrl_passwd != '':
            cmd += ' --controller-password %s' % ctrl_passwd
        self.cuisine.processmanager.ensure(name="jsagent", cmd=cmd, path='$JSAPPDIR/jsagent')
