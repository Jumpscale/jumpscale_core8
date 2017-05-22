from JumpScale import j

app = j.tools.cuisine._getBaseAppClass()


class CuisineOdoo(app):
    NAME = "odoo-bin"

    def _group_exists(self, groupname):
        return groupname in open("/etc/group").read()

    def _install_pip(self):
        self.cuisine.core.run('apt-get --assume-yes install python2.7 python2.7-dev libpq-dev')
        cmd = """
        cd $TMPDIR
        wget https://bootstrap.pypa.io/get-pip.py
        python2.7 get-pip.py
        """
        self.cuisine.core.execute_bash(cmd, profile=True)

    def build(self):
        if not self.cuisine.apps.postgresql.isInstalled():
            self.cuisine.apps.postgresql.build()
            self.cuisine.apps.postgresql.install()
        self._install_pip()
        self.cuisine.apps.nodejs.install()
        self.cuisine.core.run("npm install -g less less-plugin-clean-css -y", profile=True)
        cmd = """
        cd $TMPDIR && git clone https://github.com/odoo/odoo.git --depth=1 --branch=10.0
        export PATH=$PATH:$BINDIR/postgres/
        apt-get -y install python-ldap libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxslt-dev python-dev
        cd $TMPDIR/odoo && pip2 install -r requirements.txt
        """
        self.cuisine.core.run(cmd, profile=True)

    def install(self):
        if not self.cuisine.apps.postgresql.isStarted():
            self.cuisine.apps.postgresql.start()
        if not self._group_exists("odoo"):
            self.cuisine.core.run('adduser --system --quiet  \
        --shell /bin/bash --group --gecos "Odoo administrator" odoo')
            self.cuisine.core.run('sudo -u postgres $BINDIR/createuser -s odoo')

        self.cuisine.core.dir_ensure("$JSLIBEXTDIR")
        c = """
        cp $TMPDIR/odoo/odoo-bin $BINDIR/odoo-bin
        cp -r $TMPDIR/odoo/odoo $JSLIBEXTDIR
        cp -r $TMPDIR/odoo/addons $JSLIBEXTDIR/odoo-addons
        """
        self.cuisine.core.run(c, profile=True)

    def start(self):
        if not self.cuisine.apps.postgresql.isStarted():
            self.cuisine.apps.postgresql.start()
        cmd = """
        cd $BINDIR
        sudo -H -u odoo PYTHONPATH=$JSLIBEXTDIR:$PYTHONPATH LD_LIBRARY_PATH=$LIBDIR/postgres/:$LD_LIBRARY_PATH ./odoo-bin --addons-path=$JSLIBEXTDIR/odoo-addons,$JSLIBEXTDIR/odoo/addons/
        """
        self.cuisine.core.execute_bash(cmd, profile=True)
