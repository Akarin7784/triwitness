#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/unit/test_settings.py::test_find_config \
  tests/unit/test_ticketed_features.py::test_isort_respects_quiet_from_sort_file_api_see_1461 \
  tests/unit/test_settings.py::TestConfig::test_init \
  tests/unit/test_settings.py::TestConfig::test_init_unsupported_settings_fails_gracefully \
  tests/unit/test_settings.py::TestConfig::test_known_settings \
  tests/unit/test_settings.py::TestConfig::test_invalid_settings_path \
  tests/unit/test_settings.py::TestConfig::test_invalid_pyversion \
  tests/unit/test_settings.py::TestConfig::test_invalid_profile \
  tests/unit/test_settings.py::TestConfig::test_is_skipped \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_ioerror \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_shebang \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_editor_backup \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_defaults \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_configuration \
  tests/unit/test_settings.py::TestConfig::test_is_supported_filetype_fifo \
  tests/unit/test_settings.py::TestConfig::test_src_paths_are_combined_and_deduplicated \
  tests/unit/test_settings.py::TestConfig::test_src_paths_supports_glob_expansion \
  tests/unit/test_settings.py::TestConfig::test_deprecated_multi_line_output \
  tests/unit/test_settings.py::test_as_list \
  tests/unit/test_settings.py::test_find_config_deep \
  tests/unit/test_settings.py::test_get_config_data \
  tests/unit/test_settings.py::test_editorconfig_without_sections \
  tests/unit/test_settings.py::test_get_config_data_with_toml_and_utf8 \
  tests/unit/test_settings.py::test_as_bool \
  tests/unit/test_settings.py::test_find_all_configs \
  tests/unit/test_ticketed_features.py::test_semicolon_ignored_for_dynamic_lines_after_import_issue_1178 \
  tests/unit/test_ticketed_features.py::test_isort_automatically_removes_duplicate_aliases_issue_1193 \
  tests/unit/test_ticketed_features.py::test_isort_enables_floating_imports_to_top_of_module_issue_1228 \
  tests/unit/test_ticketed_features.py::test_isort_provides_official_api_for_diff_output_issue_1335 \
  tests/unit/test_ticketed_features.py::test_isort_warns_when_known_sections_dont_match_issue_1331 \
  tests/unit/test_ticketed_features.py::test_isort_supports_append_only_imports_issue_727 \
  tests/unit/test_ticketed_features.py::test_treating_comments_as_code_issue_1357 \
  tests/unit/test_ticketed_features.py::test_isort_allows_setting_import_types_issue_1181 \
  tests/unit/test_ticketed_features.py::test_isort_enables_deduping_section_headers_issue_953 \
  tests/unit/test_ticketed_features.py::test_isort_doesnt_remove_as_imports_when_combine_star_issue_1380 \
  tests/unit/test_ticketed_features.py::test_isort_support_custom_groups_above_stdlib_that_contain_stdlib_modules_issue_1407 \
  tests/unit/test_ticketed_features.py::test_isort_intelligently_places_noqa_comments_issue_1456 \
  tests/unit/test_ticketed_features.py::test_float_to_top_should_respect_existing_newlines_between_imports_issue_1502 \
  tests/unit/test_ticketed_features.py::test_api_to_allow_custom_diff_and_output_stream_1583 \
  tests/unit/test_ticketed_features.py::test_autofix_mixed_indent_imports_1575 \
  tests/unit/test_ticketed_features.py::test_indented_import_headings_issue_1604 \
  tests/unit/test_ticketed_features.py::test_isort_auto_detects_and_ignores_invalid_from_imports_issue_1688 \
  tests/unit/test_ticketed_features.py::test_isort_allows_reversing_sort_order_issue_1645 \
  tests/unit/test_ticketed_features.py::test_isort_can_push_star_imports_above_others_issue_1504 \
  tests/unit/test_ticketed_features.py::test_isort_can_combine_reverse_sort_with_force_sort_within_sections_issue_1726 \
  tests/unit/test_ticketed_features.py::test_isort_can_turn_off_import_adds_with_action_comment_issue_1737 \
  tests/unit/test_ticketed_features.py::test_cython_pure_python_imports_2062; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
