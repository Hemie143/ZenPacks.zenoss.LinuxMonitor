##########################################################################
#
#   Copyright 2009 Zenoss, Inc. All Rights Reserved.
#
##########################################################################


import os

from Products.DataCollector.tests.BasePluginsTestCase \
        import BasePluginsTestCase

from Products.DataCollector.plugins.zenoss.cmd.linux.ifconfig \
        import ifconfig
        
from ZenPacks.zenoss.LinuxMonitor.modeler.plugins.zenoss.cmd.linux.cpuinfo \
        import cpuinfo

class LinuxPluginsTestCase(BasePluginsTestCase):
    
    
    def runTest(self):
        """
        Test all of the plugins that have test data files in the data
        directory.
        """
        
        Plugins = [ifconfig, cpuinfo]
        datadir = "%s/plugindata/linux" % (os.path.dirname(__file__))
        self._testDataFiles(datadir, Plugins)
        
        
def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(LinuxPluginsTestCase))
    return suite
