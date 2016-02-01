
from JumpScale import j

from ActionDecorator import ActionDecorator
class actionrun(ActionDecorator):
    def __init__(self,*args,**kwargs):
        ActionDecorator.__init__(self,*args,**kwargs)
        self.selfobjCode="cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.pip"


class CuisinePIP():

    def __init__(self,executor,cuisine):
        self.executor=executor
        self.cuisine=cuisine


    # -----------------------------------------------------------------------------
    # PIP PYTHON PACKAGE MANAGER
    # -----------------------------------------------------------------------------

    @actionrun(action=True)
    def upgrade(self,package):
        '''
        The "package" argument, defines the name of the package that will be upgraded.
        '''
        self.cuisine.run('pip3 install --upgrade %s' % (package))

    @actionrun(action=True)
    def install(self,package=None,upgrade=False):
        '''
        The "package" argument, defines the name of the package that will be installed.
        '''
        cmd="pip3 install %s"%package
        if upgrade:
            cmd+=" --upgrade"
        self.cuisine.run(cmd)

    @actionrun()
    def remove(self,package):
        '''
        The "package" argument, defines the name of the package that will be ensured.
        The argument "r" referes to the requirements file that will be used by pip and
        is equivalent to the "-r" parameter of pip.
        Either "package" or "r" needs to be provided
        '''
        return self.cuisine.run('pip3 uninstall %s' %(package))

    @actionrun()
    def multiInstall(self,packagelist,upgrade=False):
        """
        @param packagelist is text file and each line is name of package
        can also be list @todo

        e.g.
            # influxdb
            # ipdb
            # ipython
            # ipython-genutils
            itsdangerous
            Jinja2
            # marisa-trie
            MarkupSafe
            mimeparse
            mongoengine

        @param runid, if specified actions will be used to execute
        """
        for dep in packagelist.split("\n"):
            dep=dep.strip()
            if dep.strip()=="":
                continue
            if dep.strip()[0]=="#":
                continue
            dep=dep.split("=",1)[0]
            self.install(dep,upgrade)



        
