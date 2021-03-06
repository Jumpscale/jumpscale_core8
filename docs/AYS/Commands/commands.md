# AYS Commands

## Help

- [help](help.md)

## Basic commands

the following commands show you the typical order in which you need to execute at your service
- [create_repo](create_repo.md) creates a new AYS repository
- [blueprint](blueprint.md) executes one or more blueprints, converting them into service instances
- [commit](commit.md) commits changes to the associated Git repository, allowing to keep track of changes
- [run](run.md) creates jobs (runs) for the scheduled actions, and proposes to start the jobs, which then executes the actions
- [simulate](simulate.md) allows you to see what will happen when executing an action, without actually having te execute it
- [destroy](destroy.md) destroys all service instances, from here you need to execute the blueprints again

## Advanced
- [noexec](noexec.md) : Enable/Disable noexec mode
- [delete](delete.md) : Delete a service and all its children
- [discover](discover.md) : Discover AYS repository on the filesystem
- [restore](restore.md)  : Load service from the filesystem
- [run_info](run_info.md) : Display info about run
- [do](do.md) : Helper method to easily schedule action from the command line
- [list](list.md) : List all services from a repository
- [repo_list](repo_list.md) : List all known repositories
- [update](update.md) : Update actor to a new version.
- [test](test.md) : Run AYS tests
- [show](show.md) : show information about a service
- [state](state.md) : Print the state of the selected services.
- [set_state](set_state.md) : Manually set the state of a service action
