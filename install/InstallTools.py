import sys

import asyncio
if sys.platform != 'cygwin':
    import uvloop

from urllib.request import urlopen

import os
import tarfile
import shutil
import tempfile
import platform
import subprocess
import time
import fnmatch
from subprocess import Popen
import re
import inspect
import yaml
import importlib
import fcntl


class FileLock():
    def __init__(self, fname):
        self._fname = fname
        self._f = None

    def __enter__(self):
        self._f = open(self._fname, 'w')
        fcntl.lockf(self._f, fcntl.LOCK_EX)

    def __exit__(self, *exit):
        try:
            fcntl.lockf(self._f, fcntl.LOCK_UN)
        finally:
            self._f.close()


class Installer():

    def __init__(self):
        self._readonly = None

    def checkPython(self):
        if sys.platform.startswith('darwin'):
            if len([item for item in do.listDirsInDir("/usr/local/lib") if item.find("python3") != -1]) > 1:
                raise RuntimeError("Please execute clean.sh in installer of jumpscale, found too many python installs")

    def installJS(self, base="", GITHUBUSER="", GITHUBPASSWD="", CODEDIR="",
                  JSGIT="https://github.com/Jumpscale/jumpscale_core8.git", JSBRANCH="master",
                  AYSGIT="https://github.com/Jumpscale/ays_jumpscale8", AYSBRANCH="master", EMAIL="", FULLNAME=""):
        """
        @param codedir is the location where the code will be installed, code which get's checked out from github
        @param base is location of root of JumpScale

        JSGIT & AYSGIT allow us to chose other install sources for jumpscale as well as AtYourService repo

        IMPORTANT: if env var's are set they get priority

        """
        # everything else is dangerous now
        copybinary = True

        tmpdir = self.do.TMPDIR

        if base != "":
            os.environ["JSBASE"] = base

        if CODEDIR != "":
            os.environ["CODEDIR"] = CODEDIR

        self.do.init()

        if sys.platform.startswith('win'):
            raise RuntimeError("Cannot find JSBASE, needs to be set as env var")

        PYTHONVERSION = "3.5"

        print(("Install Jumpscale in %s" % os.environ["JSBASE"]))

        # this means if env var's are set they get priority
        args2 = dict(map(lambda item: (item, ''), ["GITHUBUSER", "GITHUBPASSWD", "JSGIT", "JSBRANCH", "CFGDIR",
                                                   "AYSGIT", "AYSBRANCH", "CODEDIR", "EMAIL", "FULLNAME", "JSBASE", "PYTHONVERSION"]))
        # walk over all var's & set defaults or get them from env
        for var in args2.copy():
            if var in os.environ:
                args2[var] = os.environ[var]
            else:
                args2[var] = eval(var)

        os.environ.update(args2)

        args2['SANDBOX'] = int(do.sandbox)

        if EMAIL != "":
            self.gitConfig(FULLNAME, EMAIL)

        self.debug = True

        self.prepare()

        self.do.executeInteractive("mkdir -p %s/.ssh/" % os.environ["HOME"])
        self.do.executeInteractive("ssh-keyscan github.com 2> /dev/null  >> {0}/.ssh/known_hosts; ssh-keyscan git.aydo.com 2> /dev/null >> {0}/.ssh/known_hosts".format(
            os.environ["HOME"]))
        print("pull core")
        self.do.pullGitRepo(args2['JSGIT'], branch=args2['JSBRANCH'], ssh="first")
        src = "%s/github/jumpscale/jumpscale_core8/lib/JumpScale" % self.do.CODEDIR
        self.debug = False

        if self.do.TYPE.startswith("OSX"):
            self.do.delete("/usr/local/lib/python2.7/site-packages/JumpScale")
            self.do.delete("/usr/local/lib/python3.5/site-packages/JumpScale")

        # destjs = self.do.getPythonLibSystem(jumpscale=True)
        # self.do.delete(destjs)
        # self.do.createDir(destjs)

        base = args2["JSBASE"]

        self.do.createDir("%s/lib" % base)
        self.do.createDir("%s/bin" % base)
        # self.do.createDir("%s/hrd/system"%base)
        # self.do.createDir("%s/hrd/apps"%base)

        dest = "%s/lib/JumpScale" % base
        self.do.createDir(dest)
        self.do.symlinkFilesInDir(src, dest, includeDirs=True)
        # self.do.symlinkFilesInDir(src, destjs, includeDirs=True)

        for item in ["InstallTools", "ExtraTools"]:
            src = "%s/github/jumpscale/jumpscale_core8/install/%s.py" % (do.CODEDIR, item)
            dest2 = "%s/%s.py" % (dest, item)
            self.do.symlink(src, dest2)
            # dest2 = "%s/%s.py" % (destjs, item)
            # self.do.symlink(src, dest2)

        src = "%s/github/jumpscale/jumpscale_core8/shellcmds" % self.do.CODEDIR

        dest = "/usr/local/bin"
        self.do.symlinkFilesInDir(src, dest)

        dest = "%s/bin" % base
        self.do.symlinkFilesInDir(src, dest)

        # DO NOT LOAD AUTOCOMPLETE AUTOMATICALLY
        #         # create ays,jsdocker completion based on click magic variables
        #         with open(os.path.expanduser("~/.bashrc"), "a") as f:
        #             f.write('''
        # eval "$(_AYS_COMPLETE=source ays)"
        # eval "$(_JSDOCKER_COMPLETE=source jsdocker)"\n
        #             ''')

        # link python
        src = "/usr/bin/python3.5"
        if self.do.exists(src):
            # self.do.delete("/usr/bin/python")
            if not self.do.TYPE.startswith("OSX"):
                # self.do.symlink(src, "%s/bin/python"%base)
                self.do.symlink(src, "%s/bin/python3" % base)
                # self.do.symlink(src, "/usr/bin/python")

        # if self.do.TYPE.startswith("OSX"):
        #     src="/usr/local/bin/python3"
        #     self.do.symlink(src, "%s/bin/python"%base)
        #     self.do.symlink(src, "%s/bin/python3"%base)
        #     self.do.symlink(src, "%s/bin/python3.5"%base)

        self.writeEnv()

        sys.path.insert(0, "%s/lib" % base)

        print("Get atYourService metadata.")

        self.do.pullGitRepo(args2['AYSGIT'], branch=args2['AYSBRANCH'], ssh="first")

        print("install was successfull")
        print("to use do 'js'")

    @property
    def readonly(self):
        if self._readonly is None:
            ppath = "%s/bin/_writetest" % os.environ["JSBASE"]
            try:
                self.do.writeFile(ppath, "")
                self._readonly = False
            except:
                self._readonly = True
            self.do.delete(ppath)
        return self._readonly

    def _writeSystemEnv(self, cfgDir=None):
        self.do.createDir("%s/jumpscale" % os.environ["CFGDIR"])
        config = {}
        for category, items in {"identity": ["EMAIL", "FULLNAME", "GITHUBUSER"],
                                "system": ["AYSBRANCH", "JSBRANCH", "DEBUG", "SANDBOX"],
                                "dirs": ["JSBASE", "TMPDIR", "VARDIR", "DATADIR", "CODEDIR", "CFGDIR"]}.items():
            config[category] = {}
            for item in items:

                if item not in os.environ:
                    if item in ["DEBUG", "SANDBOX"]:
                        config[category][item] = False
                    else:
                        config[category][item] = ""
                else:
                    if item in ["DEBUG", "SANDBOX"]:
                        config[category][item] = str(os.environ[item]) == 1
                    else:
                        if category == "dirs":
                            while os.environ[item][-1] == "/":
                                os.environ[item] = os.environ[item][:-1]
                            os.environ[item] += "/"
                        config[category][item] = os.environ[item]

        cfgDir = cfgDir or os.environ["CFGDIR"]
        with open("%s/jumpscale/system.yaml" % cfgDir, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False)

    def _writeAYSEnv(self, cfgDir=None):
        C = """
        # By default, AYS will use the JS redis. This is for quick testing
        # and development. To configure a persistent/different redis, uncomment
        # and change the redis config

        # redis:
        #   host: "localhost"
        #   port: 6379

        # here domain = jumpscale, change name for more domains
        metadata:
            jumpscale:
                url: {AYSGIT}
                branch: {AYSBRANCH}

        """
        if "AYSGIT" not in os.environ or os.environ["AYSGIT"].strip() == "":
            os.environ["AYSGIT"] = "https://github.com/Jumpscale/ays_jumpscale8"
        if "AYSBRANCH" not in os.environ or os.environ["AYSBRANCH"].strip() == "":
            os.environ["AYSBRANCH"] = "master"

        C = C.format(**os.environ)

        cfgDir = cfgDir or os.environ["CFGDIR"]

        hpath = "%s/jumpscale/ays.yaml" % cfgDir
        if not self.do.exists(path=hpath):
            self.do.writeFile(hpath, C)

    def _writeLoggingEnv(self, cfgDir=None):
        C = """
        mode: 'DEV'
        level: 'DEBUG'

        filter:
            - 'j.sal.fs'
            - 'j.data.hrd'
            - 'j.application'
        """
        cfgDir = cfgDir or os.environ["CFGDIR"]
        self.do.writeFile("%s/jumpscale/logging.yaml" % cfgDir, C)

    def writeEnv(self):

        print("WRITENV")
        self._writeSystemEnv()
        self._writeAYSEnv()
        self._writeLoggingEnv()

        C = """

        deactivate () {
            export PATH=$_OLD_PATH
            unset _OLD_PATH
            export LD_LIBRARY_PATH=$_OLD_LD_LIBRARY_PATH
            unset _OLD_LD_LIBRARY_PATH
            export PYTHONPATH=$_OLD_PYTHONPATH
            unset _OLD_PYTHONPATH
            export PS1=$_OLD_PS1
            unset _OLD_PS1
            unset JSBASE
            unset PYTHONHOME
            if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
                    hash -r 2>/dev/null
            fi
        }

        if [[ "$JSBASE" == "$base" ]]; then
           return 0
        fi

        export JSBASE=$base

        export _OLD_PATH=$PATH
        export _OLD_LDLIBRARY_PATH=$LD_LIBRARY_PATH
        export _OLD_PS1=$PS1
        export _OLD_PYTHONPATH=$PYTHONPATH

        export PATH=$JSBASE/bin:$PATH

        export LUA_PATH="/opt/jumpscale8/lib/lua/?.lua;./?.lua;/opt/jumpscale8/lib/lua/?/?.lua;/opt/jumpscale8/lib/lua/tarantool/?.lua;/opt/jumpscale8/lib/lua/?/init.lua"

        $pythonhome
        export PYTHONPATH=$pythonpath

        $locale1
        $locale2

        export LD_LIBRARY_PATH=$JSBASE/bin
        export PS1="(JS8) $PS1"
        if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
                hash -r 2>/dev/null
        fi
        """
        C = C.replace("$base", os.environ["JSBASE"])

        if self.do.sandbox:
            C = C.replace('$pythonhome', 'export PYTHONHOME=$JSBASE/bin')
        else:
            C = C.replace('$pythonhome', '')

        if self.do.TYPE.startswith("OSX"):
            # C = C.replace("$pythonpath", ".:$JSBASE/lib:$JSBASE/lib/lib-dynload/:$JSBASE/bin:$JSBASE/lib/plat-x86_64-linux-gnu:/usr/local/lib/python3.5/site-packages:/usr/local/Cellar/python3/3.5.1/Frameworks/Python.framework/Versions/3.5/lib/python3.5:/usr/local/Cellar/python3/3.5.1/Frameworks/Python.framework/Versions/3.5/lib/python3.5/plat-darwin:/usr/local/Cellar/python3/3.5.1/Frameworks/Python.framework/Versions/3.5/lib/python3.5/lib-dynload")
            C = C.replace("$pythonpath", ".:$JSBASE/lib:$_OLD_PYTHONPATH")
            C = C.replace("$locale1", "export LC_ALL=en_US.UTF-8")
            C = C.replace("$locale2", "export LANG=en_US.UTF-8")

        else:
            C = C.replace("$locale1", "")
            C = C.replace("$locale2", "")
            C = C.replace(
                "$pythonpath", ".:$JSBASE/lib:$JSBASE/lib/lib-dynload/:$JSBASE/bin:$JSBASE/lib/python.zip:$JSBASE/lib/plat-x86_64-linux-gnu:$_OLD_PYTHONPATH")
        envfile = "%s/env.sh" % os.environ["JSBASE"]

        if self.readonly is False or die == True:
            self.do.writeFile(envfile, C)

        # pythonversion = '3' if os.environ.get('PYTHONVERSION') == '3' else ''

        C2 = """
        #!/bin/bash
        # set -x
        source $base/env.sh
        exec $JSBASE/bin/python3 -q "$@"
        """

        C2_insystem = """
        #!/bin/bash
        # set -x
        source $base/env.sh
        exec python3.5 -q "$@"
        """

        # C2=C2.format(base=basedir, env=envfile)
        if self.readonly is False:

            self.do.delete("/usr/bin/jspython")  # to remove link
            self.do.delete("%s/bin/jspython" % os.environ["JSBASE"])
            self.do.delete("/usr/local/bin/jspython")

            if self.do.sandbox:
                print("jspython in sandbox")
                dest = "%s/bin/jspython" % os.environ["JSBASE"]
                C2 = C2.replace('$base', os.environ["JSBASE"])
                self.do.writeFile(dest, C2)
            else:
                # in system
                print("jspython in system")
                dest = "/usr/local/bin/jspython"
                C2_insystem = C2_insystem.replace('$base', os.environ["JSBASE"])
                self.do.writeFile(dest, C2_insystem)

            self.do.chmod(dest, 0o770)

            # change site.py file
            def changesite(path):
                if self.do.exists(path=path):
                    C = self.do.readFile(path)
                    out = ""
                    for line in C.split("\n"):
                        if line.find("ENABLE_USER_SITE") == 0:
                            line = "ENABLE_USER_SITE = False"
                        if line.find("USER_SITE") == 0:
                            line = "USER_SITE = False"
                        if line.find("USER_BASE") == 0:
                            line = "USER_BASE = False"

                        out += "%s\n" % line
                    self.do.writeFile(path, out)
            changesite("%s/lib/site.py" % os.environ["JSBASE"])
            # if insystem:
            #     changesite("/usr/local/lib/python3/dist-packages/site.py"%basedir)

        # custom install items

    def cleanSystem(self):
        # TODO *2 no longer complete
        if self.do.TYPE.startswith("UBUNTU"):
            # pythonversion = os.environ.get('PYTHONVERSION', '')
            print("clean platform")
            CMDS = """
            pip uninstall JumpScale-core
            # killall tmux  #dangerous
            killall redis-server
            rm /usr/local/bin/js*
            rm /usr/local/bin/ays*
            rm -rf $base/lib/JumpScale
            rm -rf /opt/sentry/
            sudo stop redisac
            sudo stop redisp
            sudo stop redism
            sudo stop redisc
            killall redis-server
            rm -rf /opt/redis/
            """
            CMDS = CMDS.replace("$base", self.BASE)
            self.do.executeCmds(CMDS, showout=False, outputStderr=False, useShell=True, log=False,
                                cwd=None, timeout=60, errors=[], ok=[], captureout=False, die=False)

            for PYTHONVERSION in ["3.5", "3.4", "3.3", "2.7", ""]:
                CMDS = """
                rm -rf /usr/local/lib/python%(pythonversion)s/dist-packages/jumpscale*
                rm -rf /usr/local/lib/python%(pythonversion)s/site-packages/jumpscale*
                rm -rf /usr/local/lib/python%(pythonversion)s/dist-packages/JumpScale*
                rm -rf /usr/local/lib/python%(pythonversion)s/site-packages/JumpScale*
                rm -rf /usr/local/lib/python%(pythonversion)s/site-packages/JumpScale/
                rm -rf /usr/local/lib/python%(pythonversion)s/site-packages/jumpscale/
                rm -rf /usr/local/lib/python%(pythonversion)s/dist-packages/JumpScale/
                rm -rf /usr/local/lib/python%(pythonversion)s/dist-packages/jumpscale/
                """ % {'pythonversion': PYTHONVERSION}
                self.do.executeCmds(CMDS, showout=False, outputStderr=False, useShell=True, log=False,
                                    cwd=None, timeout=60, errors=[], ok=[], captureout=False, die=False)

    def updateSystem(self):

        if self.TYPE.startswith("UBUNTU"):
            CMDS = """
            apt-get update
            apt-get autoremove
            apt-get -f install -y
            apt-get upgrade -y
            """
            self.do.executeCmds(CMDS)

        elif self.TYPE.startswith("OSX"):
            CMDS = """
            brew update
            brew upgrade
            """
            self.do.executeCmds(CMDS)

    def installpip(self):
        tmpdir = self.do.config["dirs"]["TMPDIR"]
        if not self.do.exists(self.do.joinPaths(tmpdir, "get-pip.py")):
            if not self.do.TYPE.startswith("WIN"):
                cmd = "cd %s;curl -k https://bootstrap.pypa.io/get-pip.py > get-pip.py;python3 get-pip.py" % self.do.config[
                    "dirs"]["TMPDIR"]
                self.do.execute(cmd)

    def prepare(self):
        self.do.initCreateDirs4System()

        print("prepare")

        self.checkPython()

        # self.installpip()

        if sys.platform.startswith('win'):
            raise RuntimeError("Cannot find JSBASE, needs to be set as env var")
        elif sys.platform.startswith('darwin'):
            if "core_apps_installed" not in self.do.done:
                cmds = "tmux psutils libtiff libjpeg webp little-cms2"
                for item in cmds.split(" "):
                    if item.strip() != "":
                        cmd = "brew unlink %s" % (item)
                        self.do.execute(cmd)
                        cmd = "brew install %s" % (item)
                        self.do.execute(cmd)
                        cmd = "brew link --overwrite %s" % (item)
                        self.do.execute(cmd)

                        self.do.doneSet("core_apps_installed")
            else:
                print("no need to prepare system for base, already done.")

        self.do.dependencies.all()

    def gitConfig(self, name, email):
        if name == "":
            name = email
        if email == "":
            raise RuntimeError("email cannot be empty")
        self.do.execute("git config --global user.email \"%s\"" % email)
        self.do.execute("git config --global user.name \"%s\"" % name)

    def replacesitecustomize(self):
        if not self.TYPE == "WIN":
            ppath = "/usr/lib/python%s/sitecustomize.py" % os.environ.get('PYTHONVERSION', '')
            if ppath.find(ppath):
                os.remove(ppath)
            self.symlink("%s/utils/sitecustomize.py" % self.BASE, ppath)

            def do(path, dirname, names):
                if path.find("sitecustomize") != -1:
                    self.symlink("%s/utils/sitecustomize.py" % self.BASE, path)
            print("walk over /usr to find sitecustomize and link to new one")
            os.path.walk("/usr", do, "")
            os.path.walk("/etc", do, "")

    def develtools(self):

        [self.do.delete(item) for item in self.do.listDirsInDir(
            do.getPythonLibSystem()) if item.find(".egg-info") != -1]
        # [do.delete(item) for item in self.do.listDirsInDir(do.getPythonLibSystem()) if item.find(".dist-info")!=-1]
        [self.do.delete(item) for item in self.do.listDirsInDir(do.getPythonLibSystem()) if item.find(".egg") != -1]

        self.do.execute("rm -rf %s/pip*" % self.do.getPythonLibSystem())
        self.do.execute("rm -rf %s/pip*" % self.do.getBinDirSystem())

        # self.do.pullGitRepo("https://github.com/pypa/pip")
        # self.do.execute("cd %s;python3 setup.py install"%do.getGitRepoArgs("https://github.com/pypa/pip")[4])

        "https://bootstrap.pypa.io/get-pip.py"
        tmpfile = self.do.download("https://bootstrap.pypa.io/get-pip.py")
        self.do.execute("python3 %s" % tmpfile)
        self.do.execute("pip3 install --upgrade setuptools")

        #"pyvim"
        items = ["jedi", "python-prompt-toolkit", "ipython", "ptpython", "ptpdb", "pymux", "click"]
        for item in items:
            self.do.pullGitRepo("git@github.com:Jumpscale/%s.git" % item)
            path = self.do.joinPaths(do.CODEDIR, "github", "jumpscale", item)
            cmd = "cd %s;python3 jsinstall.py" % path
            print(cmd)
            self.do.execute(cmd)

        self.do.pullGitRepo("https://github.com/vinta/awesome-python")

        # if self.do.TYPE.startswith("OSX"):
        #     dest = "%s/Library/Application Support/Sublime Text 3/Packages" % os.environ["HOME"]
        #     src = "%s/opt/code/github/jumpscale/jumpscale_core8/tools/sublimetext/" % os.environ["HOME"]
        # else:
        #     print("implement develtools")
        #     import ipdb
        #     ipdb.set_trace()
        # if self.do.exists(src) and self.do.exists(dest):
        #     self.do.copyTree(src, dest)


