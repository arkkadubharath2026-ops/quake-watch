"""Run a job worker as a separate OS process for the job-queue tests.

Usage: python -m tests.integration.jobs_worker_proc '<WorkerConfig JSON>' — accepts every
WorkerConfig field plus ``idle_exit``. Signals behave as for ``manage.py run_worker``.
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")

import django

django.setup()

from apps.jobs.worker import Worker, WorkerConfig  # noqa: E402
from tests.integration import jobs_testtasks  # noqa: E402,F401  (registers the test tasks)

if __name__ == "__main__":
    options = json.loads(sys.argv[1])
    idle_exit = options.pop("idle_exit", None)
    worker = Worker(WorkerConfig(**options))
    worker.install_signal_handlers()
    print(json.dumps({"worker": worker.name, "pid": os.getpid()}), flush=True)
    worker.run(idle_exit=idle_exit)
