
from JumpScale import j
# import os


app = j.tools.cuisine._getBaseAppClass()


class CuisineGolang(app):

    NAME = 'go'

    def __init__(self, executor, cuisine):
        self._executor = executor
        self._cuisine = cuisine

    def isInstalled(self):
        rc, out, err = self._cuisine.core.run("go version", die=False, showout=False, profile=True)
        if rc > 0 or "1.6" not in out:
            return False
        return True

    def install(self, reset=False):
        if reset is False and self.isInstalled():
            return
        if self._cuisine.core.isMac or self._cuisine.core.isArch:
            self._cuisine.core.run(cmd="rm -rf /usr/local/go", die=False)
            self._cuisine.package.install("go")
        elif "ubuntu" in self._cuisine.platformtype.platformtypes:
            downl = "https://storage.googleapis.com/golang/go1.7.1.linux-amd64.tar.gz"
            self._cuisine.core.file_download(downl, "/usr/local", overwrite=False, retry=3, timeout=0, expand=True)
        else:
            raise j.exceptions.RuntimeError("platform not supported")

        goDir = self._cuisine.core.dir_paths['goDir']
        self._cuisine.bash.environSet("GOPATH", goDir)

        if self._cuisine.core.isMac:
            self._cuisine.bash.environSet("GOROOT", '/usr/local/opt/go/libexec/')
            self._cuisine.bash.addPath("/usr/local/opt/go/libexec/bin/")
        else:
            self._cuisine.bash.environSet("GOROOT", '/usr/local/go')
            self._cuisine.bash.addPath("/usr/local/go/bin/")

        self._cuisine.bash.addPath(self._cuisine.core.joinpaths(goDir, 'bin'))

        self._cuisine.core.dir_ensure("%s/src" % goDir)
        self._cuisine.core.dir_ensure("%s/pkg" % goDir)
        self._cuisine.core.dir_ensure("%s/bin" % goDir)

    def goraml(self):
        C = '''
        go get -u github.com/Jumpscale/go-raml
        set -ex
        cd $GOPATH/src/github.com/jteeuwen/go-bindata/go-bindata
        go build
        go install
        cd $GOPATH/src/github.com/Jumpscale/go-raml
        sh build.sh
        '''
        self._cuisine.core.execute_bash(C, profile=True)

    def install_godep(self):
        self.get("github.com/tools/godep")

    @property
    def GOPATH(self):
        return self._cuisine.core.dir_paths["goDir"]
        # if self._gopath==None:
        #     # if not "GOPATH" in self.bash.environ:
        #     #     self._cuisine.installerdevelop.golang()
        #     # self._gopath=   self.bash.environ["GOPATH"]

        # return self._gopath

    def clean_src_path(self):
        srcpath = self._cuisine.core.joinpaths(self.GOPATH, 'src')
        self._cuisine.core.dir_remove(srcpath)

    def get(self, url):
        """
        e.g. url=github.com/tools/godep
        """
        self.clean_src_path()
        self._cuisine.core.run('go get -v -u %s' % url, profile=True)

    def godep(self, url, branch=None, depth=1):
        """
        e.g. url=github.com/tools/godep
        """
        self.clean_src_path()
        GOPATH = self._cuisine.bash.environ['GOPATH']

        pullurl = "git@%s.git" % url.replace('/', ':', 1)

        dest = self._cuisine.development.git.pullRepo(pullurl,
                                                      branch=branch,
                                                      depth=depth,
                                                      dest='%s/src/%s' % (GOPATH, url),
                                                      ssh=False)
        self._cuisine.core.run('cd %s && godep restore' % dest, profile=True)
