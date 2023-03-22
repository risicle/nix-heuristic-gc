from functools import reduce
from itertools import chain
from os import scandir, stat
from stat import S_ISDIR

def direntry_stat_agg(direntry):
    try:
        if direntry.is_dir(follow_symlinks=False):
            # we are not interested in the atime of directories
            # themselves because we ourselves affect them by
            # walking them
            return dir_stat_agg(direntry.path)

        return direntry.stat(follow_symlinks=False).st_atime, 1
    except PermissionError:
        return 0, 1


def _stat_agg_reduction(a, b):
    atime_a, inodes_a = a
    atime_b, inodes_b = b
    return max(atime_a, atime_b), inodes_a + inodes_b


def dir_stat_agg(path):
    return reduce(
        _stat_agg_reduction,
        (direntry_stat_agg(direntry) for direntry in scandir(path)),
        (0, 1),
    )


def path_stat_agg(path):
    s = stat(path, follow_symlinks=False)
    if S_ISDIR(s.st_mode):
        return dir_stat_agg(path)

    return s.st_atime, 1
