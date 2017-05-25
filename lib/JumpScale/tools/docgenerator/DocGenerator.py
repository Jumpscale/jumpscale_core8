from JumpScale import j
from DocSite import DocSite


import imp
import sys
import inspect
import copy


def loadmodule(name, path):
    parentname = ".".join(name.split(".")[:-1])
    sys.modules[parentname] = __package__
    mod = imp.load_source(name, path)
    return mod


if not sys.platform.startswith("darwin"):
    caddyconfig = '''

    $ws/ {
        root $outpath
        browse
    }

    $ws/fm/ {
        filemanager / {
            show           $outpath
            allow_new      true
            allow_edit     true
            allow_commands true
            allow_command  git
            allow_command  svn
            allow_command  hg
            allow_command  ls
            block          dotfiles
        }
    }
    '''
else:
    caddyconfig = '''

    $ws/ {
        root $outpath
        browse
    }

    '''

caddyconfig = j.data.text.strip(caddyconfig)


class DocGenerator:
    """
    process all markdown files in a git repo, write a summary.md file
    optionally call pdf gitbook generator to produce pdf(s)
    """

    def __init__(self):
        self.__jslocation__ = "j.tools.docgenerator"
        self._macroPathsDone = []
        self._initOK = False
        self._macroCodepath = j.sal.fs.joinPaths(j.dirs.VARDIR, "docgenerator_internal", "macros.py")
        j.sal.fs.createDir(j.sal.fs.joinPaths(j.dirs.VARDIR, "docgenerator_internal"))
        self._docRootPathsDone = []
        self.docSites = {}  # location in the outpath per site
        self.outpath = j.sal.fs.joinPaths(j.dirs.VARDIR, "docgenerator")
        self.gitRepos = {}
        self.webserver = "http://localhost:1313/"
        self.ws = self.webserver.replace("http://", "").replace("https://", "").replace("/", "")
        self.logger = j.logger.get('docgenerator')
        self._loaded = []
        self._macrosLoaded = []

    def addGitRepo(self, path):
        if path not in self.gitRepos:
            gc = j.clients.git.get(path)
            self.gitRepos[path] = gc
        return self.gitRepos[path]

    def installDeps(self, reset=False):
        if int(j.core.db.get("docgenerator:installed") or 0) == 1 and reset == False:
            return
        cuisine = j.tools.cuisine.local
        cuisine.apps.nodejs.install()

        def hugoInstall():
            # Using package install will result in an old version on some machines
            cuisine.core.file_download('https://github.com/spf13/hugo/releases/download/v0.20.7/hugo_0.20.7_Linux-64bit.tar.gz', '$TMPDIR/hugo_0.20.7_Linux-64bit.tar.gz')
            cuisine.core.file_expand('$TMPDIR/hugo_0.20.7_Linux-64bit.tar.gz')
            cuisine.core.file_copy('$TMPDIR/hugo_0.20.7_Linux-64bit/hugo', '/usr/local/bin')

        cuisine.core.run("npm install -g phantomjs-prebuilt", profile=True)
        cuisine.core.run("npm install -g mermaid", profile=True)
        cuisine.apps.caddy.build()
        if "darwin" in str(j.core.platformtype.myplatform):
            cuisine.core.run("brew install graphviz")
            cuisine.core.run("brew install hugo")
        elif "ubuntu" in str(j.core.platformtype.myplatform):
            cuisine.package.install('graphviz')
            hugoInstall()
        j.tools.cuisine.local.development.golang.install()
        j.core.db.set("docgenerator:installed", 1)

    def startWebserver(self, generateCaddyFile=False):
        """
        start caddy on localhost:1313
        """
        if generateCaddyFile:
            self.generateCaddyFile()
        dest = "%s/docgenerator/caddyfile" % j.dirs.VARDIR
        if not j.sal.fs.exists(dest, followlinks=True):
            self.generateCaddyFile()
        j.tools.cuisine.local.apps.caddy.start(ssl=False, agree=True, cfg_path=dest)
        self.logger.info("go to %a" % self.webserver)

    def generateCaddyFile(self):
        dest = "%s/docgenerator/caddyfile" % j.dirs.VARDIR
        out2 = caddyconfig

        C2 = """
        $ws/$name/ {
            root /optvar/docgenerator/$name/public
            #log ../access.log
        }

        """
        for key, ds in self.docSites.items():
            C3 = j.data.text.strip(C2.replace("$name", ds.name))
            out2 += C3
        out2 = out2.replace("$outpath", self.outpath)
        out2 = out2.replace("$ws", self.ws)
        j.sal.fs.writeFile(filename=dest, contents=out2, append=False)

    def init(self):
        if self._initOK == False:
            self.installDeps()
            j.sal.fs.remove(self._macroCodepath)
            # load the default macro's
            self.loadMacros("https://github.com/Jumpscale/docgenerator/tree/master/macros")
            self._initOK = True
        if self.webserver[-1] != "/":
            self.webserver += "/"
        self.ws = self.webserver.replace("http://", "").replace("https://", "").replace("/", "")

    def loadMacros(self, pathOrUrl=""):
        """
        @param pathOrUrl can be existing path or url
        e.g. https://github.com/Jumpscale/docgenerator/tree/master/examples
        """

        path = j.clients.git.getContentPathFromURLorPath(pathOrUrl)

        if path not in self._macroPathsDone:

            if not j.sal.fs.exists(path=path):
                raise j.exceptions.Input("Cannot find path:'%s' for macro's, does it exist?" % path)

            if j.sal.fs.exists(path=self._macroCodepath):
                code = j.sal.fs.readFile(self._macroCodepath)
            else:
                code = ""

            for path0 in j.sal.fs.listFilesInDir(path, recursive=True, filter="*.py", followSymlinks=True):
                newdata = j.sal.fs.fileGetContents(path0)
                md5 = j.data.hash.md5_string(newdata)
                if not md5 in self._macrosLoaded:
                    code += newdata
                    self._macrosLoaded.append(md5)

            code = code.replace("from JumpScale import j", "")
            code = "from JumpScale import j\n\n" + code

            j.sal.fs.writeFile(self._macroCodepath, code)
            self.macros = loadmodule("macros", self._macroCodepath)
            self._macroPathsDone.append(path)

    def load(self, pathOrUrl=""):
        """
        will look for config.yaml in $source/config.yaml

        @param pathOrUrl is the location where the markdown docs are which need to be processed
            if not specified then will look for root of git repo and add docs
            source = $gitrepoRootDir/docs

            this can also be a git url e.g. https://github.com/Jumpscale/docgenerator/tree/master/examples

        """
        if pathOrUrl in self._loaded:
            return
        self._loaded.append(pathOrUrl)
        self.init()
        if pathOrUrl == "":
            path = j.sal.fs.getcwd()
            path = j.clients.git.findGitPath(path)
        else:
            path = j.clients.git.getContentPathFromURLorPath(pathOrUrl)

        for docDir in j.sal.fs.listFilesInDir(path, True, filter=".docs"):
            if docDir not in self.docSites:
                print("found doc dir:%s" % docDir)
                ds = DocSite(path=docDir)
                self.docSites[docDir] = ds

    def generateExamples(self, start=True):
        self.load(pathOrUrl="https://github.com/Jumpscale/docgenerator/tree/master/examples")
        # self.load(pathOrUrl="https://github.com/Jumpscale/jumpscale_core8/tree/8.2.0")
        # self.load(pathOrUrl="https://github.com/Jumpscale/jumpscale_portal8/tree/8.2.0")
        self.generate(start=start)

    def generateJSDoc(self, start=True):
        self.load(pathOrUrl="https://github.com/Jumpscale/docgenerator/tree/master/examples")
        self.load(pathOrUrl="https://github.com/Jumpscale/jumpscale_core8/tree/8.2.0")
        self.load(pathOrUrl="https://github.com/Jumpscale/jumpscale_portal8/tree/8.2.0")
        self.generate(start=start)

    def generate(self, url=None, start=True):
        if url != None:
            self.load(pathOrUrl=url)
        if self.docSites == {}:
            self.load()
        for path, ds in self.docSites.items():
            ds.write()
        self.generateCaddyFile()
        if start:
            self.startWebserver()
        print("TO CHECK GO TO: http://localhost:1313/")

    def gitUpdate(self):
        if self.docSites == {}:
            self.load()
        for gc in self.gitRepos:
            gc.pull()

    def getDoc(self, name, die=True):
        for key, ds in self.docSites.items():
            if name in ds.docs:
                return ds.docs[name]
        if die:
            raise j.exceptions.Input(message="Cannot find doc with name:%s" %
                                     name, level=1, source="", tags="", msgpub="")
        else:
            return None

    def getDocSite(self, name, die=True):
        name = name.lower()
        for key, ds in self.docSites.items():
            if ds.name == name:
                return ds
        if die:
            raise j.exceptions.Input(message="Cannot find docsite with name:%s" %
                                     name, level=1, source="", tags="", msgpub="")
        else:
            return None
