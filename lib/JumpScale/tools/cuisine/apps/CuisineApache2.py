from JumpScale import j
import textwrap

app = j.tools.cuisine._getBaseAppClass()


class CuisineApache2(app):

    NAME = 'apachectl'

    def build(self, reset=True):

        pkgs = "wget curl gcc libssl-dev zlib1g-dev libaprutil1-dev libapr1-dev libpcre3-dev libxml2-dev build-essential unzip".split()
        self._cuisine.package.multiInstall(pkgs)

        httpdir = "/optvar/build/httpd"

        if reset and self._cuisine.core.dir_exists(httpdir):
            self._cuisine.core.dir_remove("$JSAPPSDIR/apache2")

        self._cuisine.core.dir_ensure("/optvar/build")

        ## DOWNLOAD LINK
        DOWNLOADLINK = 'https://www.apache.org/dist/httpd/httpd-2.4.25.tar.bz2'
        dest = j.sal.fs.joinPaths("/optvar", 'httpd-2.4.25.tar.bz2')

        if not self._cuisine.core.file_exists(dest):
            self._cuisine.core.file_download(DOWNLOADLINK, dest)

        # EXTRACT SROURCE CODE
        self._cuisine.core.run("cd /optvar/build && tar xjf {dest} && mv /optvar/build/httpd-2.4.25 /optvar/build/httpd".format(**locals()))
        self._cuisine.core.dir_ensure("$JSAPPSDIR/apache2/bin")
        self._cuisine.core.dir_ensure("$JSAPPSDIR/apache2/lib")

        buildscript = """

        cd {httpdir} &&  ./configure --prefix=$JSAPPSDIR/apache2 --bindir=$JSAPPSDIR/apache2/bin --sbindir=$JSAPPSDIR/apache2/bin \
              --libdir=$JSAPPSDIR/apache2/lib \
              --enable-mpms-shared=all \
              --enable-modules=all \
              --enable-mods-shared=all \
              --enable-so \
              --enable-cache --enable-disk-cache --enable-mem-cache --enable-file-cache \
              --enable-ssl --with-ssl \
              --enable-deflate --enable-cgi --enable-cgid \
              --enable-proxy --enable-proxy-connect \
              --enable-proxy-http --enable-proxy-ftp \
              --enable-dbd --enable-imagemap --enable-ident --enable-cern-meta \
              --enable-xml2enc && make && make test\
        """.format(httpdir=httpdir)

        self._cuisine.core.run(buildscript)

        return True

    def install(self):
        httpdir = j.sal.fs.joinPaths("/optvar/build", 'httpd')
        installscript = """
        cd {httpdir} &&  make install
        """.format(httpdir=httpdir)
        self._cuisine.core.run(installscript)

        #COPY APACHE BINARIES to /opt/jumpscale8/bin
        self._cuisine.core.file_copy("$JSAPPSDIR/apache2/bin/*",'$BINDIR/')


    def configure(self):
        conffile = self._cuisine.core.file_read("$JSAPPSDIR/apache2/conf/httpd.conf")
        # SANE CONFIGURATIONS
        lines = """
        #LoadModule negotiation_module
        #LoadModule include_module
        #LoadModule userdir_module
        #LoadModule slotmem_shm_module
        #LoadModule rewrite_module modules/mod_rewrite.so
        #LoadModule mpm_prefork_module modules/mod_mpm_prefork.so

        #Include conf/extra/httpd-multilang-errordoc.con
        #Include conf/extra/httpd-autoindex.con
        #Include conf/extra/httpd-languages.con
        #Include conf/extra/httpd-userdir.con
        #Include conf/extra/httpd-default.con
        #Include conf/extra/httpd-mpm.con
        """.splitlines()

        for line in lines:
            line = line.strip()
            if line:
                mod = line.replace("#", "")
                conffile = conffile.replace(line, mod)
        disabled = """
        LoadModule mpm_worker_module modules/mod_mpm_worker.so
        LoadModule mpm_event_module modules/mod_mpm_event.so
        """
        for line in disabled.splitlines():
            line = line.strip()
            if line:
                mod = "#"+line
                conffile = conffile.replace(line, mod)
        conffile += "\nInclude sites-enabled/*"
        conffile += "\nAddType application/x-httpd-php .php"

        # MAKE VHOSTS DIRECTORY
        self._cuisine.core.dir_ensure("$JSAPPSDIR/apache2/sites-available")
        self._cuisine.core.dir_ensure("$JSAPPSDIR/apache2/sites-enabled")
        #self.logger.info("Config to be written = ", conffile)
        self._cuisine.core.file_write("$JSAPPSDIR/apache2/conf/httpd.conf", conffile)


    def start(self):
        """start Apache."""
        self._cuisine.core.run("apachectl start")

    def stop(self):
        """stop Apache."""
        self._cuisine.core.run("apachectl stop")

    def restart(self):
        """restart Apache."""
        self._cuisine.core.run("apachectl restart")
