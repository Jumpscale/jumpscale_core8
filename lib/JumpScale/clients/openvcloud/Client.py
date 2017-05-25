from JumpScale import j
from JumpScale.clients.portal.PortalClient import ApiError
import time
import datetime
import os
import requests

def refresh_jwt(jwt, payload):
    if payload['iss'] == 'itsyouonline':
        refreshurl = "https://itsyou.online/v1/oauth/jwt/refresh"
        response = requests.get(refreshurl, headers={'Authorization': 'bearer {}'.format(jwt)})
        if response.ok:
            return response.text
        else:
            raise RuntimeError("Failed to refresh JWT eror: {}:{}".format(response.status_code, response.text))
        pass
    else:
        raise RuntimeError('Refresh JWT with issuers {} not support'.format(payload['iss']))


class Factory:

    def __init__(self):
        self.__jslocation__ = "j.clients.openvcloud"

    def get(self, url, login=None, password=None, secret=None, port=443, jwt=None):
        cl = Client(url, login, password, secret, port, jwt)
        return cl

    def getFromService(self, service):
        return self.get(
            url=service.model.data.url,
            login=service.model.data.login,
            password=service.model.data.password,
            jwt=service.model.data.jwt,
            port=service.model.data.port)


def patchMS1(api):

    def patchmethod(method, argmap):
        def wrapper(**kwargs):
            for oldkey, newkey in argmap.items():
                if oldkey in kwargs:
                    value = kwargs.pop(oldkey)
                    kwargs[newkey] = value
            return method(**kwargs)
        wrapper.__doc__ = method.__doc__
        return wrapper

    api.cloudapi.portforwarding.list = patchmethod(
        api.cloudapi.portforwarding.list, {'cloudspaceId': 'cloudspaceid'})
    api.cloudapi.portforwarding.delete = patchmethod(
        api.cloudapi.portforwarding.delete, {'cloudspaceId': 'cloudspaceid'})
    api.cloudapi.portforwarding.create = patchmethod(api.cloudapi.portforwarding.create,
                                                     {'cloudspaceId': 'cloudspaceid', 'machineId': 'vmid'})


class Client:

    def __init__(self, url, login, password=None, secret=None, port=443, jwt=None):
        if not password and not secret and not jwt:
            raise ValueError("Can not connect to openvcloud without either password, secret or jwt")
        self._url = url
        self._login = login
        self._password = password
        self._secret = secret
        self._jwt = jwt
        self.api = j.clients.portal.get(url, port)
        # patch handle the case where the connection dies because of inactivity
        self.__patch_portal_client(self.api)

        self._isms1 = 'mothership1' in url
        self.__login(password, secret, jwt)
        if self._isms1:
            jsonpath = os.path.join(os.path.dirname(__file__), 'ms1.json')
            self.api.load_swagger(file=jsonpath, group='cloudapi')
            patchMS1(self.api)
        else:
            self.api.load_swagger(group='cloudapi')


    def __patch_portal_client(self, api):
        # try to relogin in the case the connection is dead because of
        # inactivity
        origcall = api.__call__

        def patch_call(that, *args, **kwargs):
            try:
                return origcall(that, *args, **kwargs)
            except ApiError:
                if ApiError.response.status_code == 419:
                    self.__login(self._password, self._secret, self._jwt)
                    return origcall(that, *args, **kwargs)
                raise

        api.__call__ = patch_call

    def __login(self, password, secret, jwt):
        if not password and not secret and not jwt:
            raise RuntimeError("Can not connect to openvcloud without either password, secret or jwt")
        if jwt:
            import jose.jwt
            payload = jose.jwt.get_unverified_claims(jwt)
            if payload['exp'] < time.time():
                jwt = refresh_jwt(jwt, payload)
            self.api._session.headers['Authorization'] = 'bearer {}'.format(jwt)
            self._login = payload['username']
        else:
            if password:
                if self._isms1:
                    secret = self.api.cloudapi.users.authenticate(
                        username=self._login, password=password)
                else:
                    secret = self.api.system.usermanager.authenticate(
                        name=self._login, secret=password)
            # make sure cookies are empty, clear guest cookie
            self.api._session.cookies.clear()
            self.api._session.cookies['beaker.session.id'] = secret

    @property
    def accounts(self):
        ovc_accounts = self.api.cloudapi.accounts.list()
        accounts = list()
        for account in ovc_accounts:
            accounts.append(Account(self, account))
        return accounts

    @property
    def locations(self):
        return self.api.cloudapi.locations.list()

    def account_get(self, name, create=True,
                    maxMemoryCapacity=-1, maxVDiskCapacity=-1, maxCPUCapacity=-1, maxNASCapacity=-1,
                    maxNetworkOptTransfer=-1, maxNetworkPeerTransfer=-1, maxNumPublicIP=-1):
        for account in self.accounts:
            if account.model['name'] == name:
                return account
        else:
            if create is False:
                raise KeyError("No account with name \"%s\" found" % name)
            self.api.cloudbroker.account.create(username=self.login,
                                                name=name,
                                                maxMemoryCapacity=maxMemoryCapacity,
                                                maxVDiskCapacity=maxVDiskCapacity,
                                                maxCPUCapacity=maxCPUCapacity,
                                                maxNASCapacity=maxNASCapacity,
                                                maxNetworkOptTransfer=maxNetworkOptTransfer,
                                                maxNetworkPeerTransfer=maxNetworkPeerTransfer,
                                                maxNumPublicIP=maxNumPublicIP)
            return self.account_get(name, False)


    @property
    def login(self):
        return self._login

    def __repr__(self):
        return "openvcloud client: %s" % self._url

    __str__ = __repr__


