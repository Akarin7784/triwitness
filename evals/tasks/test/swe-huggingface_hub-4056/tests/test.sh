#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_utils_tqdm.py::TestCreateProgressBarCustomClass::test_custom_tqdm_class_not_disabled_in_non_tty \
  tests/test_utils_tqdm.py::TestCreateProgressBarCustomClass::test_custom_tqdm_class_ignores_hf_disable_signal \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_cannot_disable_tqdm_when_env_variable_is_set \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_cannot_enable_tqdm_when_env_variable_is_set \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_can_be_disabled_when_globally_enabled \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_disabled \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_disabled_cannot_be_forced \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_enabled \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_helpers \
  tests/test_utils_tqdm.py::TestTqdmUtils::test_tqdm_stream_file \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_disable_override_by_environment_variable \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_disable_specific_group \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_empty_group_is_root \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_enable_override_by_environment_variable \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_enable_specific_subgroup \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_multiple_level_toggling \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_nested_subgroup_behavior \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_partial_group_name_not_affected \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_progress_bar_context_respects_group \
  tests/test_utils_tqdm.py::TestTqdmGroup::test_progress_bar_respects_group \
  tests/test_utils_tqdm.py::TestCreateProgressBarCustomClass::test_custom_tqdm_class_no_name_kwarg; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
