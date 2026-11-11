#!/usr/bin/env bash
set -euo pipefail
release=https://github.com/open-policy-agent/conftest/releases/download/v0.56.0
archive=conftest_0.56.0_Linux_x86_64.tar.gz
curl --fail --silent --show-error --location "$release/$archive" -o "$archive"
curl --fail --silent --show-error --location "$release/checksums.txt" -o checksums.txt
grep " $archive$" checksums.txt | sha256sum --check --strict
tar xzf "$archive" conftest
./conftest test plan.json --policy "$GITHUB_WORKSPACE/policies" --all-namespaces
