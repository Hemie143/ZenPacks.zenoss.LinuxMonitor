##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import itertools

from zope.component import adapts
from zope.interface import implements

from math import isnan

from zExceptions import NotFound

from Products.ZenUtils.FunctionCache import FunctionCache
from Products.Zuul.catalog.interfaces import IIndexableWrapper

try:
    from Products.Zuul.catalog.global_catalog \
        import FileSystemWrapper as BaseFileSystemWrapper
except ImportError:
    # Zenoss 4.1 doesn't have FileSystemWrapper.
    from Products.Zuul.catalog.global_catalog import ComponentWrapper

    BaseFileSystemWrapper = ComponentWrapper

from ZenPacks.zenoss.LinuxMonitor.util import override_graph_labels, keyword_search

from . import schema


class FileSystem(schema.FileSystem):

    """
    Model class for FileSystem.
    Instances of this class get stored in ZODB.
    """

    def getTotalBlocks(self):

        availBlocks = self.cacheRRDValue('availBlocks', None)
        usedBlocks = self.usedBlocks()
        if availBlocks is not None and usedBlocks is not None:
            nonRootTotalBlocks = availBlocks + usedBlocks
            return nonRootTotalBlocks

        offset = getattr(self.primaryAq(), 'zFileSystemSizeOffset', 1.0)
        return int(self.totalBlocks) * offset

    def usedBlocks(self):
        dskPercent = self.cacheRRDValue("dskPercent", None)
        if dskPercent is not None and dskPercent != "Unknown" and not isnan(dskPercent):
            return self.getTotalBlocks() * dskPercent / 100.0

        blocks = self.cacheRRDValue('usedBlocks', None)
        if blocks is not None and not isnan(blocks):
            return long(blocks)
        
        return None

    def getTotalBlocks(self):

        availBlocks = self.cacheRRDValue('availBlocks', None)
        usedBlocks = self.usedBlocks()
        if availBlocks is not None and usedBlocks is not None:
            nonRootTotalBlocks = availBlocks + usedBlocks
            return nonRootTotalBlocks

        offset = getattr(self.primaryAq(), 'zFileSystemSizeOffset', 1.0)
        return int(self.totalBlocks) * offset

    def usedBlocks(self):
        dskPercent = self.cacheRRDValue("dskPercent", None)
        if dskPercent is not None and dskPercent != "Unknown" and not isnan(dskPercent):
            return self.getTotalBlocks() * dskPercent / 100.0

        blocks = self.cacheRRDValue('usedBlocks', None)
        if blocks is not None and not isnan(blocks):
            return long(blocks)

        return None

    def logicalVolume(self):
        """Return the underlying LogicalVolume."""
        if not self.mount:
            return

        results = itertools.chain.from_iterable(
            self.device().search(name, mountpoint=self.mount)
            for name in ('LogicalVolume', 'SnapshotVolume'))

        for result in results:
            try:
                return result.getObject()
            except Exception:
                pass
   
    def blockDevice(self):
        """Return the underlying HardDisk."""
        if not self.mount:
            return

        device = self.device()
        results = device.componentSearch.search({'meta_type': 'LinuxHardDisk'})
        for brain in results:
            try:
                hd = brain.getObject()
            except Exception:
                continue
            else:
                if hd.mount == self.mount:
                    return hd

    def impacting_object(self):
        """Return the impacting LogicalVolume, HardDisk, or Device.

        A FileSystem can be impacted by only one of: it's underlying
        LogicalVolume, HardDisk, or Device. In that order.

        """
        lv = self.logicalVolume()
        if lv:
            return lv

        bd = self.blockDevice()
        if bd:
            return bd

        return self.device()

    def getRRDTemplates(self):
        """
        For NFS mounts replace general FileSystem template with NFS-specific one.
        """
        old_templates = super(FileSystem, self).getRRDTemplates()

        if self.type != 'nfs':
            return old_templates

        new_templates = []

        for template in old_templates:
            if 'FileSystem' in template.id and 'FileSystem_NFS_Client' not in template.id:
                new_templates.append(self.getRRDTemplateByName(
                    template.id.replace('FileSystem', 'FileSystem_NFS_Client')))
            else:
                new_templates.append(template)

        return new_templates

    def getDefaultGraphDefs(self, drange=None):
        # Add and re-label graphs displayed in other components
        graphs = super(FileSystem, self).getDefaultGraphDefs(drange)

        bd = self.logicalVolume() or self.blockDevice()
        if bd:
            bdGraphs = override_graph_labels(bd, drange)
            graphs.extend(bdGraphs)

        return graphs

    def getGraphObjects(self):
        graphs = super(FileSystem, self).getGraphObjects()
        underlying = self.logicalVolume() or self.blockDevice()
        if underlying:
            for graph in underlying.getGraphObjects():
                graphs.append(graph)
        return graphs

    def getStorageServers(self):
        """Generate objects for storage server for this FileSystem."""
        try:
            device = self.device()
            search_root = self.getDmdRoot('Devices').Storage

            for filesystem in getStorageServerPaths(device, search_root):
                filesystem = self.getObjByPath(filesystem)
                if self.storageDevice in filesystem.storage_clients_list:
                    yield filesystem
        except (AttributeError, NotFound,):
            """
            Pass if filesystem has been already deleted (NotFound)
            or if it is not a LinuxFileSystem instance (AttributeError).
            """
            pass

    def getStorageDevice(self):
        """Get the storage device that contains this fs.

           :return: Storage component
           :rtype:  Component object
        """
        # Return self.type for non-storage type filesystems
        if not self.blockDevice():
            return self.type

        # For network mounted servers
        for server in self.getStorageServers():
            return server

        # The remainder should be HardDisk, LVM, or other block device
        storagedevice = None
        if self.logicalVolume():
            storagedevice = self.logicalVolume()
        elif self.blockDevice():
            storagedevice = self.blockDevice()

        return storagedevice

    def capacity(self):
        utilization = super(FileSystem, self).capacity()
        if isinstance(utilization, (int, float)):
            return '{} %'.format(utilization)
        return utilization


@FunctionCache("LinuxFileSystem_getStorageServerPaths", default_timeout=60)
def getStorageServerPaths(device, search_root):
    """Return the list of paths to external file system servers."""
    filesystem_servers = []
    search_keywords = set()
    for fs in device.os.filesystems():
        storage_device = fs.storageDevice
        if ':' in storage_device:
            search_keywords.add('has-nfs-client:{}'.format(storage_device))

    if search_keywords:
        for obj in keyword_search(search_root, search_keywords):
            filesystem_servers.append(obj.getPrimaryUrlPath())

    return filesystem_servers


class FileSystemWrapper(BaseFileSystemWrapper):
    '''
    Indexing adapter for FileSystem.
    '''

    implements(IIndexableWrapper)
    adapts(FileSystem)

    def searchKeywordsForChildren(self):
        """Return tuple of search keywords for FileSystem objects.

        Overrides ComponentWrapper to add junction point information for the FileSystem.
        This provides a way for storage servers to find
        the Linux FileSystem components by their junction point.

        """
        keywords = set()

        storage_device = self._context.storageDevice
        if ':' in storage_device:
            keywords.add(
                'has-nfs-server:{0}'.format(
                    storage_device
                )
            )

        return (
            super(FileSystemWrapper, self).searchKeywordsForChildren() +
            tuple(keywords))
