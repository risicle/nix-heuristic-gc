import logging
from os.path import join as path_join

from humanfriendly import format_size

import libstore_wrapper as libstore

from nagcpy.graph import GarbageGraph

logger = logging.getLogger(__name__)

def nix_heuristic_gc(
    reclaim_bytes:int,
    penalize_substitutable:bool=True,
    penalize_drvs:bool=False,
    penalize_inodes:bool=False,
    penalize_size:bool=False,
    penalize_exceeding_limit:bool=False,
    dry_run:bool=True,
):
    store = libstore.Store()

    garbage_graph = GarbageGraph(
        store=store,
        penalize_substitutable=1e5 if penalize_substitutable else None,
        penalize_drvs=1e5 if penalize_drvs else None,
        penalize_inodes=1e6 if penalize_inodes else None,
        penalize_size=1e-3 if penalize_size else None,
        penalize_exceeding_limit=1e4 if penalize_exceeding_limit else None,
    )
    logger.info("selecting store paths for removal")
    to_reclaim = garbage_graph.remove_nar_bytes(reclaim_bytes)

    logger.info(
        "%(maybe_not)srequesting deletion of %(count)s store paths, total nar_size %(size)s, %(inodes)s inodes",
        {
            "maybe_not": "(not) " if dry_run else "",
            "count": len(to_reclaim),
            "size": format_size(sum(spn.nar_size for spn in to_reclaim), binary=True),
            "inodes": sum(spn.inodes for spn in to_reclaim),
        },
    )

    if dry_run:
        nix_store_path = libstore.get_nix_store_path()
        for spn in to_reclaim:
            print(path_join(nix_store_path, spn.path))
    else:
        _, bytes_freed = store.collect_garbage(
            action=libstore.GCAction.GCDeleteSpecific,
            paths_to_delete={
                libstore.StorePath(spn.path) for spn in to_reclaim
            },
        )
        logger.info("freed %(size)s", {"size": format_size(bytes_freed, binary=True)})
