
def _add_penalize_args(
    grp,
    name:str,
    default:bool,
    help:str="",
    default_weight:int=5,
):
    dest = f"penalize_{name.replace('-','_')}"
    grp.add_argument(
        f"--penalize-{name}",
        dest=dest,
        action="store_const",
        const=5,
    )
    grp.add_argument(
        f"--no-penalize-{name}",
        dest=dest,
        action="store_const",
        const=None,
    )
    grp.add_argument(
        f"--penalize-{name}-weight",
        dest=dest,
        action="store",
        type=int,
        metavar="WEIGHT",
        help=help,
    )
    if default:
        grp.set_defaults(**{dest: 5})


def _weighting_help_text(
    basic:str,
    sflag:str,
    expl:str,
) -> str:
    return (
        f"{basic}, with weighting WEIGHT typically being a value from "
        f"1 (weak) to 10 (strong). {sflag} flag applies a WEIGHT of 5. {expl}."
    )


def main():
    import argparse
    from importlib.metadata import version as metadata_version, PackageNotFoundError
    import logging

    from humanfriendly import parse_size
    from nix_heuristic_gc import nix_heuristic_gc

    try:
        version = metadata_version("nix_heuristic_gc")
    except PackageNotFoundError:
        version = "unknown"

    parser = argparse.ArgumentParser(
        description="delete the least recently used or most easily replaced "
        "nix store paths based on customizable heuristics",
    )

    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "drvs",
        False,
        _weighting_help_text(
            "Prefer choosing .drv paths for deletion",
            "--penalize-drvs",
            ".drv files are usually easily regenerated and occupy an inode each",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "substitutable",
        True,
        _weighting_help_text(
            "Prefer choosing paths for deletion that are substitutable from a "
            "binary cache",
            "--penalize-substitutable",
            "On by default, this can slow down the path selection process for "
            "large collections due to the mass querying of binary cache(s)",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "inodes",
        False,
        _weighting_help_text(
            "Prefer choosing paths for deletion that will free up a lot of inodes",
            "--penalize-inodes",
            "This penalizes paths which have a large inode/size ratio",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "size",
        False,
        _weighting_help_text(
            "Prefer choosing fewer, large (by nar size) paths for deletion",
            "--penalize-size",
            "Recommend use with --penalize-exceeding-limit as this can cause "
            "significant overshoot",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "exceeding-limit",
        False,
        _weighting_help_text(
            "Attempt to avoid going significantly over the size limit",
            "--penalize-exceeding-limit",
            "This penalizes path selections that would cause more deletion "
            "than requested by reclaim_bytes proportional to the overshoot",
        )
    )

    parser.add_argument(
        "--dry-run",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Don't actually delete any paths, but print list of paths "
        "that would be deleted to stdout.",
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        help="Maximum number of threads to use when gathering path information. 0 "
        "disables multi-threading entirely. Default automatic. Concurrency is "
        "also limited by store settings' max-connections value - for best "
        "results increase that to a sensible value (perhaps via NIX_REMOTE?).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=version,
    )

    loglvl_grp = parser.add_mutually_exclusive_group()
    loglvl_grp.add_argument("--verbose", "-v", dest="loglevel", action="store_const", const=logging.DEBUG)
    loglvl_grp.add_argument("--quiet", "-q", dest="loglevel", action="store_const", const=logging.WARNING)

    parser.add_argument("reclaim_bytes")

    parsed = vars(parser.parse_args())

    parsed["reclaim_bytes"] = parse_size(parsed["reclaim_bytes"])

    loglevel = parsed.pop("loglevel", None)
    if loglevel is None:
        loglevel = logging.INFO

    logging.basicConfig(
        level=parsed.pop("loglevel", loglevel),
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    nix_heuristic_gc(**parsed)


if __name__ == "__main__":
    main()
