{ pkgs ? import <nixpkgs> {}
, system ? builtins.currentSystem
, pythonPackages ? pkgs.python310Packages
, forTest ? true
, forDev ? true
}:
{
  nhgcEnv = pkgs.stdenv.mkDerivation {
    name = "nix-heuristic-gc-env";

    NIX_SYSTEM = system;

    buildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.pybind11
      pythonPackages.setuptools
      pythonPackages.retworkx
      pkgs.boost
      pkgs.nix
    ] ++ pkgs.lib.optionals forTest [
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
      pkgs.nix
      pythonPackages.pybind11
      pythonPackages.setuptools
    ];
    propagatedBuildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.retworkx
    ];
  };
}