class InstallTools():

    def __init__(self, debug=False):

        self._extratools = False
        self._asyncLoaded = False
        self._deps = None
        self._config = None

        self.installer = Installer()
        self.installer.do = self

        self.init()

    @property
    def debug(self):
        if self.config != {}:
            return self.config["system"]["DEBUG"]
        else:
            return os.environ["DEBUG"]

    @property
    def CODEDIR(self):
        if self.config != {}:
            return self.config["dirs"]["CODEDIR"]
        else:
            return os.environ["CODEDIR"]

    @property
    def BASE(self):
        if self.config != {}:
            return self.config["dirs"]["JSBASE"]
        else:
            return os.environ["JSBASE"]

    @property
    def CFGDIR(self):
        # IMPORTANT can never come from configfile!
        return os.environ["CFGDIR"]

    @property
    def TMPDIR(self):
        if self.config != {}:
            return self.config["dirs"]["TMPDIR"]
        else:
            return os.environ["TMPDIR"]

    @property
    def DATADIR(self):
        if self.config != {}:
            return self.config["dirs"]["DATADIR"]
        else:
            return os.environ["DATADIR"]

    @property
    def VARDIR(self):
        if self.config != {}:
            return self.config["dirs"]["VARDIR"]
        else:
            return os.environ["VARDIR"]

    @debug.setter
    def debug(self, value):
        if not isinstance(value, bool):
            raise RuntimeError("input for debug needs to be bool")
        if self.config != {}:
            self.config["system"]["DEBUG"] = value
        else:
            raise RuntimeError("cannot set debug, system is in readonly.")

    @property
    def sandbox(self):
        if self.config != {}:
            return self.config["system"]["SANDBOX"]
        else:
            return False

    @sandbox.setter
    def sandbox(self, value):
        if not isinstance(value, bool):
            raise RuntimeError("input for SANDBOX needs to be bool")
        if self.config != {}:
            self.config["system"]["SANDBOX"] = value
        else:
            raise RuntimeError("cannot set sandbox config arg, system is in readonly.")

    @property
    def configPath(self):
        return '%s/jumpscale/system.yaml' % self.CFGDIR

    @property
    def config(self):
        if self._config is None:
            if self.exists(self.configPath):
                with open(self.configPath, 'r') as conf:
                    self._config = yaml.load(conf)
            else:
                self._config = {}
        return self._config

    def configDestroy(self):
        self.remove(self.configPath)

    def configSet(self, category, key, value):
        c = self.config
        c[category][key] = value
        with open(self.configPath, 'w') as outfile:
            yaml.dump(c, outfile, default_flow_style=False)

    @property
    def dependencies(self):
        if self._deps == None:
            path = "%s/lib/JumpScale/install/dependencies.py" % os.environ["JSBASE"]
            if not self.exists(path):
                path = '%s/dependencies.py' % os.environ["TMPDIR"]
            if not self.exists(path):
                path = "/tmp/dependencies.py"
            if not self.exists(path):
                raise RuntimeError("Could not find dependencies file in %s" % path)

            loader = importlib.machinery.SourceFileLoader("deps", path)
            handle = loader.load_module("deps")
            self._deps = handle.dependencies(self)
        return self._deps

    @property
    def done(self):
        if self.readonly == False:
            path = '%s/jumpscale/done.yaml' % os.environ["CFGDIR"]
            if not self.exists(path):
                return {}
            with open(path, 'r') as conf:
                cfg = yaml.load(conf)
            return cfg
        else:
            # this to make sure works in readonly mode
            return {}

    def doneSet(self, key):
        if self.readonly == False:
            d = self.done
            d[key] = True
            path = '%s/jumpscale/done.yaml' % os.environ["CFGDIR"]
            parent = os.path.abspath(os.path.join(path, os.pardir))
            if not os.path.exists(parent):
                os.mkdir(parent)
            with open(path, 'w') as outfile:
                yaml.dump(d, outfile, default_flow_style=False)

    def init(self):

        if "DEBUG" in os.environ and str(os.environ["DEBUG"]).lower() in ["true", "1", "yes"]:
            os.environ["DEBUG"] = "1"
        else:
            os.environ["DEBUG"] = "0"

        if "READONLY" in os.environ and str(os.environ["READONLY"]).lower() in ["true", "1", "yes"]:
            os.environ["READONLY"] = "1"
            self.readonly = True
        else:
            os.environ["READONLY"] = "0"
            self.readonly = False

        if "AYSBRANCH" not in os.environ and "JSBRANCH" in os.environ:
            os.environ["AYSBRANCH"] = os.environ["JSBRANCH"]

        if "JSRUN" in os.environ and str(os.environ["JSRUN"]).lower() in ["true", "1", "yes"]:
            os.environ["JSRUN"] = "1"
            self.embed = True
        else:
            os.environ["JSRUN"] = "0"
            self.embed = False

        if self.embed:
            if not "JSBASE" in os.environ:
                os.environ["JSBASE"] = os.getcwd()
            os.environ["TMPDIR"] = "%s/js/tmp" % os.environ["JSBASE"]
            os.environ["VARDIR"] = "%s/js/optvar/" % os.environ["JSBASE"]
            os.environ["DATADIR"] = "%s/js/data" % os.environ["JSBASE"]
            os.environ["CODEDIR"] = "%s/js/code" % os.environ["JSBASE"]
            os.environ["CFGDIR"] = "%s/js/cfg" % os.environ["JSBASE"]

            self.initCreateDirs4System()

        elif self.exists("/JS8"):
            os.environ["JSBASE"] = "/JS8/opt/jumpscale8/"
            os.environ["TMPDIR"] = "/JS8/tmp"
            os.environ["VARDIR"] = "/JS8/optvar/"
            os.environ["DATADIR"] = "/JS8/optvar/data/"
            os.environ["CODEDIR"] = "/JS8/code"
            os.environ["CFGDIR"] = "/JS8/optvar/cfg/"

        if platform.system().lower() == "windows" or platform.system().lower() == "cygwin_nt-10.0":
            if not "JSBASE" in os.environ:
                raise RuntimeError()
            self.TYPE = "WIN"
            os.environ["JSBASE"] = "%s/" % os.environ["JSBASE"].replace("\\", "/")
            raise RuntimeError("TODO: *3")

        elif sys.platform.startswith("darwin"):
            if sys.platform.startswith("darwin"):
                self.TYPE = "OSX"

            if not "HOME" in os.environ:
                raise RuntimeError()

            if "JSBASE" not in os.environ:
                os.environ["JSBASE"] = "%s/opt/jumpscale8" % os.environ["HOME"]
            if "VARDIR" not in os.environ:
                os.environ["VARDIR"] = "%s/optvar" % os.environ["HOME"]
            if "DATADIR" not in os.environ:
                os.environ["DATADIR"] = "%s/optvar/data" % os.environ["HOME"]
            if "CODEDIR" not in os.environ:
                os.environ["CODEDIR"] = "%s/code" % os.environ["HOME"]
            if "TMPDIR" not in os.environ:
                os.environ["TMPDIR"] = "%s/tmp" % os.environ["HOME"]

        elif sys.platform.startswith("linux"):
            self.TYPE = "LINUX"
            if "JSBASE" not in os.environ:
                os.environ["JSBASE"] = "/opt/jumpscale8"
            if "VARDIR" not in os.environ:
                os.environ["VARDIR"] = "/optvar/"
            if "DATADIR" not in os.environ:
                os.environ["DATADIR"] = "/optvar/data"
            if "CFGDIR" not in os.environ:
                os.environ["CFGDIR"] = "/optvar/cfg"
            if "CODEDIR" not in os.environ:
                os.environ["CODEDIR"] = "/opt/code"
            if "TMPDIR" not in os.environ:
                os.environ["TMPDIR"] = "/tmp"

        else:
            raise RuntimeError("Jumpscale only supports windows 7+, macosx, ubuntu 12+")

        self.TYPE += platform.architecture()[0][:2]

        if not "TMPDIR" in os.environ:
            os.environ["TMPDIR"] = tempfile.gettempdir().replace("\\", "/")

        # DO NOT DO THIS, this should only be written when doing install
        # if not self.exists("%s/jumpscale/system.yaml" % os.environ["CFGDIR"]):
        #     self.installer.writeEnv()

        # if str(sys.excepthook).find("apport_excepthook")!=-1:
        # if we get here it means is std python excepthook (I hope)
        # print ("OUR OWN EXCEPTHOOK")
        # sys.excepthook = self.excepthook

        # self._initSSH_ENV()

    # def excepthook(self, ttype, exceptionObject, tb):

    #     # if isinstance(exceptionObject, HaltException):
    #     #     sys.exit(1)

    #     # print "jumpscale EXCEPTIONHOOK"
    #     # if self.inException:
    #     #     print("ERROR IN EXCEPTION HANDLING ROUTINES, which causes recursive errorhandling behavior.")
    #     #     print(exceptionObject)
    #     #     return

    #     print ("WE ARE IN EXCEPTHOOL OF INSTALLTOOLS, DEVELOP THIS FURTHER")
    #     from IPython import embed
    #     print((44))
    #     embed()
    #     #TODO: not working yet

    def initCreateDirs4System(self):
        for item in ["JSBASE", "HOME", "TMPDIR", "VARDIR", "DATADIR", "CODEDIR", "CFGDIR"]:
            path = os.environ[item]
            self.createDir(path)

    def log(self, msg, level=None):
        if self.debug:
            print(msg)

    def getBinDirSystem(self):
        return "/usr/local/bin/"

    def getPythonLibSystem(self, jumpscale=False):
        PYTHONVERSION = platform.python_version()
        if self.TYPE.startswith("OSX"):
            destjs = "/usr/local/lib/python3.5/site-packages"
        elif self.TYPE.startswith("WIN"):
            destjs = "/usr/lib/python3.4/site-packages"
        else:
            if PYTHONVERSION == '2':
                destjs = "/usr/local/lib/python/dist-packages"
            else:
                destjs = "/usr/local/lib/python3.5/dist-packages"

        if jumpscale:
            destjs += "/JumpScale/"

        self.createDir(destjs)
        return destjs

    def readFile(self, filename):
        """Read a file and get contents of that file
        @param filename: string (filename to open for reading )
        @rtype: string representing the file contents
        """
        with open(filename) as fp:
            data = fp.read()
        return data

    def touch(self, path):
        self.writeFile(path, "")

    def textstrip(self, content, ignorecomments=False):
        # remove all spaces at beginning & end of line when relevant

        # find generic prepend for full file
        minchars = 9999
        prechars = 0
        for line in content.split("\n"):
            if line.strip() == "":
                continue
            if ignorecomments:
                if line.strip().startswith('#') and not line.strip().startswith("#!"):
                    continue
            prechars = len(line) - len(line.lstrip())
            # print ("'%s':%s:%s"%(line,prechars,minchars))
            if prechars < minchars:
                minchars = prechars

        if minchars > 0:

            # if first line is empty, remove
            lines = content.split("\n")
            if len(lines) > 0:
                if lines[0].strip() == "":
                    lines.pop(0)
            content = "\n".join(lines)

            # remove the prechars
            content = "\n".join([line[minchars:] for line in content.split("\n")])

        return content

    def writeFile(self, path, content, strip=True):

        self.createDir(self.getDirName(path))

        if strip:
            content = self.textstrip(content, True)

        with open(path, "w") as fo:
            fo.write(content)

    def delete(self, path, force=False):

        self.removeSymlink(path)

        if path.strip().rstrip("/") in ["", "/", "/etc", "/root", "/usr",
                                        "/opt", "/usr/bin", "/usr/sbin", self.CODEDIR]:
            raise RuntimeError('cannot delete protected dirs')

        # if not force and path.find(self.CODEDIR)!=-1:
        #     raise RuntimeError('cannot delete protected dirs')

        if self.debug:
            print(("delete: %s" % path))
        if os.path.exists(path) or os.path.islink(path):
            if os.path.isdir(path):
                # print "delete dir %s" % path
                if os.path.islink(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
            else:
                # print "delete file %s" % path
                os.remove(path)

    def joinPaths(self, *args):
        return os.path.join(*args)

    def copyTree(self, source, dest, keepsymlinks=False, deletefirst=False,
                 overwriteFiles=True, ignoredir=[".egg-info", ".dist-info"], ignorefiles=[".egg-info"], rsync=True,
                 ssh=False, sshport=22, recursive=True, rsyncdelete=False, createdir=False):
        """
        if ssh format of source or dest is: remoteuser@remotehost:/remote/dir
        """
        if self.debug:
            print(("copy %s %s" % (source, dest)))
        if not ssh and not self.exists(source):
            raise RuntimeError("copytree:Cannot find source:%s" % source)
        if rsync:
            excl = ""
            for item in ignoredir:
                excl += "--exclude '*%s*/' " % item
            for item in ignorefiles:
                excl += "--exclude '*%s*' " % item
            excl += "--exclude '*.pyc' "
            excl += "--exclude '*.bak' "
            excl += "--exclude '*__pycache__*' "

            if self.isDir(source):
                if dest[-1] != "/":
                    dest += "/"
                if source[-1] != "/":
                    source += "/"
                if ssh:
                    pass
                    # if dest.find(":")!=-1:
                    #     if dest.find("@")!=-1:
                    #         desthost=dest.split(":")[0].split("@", 1)[1].strip()
                    #     else:
                    #         desthost=dest.split(":")[0].strip()
                    #     dir_dest=dest.split(":",1)[1]
                    #     cmd="ssh -o StrictHostKeyChecking=no -p %s  %s 'mkdir -p %s'" % (sshport,sshport,dir_dest)
                    #     print cmd
                    #     self.executeInteractive(cmd)
                else:
                    self.createDir(dest)
            if dest.find(':') == -1:  # download
                self.createDir(self.getParent(dest))

            destpath = dest.split(':')[1] if ':' in dest else dest

            cmd = "rsync "
            if keepsymlinks:
                #-l is keep symlinks, -L follow
                cmd += " -rlptgo --partial %s" % excl
            else:
                cmd += " -rLptgo --partial %s" % excl
            if not recursive:
                cmd += " --exclude \"*/\""
            if self.debug:
                cmd += ' --progress'
            if rsyncdelete:
                cmd += " --delete"
            if ssh:
                cmd += " -e 'ssh -o StrictHostKeyChecking=no -p %s' " % sshport
            if createdir:
                cmd += "--rsync-path='mkdir -p %s && rsync' " % self.getParent(destpath)
            cmd += " '%s' '%s'" % (source, dest)
            print(cmd)
            rc, out, err = self.execute(cmd)
            print(rc)
            print(out)
            return
        else:
            old_debug = self.debug
            self.debug = False
            self._copyTree(source, dest, keepsymlinks, deletefirst, overwriteFiles,
                           ignoredir=ignoredir, ignorefiles=ignorefiles)
            self.debug = old_debug

    def _copyTree(self, src, dst, keepsymlinks=False, deletefirst=False, overwriteFiles=True,
                  ignoredir=[".egg-info", "__pycache__"], ignorefiles=[".egg-info"]):
        """Recursively copy an entire directory tree rooted at src.
        The dst directory may already exist; if not,
        it will be created as well as missing parent directories
        @param src: string (source of directory tree to be copied)
        @param dst: string (path directory to be copied to...should not already exist)
        @param keepsymlinks: bool (True keeps symlinks instead of copying the content of the file)
        @param deletefirst: bool (Set to True if you want to erase destination first, be carefull, this can erase directories)
        @param overwriteFiles: if True will overwrite files, otherwise will not overwrite when destination exists
        """

        self.log('Copy directory tree from %s to %s' % (src, dst), 6)
        if ((src is None) or (dst is None)):
            raise TypeError(
                'Not enough parameters passed in system.fs.copyTree to copy directory from %s to %s ' % (src, dst))
        if self.isDir(src):
            if ignoredir != []:
                for item in ignoredir:
                    if src.find(item) != -1:
                        return
            names = os.listdir(src)

            if not self.exists(dst):
                self.createDir(dst)

            errors = []
            for name in names:
                # is only for the name
                name2 = name

                srcname = self.joinPaths(src, name)
                dstname = self.joinPaths(dst, name2)
                if deletefirst and self.exists(dstname):
                    if self.isDir(dstname, False):
                        self.removeDirTree(dstname)
                    if self.isLink(dstname):
                        self.unlink(dstname)

                if keepsymlinks and self.isLink(srcname):
                    linkto = self.readLink(srcname)
                    # self.symlink(linkto, dstname)#, overwriteFiles)
                    try:
                        os.symlink(linkto, dstname)
                    except:
                        pass
                        # TODO: very ugly change
                elif self.isDir(srcname):
                    # print "1:%s %s"%(srcname,dstname)
                    self.copyTree(srcname, dstname, keepsymlinks, deletefirst,
                                  overwriteFiles=overwriteFiles, ignoredir=ignoredir)
                else:
                    # print "2:%s %s"%(srcname,dstname)
                    extt = self.getFileExtension(srcname)
                    if extt == "pyc" or extt == "egg-info":
                        continue
                    if ignorefiles != []:
                        for item in ignorefiles:
                            if srcname.find(item) != -1:
                                continue
                    self.copyFile(srcname, dstname, deletefirst=overwriteFiles)
        else:
            raise RuntimeError('Source path %s in system.fs.copyTree is not a directory' % src)

    def copyFile(self, source, dest, deletefirst=False, skipIfExists=False, makeExecutable=False):
        """
        """
        if self.isDir(dest):
            dest = self.joinPaths(dest, self.getBaseName(source))

        if skipIfExists:
            if self.exists(dest):
                return

        if deletefirst:
            self.delete(dest)
        if self.debug:
            print(("copy %s %s" % (source, dest)))

        shutil.copy(source, dest)

        if makeExecutable:
            self.chmod(dest, 0o770)

    def createDir(self, path):
        if not os.path.exists(path) and not os.path.islink(path):
            os.makedirs(path)

    def changeDir(self, path, create=False):
        """Changes Current Directory
        @param path: string (Directory path to be changed to)
        """
        self.log('Changing directory to: %s' % path, 6)
        if create:
            self.createDir(path)
        if self.exists(path):
            if self.isDir(path):
                os.chdir(path)
            else:
                raise ValueError("Path: %s in system.fs.changeDir is not a Directory" % path)
        else:
            raise RuntimeError("Path: %s in system.fs.changeDir does not exist" % path)

    def isDir(self, path, followSoftlink=False):
        """Check if the specified Directory path exists
        @param path: string
        @param followSoftlink: boolean
        @rtype: boolean (True if directory exists)
        """
        if self.isLink(path):
            if not followSoftlink:
                return False
            else:
                link = self.readLink(path)
                return self.isDir(link)
        else:
            return os.path.isdir(path)

    def isExecutable(self, path):
        stat.S_IXUSR & statobj.st_mode

    def isFile(self, path, followSoftlink=False):
        """Check if the specified file exists for the given path
        @param path: string
        @param followSoftlink: boolean
        @rtype: boolean (True if file exists for the given path)
        """
        if self.isLink(path):
            if not followSoftlink:
                return False
            else:
                link = self.readLink(path)
                return self.isFile(link)
        else:
            return os.path.isfile(path)

    def isLink(self, path, checkJunction=False):
        """Check if the specified path is a link
        @param path: string
        @rtype: boolean (True if the specified path is a link)
        """
        if path[-1] == os.sep:
            path = path[:-1]
        if (path is None):
            raise TypeError('Link path is None in system.fs.isLink')

        if checkJunction and self.isWindows():
            cmd = "junction %s" % path
            try:
                rc, result, err = self.execute(cmd)
            except Exception as e:
                raise RuntimeError("Could not execute junction cmd, is junction installed? Cmd was %s." % cmd)
            if rc != 0:
                raise RuntimeError("Could not execute junction cmd, is junction installed? Cmd was %s." % cmd)
            if result.lower().find("substitute name") != -1:
                return True
            else:
                return False

        if(os.path.islink(path)):
            # self.log('path %s is a link'%path,8)
            return True
        # self.log('path %s is not a link'%path,8)
        return False

    def list(self, path):
        # self.log("list:%s"%path)
        if(self.isDir(path)):
            s = sorted(["%s/%s" % (path, item) for item in os.listdir(path)])
            return s
        elif(self.isLink(path)):
            link = self.readLink(path)
            return self.list(link)
        else:
            raise ValueError("Specified path: %s is not a Directory in self.listDir" % path)

    def exists(self, path):
        return os.path.exists(path)

    def pip(self, items, force=False, executor=None):
        """
        @param items is string or list
        """
        if isinstance(items, list):
            pass
        elif isinstance(items, str):
            items = self.textstrip(items)
            items = [item.strip() for item in items.split("\n") if item.strip() != ""]
        else:
            raise RuntimeError("input can only be string or list")

        for item in items:
            if "pip_%s" % item not in self.done or force:
                cmd = "pip3 install %s --upgrade" % item
                if executor == None:
                    self.executeInteractive(cmd)
                else:
                    executor.execute(cmd)
                self.doneSet("pip_%s" % item)
            else:
                print("no need to pip install:%s" % item)

    # TODO *3 does not belong here
    def findDependencies(self, path, deps={}):
        excl = ["libc.so", "libpthread.so", "libutil.so"]
        out = self.installtools.execute("ldd %s" % path)
        result = []
        for item in [item.strip() for item in out.split("\n") if item.strip() != ""]:
            if item.find("=>") != -1:
                link = item.split("=>")[1].strip()
                link = link.split("(")[0].strip()
                if self.exists(link):
                    name = os.path.basename(link)
                    if name not in deps:
                        print(link)
                        deps[name] = link
                        deps = self.findDependencies(link)
        return deps

    def copyDependencies(self, path, dest):
        self.installtools.createDir(dest)
        deps = self.findDependencies(path)
        for name in list(deps.keys()):
            path = deps[name]
            self.installtools.copydeletefirst(path, "%s/%s" % (dest, name))

    def symlink(self, src, dest, delete=False):
        """
        dest is where the link will be created pointing to src
        """
        if self.debug:
            print(("symlink: src:%s dest(islink):%s" % (src, dest)))

        if self.isLink(dest):
            self.removeSymlink(dest)

        if delete:
            if self.TYPE == "WIN":
                self.removeSymlink(dest)
                self.delete(dest)
            else:
                self.delete(dest)

        if self.TYPE == "WIN":
            cmd = "junction %s %s 2>&1 > null" % (dest, src)
            os.system(cmd)
            # raise RuntimeError("not supported on windows yet")
        else:
            dest = dest.rstrip("/")
            src = src.rstrip("/")
            if not self.exists(src):
                raise RuntimeError("could not find src for link:%s" % src)
            if not self.exists(dest):
                os.symlink(src, dest)

    def symlinkFilesInDir(self, src, dest, delete=True, includeDirs=False):
        if includeDirs:
            items = self.listFilesAndDirsInDir(src, recursive=False, followSymlinks=False, listSymlinks=False)
        else:
            items = self.listFilesInDir(src, recursive=False, followSymlinks=True, listSymlinks=True)
        for item in items:
            dest2 = "%s/%s" % (dest, self.getBaseName(item))
            dest2 = dest2.replace("//", "/")
            print(("link %s:%s" % (item, dest2)))
            self.symlink(item, dest2, delete=delete)

    def removeSymlink(self, path):
        if self.TYPE == "WIN":
            try:
                cmd = "junction -d %s 2>&1 > null" % (path)
                print(cmd)
                os.system(cmd)
            except Exception as e:
                pass
        else:
            if self.isLink(path):
                os.unlink(path.rstrip("/"))

    def getBaseName(self, path):
        """Return the base name of pathname path."""
        # self.log('Get basename for path: %s'%path,9)
        if path is None:
            raise TypeError('Path is not passed in system.fs.getDirName')
        try:
            return os.path.basename(path.rstrip(os.path.sep))
        except Exception as e:
            raise RuntimeError('Failed to get base name of the given path: %s, Error: %s' % (path, str(e)))

    def checkDirOrLinkToDir(self, fullpath):
        """
        check if path is dir or link to a dir
        """
        if fullpath is None or fullpath.strip == "":
            raise RuntimeError("path cannot be empty")

        if not self.isLink(fullpath) and os.path.isdir(fullpath):
            return True
        if self.isLink(fullpath):
            link = self.readLink(fullpath)
            if self.isDir(link):
                return True
        return False

    def getDirName(self, path, lastOnly=False, levelsUp=None):
        """
        Return a directory name from pathname path.
        @param path the path to find a directory within
        @param lastOnly means only the last part of the path which is a dir (overrides levelsUp to 0)
        @param levelsUp means, return the parent dir levelsUp levels up
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=0) would return something
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=1) would return bin
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=10) would raise an error
        """
        # self.log('Get directory name of path: %s' % path,9)
        if path is None:
            raise TypeError('Path is not passed in system.fs.getDirName')
        dname = os.path.dirname(path)
        dname = dname.replace("/", os.sep)
        dname = dname.replace("//", os.sep)
        dname = dname.replace("\\", os.sep)
        if lastOnly:
            dname = dname.split(os.sep)[-1]
            return dname
        if levelsUp is not None:
            parts = dname.split(os.sep)
            if len(parts) - levelsUp > 0:
                return parts[len(parts) - levelsUp - 1]
            else:
                raise RuntimeError("Cannot find part of dir %s levels up, path %s is not long enough" %
                                   (levelsUp, path))
        return dname + os.sep

    def readLink(self, path):
        """Works only for unix
        Return a string representing the path to which the symbolic link points.
        """
        while path[-1] == "/" or path[-1] == "\\":
            path = path[:-1]
        # self.log('Read link with path: %s'%path,8)
        if path is None:
            raise TypeError('Path is not passed in system.fs.readLink')
        if self.isWindows():
            raise RuntimeError('Cannot readLink on windows')
        try:
            return os.readlink(path)
        except Exception as e:
            raise RuntimeError('Failed to read link with path: %s \nERROR: %s' % (path, str(e)))

    def removeLinks(self, path):
        """
        find all links & remove
        """
        if not self.exists(path):
            return
        items = self._listAllInDir(path=path, recursive=True, followSymlinks=False, listSymlinks=True)
        items = [item for item in items[0] if self.isLink(item)]
        for item in items:
            self.unlink(item)

    def _listInDir(self, path, followSymlinks=True):
        """returns array with dirs & files in directory
        @param path: string (Directory path to list contents under)
        """
        if path is None:
            raise TypeError('Path is not passed in system.fs.listDir')
        if(self.exists(path)):
            if(self.isDir(path)) or (followSymlinks and self.checkDirOrLinkToDir(path)):
                names = os.listdir(path)
                return names
            else:
                raise ValueError("Specified path: %s is not a Directory in system.fs.listDir" % path)
        else:
            raise RuntimeError("Specified path: %s does not exist in system.fs.listDir" % path)

    def listDirsInDir(self, path, recursive=False, dirNameOnly=False, findDirectorySymlinks=True):
        """ Retrieves list of directories found in the specified directory
        @param path: string represents directory path to search in
        @rtype: list
        """
        # self.log('List directories in directory with path: %s, recursive = %s' % (path, str(recursive)),9)

        # if recursive:
        # if not self.exists(path):
        # raise ValueError('Specified path: %s does not exist' % path)
        # if not self.isDir(path):
        # raise ValueError('Specified path: %s is not a directory' % path)
        # result = []
        # os.path.walk(path, lambda a, d, f: a.append('%s%s' % (d, os.path.sep)), result)
        # return result
        if path is None or path.strip == "":
            raise RuntimeError("path cannot be empty")
        files = self._listInDir(path, followSymlinks=True)
        filesreturn = []
        for file in files:
            fullpath = os.path.join(path, file)
            if (findDirectorySymlinks and self.checkDirOrLinkToDir(fullpath)) or self.isDir(fullpath):
                if dirNameOnly:
                    filesreturn.append(file)
                else:
                    filesreturn.append(fullpath)
                if recursive:
                    filesreturn.extend(self.listDirsInDir(fullpath, recursive, dirNameOnly, findDirectorySymlinks))
        return filesreturn

    def listFilesInDir(self, path, recursive=False, filter=None, minmtime=None, maxmtime=None,
                       depth=None, case_sensitivity='os', exclude=[], followSymlinks=True, listSymlinks=False):
        """Retrieves list of files found in the specified directory
        @param path:       directory path to search in
        @type  path:       string
        @param recursive:  recursively look in all subdirs
        @type  recursive:  boolean
        @param filter:     unix-style wildcard (e.g. *.py) - this is not a regular expression
        @type  filter:     string
        @param minmtime:   if not None, only return files whose last modification time > minmtime (epoch in seconds)
        @type  minmtime:   integer
        @param maxmtime:   if not None, only return files whose last modification time < maxmtime (epoch in seconds)
        @Param depth: is levels deep wich we need to go
        @type  maxmtime:   integer
        @Param exclude: list of std filters if matches then exclude
        @rtype: list
        """
        if depth is not None:
            depth = int(depth)
        # self.log('List files in directory with path: %s' % path,9)
        if depth == 0:
            depth = None
        # if depth is not None:
        #     depth+=1
        filesreturn, depth = self._listAllInDir(path, recursive, filter, minmtime, maxmtime, depth, type="f",
                                                case_sensitivity=case_sensitivity, exclude=exclude, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
        return filesreturn

    def listFilesAndDirsInDir(self, path, recursive=False, filter=None, minmtime=None,
                              maxmtime=None, depth=None, type="fd", followSymlinks=True, listSymlinks=False):
        """Retrieves list of files found in the specified directory
        @param path:       directory path to search in
        @type  path:       string
        @param recursive:  recursively look in all subdirs
        @type  recursive:  boolean
        @param filter:     unix-style wildcard (e.g. *.py) - this is not a regular expression
        @type  filter:     string
        @param minmtime:   if not None, only return files whose last modification time > minmtime (epoch in seconds)
        @type  minmtime:   integer
        @param maxmtime:   if not None, only return files whose last modification time < maxmtime (epoch in seconds)
        @Param depth: is levels deep wich we need to go
        @type  maxmtime:   integer
        @param type is string with f & d inside (f for when to find files, d for when to find dirs)
        @rtype: list
        """
        if depth is not None:
            depth = int(depth)
        self.log('List files in directory with path: %s' % path, 9)
        if depth == 0:
            depth = None
        # if depth is not None:
        #     depth+=1
        filesreturn, depth = self._listAllInDir(
            path, recursive, filter, minmtime, maxmtime, depth, type=type, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
        return filesreturn

    def _listAllInDir(self, path, recursive, filter=None, minmtime=None, maxmtime=None, depth=None,
                      type="df", case_sensitivity='os', exclude=[], followSymlinks=True, listSymlinks=True):
        """
        # There are 3 possible options for case-sensitivity for file names
        # 1. `os`: the same behavior as the OS
        # 2. `sensitive`: case-sensitive comparison
        # 3. `insensitive`: case-insensitive comparison
        """

        dircontent = self._listInDir(path)
        filesreturn = []

        if case_sensitivity.lower() == 'sensitive':
            matcher = fnmatch.fnmatchcase
        elif case_sensitivity.lower() == 'insensitive':
            def matcher(fname, pattern):
                return fnmatch.fnmatchcase(fname.lower(), pattern.lower())
        else:
            matcher = fnmatch.fnmatch

        for direntry in dircontent:
            fullpath = self.joinPaths(path, direntry)

            if followSymlinks:
                if self.isLink(fullpath):
                    fullpath = self.readLink(fullpath)

            if self.isFile(fullpath) and "f" in type:
                includeFile = False
                if (filter is None) or matcher(direntry, filter):
                    if (minmtime is not None) or (maxmtime is not None):
                        mymtime = os.stat(fullpath)[ST_MTIME]
                        if (minmtime is None) or (mymtime > minmtime):
                            if (maxmtime is None) or (mymtime < maxmtime):
                                includeFile = True
                    else:
                        includeFile = True
                if includeFile:
                    if exclude != []:
                        for excludeItem in exclude:
                            if matcher(direntry, excludeItem):
                                includeFile = False
                    if includeFile:
                        filesreturn.append(fullpath)
            elif self.isDir(fullpath):
                if "d" in type:
                    if not(listSymlinks is False and self.isLink(fullpath)):
                        filesreturn.append(fullpath)
                if recursive:
                    if depth is not None and depth != 0:
                        depth = depth - 1
                    if depth is None or depth != 0:
                        exclmatch = False
                        if exclude != []:
                            for excludeItem in exclude:
                                if matcher(fullpath, excludeItem):
                                    exclmatch = True
                        if exclmatch is False:
                            if not(followSymlinks is False and self.isLink(fullpath)):
                                r, depth = self._listAllInDir(fullpath, recursive, filter, minmtime, maxmtime, depth=depth,
                                                              type=type, exclude=exclude, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
                                if len(r) > 0:
                                    filesreturn.extend(r)
            elif self.isLink(fullpath) and followSymlinks is False and listSymlinks:
                filesreturn.append(fullpath)

        return filesreturn, depth

    def getParent(self, path):
        """
        Returns the parent of the path:
        /dir1/dir2/file_or_dir -> /dir1/dir2/
        /dir1/dir2/            -> /dir1/
        TODO: why do we have 2 implementations which are almost the same see getParentDirName()
        """
        parts = path.split(os.sep)
        if parts[-1] == '':
            parts = parts[:-1]
        parts = parts[:-1]
        if parts == ['']:
            return os.sep
        return os.sep.join(parts)

    def getFileExtension(self, path):
        extcand = path.split(".")
        if len(extcand) > 0:
            ext = extcand[-1]
        else:
            ext = ""
        return ext

    def chown(self, path, user):

        from pwd import getpwnam

        getpwnam(user)[2]
        uid = getpwnam(user).pw_uid
        gid = getpwnam(user).pw_gid
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for ddir in dirs:
                path = os.path.join(root, ddir)
                try:
                    os.chown(path, uid, gid)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise RuntimeError("%s" % e)
            for file in files:
                path = os.path.join(root, file)
                try:
                    os.chown(path, uid, gid)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise RuntimeError("%s" % e)

    def chmod(self, path, permissions):
        """
        @param permissions e.g. 0o660 (USE OCTAL !!!)
        """
        os.chmod(path, permissions)
        for root, dirs, files in os.walk(path):
            for ddir in dirs:
                path = os.path.join(root, ddir)
                try:
                    os.chmod(path, permissions)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise RuntimeError("%s" % e)

            for file in files:
                path = os.path.join(root, file)
                try:
                    os.chmod(path, permissions)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise RuntimeError("%s" % e)

    def chdir(self, ddir=""):
        """
        if ddir=="" then will go to tmpdir
        """
        if ddir == "":
            ddir = self.TMPDIR
        os.chdir(ddir)

    # NON FS

    def download(self, url, to="", overwrite=True, retry=3, timeout=0, login="",
                 passwd="", minspeed=0, multithread=False, curl=False):
        """
        @return path of downloaded file
        @param minspeed is kbytes per sec e.g. 50, if less than 50 kbytes during 10 min it will restart the download (curl only)
        @param when multithread True then will use aria2 download tool to get multiple threads
        """
        def download(url, to, retry=3):
            if timeout == 0:
                handle = urlopen(url)
            else:
                handle = urlopen(url, timeout=timeout)
            nr = 0
            while nr < retry + 1:
                try:
                    with open(to, 'wb') as out:
                        while True:
                            data = handle.read(1024)
                            if len(data) == 0:
                                break
                            out.write(data)
                    handle.close()
                    out.close()
                    return
                except Exception as e:
                    print("DOWNLOAD ERROR:%s\n%s" % (url, e))
                    try:
                        handle.close()
                    except:
                        pass
                    try:
                        out.close()
                    except:
                        pass
                    handle = urlopen(url)
                    nr += 1

        print(('Downloading %s ' % (url)))
        if to == "":
            to = self.TMPDIR + "/" + url.replace("\\", "/").split("/")[-1]

        if overwrite:
            if self.exists(to):
                self.delete(to)
                self.delete("%s.downloadok" % to)
        else:
            if self.exists(to) and self.exists("%s.downloadok" % to):
                # print "NO NEED TO DOWNLOAD WAS DONE ALREADY"
                return to

        self.createDir(self.getDirName(to))

        if curl and self.checkInstalled("curl"):
            minspeed = 0
            if minspeed != 0:
                minsp = "-y %s -Y 600" % (minspeed * 1024)
            else:
                minsp = ""
            if login:
                user = "--user %s:%s " % (login, passwd)
            else:
                user = ""

            cmd = "curl '%s' -o '%s' %s %s --connect-timeout 5 --retry %s --retry-max-time %s" % (
                url, to, user, minsp, retry, timeout)
            if self.exists(to):
                cmd += " -C -"
            print(cmd)
            self.delete("%s.downloadok" % to)
            rc, out, err = self.execute(cmd, die=False)
            if rc == 33:  # resume is not support try again withouth resume
                self.delete(to)
                cmd = "curl '%s' -o '%s' %s %s --connect-timeout 5 --retry %s --retry-max-time %s" % (
                    url, to, user, minsp, retry, timeout)
                rc, out, err = self.execute(cmd, die=False)
            if rc:
                raise RuntimeError("Could not download:{}.\nErrorcode: {}".format(url, rc))
            else:
                self.touch("%s.downloadok" % to)
        elif multithread:
            raise RuntimeError("not implemented yet")
        else:
            download(url, to, retry)
            self.touch("%s.downloadok" % to)

        return to

    def isUnix(self):
        if sys.platform.lower().find("linux") != -1:
            return True
        return False

    def isWindows(self):
        if sys.platform.startswith("win") == 1:
            return True
        return False

    def executeBashScript(self, content="", path=None, die=True, remote=None,
                          sshport=22, showout=True, outputStderr=True, sshkey=""):
        """
        @param remote can be ip addr or hostname of remote, if given will execute cmds there
        """
        if path is not None:
            content = self.readFile(path)
        if content[-1] != "\n":
            content += "\n"

        if remote is None:
            tmppath = self.getTmpPath("")
            content = "cd %s\n%s" % (tmppath, content)
        else:
            content = "cd /tmp\n%s" % content

        if die:
            content = "set -ex\n%s" % content

        path2 = self.getTmpPath("do.sh")
        self.writeFile(path2, content, strip=True)

        if remote is not None:
            tmppathdest = "/tmp/do.sh"
            if sshkey:
                if not self.getSSHKeyPathFromAgent(sshkey, die=False):
                    self.execute('ssh-add %s' % sshkey)
                sshkey = '-i %s ' % sshkey.replace('!', '\!')
            self.execute("scp %s -oStrictHostKeyChecking=no -P %s %s root@%s:%s " %
                         (sshkey, sshport, path2, remote, tmppathdest), die=die)
            rc, res, err = self.execute("ssh %s -oStrictHostKeyChecking=no -A -p %s root@%s 'bash %s'" %
                                        (sshkey, sshport, remote, tmppathdest), die=die)
        else:
            rc, res, err = self.execute("bash %s" % path2, die=die, showout=showout, outputStderr=outputStderr)
        return rc, res, err

    def executeCmds(self, cmdstr, showout=True, outputStderr=True, useShell=True,
                    log=True, cwd=None, timeout=120, captureout=True, die=True):
        rc_ = []
        out_ = ""
        for cmd in cmdstr.split("\n"):
            if cmd.strip() == "" or cmd[0] == "#":
                continue
            cmd = cmd.strip()
            self.executeInteractive(cmd)
            # rc, out, err = self.execute(cmd, showout, outputStderr, useShell, log, cwd, timeout, captureout, die)
            # rc_.append(str(rc))
            # out_ += out

        return rc_, out_

    def sendmail(self, ffrom, to, subject, msg, smtpuser, smtppasswd,
                 smtpserver="smtp.mandrillapp.com", port=587, html=""):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')

        msg['Subject'] = subject
        msg['From'] = ffrom
        msg['To'] = to

        if msg != "":
            part1 = MIMEText(str(msg), 'plain')
            msg.attach(part1)

        if html != "":
            part2 = MIMEText(html, 'html')
            msg.attach(part2)

        s = smtplib.SMTP(smtpserver, port)

        s.login(smtpuser, smtppasswd)
        s.sendmail(msg['From'], msg['To'], msg.as_string())

        s.quit()

    def execute(self, command, showout=True, outputStderr=True, useShell=True, log=True, cwd=None, timeout=100,
                captureout=True, die=True, async=False, executor=None):
        """
        Execute command
        @param command: Command to be executed
        @param showout: print output line by line while processing the command
        @param outputStderr: print error line by line while processing the command
        @param useShell: Execute command as a shell command
        @param log:
        @param cwd: If cwd is not None, the function changes the working directory to cwd before executing the child
        @param timeout: If not None, raise TimeoutError if command execution time > timeout
        @param captureout: If True, returns output of cmd. Else, it returns empty str
        @param die: If True, raises error if cmd failed. else, fails silently and returns error in the output
        @param async: If true, return Process object. DO CLOSE THE PROCESS AFTER FINISHING BY process.wait()
        @param executor: If not None returns output of executor.execute(....)
        @return: (returncode, output, error). output and error defaults to empty string
        """

        if executor:
            return executor.execute(command, die=die, checkok=False, async=async, showout=True, timeout=timeout)

        # TODO: *1 need to be brought back without async & without anything
        # advanced, this is an isntaller should not have async, ...

        executable = '/bin/bash' if useShell else None

        if async:
            os.environ["PYTHONUNBUFFERED"] = "1"
            ON_POSIX = 'posix' in sys.builtin_module_names

            proc = Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=ON_POSIX,
                         shell=useShell, env=os.environ, universal_newlines=True, cwd=cwd, bufsize=0, executable=executable)
            return proc

        @asyncio.coroutine
        def _read_stream(_showout, stream):
            # print("showout:%s" % showout)
            """coroutine to read prints output based on stream"""
            out = ''
            while True:
                line = yield from stream.readline()
                if not line:
                    break
                if _showout:
                    sys.stdout.buffer.write(line)
                if captureout:
                    out += line.decode('UTF-8', errors='replace').strip() + '\n'
            return out

        @asyncio.coroutine
        def _execute(cmd):
            # Create subprocess to execute command, and wait until it's created
            proc = yield from asyncio.create_subprocess_shell(cmd,
                                                              stdout=asyncio.subprocess.PIPE,
                                                              stderr=asyncio.subprocess.PIPE,
                                                              close_fds=True,
                                                              executable=executable)

            out = yield from _read_stream(showout, proc.stdout)
            err = yield from _read_stream(outputStderr, proc.stderr)

            try:
                yield from asyncio.wait_for(proc.wait(), timeout)
            except asyncio.TimeoutError:
                if not out and err:
                    return 124, out, err
                return 0, out, err
            else:
                return proc.returncode, out, err

        if sys.platform != 'cygwin':
            # Get get and run coroutines using asyncio
            try:
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                loop = asyncio.get_event_loop()
            except Exception:
                loop = uvloop.new_event_loop()
                asyncio.set_event_loop(loop)
            rc, out, err = loop.run_until_complete(_execute(command))
            loop.close()
        else:
            loop = asyncio.get_event_loop()
            rc, out, err = loop.run_until_complete(_execute(command))
            loop.stop()
            loop.run_forever()

        if rc > 0 and die:
            if err:
                raise RuntimeError("Could not execute cmd:\n'%s'\nerr:\n%s" % (command, err))
            else:
                raise RuntimeError("Could not execute cmd:\n'%s'\nout:\n%s" % (command, out))

        return rc, out, err

    def executeInteractive(self, command, die=True):
        exitcode = os.system(command)
        if exitcode != 0 and die:
            raise RuntimeError("Could not execute %s" % command)
        return exitcode

    def downloadExpandTarGz(self, url, destdir, deleteDestFirst=True, deleteSourceAfter=True):
        print((self.getBaseName(url)))
        tmppath = self.getTmpPath(self.getBaseName(url))
        self.download(url, tmppath)
        self.expandTarGz(tmppath, destdir)

    def expandTarGz(self, path, destdir, deleteDestFirst=True, deleteSourceAfter=False):
        import gzip

        self.lastdir = os.getcwd()
        os.chdir(self.TMPDIR)
        basename = os.path.basename(path)
        if basename.find(".tar.gz") == -1:
            raise RuntimeError("Can only expand a tar gz file now %s" % path)
        tarfilename = ".".join(basename.split(".gz")[:-1])
        self.delete(tarfilename)

        if deleteDestFirst:
            self.delete(destdir)

        if self.TYPE == "WIN":
            cmd = "gzip -d %s" % path
            os.system(cmd)
        else:
            handle = gzip.open(path)
            with open(tarfilename, 'wb') as out:
                for line in handle:
                    out.write(line)
            out.close()
            handle.close()

        t = tarfile.open(tarfilename, 'r')
        t.extractall(destdir)
        t.close()

        self.delete(tarfilename)

        if deleteSourceAfter:
            self.delete(path)

        os.chdir(self.lastdir)
        self.lastdir = ""

    def getTmpPath(self, filename):
        return "%s/jumpscaleinstall/%s" % (self.TMPDIR, filename)

    def downloadJumpScaleCore(self, dest):
        # csid=getLastChangeSetBitbucket()
        self.download("https://bitbucket.org/jumpscale/jumpscale-core/get/default.tar.gz",
                      "%s/pl6core.tgz" % self.TMPDIR)
        self.expand("%s/pl6core.tgz" % self.TMPDIR, dest)

    def getPythonSiteConfigPath(self):
        minl = 1000000
        result = ""
        for item in sys.path:
            if len(item) < minl and item.find("python") != -1:
                result = item
                minl = len(item)
        return result

    def getTimeEpoch(self):
        '''
        Get epoch timestamp (number of seconds passed since January 1, 1970)
        '''
        return int(time.time())

    def rewriteGitRepoUrl(self, url="", login=None, passwd=None, ssh="auto"):
        """
        Rewrite the url of a git repo with login and passwd if specified

        Args:
            url (str): the HTTP URL of the Git repository. ex: 'https://github.com/odoo/odoo'
            login (str): authentication login name
            passwd (str): authentication login password
            ssh = if True will build ssh url, if "auto" will check if there is ssh-agent available & keys are loaded, if yes will use ssh

        Returns:
            (repository_host, repository_type, repository_account, repository_name, repository_url)
        """

        if ssh == "auto":
            ssh = self.checkSSHAgentAvailable()

        url_pattern_ssh = re.compile('^(git@)(.*?):(.*?)/(.*?)/?$')
        sshmatch = url_pattern_ssh.match(url)
        url_pattern_http = re.compile('^(https?://)(.*?)/(.*?)/(.*?)/?$')
        httpmatch = url_pattern_http.match(url)
        if not sshmatch:
            match = httpmatch
        else:
            match = sshmatch

        if not match:
            raise RuntimeError(
                "Url is invalid. Must be in the form of 'http(s)://hostname/account/repo' or 'git@hostname:account/repo'")

        protocol, repository_host, repository_account, repository_name = match.groups()
        if protocol.startswith("git") and ssh is False:
            protocol = "https://"

        if not repository_name.endswith('.git'):
            repository_name += '.git'

        if login == 'ssh' or ssh == True:
            repository_url = 'git@%(host)s:%(account)s/%(name)s' % {
                'host': repository_host,
                'account': repository_account,
                'name': repository_name,
            }
            protocol = "ssh"

        elif login and login != 'guest':
            repository_url = '%(protocol)s%(login)s:%(password)s@%(host)s/%(account)s/%(repo)s' % {
                'protocol': protocol,
                'login': login,
                'password': passwd,
                'host': repository_host,
                'account': repository_account,
                'repo': repository_name,
            }

        else:
            repository_url = '%(protocol)s%(host)s/%(account)s/%(repo)s' % {
                'protocol': protocol,
                'host': repository_host,
                'account': repository_account,
                'repo': repository_name,
            }
        if repository_name.endswith(".git"):
            repository_name = repository_name[:-4]

        return protocol, repository_host, repository_account, repository_name, repository_url

    def parseGitConfig(self, repopath):
        """
        @param repopath is root path of git repo
        @return (giturl,account,reponame,branch,login,passwd)
        login will be ssh if ssh is used
        login & passwd is only for https
        """
        path = self.joinPaths(dest, ".git", "config")
        if not self.exists(path=path):
            raise RuntimeError("cannot find %s" % path)
        config = self.fileGetContents(path)
        state = "start"
        for line in config.split("\n"):
            line2 = line.lower().strip()
            if state == "remote":
                if line.startswith("url"):
                    url = line.split("=", 1)[1]
                    url = url.strip().strip("\"").strip()
            if line2.find("[remote") != -1:
                state = "remote"
            if line2.find("[branch"):
                branch = line.split(" \"")[1].strip("]\" ").strip("]\" ").strip("]\" ")

    def whoami(self):
        if self._whoami is not None:
            return self._whoami
        rc, result, err = self.execute("whoami", die=False, showout=False, outputStderr=False)
        if rc > 0:
            # could not start ssh-agent
            raise RuntimeError("Could not call whoami,\nstdout:%s\nstderr:%s\n" % (result, err))
        else:
            self._whoami = result.strip()
        return self._whoami

    def _addSSHAgentToBashProfile(self, path=None):

        bashprofile_path = os.path.expanduser("~/.bash_profile")
        if not self.exists(bashprofile_path):
            self.execute('touch %s' % bashprofile_path)

        content = self.readFile(bashprofile_path)
        out = ""
        for line in content.split("\n"):
            if line.find("#JSSSHAGENT") != -1:
                continue
            if line.find("SSH_AUTH_SOCK") != -1:
                continue

            out += "%s\n" % line

        if "SSH_AUTH_SOCK" in os.environ:
            print("NO NEED TO ADD SSH_AUTH_SOCK to env")
            self.writeFile(bashprofile_path, out)
            return

        # out += "\njs 'j.do._.loadSSHAgent()' #JSSSHAGENT\n"
        out += "export SSH_AUTH_SOCK=%s" % self._getSSHSocketpath()
        out = out.replace("\n\n\n", "\n\n")
        out = out.replace("\n\n\n", "\n\n")
        self.writeFile(bashprofile_path, out)

    def _initSSH_ENV(self, force=False):
        if force or "SSH_AUTH_SOCK" not in os.environ:
            os.putenv("SSH_AUTH_SOCK", self._getSSHSocketpath())
            os.environ["SSH_AUTH_SOCK"] = self._getSSHSocketpath()

    def _getSSHSocketpath(self):

        if "SSH_AUTH_SOCK" in os.environ:
            return(os.environ["SSH_AUTH_SOCK"])

        socketpath = "%s/sshagent_socket" % os.environ.get("HOME", '/root')
        os.environ['SSH_AUTH_SOCK'] = socketpath
        return socketpath

    def askItemsFromList(self, items, msg=""):
        if len(items) == 0:
            return []
        if msg != "":
            print(msg)
        nr = 0
        for item in items:
            nr += 1
            print(" - %s: %s" % (nr, item))
        print("select item(s) from list (nr or comma separated list of nr, * is all)")
        item = input()
        if item.strip() == "*":
            return items
        elif item.find(",") != -1:
            res = []
            itemsselected = [item.strip() for item in item.split(",") if item.strip() != ""]
            for item in itemsselected:
                item = int(item) - 1
                res.append(items[item])
            return res
        else:
            item = int(item) - 1
            return [items[item]]

    def loadSSHKeys(self, path=None, duration=3600 * 24, die=False):
        """
        will see if ssh-agent has been started
        will check keys in home dir
        will ask which keys to load
        will adjust .profile file to make sure that env param is set to allow ssh-agent to find the keys
        """
        # print "loadsshkeys"
        # TODO *1 move ssh functionality all of it to right sal or tool in
        # jumpscale, make sure wherever we use it we adjust

        self._addSSHAgentToBashProfile()

        if path is None:
            path = os.path.expanduser("~/.ssh")
        self.createDir(path)

        if "SSH_AUTH_SOCK" not in os.environ:
            self._initSSH_ENV(True)

        self._loadSSHAgent()

        keysloaded = [self.getBaseName(item) for item in self.listSSHKeyFromAgent()]

        if self.isDir(path):
            keysinfs = [self.getBaseName(item).replace(".pub", "") for item in self.listFilesInDir(
                path, filter="*.pub") if self.exists(item.replace(".pub", ""))]
            keysinfs = [item for item in keysinfs if item not in keysloaded]

            res = self.askItemsFromList(
                keysinfs, "select ssh keys to load, use comma separated list e.g. 1,4,3 and press enter.")
        else:
            res = [self.getBaseName(path).replace(".pub", "")]
            path = self.getParent(path)

        for item in res:
            pathkey = "%s/%s" % (path, item)
            # timeout after 24 h
            print("load sshkey: %s" % pathkey)
            cmd = "ssh-add -t %s %s " % (duration, pathkey)
            self.executeInteractive(cmd)

    def getSSHKeyPathFromAgent(self, keyname, die=True):
        try:
            # TODO: why do we use subprocess here and not self.execute?
            out = subprocess.check_output(["ssh-add", "-L"])
        except:
            return None

        for line in out.splitlines():
            delim = ("/%s" % keyname).encode()

            if line.endswith(delim):
                line = line.strip()
                keypath = line.split(" ".encode())[-1]
                content = line.split(" ".encode())[-2]
                if not self.exists(path=keypath):
                    if self.exists("keys/%s" % keyname):
                        keypath = "keys/%s" % keyname
                    else:
                        raise RuntimeError("could not find keypath:%s" % keypath)
                return keypath.decode()
        if die:
            raise RuntimeError("Did not find key with name:%s, check its loaded in ssh-agent with ssh-add -l" % keyname)
        return None

    def getSSHKeyFromAgentPub(self, keyname, die=True):
        try:
            # TODO: why do we use subprocess here and not self.execute?
            out = subprocess.check_output(["ssh-add", "-L"])
        except:
            return None

        for line in out.splitlines():
            delim = (".ssh/%s" % keyname).encode()
            if line.endswith(delim):
                content = line.strip()
                content = content.decode()
                return content
        if die:
            raise RuntimeError("Did not find key with name:%s, check its loaded in ssh-agent with ssh-add -l" % keyname)
        return None

    def listSSHKeyFromAgent(self, keyIncluded=False):
        """
        returns list of paths
        """
        if "SSH_AUTH_SOCK" not in os.environ:
            self._initSSH_ENV(True)
        self._loadSSHAgent()
        cmd = "ssh-add -L"
        rc, out, err = self.execute(cmd, False, False, die=False)
        if rc:
            if rc == 1 and out.find("The agent has no identities") != -1:
                return []
            raise RuntimeError("error during listing of keys :%s" % err)
        keys = [line.split() for line in out.splitlines() if len(line.split()) == 3]
        if keyIncluded:
            return list(map(lambda key: key[2:0:-1], keys))
        else:
            return list(map(lambda key: key[2], keys))

    def ensure_keyname(self, keyname="", username="root"):
        if not self.exists(keyname):
            rootpath = "/root/.ssh/" if username == "root" else "/home/%s/.ssh/"
            fullpath = self.joinPaths(rootpath, keyname)
            if self.exists(fullpath):
                return fullpath
        return keyname

    def authorize_user(self, sftp_client, ip_address, keyname, username):
        basename = self.getBaseName(keyname)
        tmpfile = "/home/%s/.ssh/%s" % (username, basename)
        print("push key to /home/%s/.ssh/%s" % (username, basename))
        sftp_client.put(keyname, tmpfile)

        # cannot upload directly to root dir
        auth_key_path = "/home/%s/.ssh/authorized_keys" % username
        cmd = "ssh %s@%s 'cat %s | sudo tee -a %s '" % username, ip_address, tmpfile, auth_key_path
        print("do the following on the console\nsudo -s\ncat %s >> %s" % (tmpfile, auth_key_path))
        print(cmd)
        self.executeInteractive(cmd)

    def authorize_root(self, sftp_client, ip_address, keyname):
        tmppath = "%s/authorized_keys" % self.TMPDIR
        auth_key_path = "/root/.ssh/authorized_keys"
        self.delete(tmppath)
        try:
            sftp_client.get(auth_key_path, tmppath)
        except Exception as e:
            if str(e).find("No such file") != -1:
                try:
                    auth_key_path += "2"
                    sftp_client.get(auth_key_path, tmppath)
                except Exception as e:
                    if str(e).find("No such file") != -1:
                        self.writeFile(tmppath, "")
                    else:
                        raise RuntimeError("Could not get authorized key,%s" % e)

            C = self.readFile(tmppath)
            Cnew = self.readFile(keyname)
            key = Cnew.split(" ")[1]
            if C.find(key) == -1:
                C2 = "%s\n%s\n" % (C.strip(), Cnew)
                C2 = C2.strip() + "\n"
                self.writeFile(tmppath, C2)
                print("sshauthorized adjusted")
                sftp_client.put(tmppath, auth_key_path)
            else:
                print("ssh key was already authorized")

    def authorizeSSHKey(self, remoteipaddr, keyname, login="root", passwd=None, sshport=22, removeothers=False):
        """
        this required ssh-agent to be loaded !!!
        the keyname is the name of the key as loaded in ssh-agent

        if remoteothers==True: then other keys will be removed
        """
        keyname = self.ensure_keyname(keyname=keyname, username=login)
        import paramiko
        paramiko.util.log_to_file("/tmp/paramiko.log")
        ssh = paramiko.SSHClient()

        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("ssh connect:%s %s" % (remoteipaddr, login))

        if not self.listSSHKeyFromAgent(self.getBaseName(keyname)):
            self.loadSSHKeys(self.getParent(keyname))
        ssh.connect(remoteipaddr, username=login, password=passwd, allow_agent=True, look_for_keys=False)
        print("ok")

        ftp = ssh.open_sftp()

        if login != "root":
            self.authorize_user(sftp_client=ftp, ip_address=remoteipaddr, keyname=keyname, username=login)
        else:
            self.authorize_root(sftp_client=ftp, ip_address=remoteipaddr, keyname=keyname)

    def _loadSSHAgent(self, path=None, createkeys=False, killfirst=False):
        """
        check if ssh-agent is available & there is key loaded

        @param path: is path to private ssh key

        the primary key is 'id_rsa' and will be used as default e.g. if authorizing another node then this key will be used

        """
        with FileLock('/tmp/ssh-agent'):
            # check if more than 1 agent
            socketpath = self._getSSHSocketpath()
            res = [item for item in self.execute("ps aux|grep ssh-agent", False, False)
                   [1].split("\n") if item.find("grep ssh-agent") == -1]
            res = [item for item in res if item.strip() != ""]
            res = [item for item in res if item[-2:] != "-l"]

            if len(res) > 1:
                print("more than 1 ssh-agent, will kill all")
                killfirst = True
            if len(res) == 0 and self.exists(socketpath):
                self.delete(socketpath)

            if killfirst:
                cmd = "killall ssh-agent"
                # print(cmd)
                self.execute(cmd, showout=False, outputStderr=False, die=False)
                # remove previous socketpath
                self.delete(socketpath)
                self.delete(self.joinPaths(self.TMPDIR, "ssh-agent-pid"))

            if not self.exists(socketpath):
                self.createDir(self.getParent(socketpath))
                # ssh-agent not loaded
                print("load ssh agent")
                rc, result, err = self.execute("ssh-agent -a %s" % socketpath, die=False, showout=False, outputStderr=False)

                if rc > 0:
                    # could not start ssh-agent
                    raise RuntimeError(
                        "Could not start ssh-agent, something went wrong,\nstdout:%s\nstderr:%s\n" % (result, err))
                else:
                    # get pid from result of ssh-agent being started
                    if not self.exists(socketpath):
                        raise RuntimeError(
                            "Serious bug, ssh-agent not started while there was no error, should never get here")
                    piditems = [item for item in result.split("\n") if item.find("pid") != -1]
                    # print(piditems)
                    if len(piditems) < 1:
                        print("results was:")
                        print(result)
                        print("END")
                        raise RuntimeError("Cannot find items in ssh-add -l")
                    self._initSSH_ENV(True)
                    pid = int(piditems[-1].split(" ")[-1].strip("; "))
                    self.writeFile(self.joinPaths(self.TMPDIR, "ssh-agent-pid"), str(pid))
                    self._addSSHAgentToBashProfile()

            # ssh agent should be loaded because ssh-agent socket has been found
            if os.environ.get("SSH_AUTH_SOCK") != socketpath:
                self._initSSH_ENV(True)
            rc, result, err = self.execute("ssh-add -l", die=False, showout=False, outputStderr=False)
            if rc == 2:
                # no ssh-agent found
                print(result)
                raise RuntimeError("Could not connect to ssh-agent, this is bug, ssh-agent should be loaded by now")
            elif rc == 1:
                # no keys but agent loaded
                result = ""
            elif rc > 0:
                raise RuntimeError(
                    "Could not start ssh-agent, something went wrong,\nstdout:%s\nstderr:%s\n" % (result, err))

    def checkSSHAgentAvailable(self):
        if not self.exists(self._getSSHSocketpath()):
            return False
        if "SSH_AUTH_SOCK" not in os.environ:
            self._initSSH_ENV(True)
        rc, out, err = self.execute("ssh-add -l", showout=False, outputStderr=False, die=False)
        if 'The agent has no identities.' in out:
            return True
        if rc != 0:
            return False
        else:
            return True

    def getGitRepoArgs(self, url="", dest=None, login=None, passwd=None, reset=False,
                       branch=None, ssh="auto", codeDir=None, executor=None):
        """
        Extracts and returns data useful in cloning a Git repository.

        Args:
            url (str): the HTTP/GIT URL of the Git repository to clone from. eg: 'https://github.com/odoo/odoo.git'
            dest (str): the local filesystem path to clone to
            login (str): authentication login name (only for http)
            passwd (str): authentication login password (only for http)
            reset (boolean): if True, any cached clone of the Git repository will be removed
            branch (str): branch to be used
            ssh if auto will check if ssh-agent loaded, if True will be forced to use ssh for git

        # Process for finding authentication credentials (NOT IMPLEMENTED YET)

        - first check there is an ssh-agent and there is a key attached to it, if yes then no login & passwd will be used & method will always be git
        - if not ssh-agent found
            - then we will check if url is github & ENV argument GITHUBUSER & GITHUBPASSWD is set
                - if env arguments set, we will use those & ignore login/passwd arguments
            - we will check if login/passwd specified in URL, if yes willl use those (so they get priority on login/passwd arguments)
            - we will see if login/passwd specified as arguments, if yes will use those
        - if we don't know login or passwd yet then
            - login/passwd will be fetched from local git repo directory (if it exists and reset==False)
        - if at this point still no login/passwd then we will try to build url with anonymous


        # Process for defining branch

        - if branch arg: None
            - check if git directory exists if yes take that branch
            - default to 'master'
        - if it exists, use the branch arg

        Returns:
            (repository_host, repository_type, repository_account, repository_name,branch, login, passwd)

            - repository_type http or git

        Remark:
            url can be empty, then the git params will be fetched out of the git configuration at that path
        """

        if url == "":
            if dest is None:
                raise RuntimeError("dest cannot be None (url is also '')")
            if not self.exists(dest):
                raise RuntimeError(
                    "Could not find git repo path:%s, url was not specified so git destination needs to be specified." % (dest))

        if login is None and url.find("github.com/") != -1:
            # can see if there if login & passwd in OS env
            # if yes fill it in
            if "GITHUBUSER" in os.environ:
                login = os.environ["GITHUBUSER"]
            if "GITHUBPASSWD" in os.environ:
                passwd = os.environ["GITHUBPASSWD"]

        protocol, repository_host, repository_account, repository_name, repository_url = self.rewriteGitRepoUrl(
            url=url, login=login, passwd=passwd, ssh=ssh)

        repository_type = repository_host.split('.')[0] if '.' in repository_host else repository_host

        if not dest:
            if codeDir is None:
                if not executor:
                    codeDir = self.CODEDIR
                else:
                    codeDir = executor.cuisine.core.dir_paths['codeDir']
            dest = '%(codedir)s/%(type)s/%(account)s/%(repo_name)s' % {
                'codedir': codeDir,
                'type': repository_type.lower(),
                'account': repository_account.lower(),
                'repo_name': repository_name,
            }

        if reset:
            self.delete(dest)

        # self.createDir(dest)

        return repository_host, repository_type, repository_account, repository_name, dest, repository_url

    def pullGitRepo(self, url="", dest=None, login=None, passwd=None, depth=None, ignorelocalchanges=False,
                    reset=False, branch=None, revision=None, ssh="auto", executor=None, codeDir=None):
        """
        will clone or update repo
        if dest is None then clone underneath: /opt/code/$type/$account/$repo
        will ignore changes !!!!!!!!!!!

        @param ssh ==True means will checkout ssh
        @param ssh =="auto" means will checkout ssh first if that does not work will go to http
        """
        if ssh == "auto":
            try:
                return self.pullGitRepo(url, dest, login, passwd, depth, ignorelocalchanges,
                                        reset, branch, revision, True, executor)
            except Exception as e:
                try:
                    return self.pullGitRepo(url, dest, login, passwd, depth, ignorelocalchanges,
                                        reset, branch, revision, False, executor)
                except Exception as e:
                    raise RuntimeError("Could not checkout, needs to be with ssh or without.")

        base, provider, account, repo, dest, url = self.getGitRepoArgs(
            url, dest, login, passwd, reset=reset, ssh=ssh, codeDir=codeDir, executor=executor)

        print("pull:%s ->%s" % (url, dest))

        existsDir = self.exists(dest) if not executor else executor.exists(dest)

        checkdir = "%s/.git" % (dest)
        existsGit = self.exists(checkdir) if not executor else executor.exists(checkdir)

        if existsGit:
            # if we don't specify the branch, try to find the currently checkedout branch
            cmd = 'cd %s; git rev-parse --abbrev-ref HEAD' % dest
            rc, out, err = self.execute(cmd, die=False, showout=False, executor=executor)
            if rc == 0:
                branchFound = out.strip()
            else:  # if we can't retreive current branch, use master as default
                branchFound = 'master'
                # raise RuntimeError("Cannot retrieve branch:\n%s\n" % cmd)

            if branch != None and branch != branchFound and ignorelocalchanges == False:
                raise RuntimeError(
                    "Cannot pull repo, branch on filesystem is not same as branch asked for.\nBranch asked for:%s\nBranch found:%s\nTo choose other branch do e.g:\nexport JSBRANCH='%s'\n" % (branch, branchFound, branchFound))

            if branch == None:
                branch = branchFound

            if ignorelocalchanges:
                print(("git pull, ignore changes %s -> %s" % (url, dest)))
                cmd = "cd %s;git fetch" % dest
                if depth is not None:
                    cmd += " --depth %s" % depth
                    self.execute(cmd, executor=executor)
                if branch is not None:
                    print("reset branch to:%s" % branch)
                    self.execute("cd %s;git fetch; git reset --hard origin/%s" %
                                 (dest, branch), timeout=600, executor=executor)
            else:
                # pull
                print(("git pull %s -> %s" % (url, dest)))
                if url.find("http") != -1:
                    cmd = "cd %s;git -c http.sslVerify=false pull origin %s" % (dest, branch)
                else:
                    cmd = "cd %s;git pull origin %s" % (dest, branch)
                print(cmd)
                self.execute(cmd, timeout=600, executor=executor)
        else:
            print(("git clone %s -> %s" % (url, dest)))
            extra = ""
            if depth is not None:
                extra = "--depth=%s" % depth
            if url.find("http") != -1:
                if branch is not None:
                    cmd = "cd %s;git -c http.sslVerify=false clone %s -b %s %s %s" % (
                        self.getParent(dest), extra, branch, url, dest)
                else:
                    cmd = "cd %s;git -c http.sslVerify=false clone %s  %s %s" % (self.getParent(dest), extra, url, dest)
            else:
                if branch is not None:
                    cmd = "cd %s;git clone %s -b %s %s %s" % (
                        self.getParent(dest), extra, branch, url, dest)
                else:
                    cmd = "cd %s;git clone %s  %s %s" % (self.getParent(dest), extra, url, dest)

            print(cmd)

            self.execute(cmd, timeout=600, executor=executor)

        if revision is not None:
            cmd = "cd %s;git checkout %s" % (dest, revision)
            print(cmd)
            self.execute(cmd, timeout=600, executor=executor)

        return dest

    def checkInstalled(self, cmdname):
        """
        @param cmdname is cmd to check e.g. curl
        """
        _, res, _ = self.execute("which %s" % cmdname, False)
        if res[0] == 0:
            return True
        else:
            return False

    def getGitReposListLocal(self, provider="", account="", name="", errorIfNone=True):
        repos = {}
        for top in self.listDirsInDir(self.CODEDIR, recursive=False, dirNameOnly=True, findDirectorySymlinks=True):
            if provider != "" and provider != top:
                continue
            for accountfound in self.listDirsInDir("%s/%s" % (self.CODEDIR, top),
                                                   recursive=False, dirNameOnly=True, findDirectorySymlinks=True):
                if account != "" and account != accountfound:
                    continue
                accountfounddir = "/%s/%s/%s" % (self.CODEDIR, top, accountfound)
                for reponame in self.listDirsInDir(
                        "%s/%s/%s" % (self.CODEDIR, top, accountfound), recursive=False, dirNameOnly=True, findDirectorySymlinks=True):
                    if name != "" and name != reponame:
                        continue
                    repodir = "%s/%s/%s/%s" % (self.CODEDIR, top, accountfound, reponame)
                    if self.exists(path="%s/.git" % repodir):
                        repos[reponame] = repodir
        return repos

    def pushGitRepos(self, message, name="", update=True, provider="", account=""):
        """
        if name specified then will look under code dir if repo with path can be found
        if not or more than 1 there will be error
        @param provider e.g. git, github
        """
        # TODO: make sure we use gitlab or github account if properly filled in
        repos = self.getGitReposListLocal(provider, account, name)
        for name, path in list(repos.items()):
            print(("push git repo:%s" % path))
            cmd = "cd %s;git add . -A" % (path)
            self.executeInteractive(cmd)
            cmd = "cd %s;git commit -m \"%s\"" % (path, message)
            self.executeInteractive(cmd)
            branch = self.getGitBranch(path)
            if update:
                cmd = "cd %s;git pull origin %s" % (path, branch)
                self.executeInteractive(cmd)
            cmd = "cd %s;git push origin %s" % (path, branch)
            self.executeInteractive(cmd)

    def updateGitRepos(self, provider="", account="", name="", message=""):
        repos = self.getGitReposListLocal(provider, account, name)
        for name, path in list(repos.items()):
            print(("push git repo:%s" % path))
            branch = self.getGitBranch(path)
            cmd = "cd %s;git add . -A" % (path)
            self.executeInteractive(cmd)
            cmd = "cd %s;git commit -m \"%s\"" % (path, message)
            self.executeInteractive(cmd)
            cmd = "cd %s;git pull origin %s" % (path, branch)
            self.executeInteractive(cmd)

    def getGitBranch(self, path):

        # if we don't specify the branch, try to find the currently checkedout branch
        cmd = 'cd %s;git rev-parse --abbrev-ref HEAD' % path
        try:
            rc, out, err = self.execute(cmd, showout=False, outputStderr=False)
            if rc == 0:
                branch = out.strip()
            else:  # if we can't retreive current branch, use master as default
                branch = 'master'
        except:
            branch = 'master'

        return branch

        # cmd="cd %s;git branch"%path
        # rc,out,err=self.execute(cmd)
        # branch=""
        # for line in out.split("\n"):
        #     if line.startswith("*"):
        #         branch=line.strip().strip("*").strip(" ").strip()
        # if branch=="":
        #     raise RuntimeError("could not find branch")
        # return branch

    def changeLoginPasswdGitRepos(self, provider="", account="", name="",
                                  login="", passwd="", ssh=True, pushmessage=""):
        """
        walk over all git repo's found in account & change login/passwd
        """
        if ssh is False:
            for reponame, repopath in list(self.getGitReposListLocal(provider, account, name).items()):
                import re
                configpath = "%s/.git/config" % repopath
                text = self.readFile(configpath)
                text2 = text
                for item in re.findall(re.compile(r'//.*@%s' % provider), text):
                    newitem = "//%s:%s@%s" % (login, passwd, provider)
                    text2 = text.replace(item, newitem)
                if text2.strip() != text:
                    self.writeFile(configpath, text2)
        else:
            for reponame, repopath in list(self.getGitReposListLocal(provider, account, name).items()):
                configpath = "%s/.git/config" % repopath
                text = self.readFile(configpath)
                text2 = ""
                change = False
                for line in text.split("\n"):
                    if line.replace(" ", "").find("url=") != -1:
                        # print line
                        if line.find("@git") == -1:
                            # print 'REPLACE'
                            provider2 = line.split("//", 1)[1].split("/", 1)[0].strip()
                            account2 = line.split("//", 1)[1].split("/", 2)[1]
                            name2 = line.split("//", 1)[1].split("/", 2)[2].replace(".git", "")
                            line = "\turl = git@%s:%s/%s.git" % (provider2, account2, name2)
                            change = True
                        # print line
                    text2 += "%s\n" % line

                if change:
                    # print text
                    # print "===="
                    # print text2
                    # print "++++"
                    print(("changed login/passwd/git on %s" % configpath))
                    self.writeFile(configpath, text2)

        if pushmessage != "":
            self.pushGitRepos(pushmessage, name=name, update=True, provider=provider, account=account)

    def _initExtra(self):
        """
        will get extra install tools lib
        """
        if not self._extratools:
            if not self.exists("ExtraTools.py"):
                url = "https://raw.githubusercontent.com/Jumpscale/jumpscale_core/master/install/ExtraTools.py"
                self.download(url, "/tmp/ExtraTools.py")
                if "/tmp" not in sys.path:
                    sys.path.append("/tmp")
            from ExtraTools import extra
            self.extra = extra
        self._extratools = True

    def getWalker(self):
        self._initExtra()
        return self.extra.getWalker(self)

    def loadScript(self, path):
        print(("load jumpscript: %s" % path))
        source = self.readFile(path)
        out, tags = self._preprocess(source)

        def md5_string(s):
            import hashlib
            s = s.encode('utf-8')
            impl = hashlib.new('md5', s)
            return impl.hexdigest()
        md5sum = md5_string(out)
        modulename = 'JumpScale.jumpscript_%s' % md5sum

        codepath = self.joinPaths(self.getTmpPath(), "jumpscripts", "%s.py" % md5sum)
        self.writeFile(filename=codepath, contents=out)

        linecache.checkcache(codepath)
        self.module = imp.load_source(modulename, codepath)

        self.author = getattr(self.module, 'author', "unknown")
        self.organization = getattr(self.module, 'organization', "unknown")
        self.version = getattr(self.module, 'version', 0)
        self.modtime = getattr(self.module, 'modtime', 0)
        self.descr = getattr(self.module, 'descr', "")

        # identifies the actions & tags linked to it
        self.tags = tags

        for name, val in list(tags.items()):
            self.actions[name] = eval("self.module.%s" % name)

    def installPackage(self, path):
        pass


do = InstallTools()
