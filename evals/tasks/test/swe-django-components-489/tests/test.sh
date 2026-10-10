#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_autodiscover.py::TestStaticFilesDirs::test_static_files_dirs \
  tests/test_autodiscover.py::TestAutodiscover::test_autodiscover_with_components_as_views \
  tests/test_autodiscover.py::TestLoaderSettingsModule::test_complex_settings_module \
  tests/test_autodiscover.py::TestLoaderSettingsModule::test_complex_settings_module_2 \
  tests/test_autodiscover.py::TestLoaderSettingsModule::test_complex_settings_module_3 \
  tests/test_autodiscover.py::TestLoaderSettingsModule::test_get_dirs \
  tests/test_autodiscover.py::TestBaseDir::test_base_dir \
  tests/test_autodiscover.py::TestFilepathToPythonModule::test_handles_nonlinux_paths \
  tests/test_autodiscover.py::TestFilepathToPythonModule::test_prepares_path; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
