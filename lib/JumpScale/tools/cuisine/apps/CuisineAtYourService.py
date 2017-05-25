from JumpScale import j
from time import sleep


base = j.tools.cuisine._getBaseClass()


class CuisineAtYourService(base):

    def configure(self, production=False, client_secret='', client_id='', organization='', redirect_address='locahost:5000'):
        C = """
        production: {}
        oauth:
           jwt_key: "-----BEGIN PUBLIC KEY-----\\nMHYwEAYHKoZIzj0CAQYFK4EEACIDYgAES5X8XrfKdx9gYayFITc89wad4usrk0n2\\n7MjiGYvqalizeSWTHEpnd7oea9IQ8T5oJjMVH5cc0H5tFSKilFFeh//wngxIyny6\\n6+Vq5t5B0V0Ehy01+2ceEon2Y0XDkIKv\\n-----END PUBLIC KEY-----\\n"
           client_secret: "{}"
           redirect_uri: "http://{}"
           client_id: "{}"
           organization: "{}"
        """.format(production, client_secret, redirect_address, client_id, organization)
        self.core.file_write("$JSCFGDIR/ays.yaml", C)


    def install(self):
        self.cuisine.development.pip.multiInstall([
            'sanic>=0.5.2',
            'jsonschema'
        ])

        base_dir = j.sal.fs.joinPaths('$JSAPPSDIR','atyourservice')

        self.cuisine.core.dir_ensure(base_dir)

        # link apidocs and index.html
        self.cuisine.core.file_link(
            j.sal.fs.joinPaths('$CODEDIR', 'github/jumpscale/jumpscale_core8/apps/atyourservice/apidocs'),
            j.sal.fs.joinPaths(base_dir,'apidocs')
        )

        self.cuisine.core.file_link(
            j.sal.fs.joinPaths('$CODEDIR', 'github/jumpscale/jumpscale_core8/apps/atyourservice/index.html'),
            j.sal.fs.joinPaths(base_dir,'index.html')
        )

        self.cuisine.core.file_link(
            j.sal.fs.joinPaths('$CODEDIR', 'github/jumpscale/jumpscale_core8/apps/atyourservice/main.py'),
            j.sal.fs.joinPaths(base_dir,'main.py')
        )

    def start(self, host='localhost', port=5000):
        cmd = 'cd $JSAPPSDIR/atyourservice; jspython main.py -h {host} -p {port}'.format(host=host, port=port)
        self.cuisine.processmanager.ensure(name='atyourservice', cmd=cmd)

    def stop(self):
        self.cuisine.processmanager.stop(name='atyourservice')
