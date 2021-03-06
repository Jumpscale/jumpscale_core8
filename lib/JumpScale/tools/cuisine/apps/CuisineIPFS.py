from JumpScale import j


app = j.tools.cuisine._getBaseAppClass()


class CuisineIPFS(app):
    NAME = "ipfs"

    def __init__(self, executor, cuisine):
        self._executor = executor
        self._cuisine = cuisine

    def install(self, name='main', reset=False):
        if reset is False and self.isInstalled():
            return

        if self._cuisine.platformtype.isLinux():
            url = "https://dist.ipfs.io/go-ipfs/v0.4.4/go-ipfs_v0.4.4_linux-amd64.tar.gz"
        elif "darwin" in self._cuisine.platformtype.osname:
            url = "https://dist.ipfs.io/go-ipfs/v0.4.4/go-ipfs_v0.4.4_darwin-amd64.tar.gz"

        name = url.split('/')[-1]
        compress_path = self._cuisine.core.args_replace('$tmpDir/{}'.format(name))
        self._cuisine.core.file_download(url, compress_path)

        uncompress_path = self._cuisine.core.args_replace('$tmpDir/go-ipfs')
        if self._cuisine.core.file_exists(uncompress_path):
            self._cuisine.core.dir_remove(uncompress_path)

        self._cuisine.core.run("cd $tmpDir; tar xvf {}".format(name))
        self._cuisine.core.file_copy('{}/ipfs'.format(uncompress_path), '$binDir/ipfs')

    def uninstall(self):
        """
        remove ipfs binary from $binDir
        """
        if self._cuisine.core.file_exists('$binDir/ipfs'):
            self._cuisine.core.file_unlink('$binDir/ipfs')


    def start(self, name='main', readonly=False):
        cfg_dir = '$cfgDir/ipfs/{}'.format(name)
        if not self._cuisine.core.file_exists(cfg_dir):
            self._cuisine.core.dir_ensure(cfg_dir)

        # check if the ipfs repo has not been created yet.
        if not self._cuisine.core.file_exists(cfg_dir+'/config'):
            cmd = 'IPFS_PATH={} $binDir/ipfs init'.format(cfg_dir)
            self._cuisine.core.run(cmd)

        cmd = '$binDir/ipfs daemon --init'
        if not readonly:
            cmd += '  --writable'

        self._cuisine.processmanager.ensure(
            name='ipfs_{}'.format(name),
            cmd=cmd,
            path=cfg_dir,
            env={'IPFS_PATH': cfg_dir}
        )

    def stop(self, name='main'):
        self._cuisine.processmanager.stop(name='ipfs_{}'.format(name))
