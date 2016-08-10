
import msgpack
from SerializerBase import *


class SerializerMSGPack(SerializerBase):

    def __init__(self):
        self.__jslocation__ = "j.data.serializer.msgpack"

    def dumps(self, obj):
        return msgpack.packb(obj)

    def loads(self, s):
        return msgpack.unpackb(s)
