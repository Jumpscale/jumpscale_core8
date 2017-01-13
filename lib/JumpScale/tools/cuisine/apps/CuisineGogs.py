from JumpScale import j
import os
import textwrap

app = j.tools.cuisine._getBaseAppClass()

# TODO: *1 needs to be tested prob


class CuisineGogs(app):
    NAME = "gogs"

    def _init(self):
        self._gogspath = str()
        self._gopath = str()
        self._appini = str()
        self.BUILDDIR = self.replace("$BUILDDIR/caddy")
        self.GOPATH = self.cuisine.development.golang.GOPATH
        self.GOGSPATH = self.replace("$GOPATH/src/github.com/gogits/gogs")
        self.CODEDIR = self.GOGSPATH
        self.INIPATH = self.replace("$GOGSPATH/custom/conf/app.ini")

    def reset(self):
        app.reset(self)
        self._init()

    def build(self, install=True, start=True, reset=False, installDeps=False):

        if self.doneGet('build') and not reset:
            return

        self.cuisine.development.golang.install()
        self.cuisine.development.golang.glide()

        self.cuisine.bash.envSet('GOGITSDIR', '%s/src/github.com/gogits' % self.GOGSPATH)
        self.cuisine.bash.envSet('GOGSDIR', '$GOGITSDIR/gogs')

        self.cuisine.development.golang.get('golang.org/x/oauth2')
        self.cuisine.development.golang.get('github.com/gogits/gogs')

        self.cuisine.core.run('cd %s && git remote add gigforks https://github.com/gigforks/gogs' % self.GOGSPATH,
                              profile=True)
        self.cuisine.core.run('cd %s && git fetch gigforks && git checkout gigforks/itsyouimpl' % self.GOGSPATH,
                              profile=True, timeout=1200)
        self.cuisine.core.run('cd %s && glide install && go build -tags "sqlite cert"' % self.GOGSPATH, profile=True,
                              timeout=1200)

        self.doneSet('build')

    def install(self):
        """
        GOGS has no files to move this method is for standardization of cuisine
        """
        # TODO: *1 this cannot be right, files should be moved
        pass

    def write_itsyouonlineconfig(self):
        # ADD EXTRA CUSTOM INFO FOR ITS YOU ONLINE.
        if self.doneGet('config'):
            return
        itsyouonlinesection = """\
        [itsyouonline]
        CLIENT_ID     = itsyouref
        CLIENT_SECRET = khZNlrGFiVqHb9u7h6Kh5IvZXY_aE1gWYL_v2Ike9WOZkza4j2k9
        REDIRECT_URL  = http://localhost:3000/oauth/redirect
        AUTH_URL      = https://itsyou.online/v1/oauth/authorize
        TOKEN_URL     = https://itsyou.online/v1/oauth/access_token
        SCOPE        = user:email

        """

        itsyouonlinesection = textwrap.dedent(itsyouonlinesection)
        if self.cuisine.core.file_exists(self.INIPATH):
            self.cuisine.core.file_write(location=self.INIPATH,
                                         content=itsyouonlinesection,
                                         append=True)
        self.doneSet('config')

    def start(self, name='main'):
        cmd = "{gogspath}/gogs web".format(gogspath=self.GOGSPATH)
        self.cuisine.processmanager.ensure(name='gogs_%s' % name, cmd=cmd)

    def stop(self, name='main'):
        self.cuisine.processmanager.stop('gogs_%s' % name)

    def restart(self):
        self.cuisine.processmanager.stop("gogs")
        self.start()

    def reset(self):
        """
        helper method to clean what this module generates.
        """
        super().reset()
        self.core.dir_remove(self.BUILDDIR)
        self.core.dir_remove(self.CODEDIR)
