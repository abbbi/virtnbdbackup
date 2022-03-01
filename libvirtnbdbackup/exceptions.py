"""
    Exceptions
"""


class CheckpointException(Exception):
    """Base checkpoint Exception"""


class NoCheckpointsFound(CheckpointException):
    """Inc or differencial backup attempted but
    no existing checkpoints are found."""


class RedefineCheckpointError(CheckpointException):
    """During redefining existing checkpoints after
    vm relocate, an error occured"""


class ForeignCeckpointError(CheckpointException):
    """Checkpoint for vm found which was not created
    by virtnbdbackup"""


class BackupException(Exception):
    """Base backup Exception"""


class DiskBackupFailed(BackupException):
    """Backup of one disk failed"""


class DiskBackupWriterException(BackupException):
    """Opening the target file writer
    failed"""
