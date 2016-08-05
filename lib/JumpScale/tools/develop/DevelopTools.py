from JumpScale import j
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import time, os, sys


class MyFSEventHandler(FileSystemEventHandler):

    def handler(self, event,action="copy"):
        changedfile = event.src_path
        if event.is_directory:
            if changedfile.find("/.git") != -1:
                return
            elif changedfile.find("/__pycache__/") != -1:
                return

            if event.event_type=="modified":
                return
            
            j.tools.develop.syncCode()
        else:
            error=False
            for node in j.tools.develop.nodes:
                if error==False:
                    if node.cuisine.core.isJS8Sandbox:
                        sep = "jumpscale_core8/lib/JumpScale/"
                        sep_cmds = "jumpscale_core8/shellcmds/"
                        if changedfile.find(sep) != -1:
                            dest0 = changedfile.split(sep)[1]
                            dest = "/opt/jumpscale8/lib/JumpScale/%s" % (dest0)
                        elif changedfile.find(sep_cmds) != -1:
                            dest0 = changedfile.split(sep_cmds)[1]
                            dest = "/opt/jumpscale8/bin/%s" % (dest0)
                        elif changedfile.find("/.git/") != -1:
                            return
                        elif changedfile.find("/__pycache__/") != -1:
                            return
                        elif j.sal.fs.getBaseName(changedfile) in ["InstallTools.py", "ExtraTools.py"]:
                            base = j.sal.fs.getBaseName(changedfile)
                            dest = "/opt/jumpscale8/lib/JumpScale/%s" % (base)
                        else:
                            destpart = changedfile.split("jumpscale/", 1)[-1]
                            dest = "/opt/code/%s" % destpart
                    else:
                        if changedfile.find("/.git/") != -1:
                            return
                        elif changedfile.find("/__pycache__/") != -1:
                            return
                        else:
                            destpart = changedfile.split("code/", 1)[-1]
                            dest = "/opt/code/%s" % destpart
                    e=""
                    if action=="copy":
                        print("copy: %s %s:%s" % (changedfile, node, dest))
                        try:
                            node.ftpclient.put(changedfile, dest)
                        except Exception as e:
                            error=True
                    elif action=="delete":
                        print("delete: %s %s:%s" % (changedfile, node, dest))
                        try: 
                            node.ftpclient.remove(dest)
                        except Exception as e:
                            if "No such file" in str(e):
                                return
                            else:
                                raise RuntimeError(e)
                    else:
                        raise j.exceptions.RuntimeError("unsupported action:%s"%action)

                    if error:
                        try:
                            print(e)
                        except:
                            pass
                        j.tools.develop.syncCode()
                        break



    def on_moved(self, event):
        j.tools.develop.syncCode()
        self.handler(event,action="delete")

    def on_created(self, event):
        self.handler(event)

    def on_deleted(self, event):
        self.handler(event,action="delete")

    def on_modified(self, event):
        self.handler(event)

class DebugSSHNode:

    def __init__(self, addr="localhost", sshport=22):
        self.addr = addr
        self.port = sshport
        self.connected=None

    def test(self):
        if self.connected==None:
            #lets test tcp on 22 if not then 9022 which are our defaults
            test=j.sal.nettools.tcpPortConnectionTest(self.addr,self.port,3)
            if test==False:
                print ("could not connect to %s:%s, will try port 9022"%(self.addr,self.port))
                if self.port==22:
                    test= j.sal.nettools.tcpPortConnectionTest(self.addr,9022,1)
                    if test:
                        self.port=9022
            if test==False:
                raise j.exceptions.RuntimeError("Cannot connect to %s:%s"%(self.addr,self.port))

            self._platformType = None
            self._sshclient = None
            self._ftpclient = None

            self.connected=True

    @property
    def ftpclient(self):
        self.test()
        if self._ftpclient == None:
            self._ftpclient = self.sshclient.getSFTP()
        return self._ftpclient

    @property
    def executor(self):
        self.test()
        return self.cuisine.executor

    @property
    def cuisine(self):
        self.test()
        if self.port == 0:
            return j.tools.cuisine.local
        else:
            return self.sshclient.cuisine

    @property
    def sshclient(self):
        self.test()
        if self._sshclient == None:
            if self.port != 0:
                self._sshclient = j.clients.ssh.get(self.addr, port=self.port)
            else:
                return None
        return self._sshclient

    # @property
    # def platformType(self):
    #     if self._platformType != None:
    #         j.application.break_into_jshell("platformtype")
    #     return self._platformType



    def __str__(self):
        return "debugnode:%s" % self.addr

    __repr__ = __str__