class Authorizables:

    @property
    def owners(self):
        _owners = []
        for user in self.model['acl']:
            if not user['canBeDeleted']:
                _owners.append(user['userGroupId'])
        return _owners

    @property
    def authorized_users(self):
        return [u['userGroupId'] for u in self.model['acl']]

    def authorize_user(self, username, right="ACDRUX"):
        if username not in self.authorized_users:
            self._addUser(username, right)
            self.refresh()
        return True

    def unauthorize_user(self, username):
        canBeDeleted = [u['userGroupId'] for u in self.model['acl'] if u.get('canBeDeleted', True) is True]
        if username in self.authorized_users and username in canBeDeleted:
            self._deleteUser(username)
            self.refresh()
        return True


class Account(Authorizables):

    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.id = model['id']

    @property
    def spaces(self):
        ovc_spaces = self.client.api.cloudapi.cloudspaces.list()
        spaces = list()
        for space in ovc_spaces:
            if space['accountId'] == self.model['id']:
                spaces.append(Space(self, space))
        return spaces

    @property
    def disks(self):
        """
        Wrapper to list all disks related to an account
        :return: list of disks details
        """
        return self.client.api.cloudapi.disks.list(accountId=self.id)

    def delete_disk(self, disk_id, detach=True):
        """
        Wrapper to delete disk by its id. I think there should be a class for disks to list all its wrappers
        :param disk_id: integer: The disk id need to be removed 
        :param detach: boolean: detach the disk from the machine first 
        :return: 
        """
        return self.client.api.cloudapi.disks.delete(diskId=disk_id, detach=detach)

    def space_get(self, name, location="", create=True,
                  maxMemoryCapacity=-1, maxVDiskCapacity=-1, maxCPUCapacity=-1, maxNASCapacity=-1,
                  maxNetworkOptTransfer=-1, maxNetworkPeerTransfer=-1, maxNumPublicIP=-1,
                  externalnetworkId=None):
        """
        will get space if it exists,if not will create it
        to retrieve existing one location does not have to be specified

        example: for ms1 possible locations: ca1, eu1 (uk), eu2 (be)

        """
        if not location:
            raise j.exceptions.RuntimeError("Location cannot be empty.")
        for space in self.spaces:
            if space.model['name'] == name and space.model['location'] == location:
                return space
        else:
            if create:
                self.client.api.cloudapi.cloudspaces.create(access=self.client.login,
                                                            name=name,
                                                            accountId=self.id,
                                                            location=location,
                                                            maxMemoryCapacity=maxMemoryCapacity,
                                                            maxVDiskCapacity=maxVDiskCapacity,
                                                            maxCPUCapacity=maxCPUCapacity,
                                                            maxNASCapacity=maxNASCapacity,
                                                            maxNetworkOptTransfer=maxNetworkOptTransfer,
                                                            maxNetworkPeerTransfer=maxNetworkPeerTransfer,
                                                            maxNumPublicIP=maxNumPublicIP,
                                                            externalnetworkId=externalnetworkId)
                return self.space_get(name, location, False)
            else:
                raise j.exceptions.RuntimeError(
                    "Could not find space with name %s" % name)

    def create_disk(self, name, gid, description, size=0, type="B"):
        res = self.client.api.cloudapi.disks.create(accountId=self.id,
                                                    name=name,
                                                    gid=gid,
                                                    description=description,
                                                    size=size,
                                                    type=type)
        return res

    def _addUser(self, username, right):
        self.client.api.cloudapi.accounts.addUser(
            accountId=self.id, userId=username, accesstype=right)

    def _deleteUser(self, username):
        self.client.api.cloudapi.accounts.deleteUser(accountId=self.id, userId=username, recursivedelete=True)

    def save(self):
        self.client.api.cloudapi.accounts.update(accountId=self.model['id'],
                                                 name=self.model['name'],
                                                 maxMemoryCapacity=self.model.get('maxMemoryCapacity'),
                                                 maxVDiskCapacity=self.model.get('maxVDiskCapacity'),
                                                 maxCPUCapacity=self.model.get('maxCPUCapacity'),
                                                 maxNASCapacity=self.model.get('maxNASCapacity'),
                                                 maxNetworkOptTransfer=self.model.get('maxNetworkOptTransfer'),
                                                 maxNetworkPeerTransfer=self.model.get('maxNetworkPeerTransfer'),
                                                 maxNumPublicIP=self.model.get('maxNumPublicIP')
                                                 )

    def refresh(self):
        accounts = self.client.api.cloudapi.accounts.list()
        for account in accounts:
            if account['id'] == self.id:
                self.model = account
                break
        else:
            raise j.exceptions.RuntimeError("Account has been deleted")

    def delete(self):
        self.client.api.cloudbroker.account.delete(accountId=self.id, reason='API request')

    def __str__(self):
        return "openvcloud client account: %(name)s" % (self.model)

    __repr__ = __str__


