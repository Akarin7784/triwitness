#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/commands/execution/test_run.py::test_implicit_priority[regular]' \
  'tests/commands/execution/test_run.py::test_implicit_priority[adhoc]' \
  tests/commands/execution/test_run.py::test_run_requires_step \
  'tests/commands/execution/test_run.py::test_run_env_var[regular-custom]' \
  'tests/commands/execution/test_run.py::test_run_env_var[regular-override-default]' \
  'tests/commands/execution/test_run.py::test_run_env_var[adhoc-custom]' \
  'tests/commands/execution/test_run.py::test_run_env_var[adhoc-override-default]' \
  'tests/commands/execution/test_run.py::test_run_env[regular]' \
  'tests/commands/execution/test_run.py::test_run_env[adhoc]' \
  'tests/commands/execution/test_run.py::test_run_tags[regular]' \
  'tests/commands/execution/test_run.py::test_run_tags[adhoc]' \
  'tests/commands/execution/test_run.py::test_run_spot_restart[regular]' \
  'tests/commands/execution/test_run.py::test_run_spot_restart[adhoc]' \
  'tests/commands/execution/test_run.py::test_run_with_yaml_path[regular]' \
  'tests/commands/execution/test_run.py::test_run_with_yaml_path[adhoc]' \
  'tests/commands/execution/test_run.py::test_run_input[regular]' \
  'tests/commands/execution/test_run.py::test_run_input[adhoc]' \
  'tests/commands/execution/test_run.py::test_run_params[regular-direct]' \
  'tests/commands/execution/test_run.py::test_run_params[regular-file]' \
  'tests/commands/execution/test_run.py::test_run_params[regular-mix]' \
  'tests/commands/execution/test_run.py::test_run_params[adhoc-direct]' \
  'tests/commands/execution/test_run.py::test_run_params[adhoc-file]' \
  'tests/commands/execution/test_run.py::test_run_params[adhoc-mix]' \
  tests/commands/execution/test_run.py::test_param_type_validation_integer \
  tests/commands/execution/test_run.py::test_param_type_validation_flag \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[regular-yes-True]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[regular-no-False]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[regular-1-True]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[regular-FALSE-False]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[regular-True-True]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[adhoc-yes-True]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[adhoc-no-False]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[adhoc-1-True]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[adhoc-FALSE-False]' \
  'tests/commands/execution/test_run.py::test_flag_param_coercion[adhoc-True-True]' \
  tests/commands/execution/test_run.py::test_run_no_git \
  tests/commands/execution/test_run.py::test_param_input_sanitization \
  'tests/commands/execution/test_run.py::test_multi_parameter_serialization[regular]' \
  'tests/commands/execution/test_run.py::test_multi_parameter_serialization[adhoc]' \
  'tests/commands/execution/test_run.py::test_multi_parameter_command_line_argument[regular]' \
  'tests/commands/execution/test_run.py::test_multi_parameter_command_line_argument[adhoc]' \
  tests/commands/execution/test_run.py::test_typo_check \
  tests/commands/execution/test_run.py::test_run_help \
  tests/commands/execution/test_run.py::test_command_help \
  'tests/commands/execution/test_run.py::test_remote[regular]' \
  'tests/commands/execution/test_run.py::test_remote[adhoc]' \
  'tests/commands/execution/test_run.py::test_remote_both_args[regular]' \
  'tests/commands/execution/test_run.py::test_remote_both_args[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_options[regular]' \
  'tests/commands/execution/test_run.py::test_kube_options[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_options_partial[regular]' \
  'tests/commands/execution/test_run.py::test_kube_options_partial[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_options_from_step[regular]' \
  'tests/commands/execution/test_run.py::test_kube_options_from_step[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_step_overrides[regular]' \
  'tests/commands/execution/test_run.py::test_kube_step_overrides[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_step_override_device_empty[regular]' \
  'tests/commands/execution/test_run.py::test_kube_step_override_device_empty[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_runtime_config_preset_argument[regular]' \
  'tests/commands/execution/test_run.py::test_kube_runtime_config_preset_argument[adhoc]' \
  'tests/commands/execution/test_run.py::test_kube_no_runtime_config_preset_argument[regular]' \
  'tests/commands/execution/test_run.py::test_kube_no_runtime_config_preset_argument[adhoc]' \
  'tests/commands/execution/test_run.py::test_no_git_adhoc_packaging[True]' \
  'tests/commands/execution/test_run.py::test_no_git_adhoc_packaging[False]' \
  'tests/commands/execution/test_run.py::test_priority[regular-0]' \
  'tests/commands/execution/test_run.py::test_priority[regular-7]' \
  'tests/commands/execution/test_run.py::test_priority[regular-42]' \
  'tests/commands/execution/test_run.py::test_priority[adhoc-0]' \
  'tests/commands/execution/test_run.py::test_priority[adhoc-7]' \
  'tests/commands/execution/test_run.py::test_priority[adhoc-42]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
