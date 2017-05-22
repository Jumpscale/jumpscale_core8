from JumpScale import j

app = j.tools.cuisine._getBaseAppClass()


class CuisinePostgresql(app):
    NAME = "psql"

    def build(self):
        postgre_url = 'https://ftp.postgresql.org/pub/source/v9.6.1/postgresql-9.6.1.tar.gz'
        dest = '$TMPDIR/postgresql-9.6.1.tar.gz'
        self.cuisine.core.file_download(postgre_url, dest)
        self.cuisine.core.run('cd $TMPDIR; tar xvf $TMPDIR/postgresql-9.6.1.tar.gz')
        self.cuisine.core.dir_ensure("$JSAPPSDIR/pgsql")
        self.cuisine.core.dir_ensure("$BINDIR")
        self.cuisine.core.dir_ensure("$LIBDIR/postgres")
        self.cuisine.package.multiInstall(['build-essential', 'zlib1g-dev'])
        cmd = """
        apt-get --assume-yes install libreadline-dev
        cd $TMPDIR/postgresql-9.6.1
        ./configure --prefix=$JSAPPSDIR/pgsql --bindir=$BINDIR --sysconfdir=$CFGDIR --libdir=$LIBDIR/postgres --datarootdir=$JSAPPSDIR/pgsql/share
        make
        """
        self.cuisine.core.execute_bash(cmd, profile=True)

    def _group_exists(self, groupname):
        return groupname in open("/etc/group").read()

    def install(self, reset=False, start=False, port=5432):
        if reset is False and self.isInstalled():
            return
        cmd = """
        cd $TMPDIR/postgresql-9.6.1
        make install with-pgport=%s
        """ % str(port)

        self.cuisine.core.execute_bash(cmd, profile=True)
        if not self._group_exists("postgres"):
            self.cuisine.core.run('adduser --system --quiet --home $LIBDIR/postgres --no-create-home \
        --shell /bin/bash --group --gecos "PostgreSQL administrator" postgres')
        c = """
        cd $JSAPPSDIR/pgsql
        mkdir data
        mkdir log
        chown  -R postgres $JSAPPSDIR/pgsql/
        sudo -u postgres $BINDIR/initdb -D $JSAPPSDIR/pgsql/data --no-locale
        """
        self.cuisine.core.execute_bash(c, profile=True)
        if start:
            self.start()

    def start(self):
        cmd = """
        chown postgres $JSAPPSDIR/pgsql/log/
        sudo -u postgres $BINDIR/pg_ctl -D $JSAPPSDIR/pgsql/data -l $JSAPPSDIR/pgsql/log/logfile start
        """
        self.cuisine.core.execute_bash(cmd, profile=True)

    def stop(self):
        cmd = """
        sudo -u postgres $BINDIR/pg_ctl -D $JSAPPSDIR/pgsql/data -l $JSAPPSDIR/pgsql/log/logfile stop
        """
        self.cuisine.core.execute_bash(cmd, profile=True)
