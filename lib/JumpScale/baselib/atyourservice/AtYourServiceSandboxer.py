from JumpScale import j

from mongoengine import *

from JumpScale.data.models.Models import ModelBase


class Debug(ModelBase, Document):
    guid = StringField(default='')
    host = StringField(default='')
    cache = StringField(default='')
    sandboxpaths = ListField(StringField())
    paths = ListField(StringField())
    cmd_pre = ListField(StringField())
    cmd_post = ListField(StringField())
    restart = ListField(StringField())

    storpath = StringField(default="/tmp/aysfs")
    namespace = StringField(default="dedupe")

    port = IntField(default=22)

    populate_host_cache = BooleanField(default=False)
    populate_grid_cache = BooleanField(default=False)
    populate_master_cache = BooleanField(default=False)

    # def clean(self):
    #     ModelBase.clean(self)


class AtYourServiceSandboxer:

    def __init__(self, name="main"):
        j.data.models.system.addModel(Debug)
        self.model = j.data.models.system.Debug.getset(Debug(guid=name))
        self._cl = None
        self._clcache = None

    @property
    def cuisine_host(self):
        if self._cl is None:
            self._cl = j.clients.ssh.get(self.model.host, self.model.port).cuisine
        return self._cl

    @property
    def cuisine_cache(self):
        if self._clcache is None:
            self._clcache = j.clients.ssh.get(self.model.cache, 22).cuisine
        return self._clcache

    @property
    def cuisine_master(self):
        if self._clcache is None:
            self._clcache = j.clients.ssh.get("stor.jumpscale.org", 22).cuisine
        return self._clcache

    def addSandboxSource(self, sourcepath, filter=None, dest="jumpscale8/bin"):
        """
        sourcepath can be directory or file
        filter can only be used when sourcepath is directory
        filter e.g. *.py or something*something or start*.*
        """
        path = "%s___%s___%s" % (sourcepath, filter, dest)
        if path not in self.model.sandboxpaths:
            self.model.sandboxpaths.append(path)
        self.model.save()

    def addPath(self, path):
        """
        path to upload to remote aysfs
        """
        if path not in self.model.paths:
            self.model.paths.append(path)
        self.model.save()

    def reset(self):
        j.sal.fs.remove(self.model.storpath)

    def setHost(self, host, port=22):
        self.model.host = host
        self.model.port = port
        self.model.save()

    def setCache(self, host):
        self.model.cache = host
        self.model.save()

    def setNamespace(self, namespace):
        self.model.namespace = namespace
        self.model.save()

    def addCmdPre(self, cmd):
        if cmd not in self.model.cmd_pre:
            self.model.cmd_pre.append(cmd)
        self.model.save()

    def addCmdPost(self, cmd):
        if cmd not in self.model.cmd_post:
            self.model.cmd_post.append(cmd)
        self.model.save()

    def addRestart(self, name):
        if name not in self.model.restart:
            self.model.restart.append(name)
        self.model.save()

    def enableHostCacheUpdate(self):
        self.model.populate_host_cache = True
        self.model.save()

    def enableGridCacheUpdate(self):
        self.model.populate_grid_cache = True
        self.model.save()

    def enableMasterCacheUpdate(self):
        self.model.populate_master_cache = True
        self.model.save()

    def resetCaches(self):
        self.cuisine_host.run("rm -rf /mnt/ays/cachelocal/dedupe;mkdir -p /mnt/ays/cachelocal/dedupe")
        self.cuisine_cache.run("rm -rf /mnt/ays/cache/dedupe/;mkdir -p /mnt/ays/cache/dedupe/")

    # def installAYSFS(self):
    #     """
    #     install AYSFS on host
    #     """
    #     if self.model.host!="":
    #         self.cuisine_host.run("mkdir -p /mnt/ays/cachelocal/dedupe;mkdir -p /etc/ays/local")
    #         self.cuisine_host.hostfile_set("ayscache",self.model.cache)  #put in hostfile
    #         self.cuisine_host.run("umount -fl /opt;echo")
    #         self.cuisine_host.run("pkill tmux;echo")
    #         cmd = "cd /usr/local/bin;rm -f aysfs;wget http://stor.jumpscale.org/ays/bin/aysfs"
    #         self.cuisine_host.run(cmd,checkok=True)
    #         cmd = "cd /usr/local/bin;rm -f js8;wget http://stor.jumpscale.org/ays/bin/js8"
    #         self.cuisine_host.run(cmd,checkok=True)
    #         self.cuisine_host.run("chmod 550 /usr/local/bin/aysfs;chmod 550 /usr/local/bin/js8",checkok=True)
    #         cmd= "aysfs -auto /opt"
    #         self.cuisine_host.tmux_execute(cmd,interactive=True)

    def _upload(self, desthost, destpath):
        if desthost == "":
            return
        cmd = "rsync  -rlptgo --partial --exclude '*.egg-info*/' --exclude '*.dist-info*/' --exclude '*.egg-info*' "
        cmd += "--exclude '*.pyc' --exclude '*.bak' --exclude '*__pycache__*'  -e 'ssh -o StrictHostKeyChecking=no -p 22' "
        cmd += "'/tmp/aysfs/files/' 'root@%s:%s'" % (desthost, destpath)
        print(cmd)
        j.sal.process.execute(cmd)

    def buildJumpscaleMetadata(self):
        from JumpScale import findModules
        findModules()

    def sandbox(self, python=True):
        """
        look for all files in self.paths and copy to the sandbox
        """
        print("START SANDBOX")
        if python:
            paths = []
            paths.append("/usr/lib/python3.5/")
            paths.append("/usr/local/lib/python3.5/dist-packages")
            paths.append("/usr/lib/python3/dist-packages")

            excludeFileRegex = ["/xml/", "-tk/", "/xml", "/lib2to3", "-34m-", ".egg-info"]
            excludeDirRegex = ["/JumpScale", "\.dist-info", "config-x86_64-linux-gnu", "pygtk"]

            dest = "%s/lib" % j.dirs.base

            for path in paths:
                j.tools.sandboxer.copyTo(path, dest, excludeFileRegex=excludeFileRegex, excludeDirRegex=excludeDirRegex)

            if not j.sal.fs.exists("%s/bin/python" % j.dirs.base):
                j.sal.fs.copyFile("/usr/bin/python3.5", "%s/bin/python" % j.dirs.base)

        # for item in self.model.paths:
        #     sourcepath,filter,dest=item.split("___")
        #     if j.sal.fs.isDir(sourcepath):
        #         if filter!=None:
        #             for item in j.sal.fs.listFilesInDir(sourcepath,filter=filter):
        #                 j.sal.fs.copyFile(item,dest)
        #         else:
        #             j.sal.fs.copyDirTree(sourcepath,dest)
        #     else:
        #         j.sal.fs.copyFile(sourcepath,dest)

        j.tools.sandboxer.sandboxLibs("%s/lib" % j.dirs.base, recursive=True)
        j.tools.sandboxer.sandboxLibs("%s/bin" % j.dirs.base, recursive=True)
        print("SANDBOXING DONE, ALL OK IF TILL HERE, A Segfault can happen because we have overwritten ourselves.")

    def buildUpload(self, sandbox=True):
        """
        """
        # self.reset()
        self.buildJumpscaleMetadata()

        if sandbox:
            self.sandbox()

        for path in self.model.paths:
            print("DEDUPE:%s" % path)
            j.tools.sandboxer.dedupe(path, storpath=self.model.storpath, name="0", reset=False, append=True)

        if self.model.host != "":
            try:
                # check if we can find aysfs, if not install
                self.cuisine_host.run("which aysfs")
            except:
                self.installAYSFS()

            # j.sal.fs.copyDirTree(self.model.storpath+"/files/", "root@%s:/mnt/ays/cachelocal/%s"%(self.model.host,self.model.namespace), \
            # keepsymlinks=False, deletefirst=False, overwriteFiles=False, rsync=True,
            # ssh=True, sshport=self.model.port, recursive=True)

        if self.model.populate_grid_cache:
            self._upload(self.model.cache, "/mnt/ays/cache/dedupe/")

        if self.model.populate_host_cache:
            pass
            # self._upload(self.model.host,"/mnt/ays/cachelocal/dedupe/")
            # #@todo ....
            # j.sal.fs.copyDirTree(self.model.storpath+"/md/0.flist", "root@stor.jumpscale.org:/mnt/Storage/openvcloud/ftp/ays/md/jumpscale.flist",overwriteFiles=True, rsync=True, ssh=True)

        if self.model.populate_master_cache:
            store_client = j.clients.storx.get("http://stor.jumpscale.org/storx")
            files_path = j.sal.fs.joinPaths(self.model.storpath, 'files')
            files = j.sal.fs.listFilesInDir(files_path, recursive=True)
            namespace = j.atyourservice.sandboxer.model['namespace']
            error_files = []
            for f in files:
                src_hash = j.data.hash.md5(f)
                print('uploading %s' % f)
                uploaded_hash = store_client.putFile(namespace, f)
                if src_hash != uploaded_hash:
                    error_files.append(f)
                    print("%s hash doesn't match\nsrc     :%32s\nuploaded:%32s" % (f, src_hash, uploaded_hash))

            if len(error_files) == 0:
                print("all uploaded ok")
            else:
                raise j.exceptions.RuntimeError('some files didnt upload properly. %s' % ("\n".join(error_files)))

            metadataPath = j.sal.fs.joinPaths(self.model.storpath, "md", "0.flist")
            j.sal.fs.copyDirTree(metadataPath, "root@stor.jumpscale.org:/mnt/Storage/openvcloud/ftp/ays/md/jumpscale.flist",
                                 overwriteFiles=True, rsync=True, ssh=True)

        # if self.model.host!="":
        #     j.sal.fs.copyDirTree(self.model.storpath+"/md/0.flist","root@%s:/etc/ays/local/"%(self.model.host),overwriteFiles=True, rsync=True, ssh=True, sshport=self.model.port)
        #     try:
        #         pid=self.cuisine_host.run("pgrep aysfs")
        #     except:
        #         self.installAYSFS()
        #         pid=self.cuisine_host.run("pgrep aysfs")

        #     self.cuisine_host.run("kill -s sigusr1 %s"%pid)
        # else:
            # self.cuisine_host.run("pkill aysfs;echo")
            # self.cuisine_host.run("umount -fl /opt;echo")
            # self.cuisine_host.file_unlink("/etc/ays/local/md/0.flist")

        # self.cuisine_master.run("chown -R ays:root /mnt/Storage/openvcloud/ftp/ays/master/dedupe/")

    def buildUpload_JS(self, sandbox=False, name="main"):

        j.sal.fs.createDir("/usr/local/lib/python3.5/site-packages")
        # j.sal.fs.symlink("%s/lib/JumpScale/"%j.dirs.base,"/usr/local/lib/python3.5/site-packages/JumpScale/")
        # j.sal.fs.symlink("%s/lib/JumpScale/"%j.dirs.base,"/root/.ipython/JumpScale/")

        self.model.paths = []
        # d.setNamespace("dedupe")
        self.addPath(j.dirs.base)
        self.enableMasterCacheUpdate()
        self.buildUpload(sandbox)

    def destroyfileserver(self):
        self.cuisine_master.run(
            "rm -rf /mnt/Storage/openvcloud/ftp/ays/master/;mkdir -p /mnt/Storage/openvcloud/ftp/ays/master/dedupe/")

    def __str__(self):
        return str(self.model)
    __repr__ = __str__