class Space(Authorizables):

    def __init__(self, account, model):
        self.account = account
        self.client = account.client
        self.model = model
        self.id = model["id"]

    def add_external_network(self, name, subnet, gateway, startip, endip, gid, vlan):
        self.client.api.cloudbroker.iaas.addExternalNetwork(cloudspaceId=self.id,
                                                            name=name,
                                                            subnet=subnet,
                                                            getway=gateway,
                                                            startip=startip,
                                                            endip=endip,
                                                            gid=gid,
                                                            vlan=vlan)

    def save(self):
        self.client.api.cloudapi.cloudspaces.update(cloudspaceId=self.model['id'],
                                                    name=self.model['name'],
                                                    maxMemoryCapacity=self.model.get('maxMemoryCapacity'),
                                                    maxVDiskCapacity=self.model.get('maxVDiskCapacity'),
                                                    maxCPUCapacity=self.model.get('maxCPUCapacity'),
                                                    maxNASCapacity=self.model.get('maxNASCapacity'),
                                                    maxNetworkOptTransfer=self.model.get('maxNetworkOptTransfer'),
                                                    maxNetworkPeerTransfer=self.model.get('maxNetworkPeerTransfer'),
                                                    maxNumPublicIP=self.model.get('maxNumPublicIP')
                                                    )

    @property
    def machines(self):
        ovc_machines = self.client.api.cloudapi.machines.list(cloudspaceId=self.id)
        machines = dict()
        for machine in ovc_machines:
            machines[machine['name']] = Machine(self, machine)
        return machines

    def _addUser(self, username, right):
        self.client.api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.id, userId=username, accesstype=right)

    def _deleteUser(self, username):
        self.client.api.cloudapi.cloudspaces.deleteUser(cloudspaceId=self.id, userId=username, recursivedelete=True)

    def refresh(self):
        cloudspaces = self.client.api.cloudapi.cloudspaces.list()
        for cloudspace in cloudspaces:
            if cloudspace['id'] == self.id:
                self.model = cloudspace
                break
        else:
            raise j.exceptions.RuntimeError("Cloudspace has been deleted")

    def machine_create(self, name, memsize=2, vcpus=1, disksize=10, datadisks=[], image="Ubuntu 15.10 x64", sizeId=None, stackId=None):
        """
        @param memsize in MB or GB
        for now vcpu's is ignored (waiting for openvcloud)

        """
        imageId = self.image_find_id(image)
        if sizeId is None:
            sizeId = self.size_find_id(memsize)
        if name in self.machines:
            raise j.exceptions.RuntimeError(
                "Name is not unique, already exists in %s" % self)
        print("cloudspaceid:%s name:%s size:%s image:%s disksize:%s" %
              (self.id, name, sizeId, imageId, disksize))
        if stackId:
            self.client.api.cloudbroker.machine.createOnStack(cloudspaceId=self.id, name=name,
                sizeId=sizeId, imageId=imageId, disksize=disksize, datadisks=datadisks, stackid=stackId)
        else:
            self.client.api.cloudapi.machines.create(
                cloudspaceId=self.id, name=name, sizeId=sizeId, imageId=imageId, disksize=disksize, datadisks=datadisks)
        return self.machines[name]

    @property
    def portforwardings(self):
        return self.client.api.cloudapi.portforwarding.list(cloudspaceId=self.id)

    def isPortforwardExists(self, publicIp, publicport, protocol):
        for pf in self.portforwardings:
            if pf['publicIp'] == publicIp and int(pf['publicPort']) == int(publicport) and pf['protocol'] == protocol:
                return True
        return False

    def size_find_id(self, memory=None, vcpus=None):
        if memory < 100:
            memory = memory * 1024  # prob given in GB

        sizes = [(item["memory"], item) for item in self.sizes]
        sizes.sort(key=lambda size: size[0])
        sizes.reverse()
        for size, sizeinfo in sizes:
            if memory > size / 1.1:
                return sizeinfo['id']

        raise j.exceptions.RuntimeError("did not find memory size:%s" % memory)

    @property
    def sizes(self):
        return self.client.api.cloudapi.sizes.list(cloudspaceId=self.id)

    def image_find_id(self, name):
        name = name.lower()

        for image in self.images:
            imageNameFound = image["name"].lower()
            if imageNameFound.find(name) != -1:
                return image["id"]
        images = [item["name"].lower() for item in self.images]
        raise j.exceptions.RuntimeError(
            "did not find image:%s\nPossible Images:\n%s\n" % (name, images))

    @property
    def images(self):
        return self.client.api.cloudapi.images.list(cloudspaceId=self.id, accountId=self.account.id)

    def delete(self):
        self.client.api.cloudapi.cloudspaces.delete(cloudspaceId=self.id)

    def get_space_ip(self):
        space = self.client.api.cloudapi.cloudspaces.get(cloudspaceId=self.id)

        def getSpaceIP(space):
            if space['publicipaddress'] == '':
                space = self.client.api.cloudapi.cloudspaces.get(cloudspaceId=self.id)
            return space['publicipaddress']

        space_ip = getSpaceIP(space)
        start = time.time()
        timeout = 120
        while space_ip == '' and start + timeout > time.time():
            time.sleep(5)
            space_ip = getSpaceIP(space)
        if space_ip == '':
            raise j.exceptions.RuntimeError("Could not get IP Address for space %(name)s" % space)
        return space_ip

    def __repr__(self):
        return "space: %s (%s)" % (self.model["name"], self.id)

    __str__ = __repr__


