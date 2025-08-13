{ pkgs ? import <nixpkgs> {}
, system ? builtins.currentSystem
, pythonPackages ? pkgs.python311Packages
, forTest ? true
, forDev ? true
}:
let
  nixComponents = pkgs.nixVersions.nixComponents_2_29;
in
{
  nhgcEnv = pkgs.stdenv.mkDerivation {
    name = "nix-heuristic-gc-env";

    NIX_SYSTEM = system;

    buildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.pybind11
      pythonPackages.setuptools
      pythonPackages.rustworkx
      nixComponents.nix-store
      nixComponents.nix-main
      pkgs.boost
    ] ++ pkgs.lib.optionals forTest [
      pythonPackages.pytest
    ] ++ pkgs.lib.optionals forDev [
      pythonPackages.ipython
      pythonPackages.matplotlib
      pkgs.pwndbg
      pkgs.less
    ];
  };

  pkg = pythonPackages.buildPythonPackage {
    pname = "nix-heuristic-gc";
    version = pkgs.lib.removeSuffix "\n" (builtins.readFile ./VERSION);
    src = pkgs.nix-gitignore.gitignoreSource ["*.nix" "flake.lock"] ./.;

    NIX_SYSTEM = system;

    buildInputs = [
      pkgs.boost
      nixComponents.nix-store
      nixComponents.nix-main
      pythonPackages.pybind11
      pythonPackages.setuptools
    ];
    propagatedBuildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.rustworkx
    ];

    checkInputs = [
      pythonPackages.pytestCheckHook
    ];
    preCheck = ''
      mv nix_heuristic_gc .nix_heuristic_gc
    '';
  };
}
