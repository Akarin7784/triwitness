#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  conans/test/unittests/model/conanfile_test.py::ConanFileTest::test_conanfile_new_print_save \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_toolchain_user_toolchain \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_toolchain_custom_toolchain \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_toolchain_without_build_type \
  'conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_presets_duplicated_install[True]' \
  'conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_presets_duplicated_install[False]' \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_remove_missing_presets \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmake_presets_not_forbidden_build_type \
  conans/test/functional/toolchains/cmake/test_cmake_toolchain.py::test_cmaketoolchain_conf_from_tool_require \
  conans/test/unittests/model/conanfile_test.py::ConanFileTest::test_conanfile_naming \
  conans/test/unittests/model/conanfile_test.py::ConanFileTest::test_conanfile_naming_complete \
  conans/test/unittests/model/conanfile_test.py::ConanFileTest::test_conanfile_new_print; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
