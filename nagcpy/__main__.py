
def main():
    import argparse
    from pint import UnitRegistry
    from nagcpy import nix_heuristic_gc

    parser = argparse.ArgumentParser()
    parser.add_argument("--penalize-drvs", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--penalize-substitutable", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--dry-run", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("reclaim_bytes")

    parsed = vars(parser.parse_args())

    ur = UnitRegistry()
    parsed["reclaim_bytes"] = int(ur(parsed["reclaim_bytes"]).m_as("B"))

    nix_heuristic_gc(**parsed)

if __name__ == "__main__":
    main()
