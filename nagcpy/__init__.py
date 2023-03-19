import libstore_wrapper as libstore

from nagcpy.graph import GarbageGraph

def nix_heuristic_gc(
    reclaim_bytes:int,
    penalize_substitutable:bool=True,
    penalize_drvs:bool=True,
    dry_run:bool=True,
):
    store = libstore.Store()

    garbage_graph = GarbageGraph(
        store=store,
        penalize_substitutable=penalize_substitutable,
        penalize_drvs=penalize_drvs,
    )
    to_reclaim = garbage_graph.remove_nar_bytes(reclaim_bytes)

    print(to_reclaim)

    if not dry_run:
        _, bytes_freed = store.collect_garbage(
            action=libstore.GCAction.GCDeleteSpecific,
            paths_to_delete={
                libstore.StorePath(spn.path) for spn in to_reclaim
            },
        )
        print(bytes_freed)
