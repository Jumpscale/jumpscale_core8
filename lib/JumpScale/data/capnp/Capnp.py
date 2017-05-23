
from JumpScale import j
import sys
import os
import capnp
from collections import OrderedDict
import capnp
from ModelBase import *
# from ModelBase1 import *


class Tools():

    def listInDictCreation(self, listInDict, name, manipulateDef=None):
        """
        check name exist in the dict
        then check its a dict, if yes walk over it and make sure they become strings or use the manipulateDef function
        string 'a,b,c' gets translated to list
        @param manipulateDef if None then will make it a string, could be e.g. int if you want to have all elements to be converted to int
        """
        if name in listInDict:
            if j.data.types.list.check(listInDict[name]):
                if manipulateDef is None:
                    listInDict[name] = [str(item).strip() for item in listInDict[name]]
                else:
                    listInDict[name] = [manipulateDef(item) for item in listInDict[name]]
            else:
                if manipulateDef is None:
                    if "," in str(listInDict[name]):
                        listInDict[name] = [item.strip()
                                            for item in listInDict[name].split(",") if item.strip() != ""]
                    else:
                        listInDict[name] = [str(listInDict[name])]
                else:
                    listInDict[name] = [manipulateDef(listInDict[name])]
        return listInDict


class Capnp:
    """
    """

    def __init__(self):
        self.__jslocation__ = "j.data.capnp"
        self._cache = {}
        self._capnpVarDir = j.sal.fs.joinPaths(j.dirs.VARDIR, "capnp")
        j.sal.fs.createDir(self._capnpVarDir)
        if self._capnpVarDir not in sys.path:
            sys.path.append(self._capnpVarDir)
        self.tools = Tools()

    def getModelBaseClass(self):
        return ModelBase

    def getModelBaseClassWithData(self):
        return ModelBaseWithData

    def getModelBaseClassCollection(self):
        return ModelBaseCollection

    def getModelCollection(self, schema, category, namespace=None, modelBaseClass=None,
                           modelBaseCollectionClass=None, db=None, indexDb=None):
        """
        @param schema is capnp_schema

        example to use:
            ```
            #if we use a modelBaseClass do something like
            ModelBaseWithData = j.data.capnp.getModelBaseClass()
            class MyModelBase(ModelBaseWithData):
                def index(self):
                    # put indexes in db as specified
                    ind = "%s" % (self.dbobj.path)
                    self._index.index({ind: self.key})


            import capnp
            #there is model.capnp in $libdir/JumpScale/tools/issuemanager
            from JumpScale.tools.issuemanager import model as ModelCapnp

            mydb=j.servers.kvs.getMemoryStore(name="mymemdb")

            collection=j.data.capnp.getModelCollection(schema=ModelCapnp,category="issue",modelBaseClass=MyModelBase,db=mydb,indexDb=mydb)

            ```
        """
        if modelBaseCollectionClass is None:
            modelBaseCollectionClass = ModelBaseCollection

        return modelBaseCollectionClass(schema=schema, category=category, namespace=namespace,
                                        db=db, indexDb=indexDb, modelBaseClass=modelBaseClass)

    def getId(self, schemaInText):
        id = [item for item in schemaInText.split("\n") if item.strip() != ""][0][3:-1]
        return id

    def _getSchemas(self, schemaInText):
        schemaInText = j.data.text.strip(schemaInText)
        schemaInText = schemaInText.strip() + "\n"
        schemaId = self.getId(schemaInText)
        if schemaId not in self._cache:
            nameOnFS = "schema_%s.capnp" % (schemaId)
            path = j.sal.fs.joinPaths(self._capnpVarDir, nameOnFS)
            j.sal.fs.writeFile(filename=path, contents=schemaInText, append=False)
            parser = capnp.SchemaParser()
            schema = parser.load(path)
            self._cache[schemaId] = schema
        return self._cache[schemaId]

    def getSchemaFromText(self, schemaInText, name="Schema"):
        if not schemaInText.strip():
            schemaInText = """
@%s;
struct Schema {

}
""" % j.data.idgenerator.generateCapnpID()
        schemas = self._getSchemas(schemaInText)
        schema = eval("schemas.%s" % name)
        return schema

    def getSchemaFromPath(self, path, name):
        """
        @param path is path to schema
        """
        content = j.sal.fs.fileGetContents(path)
        return self.getSchemaFromText(schemaInText=content, name=name)

    def _ensure_dict(self, args):
        """
        make sure the argument schema are of the type dict
        capnp doesn't handle building a message with OrderedDict properly
        """
        if isinstance(args, OrderedDict):
            args = dict(args)
            for k, v in args.items():
                args[k] = self._ensure_dict(v)
        if isinstance(args, list):
            for i, v in enumerate(args):
                args.insert(i, self._ensure_dict(v))
                args.pop(i+1)
        return args

    def getObj(self, schemaInText, name="Schema", args={}, binaryData=None):

        # . are removed from . to Uppercase
        args = args.copy()  # to not change the args passed in argument
        for key in list(args.keys()):
            sanitize_key = j.data.hrd.sanitize_key(key)
            if key != sanitize_key:
                args[sanitize_key] = args[key]
                args.pop(key)

        schema = self.getSchemaFromText(schemaInText, name=name)

        if binaryData is not None and binaryData != b'':
            obj = schema.from_bytes_packed(binaryData).as_builder()
        else:
            try:
                args = self._ensure_dict(args)
                obj = schema.new_message(**args)
            except Exception as e:
                if str(e).find("has no such member") != -1:
                    msg = "cannot create data for schema from arguments, property missing\n"
                    msg += "arguments:\n%s\n" % j.data.serializer.json.dumps(args, sort_keys=True, indent=True)
                    msg += "schema:\n%s" % schemaInText
                    ee = str(e).split("stack:")[0]
                    ee = ee.split("failed:")[1]
                    msg += "capnperror:%s" % ee
                    print(msg)
                    raise j.exceptions.Input(message=msg, level=1, source="", tags="", msgpub="")
                if str(e).find("Value type mismatch") != -1:
                    msg = "cannot create data for schema from arguments, value type mismatch.\n"
                    msg += "arguments:\n%s\n" % j.data.serializer.json.dumps(args, sort_keys=True, indent=True)
                    msg += "schema:\n%s" % schemaInText
                    ee = str(e).split("stack:")[0]
                    ee = ee.split("failed:")[1]
                    msg += "capnperror:%s" % ee
                    print(msg)
                    raise j.exceptions.Input(message=msg, level=1, source="", tags="", msgpub="")
                raise e

        return obj

    def test(self):
        import time
        capnpschema = '''
        @0x93c1ac9f09464fc9;

        struct Issue {

          state @0 :State;
          enum State {
            new @0;
            ok @1;
            error @2;
            disabled @3;
          }

          #name of actor e.g. node.ssh (role is the first part of it)
          name @1 :Text;

        }
        '''

        # dummy test, not used later
        obj = self.getObj(capnpschema, name="Issue")
        obj.state = "ok"

        # now we just get the capnp schema for this object
        schema = self.getSchemaFromText(capnpschema, name="Issue")

        # mydb = j.servers.kvs.getRedisStore(name="mymemdb")
        mydb = None  # is memory

        collection = self.getModelCollection(schema, category="test", modelBaseClass=None, db=mydb, indexDb=mydb)
        start = time.time()
        print("start populate 100.000 records")
        for i in range(100000):
            obj = collection.new()
            obj.dbobj.name = "test%s" % i
            obj.save()

        print("population done")
        end_populate = time.time()
        collection.logger.disabled = False

        print(collection.find(name="test839"))
        end_find = time.time()
        print("population in %.2fs" % (end_populate - start))
        print("find in %.2fs" % (end_find - end_populate))

    def testWithRedis(self):
        capnpschema = '''
        @0x93c1ac9f09464fc9;
        struct Issue {
          state @0 :State;
          enum State {
            new @0;
            ok @1;
            error @2;
            disabled @3;
          }
          #name of actor e.g. node.ssh (role is the first part of it)
          name @1 :Text;
          tlist @2: List(Text);
          olist @3: List(Issue2);
          struct Issue2 {
              state @0 :State;
              enum State {
                new @0;
                ok @1;
                error @2;
                disabled @3;
              }
              text @1: Text;
          }
        }
        '''
        # mydb = j.servers.kvs.getRedisStore("test")
        mydb = j.servers.kvs.getRedisStore(name="test", unixsocket="%s/redis.sock" % j.dirs.TMPDIR)
        schema = self.getSchemaFromText(capnpschema, name="Issue")
        collection = self.getModelCollection(schema, category="test", modelBaseClass=None, db=mydb, indexDb=mydb)
        for i in range(100):
            obj = collection.new()
            obj.dbobj.name = "test%s" % i
            obj.save()
        print(collection.list())

        subobj = collection.list_olist_constructor(state="new", text="something")
        obj.addSubItem("olist", subobj)

        subobj = collection.list_tlist_constructor("sometext")
        obj.addSubItem(name="tlist", data=subobj)
        obj.addSubItem(name="tlist", data="sometext2")

        print(obj)

        obj.initSubItem("tlist")
        assert len(obj.list_tlist) == 2

        obj.addSubItem(name="tlist", data="sometext3")
        assert len(obj.list_tlist) == 3

        obj.reSerialize()

    def getJSON(self, obj):
        configdata2 = obj.to_dict()
        ddict2 = OrderedDict(configdata2)
        return j.data.serializer.json.dumps(ddict2, sort_keys=True, indent=True)

    def getBinaryData(self, obj):
        return obj.to_bytes_packed()

    def getMemoryObj(self, schema, *args, **kwargs):
        """
        creates an object similar as a capnp message but without the constraint of the capnpn on the type and list.
        Use this to store capnp object in memory instead of using directly capnp object
        It will be converted in capnp message when saved
        """
        msg = schema.new_message(**kwargs)
        obj = MemoryObject(msg.to_dict(verbose=True), schema=schema)
        return obj
