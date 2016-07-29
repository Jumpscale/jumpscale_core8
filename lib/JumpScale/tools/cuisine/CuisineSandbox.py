

from JumpScale import j

from ActionDecorator import ActionDecorator
class actionrun(ActionDecorator):
    def __init__(self,*args,**kwargs):
        ActionDecorator.__init__(self,*args,**kwargs)
        self.selfobjCode="cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.sandbox"


base=j.tools.cuisine.getBaseClass()
class CuisineSandbox(base):
    def __init__(self,executor,cuisine):
        self.executor=executor
        self.cuisine=cuisine

    @actionrun(force=True)
    def do(self,destination="/out"):
        """
        @todo specify what comes in /out

        """

        self.cuisine.package.mdupdate()

        self.cuisine.core.file_copy('/usr/local/bin/jspython', '$binDir')        

        sandbox_script = """
        cuisine = j.tools.cuisine.local
        paths = []
        paths.append("/usr/lib/python3.5/")
        paths.append("/usr/local/lib/python3.5/dist-packages")
        paths.append("/usr/lib/python3/dist-packages")

        excludeFileRegex=["-tk/", "/lib2to3", "-34m-", ".egg-info"]
        excludeDirRegex=["/JumpScale", "\.dist-info", "config-x86_64-linux-gnu", "pygtk"]

        dest = j.sal.fs.joinPaths(cuisine.core.dir_paths['base'], 'lib')

        for path in paths:
            j.tools.sandboxer.copyTo(path, dest, excludeFileRegex=excludeFileRegex, excludeDirRegex=excludeDirRegex)

        if not j.sal.fs.exists("%s/bin/python" % cuisine.core.dir_paths['base']):
            j.sal.fs.copyFile("/usr/bin/python3.5", "%s/bin/python" % cuisine.core.dir_paths['base'])

        j.tools.sandboxer.sandboxLibs("%s/lib" % cuisine.core.dir_paths['base'], recursive=True)
        j.tools.sandboxer.sandboxLibs("%s/bin" % cuisine.core.dir_paths['base'], recursive=True)
        """
        print("start sandboxing")
        self.cuisine.core.execute_jumpscript(sandbox_script)

        name="js8"

        dedupe_script = """
        j.sal.fs.removeDirTree("$out/$name")
        j.tools.sandboxer.dedupe('/opt', storpath='$out/$name', name='js8_opt', reset=False, append=True, excludeDirs=['/opt/code'])
        """
        dedupe_script=dedupe_script.replace("$name",name)
        dedupe_script=dedupe_script.replace("$out",destination)
        print("start dedupe")
        self.cuisine.core.execute_jumpscript(dedupe_script)


        copy_script="""
        j.sal.fs.removeDirTree("$out/$name/jumpscale8/")
        j.sal.fs.copyDirTree("/opt/jumpscale8/","$out/$name/jumpscale8",deletefirst=True,ignoredir=['.egg-info', '.dist-info','__pycache__'],ignorefiles=['.egg-info',"*.pyc"])
        j.sal.fs.removeIrrelevantFiles("$out")
        """
        copy_script=copy_script.replace("$name",name)
        copy_script=copy_script.replace("$out",destination)
        print("start copy sandbox")
        self.cuisine.core.execute_jumpscript(copy_script)

