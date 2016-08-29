
from JumpScale import j
import netaddr


base = j.tools.cuisine._getBaseClass()


class CuisineSSH(base):

    def __init__(self, executor, cuisine):
        self._executor = executor
        self._cuisine = cuisine

    def test_login(self, passwd, port=22, range=None, onlyplatform="arch"):
        login = "root"
        res = []
        for item in self.scan(range=range):
            print("test for login/passwd on %s" % item)
            try:
                client = j.clients.ssh.get(item, port, login, passwd, timeout=1, die=False)
            except Exception as e:
                print("  NOT OK")
                continue
            if testoutput == False:
                print("  NOT OK")
                continue
            executor = j.tools.executor.getSSHBased(item, port, login, passwd, checkok=True)
            if onlyplatform != "":
                if not str(executor.cuisine.platformtype).startswith(onlyplatform):
                    continue
            print("  RESPONDED!!!")
            res.append(item)
        return res

    def test_login_pushkey(self, passwd, keyname, port=22, range=None, changepasswdto="", onlyplatform="arch"):
        """
        """
        login = "root"
        done = []
        for item in self.test_login(passwd, port, range, onlyplatform=onlyplatform):
            keypath = j.sal.fs.joinPaths(self._cuisine.bash.environ["HOME"], ".ssh", keyname + ".pub")
            if j.sal.fs.exists(keypath):
                key = j.sal.fs.fileGetContents(keypath)
                executor = j.tools.executor.getSSHBased(item, port, login, passwd, checkok=True)
                executor.cuisine.ssh.authorize(user="root", key=key)
                if changepasswdto != "":
                    executor.cuisine.user.passwd(login, changepasswdto, encrypted_passwd=False)
            else:
                raise j.exceptions.RuntimeError("Cannot find key:%s" % keypath)
            done.append(item)
        return done

    def scan(self, range=None, ips={}, port=22):
        """
        @param range in format 192.168.0.0/24
        if range not specified then will take all ranges of local ip addresses (nics)
        """
        if not range:
            res = self._cuisine.net.get_info()
            for item in res:
                cidr = item['cidr']

                name = item['name']
                if not name.startswith("docker") and name not in ["lo"]:
                    if len(item['ip']) > 0:
                        ip = item['ip'][0]
                        ipn = netaddr.IPNetwork(ip + "/" + str(cidr))
                        range = str(ipn.network) + "/%s" % cidr
                        ips = self.scan(range, ips)
            return ips
        else:
            try:
                # out=self._cuisine.core.run("nmap -p 22 %s | grep for"%range,showout=False)
                _, out, _ = self._cuisine.core.run("nmap %s -p %s --open -oX $tmpDir/nmap" %
                                                   (range))
            except Exception as e:
                if str(e).find("command not found") != -1:
                    self._cuisine.package.install("nmap")
                    # out=self._cuisine.core.run("nmap -p 22 %s | grep for"%range)
                    _, out, _ = self._cuisine.core.run("nmap %s -p %s --open -oX $tmpDir/nmap" %
                                                       (range))
            out = self._cuisine.core.file_read("$tmpDir/nmap")
            import xml.etree.ElementTree as ET
            root = ET.fromstring(out)
            for child in root:
                if child.tag == "host":
                    ip = None
                    mac = None
                    for addr in child.findall("address"):
                        if addr.get("addrtype") == "ipv4":
                            ip = addr.get("addr")

                    for addr in child.findall("address"):
                        if addr.get("addrtype") == "mac":
                            mac = addr.get("addr")

                    if ip != None:
                        ips[ip] = {"mac": mac}

            # for line in out.split("\n"):
            #     ip=line.split("for")[1].strip()
            #     if ip.find("(")!=-1:
            #         ip=ip.split("(")[1].strip(")").strip()
            #     if ip not in ips:

            #         ips.append(ip)
            return ips

    def keygen(self, user="root", keytype="rsa", name="default"):
        """Generates a pair of ssh keys in the user's home .ssh directory."""
        user = user.strip()
        d = self._cuisine.user.check(user)
        assert d, "User does not exist: %s" % (user)
        home = d["home"]
        path = '%s/.ssh/%s' % (home, name)
        if not self._cuisine.core.file_exists(path + ".pub"):
            self._cuisine.core.dir_ensure(home + "/.ssh", mode="0700", owner=user, group=user)

            self._cuisine.core.run("ssh-keygen -q -t %s -f %s -N ''" % (keytype, path))
            self._cuisine.core.file_attribs(path, owner=user, group=user)
            self._cuisine.core.file_attribs("%s.pub" % path, owner=user, group=user)
            return "%s.pub" % path
        else:
            return "%s.pub" % path

    #
    def authorize(self, user, key):
        """Adds the given key to the '.ssh/authorized_keys' for the given
        user."""

        if key is None or key.strip() == "":
            raise j.exceptions.Input("key cannot be empty")
        sudomode = self._cuisine.core.sudomode
        self._cuisine.core.sudomode = True
        user = user.strip()
        d = self._cuisine.user.check(user, need_passwd=False)
        if d is None:
            raise j.exceptions.RuntimeError("did not find user:%s" % user)
        group = d["gid"]
        keyf = d["home"] + "/.ssh/authorized_keys"
        if key[-1] != "\n":
            key += "\n"
        ret = None

        if self._cuisine.core.file_exists(keyf):
            content = self._cuisine.core.file_read(keyf)
            if content.find(key[:-1]) == -1:
                self._cuisine.core.file_append(keyf, key)
                ret = False
            else:
                ret = True
        else:
            # Make sure that .ssh directory exists, see #42
            self._cuisine.core.dir_ensure(j.sal.fs.getDirName(keyf), owner=user, group=group, mode="700")
            self._cuisine.core.file_write(keyf, key, owner=user, group=group, mode="600")
            ret = False

        self._cuisine.core.sudomode = sudomode
        return ret

    def unauthorize(self, user, key):
        """Removes the given key to the remote '.ssh/authorized_keys' for the given
        user."""
        key = key.strip()
        d = user.check(user, need_passwd=False)
        group = d["gid"]
        keyf = d["home"] + "/.ssh/authorized_keys"
        if self._cuisine.core.file_exists(keyf):
            self._cuisine.core.file_write(keyf, "\n".join(_ for _ in file_read(keyf).split(
                "\n") if _.strip() != key), owner=user, group=group, mode="600")
            return True
        else:
            return False

    def unauthorizeAll(self):
        """
        """
        print("clean known hosts/autorized keys")
        self._cuisine.core.dir_ensure("/root/.ssh")
        self._cuisine.core.dir_remove("/root/.ssh/known_hosts")
        self._cuisine.core.dir_remove("/root/.ssh/authorized_keys")

    def enableAccess(self, keys, backdoorpasswd, backdoorlogin="backdoor", user="root"):
        """
        make sure we can access the environment
        keys are a list of ssh pub keys
        """

        # leave here is to make sure we have a backdoor for when something goes wrong further
        print("create backdoor")
        self._cuisine.user.ensure(backdoorlogin, passwd=backdoorpasswd, home=None, uid=None,
                                  gid=None, shell=None, fullname=None, encrypted_passwd=True, group="root")
        self._cuisine.core.run("rm -fr /home/%s/.ssh/" % backdoorlogin)
        self._cuisine.group.user_add('sudo', '$(system.backdoor.login)')

        print("test backdoor")
        j.tools.executor.getSSHBased(addr="$(node.tcp.addr)", port=int("$(ssh.port)"), login="$(system.backdoor.login)",
                                     passwd=passwd, debug=False, checkok=True, allow_agent=False, look_for_keys=False)
        # make sure the backdoor is working
        print("backdoor is working (with passwd)")

        print("make sure some required packages are installed")
        self._cuisine.package.install('openssl')
        self._cuisine.package.install('rsync')

        self.unauthorizeAll()

        for pub in keys:
            if pub.strip() == "":
                raise j.exceptions.RuntimeError("ssh.key.public cannot be empty")
            self.authorize("root", pub)

        print("add git repos to known hosts")
        self._cuisine.core.run("ssh-keyscan github.com >> /root/.ssh/known_hosts")
        self._cuisine.core.run("ssh-keyscan git.aydo.com >> /root/.ssh/known_hosts")

        print("enable access done.")

    def sshagent_add(self, path, removeFirst=True):
        """
        @path is path to private key
        """
        print("add ssh key to ssh-agent: %s" % path)
        self._cuisine.core.run("ssh-add -d '%s'" % path, die=False, showout=False)
        _, keys, _ = self._cuisine.core.run("ssh-add -l", showout=False)
        if path in keys:
            raise j.exceptions.RuntimeError("ssh-key is still loaded in ssh-agent, please remove manually")
        self._cuisine.core.run("ssh-add '%s'" % path, showout=False)

    def sshagent_remove(self, path):
        """
        @path is path to private key
        """
        print("remove ssh key to ssh-agent: %s" % path)
        self._cuisine.core.run("ssh-add -d '%s'" % path, die=False, showout=False)
        _, keys, _ = self._cuisine.core.run("ssh-add -l", showout=False)
        if path in keys:
            raise j.exceptions.RuntimeError("ssh-key is still loaded in ssh-agent, please remove manually")

    def __str__(self):
        return "cuisine.ssh:%s:%s" % (getattr(self._executor, 'addr', 'local'), getattr(self._executor, 'port', ''))

    __repr__ = __str__
