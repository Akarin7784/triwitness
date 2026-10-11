#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/integration/test_main.py::test_errors_sorted \
  tests/integration/test_main.py::test_form_feed_line_split \
  tests/integration/test_main.py::test_e101_indent_char_does_not_reset \
  tests/integration/test_main.py::test_statistics_option \
  tests/integration/test_main.py::test_show_source_option \
  tests/integration/test_main.py::test_extend_exclude \
  tests/integration/test_main.py::test_malformed_per_file_ignores_error \
  tests/integration/test_main.py::test_tokenization_error_but_not_syntax_error \
  tests/integration/test_main.py::test_tokenization_error_is_a_syntax_error \
  tests/integration/test_main.py::test_bug_report_successful \
  tests/integration/test_main.py::test_benchmark_successful \
  tests/integration/test_main.py::test_specific_noqa_does_not_clobber_pycodestyle_noqa \
  tests/integration/test_main.py::test_specific_noqa_on_line_with_continuation \
  tests/integration/test_main.py::test_physical_line_file_not_ending_in_newline \
  tests/integration/test_main.py::test_physical_line_file_not_ending_in_newline_trailing_ws \
  tests/integration/test_main.py::test_obtaining_args_from_sys_argv_when_not_explicity_provided \
  tests/integration/test_main.py::test_cli_config_option_respected \
  tests/integration/test_main.py::test_cli_isolated_overrides_config_option \
  tests/integration/test_main.py::test_file_not_found \
  tests/integration/test_main.py::test_output_file \
  tests/integration/test_main.py::test_early_keyboard_interrupt_does_not_crash \
  tests/integration/test_main.py::test_config_file_not_found \
  tests/integration/test_main.py::test_format_option_help; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
