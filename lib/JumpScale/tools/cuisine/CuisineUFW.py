
from JumpScale import j

from ActionDecorator import ActionDecorator


class actionrun(ActionDecorator):

    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.ufw"

base = j.tools.cuisine.getBaseClass()


class CuisineUFW(base):

    def __init__(self, executor, cuisine):
        self._executor = executor
        self._cuisine = cuisine
        self._ufw_allow = {}
        self._ufw_deny = {}
        self._ufw_enabled = None

    @property
    def ufw_enabled(self):
        if not self._ufw_enabled:
            if not self._cuisine.core.isMac:
                if self._cuisine.bash.cmdGetPath("nft", die=False) is not False:
                    self._ufw_enabled = False
                    print("cannot use ufw, nft installed")
                if self._cuisine.bash.cmdGetPath("ufw", die=False) == False:
                    self._cuisine.package.install("ufw")
                    self._cuisine.bash.cmdGetPath("ufw")
                self._ufw_enabled = not "inactive" in self._cuisine.core.run("ufw status")[1]
        return self._ufw_enabled

    
    def ufw_enable(self):
        if not self.ufw_enabled:
            if not self._cuisine.core.isMac:
                if self._cuisine.bash.cmdGetPath("nft", die=False) is not False:
                    self._fw_enabled = False
                    raise j.exceptions.RuntimeError("Cannot use ufw, nft installed")
                if self._executor.type != 'local':
                    self._cuisine.core.run("ufw allow %s" % self._executor.port)
                self._cuisine.core.run("echo \"y\" | ufw enable")
                self._fw_enabled = True
                return True
        raise j.exceptions.Input(message="cannot enable ufw, not supported or ",
                                 level=1, source="", tags="", msgpub="")
        return True

    @property
    def ufw_rules_allow(self):
        if self._cuisine.core.isMac:
            return {}
        if self._ufw_allow == {}:
            self._ufw_status()
        return self._ufw_allow

    @property
    def ufw_rules_deny(self):
        if self._cuisine.core.isMac:
            return {}
        if self._ufw_deny == {}:
            self._ufw_status()
        return self._ufw_deny

    def _ufw_status(self):
        self.ufw_enable()
        _, out, _ = self._cuisine.core.run("ufw status")
        for line in out.splitlines():
            if line.find("(v6)") != -1:
                continue
            if line.find("ALLOW ") != -1:
                ip = line.split(" ", 1)[0]
                self._ufw_allow[ip] = "*"
            if line.find("DENY ") != -1:
                ip = line.split(" ", 1)[0]
                self._ufw_deny[ip] = "*"

    
    def allowIncoming(self, port, protocol='tcp'):
        if self._cuisine.core.isMac:
            return
        self.ufw_enable()
        self._cuisine.core.run("ufw allow %s/%s" % (port, protocol))

    
    def denyIncoming(self, port):
        if self._cuisine.core.isMac:
            return

        self.ufw_enable()
        self._cuisine.core.run("ufw deny %s" % port)

    
    def flush(self):
        C = """
        ufw disable
        iptables --flush
        iptables --delete-chain
        iptables --table nat --flush
        iptables --table filter --flush
        iptables --table nat --delete-chain
        iptables --table filter --delete-chain
        """
        self._cuisine.core.run_script(C)

    def show(self):
        a = self.ufw_rules_allow
        b = self.ufw_rules_deny
        print("ALLOW")
        print(a)
        print("DENY")
        print(b)

        # print(self._cuisine.core.run("iptables -t nat -nvL"))
