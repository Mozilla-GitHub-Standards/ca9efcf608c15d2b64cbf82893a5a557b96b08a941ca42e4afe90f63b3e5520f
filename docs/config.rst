=============
Configuration
=============

`qdo` uses an ini-style configuration file for most of its configuration. The
configuration file is specified via the `-c` option to the `qdo-worker`
script. It defaults to `etc/qdo-worker.conf`.

For example::

    bin/qdo-worker -c etc/my-qdo.conf

Settings
========

All settings are specified in the `[qdo-worker]` section.

wait_interval
    Interval in seconds for which the worker pauses if it has no messages to
    work on. Defaults to 5 seconds.

zookeeper_connection
    Which Zookeeper instance(s) to connect to. Defaults to `127.0.0.1:2181`.
    Multiple Zookeeper instances can be specified as a comma separated list:
    10.0.0.1:2181,10.0.0.2:2181,10.0.0.3:2181

zookeeper_namespace
    The path to the root Zookeeper node, under which `qdo` will store all its
    information. Defaults to `mozilla-qdo`. The node needs to be created
    before `qdo-worker` is run.