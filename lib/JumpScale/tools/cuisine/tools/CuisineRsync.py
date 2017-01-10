from JumpScale import j

base = j.tools.cuisine._getBaseClass()


class CuisineRsync(base):

    def _init(self):
        self.BUILDDIRL = self.core.replace("$BUILDDIR/rsync/")
        self.VERSION = 'rsync-3.1.2'

    def reset(self):
        self.core.dir_remove(self.BUILDDIRL)

    def build(self, reset=False, install=True):
        """
        """

        if reset:
            self.reset()

        if self.doneGet("build") and not reset:
            return

        self.cuisine.core.dir_ensure(self.BUILDDIRL)

        self.cuisine.package.ensure("gcc")
        self.cuisine.package.ensure("g++")
        self.cuisine.package.ensure('make')

        self.cuisine.core.file_download("https://download.samba.org/pub/rsync/src/%s.tar.gz" % self.VERSION, to="%s/%s.tar.gz" % (self.BUILDDIRL, self.VERSION))

        C = """
        set -xe
        cd $BUILDDIRL
        tar -xf $VERSION.tar.gz
        cd $VERSION
        ./configure
        make
        """
        C = C.replace('$BUILDDIRL', self.BUILDDIRL)
        C = C.replace('$VERSION', self.VERSION)
        self.cuisine.core.run(C, profile=True)

        self.doneSet("build")
        if install:
            self.install()

    def install(self):
        self.cuisine.bash.profileDefault.addPath(self.cuisine.core.replace("$BINDIR"))
        self.cuisine.bash.profileDefault.save()
        self.cuisine.core.file_copy("%s/%s/rsync" % (self.BUILDDIRL, self.VERSION), self.cuisine.core.dir_paths['BINDIR'])
