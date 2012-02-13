# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import time
import socket

import zookeeper
from zc.zk import ZooKeeper
from zktools.node import ZkNode

from qdo.queue import Queue
from qdo.utils import metlogger

ZOO_DEFAULT_NS = 'mozilla-qdo'


class Worker(object):
    """A Worker works on jobs"""

    def __init__(self, settings):
        """Create a worker

        :param settings: Configuration settings
        :type settings: dict
        """
        self.settings = settings
        self.shutdown = False
        self.name = "%s-%s" % (socket.getfqdn(), os.getpid())
        self.zk_worker_node = None
        self.configure()
        self.queue = Queue()
        self.job = None

    def configure(self):
        """Configure the worker based on the configuration settings.
        """
        qdo_section = self.settings.getsection('qdo-worker')
        self.wait_interval = qdo_section.get('wait_interval', 5)
        zkhost = qdo_section.get('zookeeper_connection', '127.0.0.1:2181')
        zkns = qdo_section.get('zookeeper_namespace', ZOO_DEFAULT_NS)
        # TODO: handle connection failure
        self.zkconn = ZooKeeper(zkhost + '/' + zkns)

    def work(self):
        """Work on jobs

        This is the main method of the worker.
        """
        self.setup_zookeeper()
        self.register()
        try:
            while True:
                if self.shutdown:
                    break
                try:
                    message = self.queue.pop()
                    if self.job:
                        self.job(message)
                except IndexError:
                    metlogger.incr('wait_for_jobs')
                    time.sleep(self.wait_interval)
        finally:
            self.unregister()

    def setup_zookeeper(self):
        """Setup global data structures in Zookeeper."""
        ZkNode(self.zkconn, "/workers")
        ZkNode(self.zkconn, "/queues")
        ZkNode(self.zkconn, "/queue-locks")

    def register(self):
        """Register this worker with Zookeeper."""
        self.zk_worker_node = ZkNode(self.zkconn, "/workers/%s" % self.name,
            create_mode=zookeeper.EPHEMERAL)

    def unregister(self):
        """Unregister this worker from Zookeeper."""
        self.zkconn.close()


def run(settings):  # pragma: no cover
    worker = Worker(settings)
    worker.work()
