from JumpScale import j
import asyncio

class RecurringTask:
    """Execute a job periodicly"""
    def __init__(self, service, action, period, loop=None):
        self.logger = j.logger.get('j.atyourservice')
        self._loop = None or asyncio.get_event_loop()
        self._future = None
        self._job = None
        self.service = service
        self.action = action
        self.period = period
        self.started = False

    async def _run(self):
        while self.started:
            self._job =  self.service.getJob(actionName=self.action)
            await self._job.execute()

            action_info = self.service.model.actions[self.action]
            elapsed = (j.data.time.epoch - action_info.lastRun)
            sleep = action_info.period - elapsed
            if sleep < 0:
                sleep = 0
            await asyncio.sleep(sleep)

    def start(self):
        self.started = True
        self._future = asyncio.ensure_future(self._run(), loop=self._loop)
        return self._future

    async def stop(self):
        self.started = False
        # cancel recurring task
        if self._future:
            self._future.cancel()
            try:
                # we wait here to make sure to give the time to the futur to cancel itself.
                # TODO: timeout after a while ?
                await self._future
            except asyncio.CancelledError:
                #  it should pass here, the canceld future should raise this exception
                self.logger.info("recurring task for {}:{} is cancelled".format(self.service, self.action))

        if self._job:
            await self._job.cancel()


if __name__ == '__main__':
    import logging
    logging.basicConfig()

    loop = asyncio.get_event_loop()

    j.atyourservice.aysRepos._load()
    repo = j.atyourservice.aysRepos.get('/opt/code/cockpit_repos/testrepo')
    s = repo.serviceGet('node','demo')
    t = RecurringTask(s,'monitor', 10, loop=loop)
    t.start()
    def cb(t):
        t.stop()
    loop.call_later(20, cb, t)
    loop.run_forever()

    from IPython import embed;embed()