class Machine:

    def __init__(self, space, model):
        self.space = space
        self.client = space.client
        self.model = model
        self.id = self.model["id"]
        self.name = self.model["name"]

    def start(self):
        self.client.api.cloudapi.machines.start(machineId=self.id)

    def stop(self):
        self.client.api.cloudapi.machines.stop(machineId=self.id)

    def restart(self):
        self.client.api.cloudapi.machines.restart(machineId=self.id)

    def delete(self):
        self.client.api.cloudapi.machines.delete(machineId=self.id)

    def create_snapshot(self, name=str(datetime.datetime.now())):
        self.client.api.cloudapi.machines.snapshot(machineId=self.id, name=name)

    def list_snapshots(self):
        return self.client.api.cloudapi.machines.listSnapshots(machineId=self.id)

    def delete_snapshot(self, epoch):
        self.client.api.cloudapi.machines.deleteSnapshot(machineId=self.id, epoch=epoch)

    def add_disk(self, name, description, size=10, type='D', ssdSize=0):
        disk_id = self.client.api.cloudapi.machines.addDisk(machineId=self.id,
                                                            diskName=name,
                                                            description=description,
                                                            size=size,
                                                            type=type,
                                                            ssdSize=ssdSize)
        return disk_id

    def disk_limit_io(self, disk_id, iops=50):
        self.client.api.cloudapi.disks.limitIO(diskId=disk_id, iops=iops)

    @property
    def portforwardings(self):
        return self.client.api.cloudapi.portforwarding.list(cloudspaceId=self.space.id, machineId=self.id)

    def create_portforwarding(self, publicport, localport, protocol='tcp'):
        if protocol not in ['tcp', 'udp']:
            raise j.exceptions.RuntimeError("Protocol for portforward should be tcp or udp not %s" % protocol)

        machineip, _ = self.get_machine_ip()


        publicAddress = self.space.model['publicipaddress']
        if not publicAddress:
            raise j.exceptions.RuntimeError("No public address found, cannot create port forward")

        # define real publicport, override it by a generated one if needed
        realpublicport = publicport

        if publicport is None:
            unavailable_ports = [int(portinfo['publicPort']) for portinfo in self.space.portforwardings]
            candidate = 2200

            while candidate in unavailable_ports:
                candidate += 1

            realpublicport = candidate

        if not self.space.isPortforwardExists(publicAddress, realpublicport, protocol):
            try:
                self.client.api.cloudapi.portforwarding.create(
                    cloudspaceId=self.space.id,
                    protocol=protocol,
                    localPort=localport,
                    machineId=self.id,
                    publicIp=publicAddress,
                    publicPort=realpublicport
                )

            except Exception as e:
                # if we have a conflict response, let's check something:
                # - if it's an auto-generated port, we probably hit a concurrence issue
                #   let's try again with a new port
                if str(e).startswith("409 Conflict") and publicport is None:
                    return self.create_portforwarding(None, localport, protocol)

                # - if the port was choose excplicitly, then it's not the lib's fault
                raise

        return (realpublicport, localport)

    def delete_portforwarding(self, publicport):
        self.client.api.cloudapi.portforwarding.deleteByPort(
            cloudspaceId=self.space.id,
            publicIp=self.space.model['publicipaddress'],
            publicPort=publicport,
            proto='tcp'
        )

    def delete_portfowarding_by_id(self, pfid):
        self.client.api.cloudapi.portforwarding.delete(cloudspaceid=self.space.id,
                                                       id=pfid)

    def get_machine_ip(self):
        machine = self.client.api.cloudapi.machines.get(machineId=self.id)

        def getMachineIP(machine):
            if machine['interfaces'][0]['ipAddress'] == 'Undefined':
                machine = self.client.api.cloudapi.machines.get(
                    machineId=self.id)
            return machine['interfaces'][0]['ipAddress']

        machineip = getMachineIP(machine)
        start = time.time()
        timeout = 200
        while machineip == 'Undefined' and start + timeout > time.time():
            time.sleep(5)
            machineip = getMachineIP(machine)
        if machineip == 'Undefined':
            raise j.exceptions.RuntimeError(
                "Could not get IP Address for machine %(name)s" % machine)
        return machineip, machine

    def get_ssh_connection(self, requested_sshport=None):
        """
        Will get a cuisine executor for the machine.
        Will attempt to create a portforwarding
        :return:
        """
        machineip, machine = self.get_machine_ip()
        publicip = self.space.model['publicipaddress']
        while not publicip:
            time.sleep(5)
            self.space.refresh()
            publicip = self.space.model['publicipaddress']

        sshport = None
        usedports = set()
        for portforward in self.space.portforwardings:
            if portforward['localIp'] == machineip and int(portforward['localPort']) == 22:
                sshport = int(portforward['publicPort'])
                break
            usedports.add(int(portforward['publicPort']))
        if not requested_sshport:
            requested_sshport = 2200
            while requested_sshport in usedports:
                requested_sshport += 1
        if not sshport:
            self.create_portforwarding(requested_sshport, 22)
            sshport = requested_sshport
        login = machine['accounts'][0]['login']
        password = machine['accounts'][0]['password']
        # TODO: we need tow work with keys *2
        return j.tools.executor.getSSHBased(publicip, sshport, login, password)

    def __repr__(self):
        return "machine: %s (%s)" % (self.model["name"], self.id)

    __str__ = __repr__
