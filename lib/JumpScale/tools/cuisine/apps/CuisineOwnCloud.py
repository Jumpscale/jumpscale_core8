from JumpScale import j
import textwrap
import re
app = j.tools.cuisine._getBaseAppClass()


class CuisineOwnCloud(app):

    NAME = 'owncloud'

    def installAll(self):
        """
        install all deps (check if e.g. php, apache is installed otherwise not)
        then install this sw
        configure
        """
        """
        install all deps (check if e.g. php, apache is installed otherwise not)
        then install this sw
        configure
        """
        # SQL client
        self.cuisine.package.install("mysql-client-core-5.7")
        if not self.cuisine.apps.apache2.isInstalled():
            self.cuisine.apps.apache2.build()
            self.cuisine.apps.apache2.install()
            self.cuisine.apps.apache2.start()
        if not self.cuisine.development.php.isInstalled():
            self.cuisine.development.php.install()
        if not self.cuisine.apps.tidb.isInstalled():
            self.cuisine.apps.tidb.build()
            self.cuisine.apps.tidb.install()

        self.install()
        self.start(localinstall=True)



        # TODO: *2 create 1 method which does all and is sort of guideline for a customer to understand this

    def install(self, start=True, storagepath="/data", sitename="owncloudy.com", nginx=False):
        """
        install owncloud 9.1 on top of nginx/php/tidb
        tidb is the mysql alternative which is ultra reliable & distributed

        REQUIREMENT: nginx/php/tidb installed before
        """
        self.cuisine.package.mdupdate()
        self.cuisine.package.install('bzip2')
        self.cuisine.package.install("mysql-client-core-5.7")
        C = """
        set -xe
        #TODO: *1 need to use primitives in cuisine
        cd $TMPDIR && [ ! -d $TMPDIR/ays_owncloud ] && git clone https://github.com/0-complexity/ays_owncloud
        cd $TMPDIR && [ ! -f $TMPDIR/owncloud-9.1.3.tar.bz2 ] && wget https://download.owncloud.org/community/owncloud-9.1.3.tar.bz2 && cd $TMPDIR && tar jxf owncloud-9.1.3.tar.bz2 && rm owncloud-9.1.3.tar.bz2
        [ ! -d {storagepath} ] && mkdir -p {storagepath}
        """.format(storagepath=storagepath)

        self.cuisine.core.execute_bash(C)

        # deploy in $JSAPPSDIR/owncloud
        # use nginx/php other cuisine packages

        C = """
        set -xe
        rm -rf $JSAPPSDIR/owncloud
        mv $TMPDIR/owncloud $JSAPPSDIR/owncloud

        # copy config.php to new owncloud home httpd/docs
        /bin/cp -Rf $TMPDIR/ays_owncloud/owncloud/config.php $JSAPPSDIR/owncloud/config/
        # copy gig theme
        /bin/cp -Rf $TMPDIR/ays_owncloud/owncloud/gig $JSAPPSDIR/owncloud/themes/


        """

        self.cuisine.core.run(C)
        gigconf = self._get_default_conf_owncloud()
        gigconf = gigconf % {'storagepath': storagepath}
        self.cuisine.core.file_write("$JSAPPSDIR/owncloud/config/config.php", content=gigconf)

        if start:
            self.start(sitename, nginx=nginx)
        # look at which owncloud plugins to enable(pdf, ...)
        # TODO: *1 storage path

    def _get_default_conf_owncloud(self):
        return """\
        <?php
        $CONFIG = array (
            'theme' => 'gig',
            'datadirectory' => '%(storagepath)s'
        );
        """

        # <?php
        # $CONFIG = array (
        #   'theme' => 'gig',
        #   'datadirectory' => '/data/',
        #   'instanceid' => 'oc9c63xcgy7l',
        #   'passwordsalt' => 'MB/U0WgxwRZ6BLnzN0reuQ3uwmDUiG',
        #   'secret' => 'pTG61+fi55qjzoCtik7ROHBN8HoH2vrn1SKSIFXBDlZ+g2Sa',
        #   'trusted_domains' =>
        #   array (
        #     0 => 'owncloudy.com',
        #   ),
        #   'overwrite.cli.url' => 'http://owncloudy.com',
        #   'dbtype' => 'mysql',
        #   'version' => '9.1.1.3',
        #   'dbname' => 'owncloud',
        #   'dbhost' => '127.0.0.1',
        #   'dbtableprefix' => 'oc_',
        #   'dbuser' => 'oc_admin',
        #   'dbpassword' => 'l1R5ILt15MOwq/a2KkIMSfW+1GmMEA',
        #   'logtimezone' => 'UTC',
        #   'installed' => true,
        # );

    def _get_default_conf_nginx_site(self):
        conf = """\
        upstream php-handler {
            server 127.0.0.1:9000;
            #server unix:/var/run/php5-fpm.sock;
        }

        server {
            listen 80;
            #listen [::]:80 default_server;
            server_name %(sitename)s;


            root $JSAPPSDIR/owncloud/;

            # Add headers to serve security related headers
            # Before enabling Strict-Transport-Security headers please read into this topic first.
            #add_header Strict-Transport-Security "max-age=15552000; includeSubDomains";

            add_header X-Content-Type-Options nosniff;
            add_header X-Frame-Options "SAMEORIGIN";
            add_header X-XSS-Protection "1; mode=block";
            add_header X-Robots-Tag none;
            add_header X-Download-Options noopen;
            add_header X-Permitted-Cross-Domain-Policies none;

            location = /robots.txt {
                allow all;
                log_not_found off;
                access_log off;
            }

            # The following 2 rules are only needed for the user_webfinger app.
            # Uncomment it if you're planning to use this app.
            #rewrite ^/.well-known/host-meta /public.php?service=host-meta last;
            #rewrite ^/.well-known/host-meta.json /public.php?service=host-meta-json last;

            location = /.well-known/carddav {
                return 301 $scheme://$host/remote.php/dav;
            }
            location = /.well-known/caldav {
                return 301 $scheme://$host/remote.php/dav;
            }

            location /.well-known/acme-challenge { }

            # set max upload size
            client_max_body_size 512M;
            fastcgi_buffers 64 4K;

            # Disable gzip to avoid the removal of the ETag header
            gzip off;

            # Uncomment if your server is build with the ngx_pagespeed module
            # This module is currently not supported.
            #pagespeed off;

            error_page 403 /core/templates/403.php;
            error_page 404 /core/templates/404.php;

            location / {
                rewrite ^ /index.php$uri;
            }

            location ~ ^/(?:build|tests|config|lib|3rdparty|templates|data)/ {
                return 404;
            }
            location ~ ^/(?:\.|autotest|occ|issue|indie|db_|console) {
                return 404;
            }

            location ~ ^/(?:index|remote|public|cron|core/ajax/update|status|ocs/v[12]|updater/.+|ocs-provider/.+|core/templates/40[34])\.php(?:$|/) {
                fastcgi_split_path_info ^(.+\.php)(/.*)$;
                include $JSAPPSDIR/nginx/etc/fastcgi_params;
                fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
                fastcgi_param PATH_INFO $fastcgi_path_info;
                # fastcgi_param HTTPS on;
                fastcgi_param modHeadersAvailable true; #Avoid sending the security headers twice
                fastcgi_param front_controller_active true;
                fastcgi_pass php-handler;
                fastcgi_intercept_errors on;
                fastcgi_request_buffering off;
                fastcgi_read_timeout 300;
            }

            location ~ ^/(?:updater|ocs-provider)(?:$|/) {
                try_files $uri $uri/ =404;
                index index.php;
            }

            # Adding the cache control header for js and css files
            # Make sure it is BELOW the PHP block
            location ~* \.(?:css|js)$ {
                try_files $uri /index.php$uri$is_args$args;
                add_header Cache-Control "public, max-age=7200";
                # Add headers to serve security related headers (It is intended to have those duplicated to the ones above)
                # Before enabling Strict-Transport-Security headers please read into this topic first.
                #add_header Strict-Transport-Security "max-age=15552000; includeSubDomains";
                add_header X-Content-Type-Options nosniff;
                add_header X-Frame-Options "SAMEORIGIN";
                add_header X-XSS-Protection "1; mode=block";
                add_header X-Robots-Tag none;
                add_header X-Download-Options noopen;
                add_header X-Permitted-Cross-Domain-Policies none;
                # Optional: Don't log access to assets
                access_log off;
            }

            location ~* \.(?:svg|gif|png|html|ttf|woff|ico|jpg|jpeg)$ {
                try_files $uri /index.php$uri$is_args$args;
                # Optional: Don't log access to other assets
                access_log off;
            }
        }
        """
        conf = textwrap.dedent(conf)
        conf = self.cuisine.core.replace(conf)
        return conf

    def start(self, sitename='owncloudy.com', dbhost="127.0.0.1", dbuser="root", dbpass="", nginx=False, localinstall=False):
        dbpass = "" if dbpass == "" else ' -p "{dbpass}"'.format(dbpass=dbpass)
        if localinstall:
            privateIp = dbhost
        else:
            privateIp = self.cuisine.net.getInfo(self.cuisine.net.nics[0])['ip'][0]

        C = r"""\
        mysql -h {dbhost} -u {dbuser} {dbpass} --port 3306 --execute "CREATE DATABASE owncloud"
        mysql -h {dbhost} -u {dbuser} {dbpass} --port 3306 --execute "CREATE USER 'owncloud'@'{ip}' IDENTIFIED BY 'owncloud'"
        mysql -h {dbhost} -u {dbuser} {dbpass} --port 3306 --execute "grant all on *.* to 'owncloud'@'{ip}'"
        """.format(dbhost=dbhost, dbuser=dbuser, dbpass=dbpass, ip=privateIp)

        self.cuisine.core.run(C)
        # TODO: if not installed
        cmd = """
        $JSAPPSDIR/php/bin/php $JSAPPSDIR/owncloud/occ maintenance:install  --database="mysql" --database-name="owncloud"\
        --database-host="{dbhost}" --database-user="owncloud" --database-pass="owncloud" --admin-user="admin" --admin-pass="admin"\
        --data-dir="/data"

        $JSAPPSDIR/php/bin/php $JSAPPSDIR/owncloud/occ config:system:set trusted_domains 1 --value={sitename}
        """.format(dbhost=dbhost, sitename=sitename)

        self.cuisine.core.run(cmd)

        if nginx:
            owncloudsiterules = self._get_default_conf_nginx_site()
            owncloudsiterules = owncloudsiterules % {"sitename": sitename}
            self._cuisine.core.file_write("$JSCFGDIR/nginx/etc/sites-enabled/{sitename}".format(sitename=sitename), content=owncloudsiterules)
            basicnginxconf = self._cuisine.apps.nginx.get_basic_nginx_conf()
            basicnginxconf = basicnginxconf.replace(
                "include $JSAPPSDIR/nginx/etc/sites-enabled/*;", "include $JSCFGDIR/nginx/etc/sites-enabled/*;")
            basicnginxconf = self.cuisine.core.replace(basicnginxconf)
            C = """
            chown -R www-data:www-data $JSAPPSDIR/owncloud $cfgDir/nginx
            chmod 777 -R $JSAPPSDIR/owncloud/config
            chown -R www-data:www-data /data
            """
            self.cuisine.core.execute_bash(C)
            self.cuisine.core.file_write("$JSCFGDIR/nginx/etc/nginx.conf", content=basicnginxconf)
            self.cuisine.processmanager.stop("nginx")
            self.cuisine.apps.nginx.start()
            self.cuisine.development.php.start()
        else:
            # APACHE CONF.
            apachesiteconf = self.cuisine.core.replace(self._get_apache_siteconf())
            apachesiteconf = apachesiteconf.format(ServerName=sitename)
            self.cuisine.core.dir_ensure("$JSCFGDIR/apache2/sites-enabled")
            self.cuisine.core.file_write("$JSCFGDIR/apache2/sites-enabled/owncloud.conf", apachesiteconf)
            self.cuisine.apps.apache2.stop()
            C = """
            chown -R daemon:daemon $JSAPPSDIR/owncloud
            chmod 777 -R $appDir/owncloud/config
            chown -R daemon:daemon /data
            """
            self.cuisine.core.execute_bash(C)
            #self.cuisine.development.php.start()
            self.cuisine.apps.apache2.start()

    def _get_apache_siteconf(self):
        conf = textwrap.dedent("""\

        Alias / "$JSAPPSDIR/owncloud/"

        <Directory $JSAPPSDIR/owncloud/>
          Options +FollowSymlinks
          AllowOverride All
          Require all granted
         <IfModule mod_dav.c>
          Dav off
         </IfModule>

         SetEnv HOME $JSAPPSDIR/owncloud/
             SetEnv HTTP_HOME $JSAPPSDIR/owncloud/
        </Directory>
        <VirtualHost *:80>
            ServerAdmin admin@there.com
            ServerName {ServerName}
            DocumentRoot $JSAPPSDIR/owncloud
            PHPINIDIR $JSAPPSDIR/php/lib/php.ini
        </VirtualHost>


        """)
        conf = re.sub(r"//", "/", conf)  #remove // in paths
        return conf

    def restart(self):
        pass

    def test(self):
        # TODO: *2
        # call the api up/download a file
        pass
