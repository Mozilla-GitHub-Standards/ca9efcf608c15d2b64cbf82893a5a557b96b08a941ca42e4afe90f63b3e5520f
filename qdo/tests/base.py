# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from zc.zk import ZooKeeper
from zktools.node import ZkNode

from qdo.config import ZOO_DEFAULT_ROOT

connections = {}


class ZKBase(object):

    zk_root = ZOO_DEFAULT_ROOT

    @classmethod
    def setUpClass(cls):
        global connections
        conn = connections.get(u'zk_root', None)
        if conn is None:
            connections[u'zk_root'] = conn = ZooKeeper(
                u'127.0.0.1:2187', wait=True)
        if conn.exists(cls.zk_root):
            conn.delete_recursive(cls.zk_root)
        ZkNode(conn, cls.zk_root)

    @classmethod
    def tearDownClass(cls):
        global connections
        conn = connections.get(u'zk_root', None)
        if conn is not None:
            conn.delete_recursive(cls.zk_root)
            conn.close()
            del connections[u'zk_root']

    @classmethod
    def _make_zk_conn(cls):
        return ZooKeeper(u'127.0.0.1:2181,127.0.0.1:2184,127.0.0.1:2187' +
            cls.zk_root, wait=True)

    @classmethod
    def _clean_zk(cls, conn):
        for child in conn.get_children(u'/'):
            conn.delete_recursive(u'/' + child)