class DevelopToolsFactory:

    def __init__(self):
        self.__jslocation__ = "j.tools.develop"
        self._nodes = []
        # self.installer=Installer()

    def help(self):
        H = """
        example to use #@todo change python3... to js... (but not working on osx yet)
        js 'j.tools.develop.init("ovh4,ovh3:2222")'
        js 'j.tools.develop.jumpscale8(rw=True)' #will install overlay sandbox wich can be editted
        js 'j.tools.develop.jumpscale8develop()'
        js 'j.tools.develop.syncCode(ask=True,monitor=False,rsyncdelete=False,reset=False)'

        if you now go onto e.g. ovh4 you will see on /opt/... all changes reflected which you make locally

        example output:
        ```
        Make a selection please:
           1: /Users/despiegk/opt/code/github/jumpscale/ays_jumpscale8
           2: /Users/despiegk/opt/code/github/jumpscale/dockers
           3: /Users/despiegk/opt/code/github/jumpscale/docs8
           4: /Users/despiegk/opt/code/github/jumpscale/gig_it_ays
           5: /Users/despiegk/opt/code/github/jumpscale/jumpscale_core8
           6: /Users/despiegk/opt/code/github/jumpscale/play7
           7: /Users/despiegk/opt/code/github/jumpscale/play8

        Select Nr, use comma separation if more e.g. "1,4", * is all, 0 is None: 2,5

        rsync  -rlptgo --partial --exclude '*.egg-info*/' --exclude '*.dist-info*/' --exclude '*__pycache__*/' --exclude '*.git*/' --exclude '*.egg-info*' --exclude '*.pyc' --exclude '*.bak' --exclude '*__pycache__*'  -e 'ssh -o StrictHostKeyChecking=no -p 22' '/Users/despiegk/opt/code/github/jumpscale/dockers/' 'root@ovh4:/opt/code/dockers/'
        ... some more rsync commands

        monitor:/Users/despiegk/opt/code/github/jumpscale/dockers
        monitor:/Users/despiegk/opt/code/github/jumpscale/jumpscale_core8

        #if you change a file:

        copy: /Users/despiegk/opt/code/github/jumpscale/jumpscale_core8/lib/JumpScale/tools/debug/Debug.py debugnode:ovh4:/opt/jumpscale8/lib/JumpScale/tools/debug/Debug.py

        ```

        """
        print (H)

    def init(self, nodes=[]):
        """
        define which nodes to init,
        format = ["localhost", "ovh4", "anode:2222", "192.168.6.5:23"]
        this will be remembered in local redis for further usage

        format can also be a string e.g. ovh4,ovh3:2022

        """
        self._nodes = []
        if j.data.types.string.check(nodes):
            nodes2=[]
            if "," in nodes:
                nodes2=[]
                for it in nodes.split(","):
                    it=it.strip()
                    if it=="":
                        continue
                    if it not in nodes2:
                        nodes2.append(it)
            else:
                if nodes.strip()=="":
                    nodes2=[]
                else:
                    nodes2 = [nodes.strip()]            
            nodes=nodes2    

        if not j.data.types.list.check(nodes):
            raise j.exception.Input("nodes need to be list or string, got:%s"%nodes)

        if nodes==[]:
            j.core.db.set("debug.nodes", "")
        else:
        
            j.core.db.set("debug.nodes", ','.join(nodes))

    @property
    def nodes(self):
        if self._nodes == []:
            if j.core.db.get("debug.nodes") == None:
                self.init()
            nodes = j.core.db.get("debug.nodes").decode()
            if nodes=="":
                return []

            for item in nodes.split(","):
                if item.find(":") != -1 and len( item.split(":"))==2:
                    addr, sshport= item.split(":")
                elif item.find(":") != -1 and len( item.split(":"))==4:
                    addr, sshport, key_filename, passphrase = item.split(":")
                else:
                    addr = item.strip()
                    if addr != "localhost":
                        sshport = 22
                    else:
                        sshport = 0
                    key_filename = None
                addr = addr.strip()
                sshport = int(sshport)
                self._nodes.append(DebugSSHNode(addr, sshport))
        return self._nodes

    def jumpscale8sb(self, rw=False,synclocalcode=False,monitor=False,resetstate=False):
        """
        install jumpscale, will be done as sandbox over fuse layer for linux

        @input rw, if True will put overlay filesystem on top of /opt -> /opt which will allow you to manipulate/debug the install
        @input synclocalcode, sync the local github code to the node (jumpscale) (only when in rw mode)
        @input reset, remove old code (only used when rw mode)
        @input monitor detect local changes & sync (only used when rw mode)
        """

        for node in self.nodes:
            node.cuisine.installer.base()
            node.cuisine.installer.jumpscale8(rw=rw,reset=resetstate)

        if synclocalcode:
            self.syncCode()

        if monitor:
            self.monitor

    def jumpscale8develop(self, rw=False,resetstate=False):
        """
        install jumpscale, install in development mode

        @input rw, if True will put overlay filesystem on top of /opt -> /opt which will allow you to manipulate/debug the install
        @input synclocalcode, sync the local github code to the node (jumpscale) (only when in rw mode)
        @input reset, remove old code (only used when rw mode)
        @input monitor detect local changes & sync (only used when rw mode)
        """

        for node in self.nodes:
            node.cuisine.installer.base()
            node.cuisine.installerdevelop.jumpscale8()

        if synclocalcode:
            self.syncCode()

        if monitor:
            self.monitor

    def resetState(self):
        j.actions.setRunId("developtools")
        j.actions.reset()
        self.init()


    def syncCode(self, ask=False,monitor=False,rsyncdelete=True,reset=False):
        """
        sync all code to the remote destinations

        @param reset=True, means we remove the destination first
        @param ask=True means ask which repo's to sync (will get remembered in redis)

        """
        if ask or j.core.db.get("debug.codepaths") == None:
            path = j.dirs.codeDir + "/github/jumpscale"
            if j.sal.fs.exists(path):
                items = j.sal.fs.listDirsInDir(path)
            chosen = j.tools.console.askChoiceMultiple(items)
            j.core.db.set("debug.codepaths", ",".join(chosen))

        if reset:
            raise j.exceptions.RuntimeError("not implemented")

        codepaths = []
        for it in j.core.db.get("debug.codepaths").decode().split(","):
            it=it.strip()
            if it=="":
                continue
            if it not in codepaths:
                codepaths.append(it)
            
        for source in codepaths:
            destpart = source.split("jumpscale/", 1)[-1]
            for node in self.nodes:
                if node.port != 0:

                    if not node.cuisine.core.isJS8Sandbox:
                        #non sandboxed mode, need to sync to \
                        dest="root@%s:/opt/code/%s"%(node.addr, source.split("code/", 1)[1])
                    else:
                        dest = "root@%s:/opt/code/%s" % (node.addr, destpart)

                    if destpart == "jumpscale_core8" and node.cuisine.core.isJS8Sandbox:
                        dest = "root@%s:/opt/jumpscale8/lib/JumpScale/" % node.addr
                        source2 = source + "/lib/JumpScale/"

                        j.sal.fs.copyDirTree(source2, dest, ignoredir=['.egg-info', '.dist-info', '__pycache__', ".git"], rsync=True, ssh=True, sshport=node.port, recursive=True,rsyncdelete=rsyncdelete)

                        source2 = source + "/install/InstallTools.py"
                        dest = "root@%s:/opt/jumpscale8/lib/JumpScale/InstallTools.py" % node.addr
                        j.sal.fs.copyDirTree(source2, dest, ignoredir=['.egg-info', '.dist-info', '__pycache__', ".git"], rsync=True, ssh=True, sshport=node.port, recursive=False)

                        source2 = source + "/install/ExtraTools.py"
                        dest = "root@%s:/opt/jumpscale8/lib/JumpScale/ExtraTools.py" % node.addr
                        j.sal.fs.copyDirTree(source2, dest, ignoredir=['.egg-info', '.dist-info', '__pycache__', ".git"], rsync=True, ssh=True, sshport=node.port, recursive=False)

                    else:
                        node.cuisine.core.run("mkdir -p /opt/code/%s" % source.split("code/", 1)[1])
                        if node.cuisine.core.isJS8Sandbox:
                            rsyncdelete2=True
                        else:
                            rsyncdelete2=rsyncdelete
                        j.sal.fs.copyDirTree(source, dest, ignoredir=['.egg-info', '.dist-info', '__pycache__', ".git"], rsync=True, ssh=True, sshport=node.port, recursive=True,rsyncdelete=rsyncdelete2)
                else:
                    raise j.exceptions.RuntimeError("only ssh nodes supported")

        if monitor:
            self.monitorChanges(sync=False,reset=False)

    def monitorChanges(self,sync=True,reset=False):
        """
        look for changes in directories which are being pushed & if found push to remote nodes
        """
        event_handler = MyFSEventHandler()
        observer = Observer()
        if sync or j.core.db.get("debug.codepaths") == None:
            self.syncCode(monitor=False,rsyncdelete=False,reset=reset)
        codepaths = j.core.db.get("debug.codepaths").decode().split(",")
        for source in codepaths:
            print("monitor:%s" % source)
            observer.schedule(event_handler, source, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
