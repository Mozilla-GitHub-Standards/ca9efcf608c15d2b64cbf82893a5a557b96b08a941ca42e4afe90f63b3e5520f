# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest2 as unittest

from zc.zk import ZooKeeper
from zktools.node import ZkNode

from qdo import testing
from qdo.tests.base import ZKBase


class TestZookeeper(unittest.TestCase, ZKBase):

    @classmethod
    def setUpClass(cls):
        ZKBase.setUpClass()
        cls.supervisor = testing.processes['supervisor']

    @classmethod
    def tearDownClass(cls):
        ZKBase.tearDownClass()

    def tearDown(self):
        self.supervisor.startProcessGroup('zookeeper')

    def test_add_node_cluster_visibility(self):
        conn = ZooKeeper('127.0.0.1:2181', wait=True)
        ZkNode(conn, u'/test/node1')
        conn.close()
        conn2 = ZooKeeper('127.0.0.1:2184', wait=True)
        self.assertTrue(conn2.exists(u'/test/node1'))
        conn2.close()
        conn3 = ZooKeeper('127.0.0.1:2187', wait=True)
        self.assertTrue(conn3.exists(u'/test/node1'))
        conn3.close()

    def test_cluster_connection(self):
        conn = ZooKeeper(
            '127.0.0.1:2181,127.0.0.1:2184,127.0.0.1:2187', wait=True)
        node = ZkNode(conn, u'/test/node2')
        node.value = 1
        # shut down the current zk server
        self.supervisor.stopProcess('zookeeper:zk1')
        node.value = 2
        conn.close()
        # open a new connection and ensure the value has been set in
        # Zookeeper
        conn2 = ZooKeeper('127.0.0.1:2184', wait=True)
        self.assertTrue(conn2.exists(u'/test/node2'))
        node2 = ZkNode(conn2, u'/test/node2')
        self.assertEqual(node2.value, 2)
        conn2.close()
