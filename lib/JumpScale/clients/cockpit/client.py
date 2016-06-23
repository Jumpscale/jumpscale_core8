import requests
from client_utils import build_query_string
import client_lower
from JumpScale import j


class Client:
    """
    This client is the upper layer of the cockpit client.
    It uses the generated client from go-raml as backend.
    The backend client is not touch, this allow to re-generate the client
    without modifying the upper interface of the client.
    """

    def __init__(self, base_uri, jwt):
        """
        base_uri: str, URL of the cockpit api. e.g: https://mycockpit.com/api
        jwt: str, json web token from itsyou.online
        """
        self._client = client_lower.Client()
        self._client.url = base_uri
        self._jwt = jwt
        self._client.session.headers = {
            "Authorization": "Bearer " + jwt,
            "Content-Type": "application/json"
        }

    def reloadAll(self, headers=None, query_params=None):
        """
        empty memory and reload all services
        It is method for GET /ays/reload
        """
        resp = self._client.reloadAll(headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def listRepositories(self, headers=None, query_params=None):
        """
        list all repositorys
        It is method for GET /ays/repository
        """
        resp = self._client.listRepositories(headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def createNewRepository(self, name, headers=None, query_params=None):
        """
        create a new repository
        It is method for POST /ays/repository

        data: dict, {'path': '/path/to/repo', 'name': 'repo'}
        """
        data = j.data.serializer.json.dumps({'name': name})
        resp = self._client.createNewRepository(data=data, headers=headers, query_params=query_params)
        if resp.status_code != 201:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def getRepository(self, repository, headers=None, query_params=None):
        """
        Get information of a repository
        It is method for GET /ays/repository/{repository}
        """
        resp = self._client.getRepository(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def deleteRepository(self, repository, headers=None, query_params=None):
        """
        Delete a repository
        It is method for DELETE /ays/repository/{repository}
        """
        resp = self._client.deleteRepository(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 204:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def initRepository(self, repository, role='', instance='', force=False, headers=None, query_params=None):
        """
        Run init action on full repository
        It is method for POST /ays/repository/{repository}/init
        """
        query = {
            'role': role,
            'instance': instance,
        }
        query_params = query_params or {}
        query_params.update(query)

        resp = self._client.initRepository(repository=repository, data=None, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])

        return resp.json()

    def simulateAction(self, repository, action, role='', instance='', producer_roles='*', force=False, headers=None, query_params=None):
        """
        simulate the execution of an action
        It is method for POST /ays/repository/{repository}/simulate
        """
        query = {
            'action': action,
            'role': role,
            'instance': instance,
            'producer_roles': producer_roles,
            'force': force,
        }
        query_params = query_params or {}
        query_params.update(query)
        
        resp = self._client.simulateAction(data=None, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def executeAction(self, repository, action, role='', instance='', producer_roles='*', force=False, async=False, headers=None, query_params=None):
        """
        simulate the execution of an action
        It is method for POST /ays/repository/{repository}/simulate
        """
        query = {
            'action': action,
            'role': role,
            'instance': instance,
            'producer_roles': producer_roles,
            'force': force,
            'async': async,
        }
        query_params = query_params or {}
        query_params.update(query)
        
        resp = self._client.executeAction(data=None, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def listBlueprints(self, repository, archived=True, headers=None, query_params=None):
        """
        List all blueprint
        It is method for GET /ays/repository/{repository}/blueprint
        archived: boolean, include archived blueprint or not
        """
        query = {'archived': archived}
        query_params = query_params or {}
        query_params.update(query)
        
        resp = self._client.listBlueprints(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def createNewBlueprint(self, data, repository, headers=None, query_params=None):
        """
        Create a new blueprint
        It is method for POST /ays/repository/{repository}/blueprint

        data: dict, {'name': 'my_bp', content: 'valid yaml blueprint'}
        """
        data = j.data.serializer.json.dumps(data)
        resp = self._client.createNewBlueprint(data=data, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 201:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def getBlueprint(self, repository, blueprint, headers=None, query_params=None):
        """
        Get a blueprint
        It is method for GET /ays/repository/{repository}/blueprint/{blueprint}
        """
        resp = self._client.getBlueprint(blueprint=blueprint, repository=blueprint, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def executeBlueprint(self, repository, blueprint, role='', instance='', headers=None, query_params=None):
        """
        Execute the blueprint
        It is method for POST /ays/repository/{repository}/blueprint/{blueprint}
        """
        query = {
            'role': role,
            'instance': instance,
        }
        query_params = query_params or {}
        query_params.update(query)
        
        resp = self._client.executeBlueprint(data=None, blueprint=blueprint, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def updateBlueprint(self, data, repository, blueprint, headers=None, query_params=None):
        """
        Update existing blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}

        data: dict, {'name': 'my_bp', content: 'valid yaml blueprint'}
        """
        data = j.data.serializer.json.dumps(data)
        resp = self._client.updateBlueprint(data=data, blueprint=blueprint, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def deleteBlueprint(self, repository, blueprint, headers=None, query_params=None):
        """
        delete blueprint
        It is method for DELETE /ays/repository/{repository}/blueprint/{blueprint}
        """
        resp = self._client.deleteBlueprint(blueprint=blueprint, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 204:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def archiveBlueprint(self, repository, blueprint, headers=None, query_params=None):
        """
        archive blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}/archive
        """
        resp = self._client.archiveBlueprint(data=None, blueprint=blueprint, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def restoreBlueprint(self, repository, blueprint, headers=None, query_params=None):
        """
        archive blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}/restore
        """
        resp = self._client.restoreBlueprint(data=None, blueprint=blueprint, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def listServices(self, repository, headers=None, query_params=None):
        """
        List all services in the repository
        It is method for GET /ays/repository/{repository}/service
        """
        resp = self._client.listServices(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def listServicesByRole(self, role, repository, headers=None, query_params=None):
        """
        List all services of role 'role' in the repository
        It is method for GET /ays/repository/{repository}/service/{role}
        """
        resp = self._client.listServicesByRole(role=role, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def executeServiceActionByRole(self, action, role, repository, headers=None, query_params=None):
        """
        Perform an action on all service with the role 'role'
        It is method for POST /ays/repository/{repository}/service/{role}/action/{action}
        """
        resp = self._client.executeServiceActionByRole(data=None, action=action, role=role, repository=repository, headers=headers, query_params=query_params)
        resp.raise_for_status()
        return resp.json()

    def getServiceByInstance(self, instance, role, repository, headers=None, query_params=None):
        """
        Get a service instance
        It is method for GET /ays/repository/{repository}/service/{role}/{instance}
        """
        resp = self._client.getServiceByInstance(instance=instance, role=role, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def deleteServiceByInstance(self, instance, role, repository, headers=None, query_params=None):
        """
        uninstall and delete a service
        It is method for DELETE /ays/repository/{repository}/service/{role}/{instance}
        """
        resp = self._client.deleteServiceByInstance(instance=instance, role=role, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 204:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return

    def listServiceActions(self, instance, role, repository, headers=None, query_params=None):
        """
        Get list of action available on this service
        It is method for GET /ays/repository/{repository}/service/{role}/{instance}/action
        """
        resp = self._client.listServiceActions(instance=instance, role=role, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def executeServiceActionByInstance(self, action, instance, role, repository, headers=None, query_params=None):
        """
        Perform an action on a services
        It is method for POST /ays/repository/{repository}/service/{role}/{instance}/{action}
        """
        resp = self._client.executeServiceActionByInstance(data=None, action=action, instance=instance, role=role, repository=repository, headers=headers, query_params=query_params)
        resp.raise_for_status()
        return resp.json()

    def listTemplates(self, repository, headers=None, query_params=None):
        """
        list all templates
        It is method for GET /ays/repository/{repository}/template
        """
        resp = self._client.listTemplates(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def createNewTemplate(self, data, repository, headers=None, query_params=None):
        """
        Create new template
        It is method for POST /ays/repository/{repository}/template

        data: dict, {'name': 'myTemplate', 'action_py': 'valid action file', schema_hrd: 'valid hrd schema'}
        """
        resp = self._client.createNewTemplate(data=data, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def getTemplate(self, template, repository, headers=None, query_params=None):
        """
        Get a template
        It is method for GET /ays/repository/{repository}/template/{template}
        """
        resp = self._client.getTemplate(template=template, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def listRuns(self, repository, headers=None, query_params=None):
        """
        list all runs in the repository
        It is method for GET /ays/repository/{repository}/aysrun
        """
        resp = self._client.listRuns(repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()

    def getRun(self, aysrun, repository, headers=None, query_params=None):
        """
        Get an aysrun
        It is method for GET /ays/repository/{repository}/aysrun/{aysrun}
        """
        resp = self._client.getRun(aysrun=aysrun, repository=repository, headers=headers, query_params=query_params)
        if resp.status_code != 200:
            raise j.exceptions.RuntimeError(resp.json()['error'])
        return resp.json()
