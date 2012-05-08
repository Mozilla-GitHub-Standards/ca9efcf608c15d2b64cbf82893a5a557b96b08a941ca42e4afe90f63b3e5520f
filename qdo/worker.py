# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import atexit
from contextlib import contextmanager
import os
import time
import socket

from qdo.partition import Partition
from qdo.queuey import QueueyConnection
from qdo.log import get_logger


@contextmanager
def dict_context():
    context = dict()
    try:
        yield context
    finally:
        del context


class Worker(object):
    """A Worker works on jobs.

    :param settings: Configuration settings
    :type settings: dict
    """

    error_queue = u'qdo_error'
    status_queue = u'qdo_status'

    def __init__(self, settings):
        self.settings = settings
        self.shutdown = False
        self.name = u'%s-%s' % (socket.getfqdn(), os.getpid())
        self.job = None
        self.job_context = dict_context
        self.partition_policy = u'manual'
        self.partitions = {}
        self._all_partitions = None
        self.configure()

    def configure(self):
        """Configure the worker based on the configuration settings.
        """
        qdo_section = self.settings.getsection(u'qdo-worker')
        self.wait_interval = qdo_section[u'wait_interval']
        if qdo_section[u'job']:
            mod, fun = qdo_section[u'job'].split(u':')
            result = __import__(mod, globals(), locals(), fun)
            self.job = getattr(result, fun)
        if qdo_section[u'job_context']:
            mod, fun = qdo_section[u'job_context'].split(u':')
            result = __import__(mod, globals(), locals(), fun)
            self.job_context = getattr(result, fun)
        queuey_section = self.settings.getsection(u'queuey')
        self.queuey_conn = QueueyConnection(
            queuey_section[u'app_key'],
            connection=queuey_section[u'connection'])
        partitions_section = self.settings.getsection(u'partitions')
        self.configure_partitions(partitions_section)

    def configure_partitions(self, section):
        self.partition_policy = policy = section[u'policy']
        partition_ids = []
        if policy == u'manual':
            partition_ids = section[u'ids']
        elif policy == u'all':
            self._all_partitions = self.queuey_conn._partitions()
            partition_ids = self._all_partitions
        for pid in partition_ids:
            if pid.startswith((self.error_queue, self.status_queue)):
                continue
            self.partitions[pid] = Partition(self.queuey_conn, pid)

    def assign_partitions(self):
        if self._all_partitions is None:
            self._all_partitions = self.queuey_conn._partitions()

        def cond_create(queue_name):
            if queue_name + u'-1' not in self._all_partitions:
                self.queuey_conn._create_queue(queue_name=queue_name)
        cond_create(self.error_queue)
        cond_create(self.status_queue)
        self._all_partitions = None

        for name in self.queuey_conn._partitions():
            self.partitions[name] = Partition(self.queuey_conn, name)

    def work(self):
        """Work on jobs.

        This is the main loop of the worker.
        """
        if not self.job:
            return
        atexit.register(self.stop)
        # Try Queuey heartbeat connection
        self.queuey_conn.connect()
        # Assign partitions
        self.assign_partitions()
        with self.job_context() as context:
            while 1:
                if self.shutdown:
                    break
                no_messages = 0
                for name, partition in self.partitions.items():
                    messages = partition.messages(limit=2)
                    if not messages:
                        no_messages += 1
                        continue
                    message = messages[0]
                    timestamp = message[u'timestamp']
                    self.job(context, message)
                    partition.timestamp = timestamp
                if no_messages == len(self.partitions):
                    get_logger().incr(u'worker.wait_for_jobs')
                    time.sleep(self.wait_interval)

    def stop(self):
        """Stop the worker loop. Used in an `atexit` hook."""
        self.shutdown = True


def run(settings):
    worker = Worker(settings)
    worker.work()
