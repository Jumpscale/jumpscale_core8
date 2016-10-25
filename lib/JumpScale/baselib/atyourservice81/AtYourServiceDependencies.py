from JumpScale import j

# logic inspired by https://breakingcode.wordpress.com/2013/03/11/an-example-dependency-resolution-algorithm-in-python


def build_nodes(repo):
    """
    Create a node object for every service in the repo.
    These node are going to be used to create the dependency graphs
    """
    all_nodes = {}
    for model in repo.db.service.find():
        for action in model.actions.keys():
            node = Node(model, action)
            all_nodes[node.id] = node
    return all_nodes


def create_graphs(repo, all_nodes):
    """
    Create a depency graphs base of the consumption between services and actions
    """
    nodes = []

    for model, actions in repo.findScheduledActions().items():
        actions.reverse()

        for i, action in enumerate(actions):
            name = "%s-%s" % (model.key, action)
            node = all_nodes[name]
            nodes.append(node)

            addEdges(node, action, all_nodes, nodes)

            if i + 1 < len(actions):
                action = actions[i + 1]
                name = "%s-%s" % (model.key, action)
                edge = all_nodes[name]
                node.addEdge(edge)
                nodes.append(edge)

    return nodes


def addEdges(node, action, all_nodes, nodes):
    """
    recursivlely add edged to a node
    """
    for prod in node.model.producers:
        name = "%s-%s" % (prod.key, action)
        edge = all_nodes[name]
        addEdges(edge, action, all_nodes, nodes)
        node.addEdge(edge)
        nodes.append(edge)


def get_task_batches(nodes):

    # Build a map of node names to node instances
    id_to_instance = dict((n.id, n) for n in nodes)

    # Build a map of node names to dependency names
    id_to_deps = dict((n.id, set(n.edges)) for n in nodes)

    # This is where we'll store the batches
    batches = []

    # While there are dependencies to solve...
    while id_to_deps:

        # Get all nodes with no dependencies
        ready = {id for id, deps in id_to_deps.items() if not deps}

        # If there aren't any, we have a loop in the graph
        if not ready:
            msg = "Circular dependencies found!\n"
            msg += format_dependencies(id_to_deps)
            raise ValueError(msg)

        # Remove them from the dependency graph
        for name in ready:
            del id_to_deps[name]
        for deps in id_to_deps.values():
            deps.difference_update(ready)

        # Add the batch to the list
        batches.append({id_to_instance[id] for id in ready})

    # Return the list of batches
    return batches


def format_dependencies(id_to_deps):
    """Format a dependency graph for printing"""
    msg = []
    for name, deps in id_to_deps.items():
        for parent in deps:
            msg.append("%s -> %s" % (name, parent))
        if len(deps) == 0:
            msg.append('%s -> no desp' % name)
    return "\n".join(msg)


def format_nodes(nodes):
    """Create and format a dependency graph for printing"""
    return format_dependencies(dict((n.name, n.edges) for n in nodes))


def create_job(repo, model, action):
    action_model = model.actions[action]
    job_model = j.core.jobcontroller.db.job.new()
    job_model.dbobj.repoKey = repo.model.key
    job_model.dbobj.actionKey = action_model.actionKey
    job_model.dbobj.actionName = action_model.name
    job_model.dbobj.actorName = model.dbobj.actorName
    job_model.dbobj.serviceName = model.dbobj.name
    job_model.dbobj.serviceKey = model.key
    job_model.dbobj.state = "new"
    job_model.dbobj.lastModDate = j.data.time.epoch
    job_model.dbobj.serviceKey = model.key
    job_model.dbobj.repoKey = repo.model.key
    job = j.core.jobcontroller.newJobFromModel(job_model)
    job.saveService = False
    return job


class Node():

    def __init__(self, model, action):
        self.model = model
        self.edges = []
        self.action = action
        self.id = "%s-%s" % (model.key, action)
        self.name = "%s!%s-%s" % (model.dbobj.actorName, model.name, action)

    def addEdge(self, node):
        self.edges.append(node)

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return '%s-%s' % (str(self.model), self.action)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.id == other
        return self.id == other.name
