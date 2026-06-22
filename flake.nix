{
  description = "User-space development shell for ARIS on NVIDIA DGX Spark";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "aarch64-linux" "x86_64-linux" ] (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          config.android_sdk.accept_license = true;
        };
        lib = pkgs.lib;
        pick = names:
          let found = lib.findFirst (name: builtins.hasAttr name pkgs) null names;
          in if found == null then null else builtins.getAttr found pkgs;
        maybe = names:
          let p = pick names;
          in lib.optional (p != null) p;
        androidComposition = pkgs.androidenv.composeAndroidPackages {
          platformVersions = [ "36" ];
          buildToolsVersions = [ "36.0.0" "35.0.0" "28.0.3" ];
          includeNDK = true;
          ndkVersions = [ "28.2.13676358" ];
          includeCmake = true;
          cmakeVersions = [ "3.22.1" ];
          includeEmulator = false;
          includeSystemImages = false;
        };
      in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            git
            git-lfs
            direnv
            just
            jq
            yq
            ripgrep
            fd
            tree
            tmux
            neovim
            python3
            python3Packages.pytest
            python3Packages.pydantic
            uv
            ruff
            mypy
            pre-commit
            flutter
            dart
            jdk17
            android-tools
            androidComposition.androidsdk
            cmake
            ninja
            pkg-config
            clang
            clang-tools
            gtk3
            gdb
            usbutils
            pciutils
            lsof
            socat
            can-utils
            xauth
            xhost
            openocd
          ]
          ++ maybe [ "probe-rs-tools" "probe-rs" ]
          ++ maybe [ "rustc" ]
          ++ maybe [ "cargo" ]
          ++ maybe [ "rustfmt" ]
          ++ maybe [ "clippy" ]
          ++ maybe [ "rust-analyzer" ]
          ++ maybe [ "cargo-binutils" ]
          ++ maybe [ "docker-client" "docker" ]
          ++ maybe [ "docker-compose" "docker-compose_2" "docker-compose-v2" ]
          ++ maybe [ "minicom" "tio" ]
          ++ maybe [ "gcc-arm-embedded" "gcc-arm-none-eabi" "pkgsCross.arm-embedded.stdenv.cc" ];

          shellHook = ''
            export ARIS_HOME="''${ARIS_HOME:-$HOME/aris}"
            export ARIS_WS="''${ARIS_WS:-$PWD}"
            export ARIS_DATA="''${ARIS_DATA:-$ARIS_HOME/data}"
            export ARIS_LOGS="''${ARIS_LOGS:-$ARIS_HOME/logs}"
            export ARIS_MODELS="''${ARIS_MODELS:-$ARIS_HOME/models}"
            export HF_HOME="''${HF_HOME:-$ARIS_MODELS/hf}"
            export TRANSFORMERS_CACHE="''${TRANSFORMERS_CACHE:-$ARIS_MODELS/hf}"
            export TORCH_HOME="''${TORCH_HOME:-$ARIS_MODELS/torch}"
            export ROS_DOMAIN_ID="''${ROS_DOMAIN_ID:-42}"
            export ROS_LOCALHOST_ONLY="''${ROS_LOCALHOST_ONLY:-1}"
            export RMW_IMPLEMENTATION="''${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
            export ARIS_ENABLE_REAL_ACTUATION="''${ARIS_ENABLE_REAL_ACTUATION:-0}"
            export ANDROID_HOME="${androidComposition.androidsdk}/libexec/android-sdk"
            export ANDROID_SDK_ROOT="$ANDROID_HOME"
            export ANDROID_NDK_ROOT="$ANDROID_HOME/ndk-bundle"
            export ANDROID_NDK_HOME="$ANDROID_NDK_ROOT"
            export JAVA_HOME="${pkgs.jdk17.home}"
            export PATH="${pkgs.android-tools}/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

            mkdir -p "$ARIS_DATA" "$ARIS_LOGS" "$ARIS_MODELS" "$HF_HOME" "$TORCH_HOME"

            echo "ARIS dev shell"
            echo "  system: ${system}"
            echo "  ARIS_WS=$ARIS_WS"
            echo "  ARIS_HOME=$ARIS_HOME"
            echo "  ROS_DOMAIN_ID=$ROS_DOMAIN_ID ROS_LOCALHOST_ONLY=$ROS_LOCALHOST_ONLY"
            echo "  real actuation: $ARIS_ENABLE_REAL_ACTUATION (must be 1 to enable hardware outputs)"
          '';
        };
      });
}
