from JumpScale import j
from time import sleep


app = j.tools.cuisine._getBaseAppClass()


class CuisineS3Server(app):
    NAME = 's3server'

    def install(self, start=False, storageLocation="/data/", metaLocation="/meta/"):
        """
        put backing store on /storage/...
        """
        self.cuisine.package.mdupdate()
        self.cuisine.package.install('build-essential')
        self.cuisine.package.install('python2.7')
        self.cuisine.core.dir_ensure(storageLocation)
        self.cuisine.core.dir_ensure(metaLocation)

        self.cuisine.core.dir_ensure('/opt/code/github/scality')
        path = self.cuisine.development.git.pullRepo('https://github.com/scality/S3.git', ssh=False)
        profile = self.cuisine.bash.profileDefault
        profile.addPath(self.cuisine.core.dir_paths['BINDIR'])
        profile.save()
        self.cuisine.apps.nodejs.install()
        self.cuisine.core.run('cd {} && npm install --python=python2.7'.format(path), profile=True)
        self.cuisine.core.dir_remove('$JSAPPSDIR/S3', recursive=True)
        self.cuisine.core.dir_ensure('$JSAPPSDIR')
        self.cuisine.core.run('mv {} $JSAPPSDIR/'.format(path))

        cmd = 'S3DATAPATH={data} S3METADATAPATH={meta} npm start'.format(
            data=storageLocation,
            meta=metaLocation,
        )

        content = self.cuisine.core.file_read('$JSAPPSDIR/S3/package.json')
        pkg = j.data.serializer.json.loads(content)
        pkg['scripts']['start_location'] = cmd

        content = j.data.serializer.json.dumps(pkg, indent=True)
        self.cuisine.core.file_write('$JSAPPSDIR/S3/package.json', content)

        if start:
            self.start()

    def start(self, name=NAME):
        nodePath = '$BASEDIR/node/lib/node_modules'
        # Temporary. Should be removed after updating the building process
        self.cuisine.core.dir_ensure('/data/data')
        self.cuisine.core.dir_ensure('/data/meta')
        # Temporary. npm install should be added to install() function after updating the building process
        if not self.cuisine.core.dir_exists('%s/npm-run-all' % nodePath):
            self.cuisine.core.run('npm install npm-run-all')
        nodePath = self.cuisine.core.replace('$BASEDIR/node/lib/node_modules/s3/node_modules:%s' % nodePath)
        if self.cuisine.bash.profileDefault.envGet('NODE_PATH') != nodePath:
            self.cuisine.bash.profileDefault.envSet("NODE_PATH", nodePath)
            self.cuisine.bash.profileDefault.addPath(self.cuisine.core.replace("$BASEDIR/node/bin/"))
            self.cuisine.bash.profileDefault.save()
        path = j.sal.fs.joinPaths(j.dirs.JSAPPSDIR, 'S3')
        self.cuisine.core.run('cd {} && npm run start_location'.format(path), profile=True)

    def test(self):
        # put/get file over S3 interface using a python S3 lib
        raise NotImplementedError
