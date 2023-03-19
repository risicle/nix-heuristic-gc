from itertools import chain
from os import scandir, stat
from stat import S_ISDIR

def direntry_max_atime(direntry):
    try:
        if direntry.is_dir(follow_symlinks=False):
            # we are not interested in the atime of directories
            # themselves because we ourselves affect them by
            # walking them
            return dir_max_atime(direntry.path)

        return direntry.stat(follow_symlinks=False).st_atime
    except PermissionError:
        return 0


def dir_max_atime(path):
    return max(chain(
        (direntry_max_atime(direntry) for direntry in scandir(path)),
        # avoid max() being fed an empty sequence
        (0,),
    ))


def path_max_atime(path):
    s = stat(path, follow_symlinks=False)
    if S_ISDIR(s.st_mode):
        return dir_max_atime(path)

    return s.st_atime