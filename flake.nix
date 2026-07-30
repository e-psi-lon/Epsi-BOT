{
  description = "epsi-bot: dev shell + package build (uv2nix)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ flake-parts, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      perSystem = { pkgs, lib, ... }:
        let
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };
          pyprojectOverrides = final: prev: {
            pynacl = prev.pynacl.overrideAttrs (old: {
              buildInputs = (old.buildInputs or [ ]) ++ [ pkgs.libsodium ];
              nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.pkg-config ];
            });
            asyncpg = prev.asyncpg.overrideAttrs (old: {
              nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.pkg-config ];
              buildInputs = (old.buildInputs or [ ]) ++ [ pkgs.postgresql.lib ];
            });
            epsi-bot = prev.epsi-bot.overrideAttrs (old: {
              nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ final.resolveBuildSystem {
                editables = [ ];
              };
            });
          };

          python = pkgs.python314;
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope
              (lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                overlay
                pyprojectOverrides
              ]);

          venv = pythonSet.mkVirtualEnv "epsi-bot-env" workspace.deps.default;

          editableOverlay = workspace.mkEditablePyprojectOverlay {
            root = "$REPO_ROOT";
          };
          editablePythonSet = pythonSet.overrideScope editableOverlay;
          editableVenv = editablePythonSet.mkVirtualEnv "epsi-bot-dev-env" workspace.deps.all;
        in
        {
          packages = {
            default = venv;
            epsi-bot = venv;
            image = pkgs.dockerTools.streamLayeredImage {
              name = "epsi-bot";
              tag = "latest";
              contents = [ venv ];
              config = {
                Entrypoint = [ "${venv}/bin/epsi-bot" ];
              };
            };
          };

          apps.default = {
            type = "app";
            program = "${venv}/bin/epsi-bot";
          };

          devShells.default = pkgs.mkShell {
            packages = with pkgs; [
              editableVenv
              uv
              ffmpeg
              libsodium
              postgresql
              pkg-config
              gcc
              git
            ];

            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = "${editableVenv}/bin/python";
              UV_PYTHON_DOWNLOADS = "never";
            };

            shellHook = ''
              export REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
              echo "Python: $(python3 --version)"
              echo "uv: $(uv --version)"
              echo "epsi-bot dev venv active (editable, live source)"
            '';
          };

          devShells.impure = pkgs.mkShell {
            packages = with pkgs; [ python uv ffmpeg libsodium postgresql pkg-config gcc git ];
            env = {
              UV_PYTHON = "${python}/bin/python3.14";
              UV_PYTHON_DOWNLOADS = "never";
              UV_LINK_MODE = "copy";
            };
          };
        };
  };
}
