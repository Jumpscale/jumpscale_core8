from JumpScale import j

CATEGORY = "ays:bp"


def log(msg, level=2):
    j.logger.log(msg, level=level, category=CATEGORY)


class Blueprint(object):
    """
    """

    def __init__(self, path):
        self.path=path
        self.models=[]
        self._contentblocks=[]
        content=""
        content0=j.do.readFile(path)
        nr=0
        #we need to do all this work because the yaml parsing does not maintain order because its a dict
        for line in content0.split("\n"):
            if len(line)>0 and line[0]=="#":
                continue
            if content=="" and line.strip()=="":
                continue

            line=line.replace("\t","    ")
            nr+=1
            if len(content)>0 and (len(line)>0 and line[0]!=" "):
                self._add2models(content,nr)
                content=""

            content+="%s\n"%line

        self._add2models(content,nr)
        self._contentblocks=[]

        self.content=content0

    def loadrecipes(self):
        for model in self.models:
            if model!=None:
                for key,item in model.items():
                    aysname,aysinstance=key.split("_",1)
                    j.atyourservice.getRecipe(name=aysname)

    def execute(self):
        for model in self.models:
            if model is not None:
                for key, item in model.items():
                    # print ("blueprint model execute:%s %s"%(key,item))
                    aysname, aysinstance = key.split("_", 1)
                    r = j.atyourservice.getRecipe(name=aysname)
                    r.newInstance(instance=aysinstance, args=item, yaml=model)

    def _add2models(self,content,nr):
        #make sure we don't process double
        if content in self._contentblocks:
            return
        self._contentblocks.append(content)
        try:
            model=j.data.serializer.yaml.loads(content)
        except Exception as e:
            msg="Could not process blueprint: '%s', line: '%s', content '%s'\nerror:%s"%(self.path,nr,content,e)
            raise RuntimeError(msg)

        self.models.append(model)

    def __str__(self):
        return str(self.content)

    __repr__=__str__
