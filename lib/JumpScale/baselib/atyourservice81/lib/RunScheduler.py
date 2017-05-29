import asyncio
from JumpScale import j

NORMAL_RUN_PRIORITY = 1
ERROR_RUN_PRIORITY = 10

RETRY_DELAY = {
    1: 10,  # 10sec
    2: 30,  # 30sec
    3: 60,  # 1min
    4: 300,  # 5min
    5: 600,  # 10min
    6: 1800,  # 30min
}  # total: 46min 10sec


class RunScheduler:
    """
    This class is reponsible to execte the run requested by the users
    as well as the automatic error runs

    Since only one can be executed at a time, all the run are pushed on a PriorityQueue.
    Requested runs have always hightest priority over error runs.
    """

    def __init__(self, repo):
        self.logger = j.logger.get("j.ays.RunScheduler")
        self.repo = repo
        self._git = j.clients.git.get(repo.path, check_path=False)
        self.queue = asyncio.PriorityQueue(maxsize=0, loop=self.repo._loop)
        self._retries = []
        self._retries_lock = asyncio.Lock(loop=self.repo._loop)
        self._accept = False
        self._is_running = False
        self._current = None

    @property
    def status(self):
        if self._accept and self._is_running:
            return "running"
        if not self._accept and self._is_running:
            return "stopping"
        return "halted"

    @property
    def current_run(self):
        """
        returns the run that is currently beeing executed.
        """
        if self._current is not None:
            try:
                run_model = j.core.jobcontroller.db.runs.get(self._current)
                return run_model.objectGet()
            except j.exceptions.Input:
                return None
        return None

    def _commit(self, run):
        """
        create a commit on the ays repo
        """
        self.logger.debug("create commit on repo %s for un %s", self.repo.path, run.model.key)
        msg = "Run {}\n\n{}".format(run.model.key, str(run))
        self._git.commit(message=msg)

    async def start(self):
        """
        starts the run scheduler and begin whating the run queue.
        """
        self.logger.info("{} started".format(self))
        if self._is_running:
            return

        self._is_running = True
        self._accept = True
        while self._is_running:

            try:
                _, run = await asyncio.wait_for(self.queue.get(), timeout=10)
            except asyncio.TimeoutError:
                # this allow to exit the loop when stopped is asked.
                # without the timeout the queue.get blocks forever
                if not self._accept:
                    break
                continue

            try:
                self._current = run.model.key
                await run.execute()
                self._commit(run)
            except:
                # retry the run after a delay
                await self._retry(run)
            finally:
                self._current = None
                self.queue.task_done()

        self._is_running = False
        self.logger.info("{} stopped".format(self))

    async def stop(self, timeout=30):
        """
        stops the run scheduler
        When the run scheduler is stopped you can't add send new run to it
        @param timout: number of second we wait for the current run to finish before force stopping execution.

        """
        self._accept = False
        self.logger.info("{} stopping...".format(self))

        try:
            # wait for runs in the queue and all retries actions
            with await self._retries_lock:
                for retry in self._retries:
                    retry.cancel()
            to_wait = [self.queue.join(), *self._retries]
            await asyncio.wait(to_wait, timeout=timeout, loop=self.repo._loop)

        except asyncio.TimeoutError:
            self.logger.warning("stop timeout reach for {}. possible run interrupted".format(self))

        self._retries = []

    async def add(self, run, priority=NORMAL_RUN_PRIORITY):
        """
        add a run to the queue of run to be executed
        @param priority: one of NORMAL_RUN_PRIORITY or ERROR_RUN_PRIORITY
                         runs added with NORMAL_RUN_PRIORITY will always be executed before
                         the ones added with ERROR_RUN_PRIORITY
        """
        if priority not in [NORMAL_RUN_PRIORITY, ERROR_RUN_PRIORITY]:
            raise j.exceptions.Input("priority should {} or {}, {} given".format(
                             NORMAL_RUN_PRIORITY,
                             ERROR_RUN_PRIORITY,
                             priority))

        if not self._accept:
            raise j.exceptions.RuntimeError("{} is stopping, can't add new run to it".format(self))

        self.logger.debug("add run {} to {}".format(run.model.key, self))
        await self.queue.put((priority, run))

    async def _retry(self, run):
        async def do_retry(run):

            # find lowest error level
            levels = set()
            for step in run.steps:
                for job in step.jobs:
                    service_action_obj = job.service.model.actions[job.model.dbobj.actionName]
                    if service_action_obj.errorNr > 0:
                        levels.add(service_action_obj.errorNr)

            # if we are in dev mode, always reschedule after 10 sec
            if j.atyourservice.dev_mode:
                delay = RETRY_DELAY[1]
            else:
                delay = RETRY_DELAY[min(levels)]

            self.logger.info("reschedule run %s in %ssec", run.model.key, delay)
            await asyncio.sleep(delay)

            # sending this action to the run queue
            self.logger.debug("add run %s to %s", run.model.key, self)
            await self.repo.run_scheduler.add(run, ERROR_RUN_PRIORITY)

            # remove this task from the retries list
            with await self._retries_lock:
                current_task = asyncio.Task.current_task()
                if current_task in self._retries:
                    self._retries.remove(current_task)

        # don't add if we are stopping the server
        if not self._accept:
            self.logger.warning("%s is stopping, can't add new run to it", self)
            return
        # add the rery to the event loop
        with await self._retries_lock:
            self._retries.append(asyncio.ensure_future(do_retry(run)))

    def __repr__(self):
        return "RunScheduler<{}>".format(self.repo.name)
