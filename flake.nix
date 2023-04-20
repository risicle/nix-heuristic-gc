{
  description = "nix-heuristic-gc";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem flake-utils.lib.allSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      nhgc = import ./default.nix { inherit pkgs; };
    in {
      packages.default = nhgc.pkg;
    });
}
