from JumpScale import j
from ActionDecorator import ActionDecorator


class actionrun(ActionDecorator):

    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.lua"


base = j.tools.cuisine.getBaseClass()


class CuisineLua(base):

    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    @actionrun(action=True)
    def install(self):
        """
        installs and builds geodns from github.com/abh/geodns
        """
        # deps
        self.cuisine.package.install("lua5.1", force=False)
        self.cuisine.package.install("luarocks", force=False)

        url = "https://raw.githubusercontent.com/zserge/luash/master/sh.lua"
        # check http://zserge.com/blog/luash.html
        # curl -L https://github.com/luvit/lit/raw/master/get-lit.sh | sh
        # luasec
        # curl
        # https://raw.githubusercontent.com/slembcke/debugger.lua/master/debugger.lua
        # > /usr/local/share/lua/5.1/debugger.lua

        self.package("luasocket")

    def install_lua_tarantool(self):
        C = """
        set -ex

        apt-get install -y git build-essential cmake lua5.1 liblua5.1-0-dev luarocks libssl-dev

        mkdir -p /opt/code/varia
        cd /opt/code/varia

        ## install tarantool from tarantool repo
        curl -s https://packagecloud.io/install/repositories/tarantool/1_7/script.deb.sh | sudo bash

        ## install tarantool
        sudo apt-get update
        sudo apt-get -y install tarantool tarantool-dev 
        #tarantool-luassl

        rm -rf tdb
        git clone --recursive https://github.com/Sulverus/tdb 
        cd tdb
        make 
        sudo make install prefix=/usr/share/tarantool/
        cd ..

        ## capnproto support
        apt-get install -y capnproto

        rm -rf luajit-2.0
        git clone http://luajit.org/git/luajit-2.0.git
        cd luajit-2.0/
        git checkout v2.1
        make && sudo make install
        ln -sf /usr/local/bin/luajit-2.1.0-beta2 /usr/local/bin/luajit

        luarocks install lua-capnproto
        luarocks install lua-cjson
        luarocks install penlight

        ## tarantool packages

        mkdir -p ~/.luarocks/
        cat > ~/.luarocks/config.lua <<EOF
        rocks_servers = {
            [[http://rocks.tarantool.org/]]
        }
        EOF

        luarocks install expirationd

        luarocks install http --local
        luarocks install  connpool
        luarocks install queue
        luarocks install shard
        # luarocks install spmon

        rm ~/.luarocks/config.lua

        cd /opt/code/varia

        ## install lua IPC library
        cd /opt/code/varia
        rm -rf lua-luaipc
        git clone https://github.com/siffiejoe/lua-luaipc.git
        cd lua-luaipc
        make LUA_INCDIR=/usr/include/lua5.1
        sudo make install DLL_INSTALL_DIR=/usr/local/lib/lua/5.1

        ## install lightningmdb
        cd /opt/code/varia
        rm -rf lmdb
        git clone https://github.com/LMDB/lmdb
        cd lmdb/libraries/liblmdb/
        make
        sudo make install

        sudo luarocks install lightningmdb
        """
        self.cuisine.core.run_script(C)

        # REQUIRED IN BASH
        # export LUA_PATH=$JSBASE/lib/lua/?.lua;./?.lua;$JSBASE/lib/lua/?/?.lua;$JSBASE/lib/lua/?/init.lua

    @actionrun(action=True)
    def package(self, name):
        #@todo need to check for e.g. openwrt
        self.cuisine.core.run("luarocks install %s" % name)

    # local socket = require("socket")
