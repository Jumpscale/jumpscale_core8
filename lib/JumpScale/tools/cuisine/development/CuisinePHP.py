from JumpScale import j
import textwrap
from copy import deepcopy
app = j.tools.cuisine._getBaseAppClass()

compileconfig = {}
compileconfig['enable_mbstring'] = True
compileconfig['enable_zip'] = True
compileconfig['with_gd'] = True
compileconfig['with_curl'] = True  # apt-get install libcurl4-openssl-dev libzip-dev
compileconfig['with_libzip'] = True
compileconfig['with_zlib'] = True
compileconfig['with_openssl'] = True
compileconfig['enable_fpm'] = True
compileconfig['prefix'] = "$appDir/php"
compileconfig['exec_prefix'] = "$appDir/php"
compileconfig['with_mysqli'] = True
compileconfig['with_pdo_mysql'] = True
compileconfig['with_mysql_sock'] = "/var/run/mysqld/mysqld.sock"



class CuisinePHP(app):

    NAME = 'php'

    def build(self, **config):
        pkgs = "libxml2-dev libpng-dev libcurl4-openssl-dev libzip-dev zlibc zlib1g zlib1g-dev libmysqld-dev libmysqlclient-dev re2c bison"
        list(map(self._cuisine.package.ensure, pkgs.split(sep=" ")))

        compileconfig['with_apxs2'] = self._cuisine.core.args_replace("$appDir/apache2/bin/apxs")
        buildconfig = deepcopy(compileconfig)
        buildconfig.update(config)  # should be defaultconfig.update(config) instead of overriding the explicit ones.

        # check for apxs2 binary if it's valid.
        apxs = buildconfig['with_apxs2']
        if not self._cuisine.core.file_exists(apxs):
            buildconfig.pop('with_apxs2')

        args_string = ""
        for k, v in buildconfig.items():
            k = k.replace("_", "-")
            if v is True:
                args_string += " --{k}".format(k=k)
            else:
                args_string += " --{k}={v}".format(k=k, v=v)
        C = """
        cd $TMPDIR && [ ! -f $TMPDIR/php-7.0.11.tar.bz2 ] && wget http://be2.php.net/distributions/php-7.0.11.tar.bz2
        cd $TMPDIR && tar xvjf $TMPDIR/php-7.0.11.tar.bz2
        mv $TMPDIR/php-7.0.11/ $TMPDIR/php

        """

        C = self.cuisine.core.args_replace(C)
        self.cuisine.core.run(C)

        C = """cd $TMPDIR/php && ./configure {args_string}""".format(args_string=args_string)
        self.cuisine.core.run(C, die=False)

        C = """cd $TMPDIR/php && make"""
        self.cuisine.core.run(C, die=False)


        # check if we need an php accelerator: https://en.wikipedia.org/wiki/List_of_PHP_accelerators

    def install(self, start=False):
        fpmdefaultconf = """\
        include=$appDir/php/etc/php-fpm.d/*.conf
        """
        fpmwwwconf = """\
        ;nobody Start a new pool named 'www'.
        [www]

        ;prefix = /path/to/pools/$pool

        user =  www-data
        group = www-data

        listen = 127.0.0.1:9000

        listen.allowed_clients = 127.0.0.1

        pm = dynamic
        pm.max_children = 5
        pm.start_servers = 2
        pm.min_spare_servers = 1
        pm.max_spare_servers = 3
        """
        fpmdefaultconf = textwrap.dedent(fpmdefaultconf)
        fpmwwwconf = textwrap.dedent(fpmwwwconf)
        # make sure to save that configuration file ending with .conf under php/etc/php-fpm.d/www.conf
        C = """
        cd $tmpDir/php && make install
        """

        C = self._cuisine.core.args_replace(C)
        self._cuisine.core.execute_bash(C)
        fpmdefaultconf = self._cuisine.core.args_replace(fpmdefaultconf)
        fpmwwwconf = self._cuisine.core.args_replace(fpmwwwconf)
        self._cuisine.core.file_write("$appDir/php/etc/php-fpm.conf.default", content=fpmdefaultconf)
        self._cuisine.core.file_write("$appDir/php/etc/php-fpm.d/www.conf", content=fpmwwwconf)
        self._cuisine.bash.addPath(self._cuisine.core.args_replace('$appDir/php/bin'))

        # FOR APACHE
        self._cuisine.file_copy("$tmpDir/php/php.ini-development", "$appDir/php/lib/php.ini")
        if start:
            self.start()

    def start(self):
        phpfpmbinpath = '$appDir/php/sbin'

        phpfpmcmd = "$appDir/php/sbin/php-fpm -F -y $appDir/php/etc/php-fpm.conf.default"  # foreground
        phpfpmcmd = self._cuisine.core.args_replace(phpfpmcmd)
        self._cuisine.processmanager.ensure(name="php-fpm", cmd=phpfpmcmd, path=phpfpmbinpath)

    def stop(self):
        self._cuisine.processmanager.stop("php-fpm")

    def test(self):
        # TODO: *1
        # check there is a local nginx running, if not install it
        # deploy some php script, test it works
        raise NotImplementedError
