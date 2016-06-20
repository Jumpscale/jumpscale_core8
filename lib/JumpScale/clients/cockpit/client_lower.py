import requests
from client_utils import build_query_string

BASE_URI = "http://js8:5000"


class Client:
    def __init__(self):
        self.url = BASE_URI
        self.session = requests.Session()

    def webhooks_github_post(self, data, headers=None, query_params=None):
        """
        Endpoint that receives the events from github
        It is method for POST /webhooks/github
        """
        uri = self.url + "/webhooks/github"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def oauth_callback_get(self, headers=None, query_params=None):
        """
        oauth endpoint where oauth provider need to send authorization code
        It is method for GET /oauth/callback
        """
        uri = self.url + "/oauth/callback"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def reloadAll(self, headers=None, query_params=None):
        """
        empty memory and reload all services
        It is method for GET /ays/reload
        """
        uri = self.url + "/ays/reload"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def listRepositories(self, headers=None, query_params=None):
        """
        list all repositorys
        It is method for GET /ays/repository
        """
        uri = self.url + "/ays/repository"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def createNewRepository(self, data, headers=None, query_params=None):
        """
        create a new repository
        It is method for POST /ays/repository
        """
        uri = self.url + "/ays/repository"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def getRepository(self, repository, headers=None, query_params=None):
        """
        Get information of a repository
        It is method for GET /ays/repository/{repository}
        """
        uri = self.url + "/ays/repository/"+repository
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def deleteRepository(self, repository, headers=None, query_params=None):
        """
        Delete a repository
        It is method for DELETE /ays/repository/{repository}
        """
        uri = self.url + "/ays/repository/"+repository
        uri = uri + build_query_string(query_params)
        return self.session.delete(uri, headers=headers)

    def listBlueprints(self, repository, headers=None, query_params=None):
        """
        List all blueprint
        It is method for GET /ays/repository/{repository}/blueprint
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def createNewBlueprint(self, data, repository, headers=None, query_params=None):
        """
        Create a new blueprint
        It is method for POST /ays/repository/{repository}/blueprint
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def getBlueprint(self, blueprint, repository, headers=None, query_params=None):
        """
        Get a blueprint
        It is method for GET /ays/repository/{repository}/blueprint/{blueprint}
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def executeBlueprint(self, data, blueprint, repository, headers=None, query_params=None):
        """
        Execute the blueprint
        It is method for POST /ays/repository/{repository}/blueprint/{blueprint}
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def updateBlueprint(self, data, blueprint, repository, headers=None, query_params=None):
        """
        Update existing blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint
        uri = uri + build_query_string(query_params)
        return self.session.put(uri, data, headers=headers)

    def deleteBlueprint(self, blueprint, repository, headers=None, query_params=None):
        """
        delete blueprint
        It is method for DELETE /ays/repository/{repository}/blueprint/{blueprint}
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint
        uri = uri + build_query_string(query_params)
        return self.session.delete(uri, headers=headers)

    def archiveBlueprint(self, data, blueprint, repository, headers=None, query_params=None):
        """
        archive the blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}/archive
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint+"/archive"
        uri = uri + build_query_string(query_params)
        return self.session.put(uri, data, headers=headers)

    def restoreBlueprint(self, data, blueprint, repository, headers=None, query_params=None):
        """
        restore the blueprint
        It is method for PUT /ays/repository/{repository}/blueprint/{blueprint}/restore
        """
        uri = self.url + "/ays/repository/"+repository+"/blueprint/"+blueprint+"/restore"
        uri = uri + build_query_string(query_params)
        return self.session.put(uri, data, headers=headers)

    def listServices(self, repository, headers=None, query_params=None):
        """
        List all services in the repository
        It is method for GET /ays/repository/{repository}/service
        """
        uri = self.url + "/ays/repository/"+repository+"/service"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def listServicesByRole(self, role, repository, headers=None, query_params=None):
        """
        List all services of role 'role' in the repository
        It is method for GET /ays/repository/{repository}/service/{role}
        """
        uri = self.url + "/ays/repository/"+repository+"/service/"+role
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def getServiceByInstance(self, instance, role, repository, headers=None, query_params=None):
        """
        Get a service instance
        It is method for GET /ays/repository/{repository}/service/{role}/{instance}
        """
        uri = self.url + "/ays/repository/"+repository+"/service/"+role+"/"+instance
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def deleteServiceByInstance(self, instance, role, repository, headers=None, query_params=None):
        """
        uninstall and delete a service
        It is method for DELETE /ays/repository/{repository}/service/{role}/{instance}
        """
        uri = self.url + "/ays/repository/"+repository+"/service/"+role+"/"+instance
        uri = uri + build_query_string(query_params)
        return self.session.delete(uri, headers=headers)

    def listServiceActions(self, instance, role, repository, headers=None, query_params=None):
        """
        Get list of action available on this service
        It is method for GET /ays/repository/{repository}/service/{role}/{instance}/action
        """
        uri = self.url + "/ays/repository/"+repository+"/service/"+role+"/"+instance+"/action"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def listTemplates(self, repository, headers=None, query_params=None):
        """
        list all templates
        It is method for GET /ays/repository/{repository}/template
        """
        uri = self.url + "/ays/repository/"+repository+"/template"
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def createNewTemplate(self, data, repository, headers=None, query_params=None):
        """
        Create new template
        It is method for POST /ays/repository/{repository}/template
        """
        uri = self.url + "/ays/repository/"+repository+"/template"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def getTemplate(self, template, repository, headers=None, query_params=None):
        """
        Get a template
        It is method for GET /ays/repository/{repository}/template/{template}
        """
        uri = self.url + "/ays/repository/"+repository+"/template/"+template
        uri = uri + build_query_string(query_params)
        return self.session.get(uri, headers=headers)

    def initRepository(self, data, repository, headers=None, query_params=None):
        """
        init repository
        It is method for POST /ays/repository/{repository}/init
        """
        uri = self.url + "/ays/repository/"+repository+"/init"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def simulateAction(self, data, repository, headers=None, query_params=None):
        """
        simulate the execution of an action
        It is method for POST /ays/repository/{repository}/simulate
        """
        uri = self.url + "/ays/repository/"+repository+"/simulate"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)

    def executeAction(self, data, repository, headers=None, query_params=None):
        """
        Perform an action on the services matches by the query arguments
        It is method for POST /ays/repository/{repository}/execute
        """
        uri = self.url + "/ays/repository/"+repository+"/execute"
        uri = uri + build_query_string(query_params)
        return self.session.post(uri, data, headers=headers)
