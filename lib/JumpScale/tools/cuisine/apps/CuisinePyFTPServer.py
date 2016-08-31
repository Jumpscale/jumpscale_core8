from JumpScale import j


base = j.tools.cuisine._getBaseClass()


class CuisinePyFTPServer(base):

    def install(self, root="/storage/ftpserver", config="", port=2121):
        self._cuisine.development.js8.install()
        self._cuisine.systemservices.ufw.ufw_enable()
        self._cuisine.systemservices.ufw.allowIncoming(port)

        cmd = "sudo ufw allow 50000:65535/tcp"
        self._cuisine.core.run(cmd)

        """
        example config
            config='''
                home:
                  guest2: ['123456']
                  root: ['1234', elradfmwM]
                public:
                  guest: ['123456']
                  anonymous: []
            '''
        key is subpath in rootpath
        then users who have access

        cannot have same user in multiple dirs (shortcoming for now, need to investigate)

        . is home dir for user

        to set specific permissions is 2e element of list


        permissions
        ```
        Read permissions:
        "e" = change directory (CWD, CDUP commands)
        "l" = list files (LIST, NLST, STAT, MLSD, MLST, SIZE commands)
        "r" = retrieve file from the server (RETR command)
        Write permissions:

        "a" = append data to an existing file (APPE command)
        "d" = delete file or directory (DELE, RMD commands)
        "f" = rename file or directory (RNFR, RNTO commands)
        "m" = create directory (MKD command)
        "w" = store a file to the server (STOR, STOU commands)
        "M" = change mode/permission (SITE CHMOD command)
        ```

        """

        # DEBUG
        # config='''
        # home:
        #   guest2: ['123456']
        #   root: ['1234', elradfmwM]
        # public:
        #   guest: ['123456']
        #   anonymous: []
        # '''

        self._cuisine.systemservices.base.install()
        self._cuisine.development.pip.install("pyftpdlib")

        self._cuisine.btrfs.subvolumeCreate(root)

        #
        #

        if config == "":
            authorizer = "    pyftpdlib.authorizers.UnixAuthorizer"
        else:
            authorizer = ""
            configmodel = j.data.serializer.yaml.loads(config)
            for key, obj in configmodel.items():
                self._cuisine.btrfs.subvolumeCreate(j.sal.fs.joinPaths(root, key))
                for user, obj2 in obj.items():
                    if user.lower() == "anonymous":
                        authorizer += "    authorizer.add_anonymous('%s')\n" % j.sal.fs.joinPaths(root, key)
                    else:
                        if len(obj2) == 1:
                            # no rights
                            rights = "elradfmwM"
                            secret = obj2[0]
                        elif len(obj2) == 2:
                            secret, rights = obj2
                        else:
                            raise j.exceptions.Input("wrong format in ftp config:%s, for user:%s" % (config, user))
                        authorizer += "    authorizer.add_user('%s', '%s', '%s', perm='%s')\n" % (user,
                                                                                                  secret, j.sal.fs.joinPaths(root, key), rights)

        C = """
        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.handlers import FTPHandler
        from pyftpdlib.servers import FTPServer

        def main():
            # Instantiate a dummy authorizer for managing 'virtual' users
            authorizer = DummyAuthorizer()

            # Define a new user having full r/w permissions and a read-only
            # anonymous user
        $authorizers

            # Instantiate FTP handler class
            handler = FTPHandler
            handler.authorizer = authorizer

            # Define a customized banner (string returned when client connects)
            handler.banner = "ftpd ready."

            # Specify a masquerade address and the range of ports to use for
            # passive connections.  Decomment in case you're behind a NAT.
            #handler.masquerade_address = '151.25.42.11'
            handler.passive_ports = range(60000, 65535)

            # Instantiate FTP server class and listen on 0.0.0.0:2121
            address = ('0.0.0.0', $port)
            server = FTPServer(address, handler)

            # set a limit for connections
            server.max_cons = 256
            server.max_cons_per_ip = 20

            # start ftp server
            server.serve_forever()

        if __name__ == '__main__':
            main()
        """
        C = j.data.text.strip(C)

        C = C.replace("$port", str(port))
        C = C.replace("$authorizers", authorizer)

        self._cuisine.core.dir_ensure("/etc/ftpserver")

        self._cuisine.core.file_write("/etc/ftpserver/start.py", C)

        self._cuisine.processmanager.ensure("polipo", cmd)

        self._cuisine.processmanager.ensure("pyftpserver", "python3 /etc/ftpserver/start.py")
