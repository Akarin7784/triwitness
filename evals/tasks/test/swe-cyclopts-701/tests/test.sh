#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_lazy_commands.py::test_lazy_subapp_help_excludes_help_version_flags \
  tests/test_lazy_commands.py::test_command_spec_basic_function \
  tests/test_lazy_commands.py::test_command_spec_invalid_format \
  tests/test_lazy_commands.py::test_command_spec_module_not_found \
  tests/test_lazy_commands.py::test_command_spec_attribute_not_found \
  tests/test_lazy_commands.py::test_command_spec_caching \
  tests/test_lazy_commands.py::test_lazy_command_registration \
  tests/test_lazy_commands.py::test_lazy_command_execution \
  tests/test_lazy_commands.py::test_lazy_command_name_transform \
  tests/test_lazy_commands.py::test_lazy_command_with_alias \
  tests/test_lazy_commands.py::test_lazy_command_collision \
  tests/test_lazy_commands.py::test_lazy_command_help \
  tests/test_lazy_commands.py::test_lazy_and_immediate_commands_mixed \
  tests/test_lazy_commands.py::test_lazy_command_not_resolved_until_accessed \
  tests/test_lazy_commands.py::test_lazy_command_app_kwargs \
  tests/test_lazy_commands.py::test_lazy_command_parse_commands \
  tests/test_lazy_commands.py::test_lazy_command_iteration \
  tests/test_lazy_commands.py::test_lazy_command_contains \
  tests/test_lazy_commands.py::test_lazy_command_resolves_to_app_instance \
  tests/test_lazy_commands.py::test_lazy_subcommands \
  tests/test_lazy_commands.py::test_lazy_command_custom_name_in_help \
  tests/test_lazy_commands.py::test_lazy_function_inherits_parent_help_flags \
  tests/test_lazy_commands.py::test_lazy_function_inherits_parent_version_flags \
  tests/test_lazy_commands.py::test_lazy_function_inherits_parent_groups \
  tests/test_lazy_commands.py::test_lazy_app_inherits_parent_groups_when_unset \
  tests/test_lazy_commands.py::test_lazy_app_doesnt_override_existing_groups \
  tests/test_lazy_commands.py::test_lazy_app_rejects_kwargs \
  tests/test_lazy_commands.py::test_lazy_app_name_must_match \
  tests/test_lazy_commands.py::test_lazy_app_name_match_allows_resolution; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
