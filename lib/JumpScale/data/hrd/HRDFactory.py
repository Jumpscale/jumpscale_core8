from JumpScale import j
# import JumpScale.baselib.codeexecutor
from HRD import HRD
from HRDTree import HRDTree
from HRDSchema import HRDSchema


class HRDFactory:

    def __init__(self):
        self.__jslocation__ = "j.data.hrd"
        self.logger = j.logger.get("j.data.hrd")

    def sanitize_key(self, key):
        """
        make sure the key of an HRD schema has a valid format for Capnp Schema
        e.g.:
            ssh.port becomes sshPort
        """
        return HRDSchema.sanitize_key(key)

    def getSchema(self, path=None, content=""):
        return HRDSchema(path=path, content=content)

    def get(self, path=None, content="", prefixWithName=True, keepformat=False, args={}, templates=[]):
        """
        @param path
        """
        if templates == "":
            templates = []
        if path is not None and j.sal.fs.isDir(path):
            if content != "":
                raise j.exceptions.Input(
                    "HRD of directory cannot be build with as input content (should be empty)")
            return HRDTree(path, prefixWithName=prefixWithName, keepformat=keepformat)
        else:
            return HRD(path=path, content=content, prefixWithName=prefixWithName,
                       keepformat=keepformat, args=args, templates=templates)

    def getHRDFromMongoObject(self, mongoObject, prefixRootObjectType=True):
        txt = j.data.serializer.serializers.hrd.dumps(mongoObject.to_dict())
        prefix = mongoObject._P__meta[2]
        out = ""
        for line in txt.split("\n"):
            if line.strip() == "":
                continue
            if line[0] == "_":
                continue
            if line.find("_meta.") != -1:
                continue
            if prefixRootObjectType:
                out += "%s.%s\n" % (prefix, line)
            else:
                out += "%s\n" % (line)
        return self.getHRDFromContent(out)

    def getHRDFromDict(self, ddict={}):
        hrd = self.get(content=" ", prefixWithName=False)
        for key, val in ddict.items():
            hrd.set(key, val)
        return hrd
