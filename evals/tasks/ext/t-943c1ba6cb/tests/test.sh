#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_create_filtered_test_list \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_get_greentea_version \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_get_hello_string \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_get_local_host_tests_dir_default_path \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_get_local_host_tests_dir_invalid_path \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_get_local_host_tests_dir_valid_path \
  test/mbed_gt_cli.py::GreenteaCliFunctionality::test_print_version \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_find_targets_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_find_targets_json_ignored \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_mbed_target_from_current_dir_ok \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_mbed_targets_from_yotta_local_module_invalid_path \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_mbed_targets_from_yotta_local_module_invalid_target \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_mbed_targets_from_yotta_local_module_valid \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_empty_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_in_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_invalid_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_no_file \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_no_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_platform_property_from_targets_no_value \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_yotta_target_from_local_config_failed_open \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_yotta_target_from_local_config_invalid_path \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_get_yotta_target_from_local_config_valid_path \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_add_target_info_mapping \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_missing_json_data \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_missing_keywords \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_missing_name \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_missing_target \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_multiple \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_no_keywords \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_mbed_target_from_target_json_no_name \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_json_for_build_name \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output_new_style \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output_new_style_text \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output_new_style_text_2 \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output_text \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_search_cmd_output_with_ssl_errors \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_fail \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_chars \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_nl \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_nl_whitechars \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_rcnl \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_rcnl_whitechars \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_version \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_parse_yotta_target_cmd_output_mixed_whitechars \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_default \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_default_missing \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_info_mapping \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_info_mapping_bad_platform \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_info_mapping_missing \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_targets_json_base_target \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_targets_json_empty \
  test/mbed_gt_target_info.py::GreenteaTargetInfo::test_platform_property_from_targets_json_inherits; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
