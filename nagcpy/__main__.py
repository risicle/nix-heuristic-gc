
def main():
    import argparse
    import logging
    from humanfriendly import parse_size
    from nagcpy import nix_heuristic_gc

    parser = argparse.ArgumentParser()
    parser.add_argument("--penalize-drvs", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--penalize-substitutable", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--penalize-inodes", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--penalize-size", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--penalize-exceeding-limit", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--dry-run", default=False, action=argparse.BooleanOptionalAction)

    loglvl_grp = parser.add_mutually_exclusive_group()
    loglvl_grp.add_argument("--verbose", "-v", dest="loglevel", action="store_const", const=logging.DEBUG)
    loglvl_grp.add_argument("--quiet", "-q", dest="loglevel", action="store_const", const=logging.WARNING)

    parser.add_argument("reclaim_bytes")

    parsed = vars(parser.parse_args())

    parsed["reclaim_bytes"] = parse_size(parsed["reclaim_bytes"])

    logging.basicConfig(
        level=parsed.pop("loglevel", logging.INFO),
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    nix_heuristic_gc(**parsed)

if __name__ == "__main__":
    main()
