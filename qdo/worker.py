# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import atexit
from contextlib import contextmanager
import os
import random
import time
import socket

from queuey_py import Client
from ujson import decode as ujson_decode

from qdo.config import ERROR_QUEUE
from qdo.config import STATUS_PARTITIONS
from qdo.config import STATUS_QUEUE
from qdo.partition import Partition
from qdo.log import get_logger


@contextmanager
def dict_context():
    context = dict()
    try:
        yield context
    finally:
        del context


def log_failure(exc, context, queuey_conn):
    logger = get_logger()
    raven = getattr(logger, u'raven', None)
    if raven is not None:
        raven()


def save_failed_message(exc, context, queuey_conn):
    log_failure(exc, context, queuey_conn)


def resolve(worker, section, name):
    if section[name]:
        mod, func_name = section[name].split(u':')
        result = __import__(mod, globals(), locals(), func_name)
        func = getattr(result, func_name)
        setattr(worker, name, func)


class Worker(object):
    """A Worker works on jobs.

    :param settings: Configuration settings
    :type settings: dict
    """

    def __init__(self, settings):
        self.settings = settings
        self.shutdown = False
        self.name = u'%s-%s' % (socket.getfqdn(), os.getpid())
        self.job = None
        self.job_context = dict_context
        self.job_failure = log_failure
        self.partition_policy = u'manual'
        self.partitions = {}
        self.configure()

    def configure(self):
        """Configure the worker based on the configuration settings.
        """
        qdo_section = self.settings.getsection(u'qdo-worker')
        self.wait_interval = qdo_section[u'wait_interval']
        resolve(self, qdo_section, u'job')
        resolve(self, qdo_section, u'job_context')
        resolve(self, qdo_section, u'job_failure')
        queuey_section = self.settings.getsection(u'queuey')
        self.queuey_conn = Client(
            queuey_section[u'app_key'],
            connection=queuey_section[u'connection'])

    def _partitions(self):
        # List all partitions
        queuey_conn = self.queuey_conn
        response = queuey_conn.get(params={u'details': True})
        queues = ujson_decode(response.text)[u'queues']
        partitions = []
        for q in queues:
            name = q[u'queue_name']
            part = q[u'partitions']
            for i in xrange(1, part + 1):
                partitions.append(u'%s-%s' % (name, i))
        return partitions

    def configure_partitions(self, section):
        self.partition_policy = policy = section[u'policy']
        partition_ids = []
        queuey_conn = self.queuey_conn
        all_partitions = self._partitions()
        if policy == u'manual':
            partition_ids = section[u'ids']
        elif policy == u'all':
            partition_ids = all_partitions

        def cond_create(queue_name):
            if queue_name + u'-1' not in all_partitions:
                queuey_conn.create_queue(
                    queue_name=queue_name, partitions=STATUS_PARTITIONS)
        cond_create(ERROR_QUEUE)
        cond_create(STATUS_QUEUE)
        self.assign_partitions(partition_ids)

    def track_partitions(self):
        status = {}
        # get all status messages, starting with the newest ones
        status_messages = self.queuey_conn.messages(
            STATUS_QUEUE, limit=100, order='descending')
        if len(status_messages) >= 100:
            # TODO deal with more than 100 status messages / partitions
            raise RuntimeError(u'More than 100 status messages detected!')
        for message in status_messages:
            body = ujson_decode(message[u'body'])
            partition = body[u'partition']
            if partition not in status:
                # don't overwrite newer messages with older status
                status[partition] = message[u'message_id']
        return status

    def assign_partitions(self, partition_ids):
        for pid in list(self.partitions.keys()):
            if pid not in partition_ids:
                del self.partitions[pid]
        status = self.track_partitions()
        for pid in partition_ids:
            if pid.startswith((ERROR_QUEUE, STATUS_QUEUE)):
                continue
            self.partitions[pid] = Partition(self.queuey_conn, pid,
                msgid=status.get(pid, None), worker_id=self.name)

    def work(self):
        """Work on jobs.

        This is the main loop of the worker.
        """
        if not self.job:
            return
        # Try Queuey heartbeat connection
        self.queuey_conn.connect()
        partitions_section = self.settings.getsection(u'partitions')
        self.configure_partitions(partitions_section)
        atexit.register(self.stop)
        timer = get_logger().timer
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
                    message_id = message[u'message_id']
                    try:
                        with timer(u'worker.job_time'):
                            self.job(message, context)
                    except Exception as exc:
                        with timer(u'worker.job_failure_time'):
                            self.job_failure(exc, context, self.queuey_conn)
                    partition.last_message = message_id
                if no_messages == len(self.partitions):
                    self.wait()

    def wait(self):
        get_logger().incr(u'worker.wait_for_jobs')
        jitter = random.uniform(0.8, 1.2)
        time.sleep(self.wait_interval * jitter)

    def stop(self):
        """Stop the worker loop. Used in an `atexit` hook."""
        self.shutdown = True


def run(settings):
    worker = Worker(settings)
    worker.work()