class AtYourServiceDebugFactory:

    @property
    def doc(self):
        D = """
    example usage:
    ```
    #ALL IN ONE to only update master
    d=j.atyourservice.debug.buildUpload_master()

    #DEBUG TO LOCAL HOST FO DEBUG PURPOSES
    d=j.atyourservice.debug.get("ahost")
    d.setHost("192.168.0.105")
    d.buildUpload_JS()

    #DETAIL
    d=j.atyourservice.debug.get("main")
    d.setHost("192.168.0.105")
    d.setCache("192.168.0.140")
    d.enableMasterCacheUpdate()
    d.addPath(j.dirs.base)
    d.upload()

    #SANDBOXING
    d=j.atyourservice.debug.get("main")
    d.addSandboxSource("/usr/bin/rsync")
    d.addSandboxSource("/usr/local/bin/","afile*","myapp/") #will look for files starting with afile and then copy to myapp in /optrw/... or /opt/
    d.sandbox()

    ```

    next time you can do
    ```
    js 'j.atyourservice.debug.upload("mytest")'
    ```

    """
        print(D)

    def get(self, name="main"):
        """
        """
        d = AtYourServiceDebug(name=name)
        return d

    def buildUpload(self, name="main"):
        d = self.get(name=name)
        d.buildUpload()

    def buildUpload_master(self, name="master"):
        d = self.get(name=name)
        d.buildUpload_JS()
