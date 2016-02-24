from JumpScale import j

class ALog():
    """
    actionlog

    format of log is


    RUN
    ===
    R | $epoch | $runid | $hrtime
    A | $epoch | $role!$instance | $actionname | $state
    G | $epoch | $cat   | $githash
    L | $epoch | $level $cat | $msg
    L | $epoch | $cat   | $msg

    R stands for RUN & has unique id
    each action has id

    A stands for action

    L stands for Log

    G stands for GIT action with cat e.g. init, deploy, ...

    multiline messages are possible, they will just reuse their id

    """
    def __init__(self,category):
        if category.strip()=="":
            raise RuntimeError("category cannot be empty")
        self.category=category
        self.path=j.sal.fs.joinPaths(j.atyourservice.basepath,"alog","%s.alog"%category)
        j.sal.fs.createDir(j.sal.fs.joinPaths(j.atyourservice.basepath,"alog"))

        self.lastGitRef={} #key = action used to log the git hash
        self.lastRunId=0
        self.lastRunEpoch=0

        self.changecache={}


        if not j.sal.fs.exists(self.path):
            j.sal.fs.writeFile(self.path,"")
            self.newRun()
        else:
            self.read()



    def newRun(self,action="unknown"):
        self.lastRunId+=1
        self._append("R | %-8s | %-8s | %-10s | %s"%(j.data.time.getTimeEpoch(),self.lastRunId,action,j.data.time.getLocalTimeHR()))
        return self.lastRunId

    def newGitCommit(self,action,githash=""):
        if githash=="":
            git=j.clients.git.get()
            githash=git.getCommitRefs()[0][1]
        self._append("G | %-8s | %-8s | %s"%(j.data.time.getTimeEpoch(),action,githash))

    def newAction(self,service,action,state="INIT",logonly=False):
        self._append("A | %-8s | %-20s | %-8s | %s"%(j.data.time.getTimeEpoch(),service.shortkey,action,state),logonly=logonly)


    def log(self,msg,level=5,cat=""):
        for item in  msg.strip().splitlines():
            self._append("L | %-8s | %-8s | %s"%(j.data.time.getTimeEpoch(),level,item),logonly=True)

    def _append(self,msg,logonly=False):
        msg=msg.strip()
        if len(msg)==0:
            return
        line=msg+"\n"
        j.sal.fs.writeFile(self.path, line, append=True)
        if not logonly:
            self._processLine(line=msg)

    def getLastRef(self,action="install"):
        if action in self.lastGitRef:
            lastref=self.lastGitRef[action]
        else:
            # if action!="init":
            #     lastref=self.getLastRef("init")
            # else:
            lastref=""
        return lastref

    def getChangedFiles(self,action="install"):
        git=j.clients.git.get()
        changes=git.getChangedFiles(fromref=self.getLastRef(action))
        changes=[item for item in changes if j.sal.fs.exists(j.sal.fs.joinPaths(git.baseDir,item))]  #we will have to do something for deletes here
        changes.sort()
        return changes

    def getChangedAtYourservices(self,action="install"):
        """
        return (changed,changes)
        changed is list of all changed aysi or ays

        """
        if action in self.changecache:
            return self.changecache[action]

        changed=[]
        changes={}
        for path in self.getChangedFiles(action):
            if path.find("/services/")!=-1 or path.find("/recipes/")!=-1:
                if path.find("/services/")!=-1:
                    ttype="services"
                else:
                    ttype="recipes"

                path0=path.split("/%s/"%ttype,1)[1]
                basename=j.sal.fs.getBaseName(path0)
                path1=path0.replace(basename,"").strip("/")
                key=path1.split("/")[-1]

                if ttype=="services":
                    keys=[key]
                else:
                    keys=[]
                    for aysi in j.atyourservice.findServices(role=key):
                        keys.append(aysi.shortkey)

                for key in keys:
                    # print ("get changed ays for key:%s"%key)
                    role,instance=key.split("!")
                    aysi=j.atyourservice.getService(role,instance)
                    if basename not in changes:
                        changes[basename]=[]
                    changes[basename].append(aysi)
                    if aysi not in changed:
                        changed.append(aysi)

        self.changecache[action]=(changed,changes)

        return changed,changes

    def _processLine(self,line):
        cat,line1=line.split("|",1)
        cat=cat.strip()
        if cat=="R":
            epoch,runid,remaining=line1.split("|",2)
            self.lastRunId=int(runid)
            self.lastRunEpoch=int(epoch)
            return

        if cat =="G":
            epoch,gitcat,githash=[item.strip() for item in line1.split("|",3)]
            self.lastGitRef[gitcat]=githash
            return

        if cat=="A":
            line1.split("|")
            epoch,servicekey,action,state=[item.strip() for item in line1.split("|")]
            role,instance=servicekey.split("!")
            service=j.atyourservice.getService(role=role, instance=instance)
            service._setAction(name=action,epoch=int(epoch),state=state,log=False)
            return

    def removeLastRun(self):
        self.removeRun(self.lastRunId)

    def removeRun(self,id):

        C=j.sal.fs.fileGetContents(self.path)
        path2=self.path+"_"
        j.sal.fs.writeFile(path2,"")
        for line in C.split("\n"):
            if line.strip()=="" or line.startswith("=="):
                continue
            cat,line1=line.split("|",1)
            cat=cat.strip()
            if cat=="R":
                epoch,runid,remaining=line1.split("|",2)
                if int(runid)==id:
                    #found end
                    j.sal.fs.moveFile(path2,self.path)
                    return

            j.sal.fs.writeFile(path2,line+"\n",append=True)



    def read(self):

        C=j.sal.fs.fileGetContents(self.path)

        for line in C.split("\n"):

            if line.strip()=="" or line.startswith("=="):
                continue

            self._processLine(line)
