from JumpScale import j

app = j.tools.cuisine._getBaseAppClass()


class CuisineG8OSFs(app):
    """
    fuse based filesystem for our g8OS, but can be used in other context too
    """
    NAME = 'fs'

    def build(self, start=False, install=True, reset=False):
        if reset is False and self.isInstalled():
            return

        self.cuisine.package.mdupdate()
        self.cuisine.package.install('build-essential')

        self.cuisine.development.golang.get("github.com/g8os/fs")
        self.cuisine.core.file_copy("$GOPATHDIR/bin/fs", "$BASEDIR/bin/")

        if install:
            self.install(start)

    def install(self, start=False):
        """
        download, install, move files to appropriate places, and create relavent configs
        """
        content = """
        [[mount]]
            path="/opt"
            flist="/optvar/cfg/fs/js8_opt.flist"
            backend="opt"
            mode="RO"
            trim_base=true
        [backend]
        [backend.opt]
            path="/optvar/fs_backend/opt"
            stor="public"
            namespace="js8_opt"
            cleanup_cron="@every 1h"
            cleanup_older_than=24
            log=""
        [aydostor]
        [aydostor.public]
            addr="http://stor.jumpscale.org/storx"
            login=""
            passwd=""
        """
        self.cuisine.core.dir_ensure("$TEMPLATEDIR/cfg/fs")
        self.cuisine.core.file_copy("$GOPATHDIR/bin/fs", "$BASEDIR/bin")
        self.cuisine.core.file_write("$GOPATHDIR/src/github.com/g8os/fs/config/config.toml", content)
        self.cuisine.core.file_copy("$GOPATHDIR/src/github.com/g8os/fs/config/config.toml", "$TEMPLATEDIR/cfg/fs")
        self.cuisine.core.file_download(
            "https://stor.jumpscale.org/storx/static/js8_opt.flist", "$TEMPLATEDIR/cfg/fs/js8_opt.flist", minsizekb=0)
        if start:
            self.start()

    def start(self):
        self.cuisine.core.file_copy("$TEMPLATEDIR/cfg/fs", "$JSCFGDIR", recursive=True)
        self.cuisine.processmanager.ensure('fs', cmd="$BINDIR/fs -c $JSCFGDIR/fs/config.toml")
