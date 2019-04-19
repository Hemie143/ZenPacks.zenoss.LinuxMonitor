##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from . import schema


class LinuxDevice(schema.LinuxDevice):

    """Model class for evice.

    Extends Device defined in zenpack.yaml.

    """

    def all_harddisks(self):
        """Generate all HardDisk components."""
        for hd in self.hw.harddisks():
            yield hd

    def impacted_filesystems(self):
        """Generate filesystems impacted by this device.

        The filesystems on a device can either be impacted by their underlying
        HardDisk, LogicalVolume, or in the absence of either of those, its
        Device. This method only generates filesystems that themselves claim to
        be impacted by their device.

        """
        from .FileSystem import FileSystem
        for fs in self.os.filesystems():
            if isinstance(fs, FileSystem):
                if fs.impacting_object() == self:
                    yield fs
