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
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  outputs = inputs@{ flake-parts, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      perSystem = { pkgs, lib, ... }:
        let
          ffmpeg-slim = pkgs.ffmpeg-headless.override {
            # video codecs / image formats
            withAom = false; withDav1d = false; withSvtav1 = false; withVpx = false;
            withX264 = false; withX265 = false; withXvid = false; withTheora = false;
            withWebp = false; withOpenjpeg = false; withOpenapv = false;
            withBluray = false; withZimg = false; withVidStab = false;
            # text rendering
            withAss = false; withFontconfig = false; withFreetype = false;
            withFribidi = false; withHarfbuzz = false; withZvbi = false;
            # hardware / devices
            withVulkan = false; withV4l2 = false; withVaapi = false; withDrm = false;
            withOpencl = false; withAlsa = false; withNvcodec = false;
            # audio extras (this is what removes pulse/dbus/glib/jack)
            withOpenmpt = false; withMp3lame = false; withVorbis = false; withSpeex = false;
            # network extras (gnutls stays on)
            withSsh = false; withSrt = false; withRist = false; withGmp = false;
            # build time and size
            withSmallBuild = true;
            withCudaLLVM = false;
            withHtmlDoc = false; withManPages = false; withPodDoc = false; withTxtDoc = false;
          };
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };
          pyprojectOverrides = final: prev: {
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
          runtimeDeps = [ ffmpeg-slim ];

          epsi-bot = pkgs.symlinkJoin {
            name = "epsi-bot";
            paths = [ venv ];
            nativeBuildInputs = [ pkgs.makeWrapper ];
            postBuild = ''
              wrapProgram $out/bin/epsi-bot \
                --prefix PATH : ${lib.makeBinPath runtimeDeps}
            '';
            meta.mainProgram = "epsi-bot";
          };

          editableOverlay = workspace.mkEditablePyprojectOverlay {
            root = "$REPO_ROOT";
          };
          editablePythonSet = pythonSet.overrideScope editableOverlay;
          editableVenv = editablePythonSet.mkVirtualEnv "epsi-bot-dev-env" workspace.deps.all;
        in
        {
          packages = {
            default = epsi-bot;
            epsi-bot = epsi-bot;
            image = pkgs.dockerTools.streamLayeredImage {
              name = "epsi-bot";
              tag = "latest";
              contents = with pkgs; [ epsi-bot cacert ];
              config = {
                Entrypoint = [ (lib.getExe epsi-bot) ];
                Env = [
                  "DB_USER=epsi_bot"
                  "DB_NAME=epsi_bot"
                  "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                ];
              };
            };
          };

          apps.default = {
            type = "app";
            program = lib.getExe epsi-bot;
          };

          devShells.default = pkgs.mkShell {
             packages = [ editableVenv ] ++ runtimeDeps ++ (with pkgs; [
              uv
              libsodium
              postgresql
              pkg-config
              gcc
              git
            ]);

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
              packages = [ python ] ++ runtimeDeps ++ (with pkgs; [ uv libsodium postgresql pkg-config gcc git ]);
              env = {
              UV_PYTHON = lib.getExe python;
              UV_PYTHON_DOWNLOADS = "never";
              UV_LINK_MODE = "copy";
            };
          };
        };
  };
}
