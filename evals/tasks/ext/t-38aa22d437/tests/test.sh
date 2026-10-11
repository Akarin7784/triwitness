#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_pytest.py::test_number_multiple_of_validation \
  'test/test_pytest.py::test_warnings_on_schema_version[http://json-schema.org/schema#-True]' \
  'test/test_pytest.py::test_warnings_on_schema_version[http://json-schema.org/draft-03/schema#-False]' \
  'test/test_pytest.py::test_warnings_on_schema_version[http://json-schema.org/draft-04/schema#-False]' \
  'test/test_pytest.py::test_warnings_on_schema_version[http://json-schema.org/draft-06/schema#-True]' \
  'test/test_pytest.py::test_warnings_on_schema_version[http://json-schema.org/draft-07/schema#-True]' \
  test/test_pytest.py::test_schema_validation \
  test/test_pytest.py::test_regression_9 \
  test/test_pytest.py::test_build_classes_is_idempotent \
  test/test_pytest.py::test_underscore_properties \
  test/test_pytest.py::test_array_regressions \
  test/test_pytest.py::test_arrays_can_have_reffed_items_of_mixed_type \
  test/test_pytest.py::test_regression_39 \
  test/test_pytest.py::test_loads_markdown_schema_extraction \
  test/test_pytest.py::test_object_builder_loads_memory_references \
  test/test_pytest.py::test_object_builder_reads_all_definitions \
  test/test_pytest.py::test_oneOf_fails_against_non_matching \
  test/test_pytest.py::test_oneOfBare_fails_against_non_matching \
  test/test_pytest.py::test_additional_props_allowed_by_default \
  test/test_pytest.py::test_additional_props_permitted_explicitly \
  test/test_pytest.py::test_still_raises_when_accessing_undefined_attrs \
  test/test_pytest.py::test_permits_deletion_of_additional_properties \
  test/test_pytest.py::test_additional_props_disallowed_explicitly \
  test/test_pytest.py::test_objects_can_be_empty \
  test/test_pytest.py::test_object_equality_should_compare_data \
  test/test_pytest.py::test_object_allows_attributes_in_oncstructor \
  test/test_pytest.py::test_object_validates_on_json_decode \
  test/test_pytest.py::test_object_validates_enumerations \
  test/test_pytest.py::test_validation_of_mixed_type_enums \
  test/test_pytest.py::test_objects_allow_non_required_attrs_to_be_missing \
  test/test_pytest.py::test_objects_require_required_attrs_on_validate \
  test/test_pytest.py::test_attribute_access_via_dict \
  test/test_pytest.py::test_attribute_set_via_dict \
  test/test_pytest.py::test_keys_can_be_other_pjo_objects \
  test/test_pytest.py::test_numeric_attribute_validation \
  test/test_pytest.py::test_objects_validate_prior_to_serializing \
  test/test_pytest.py::test_serializing_removes_null_objects \
  test/test_pytest.py::test_lists_get_serialized_correctly \
  'test/test_pytest.py::test_dictionary_transformation[pdict0]' \
  'test/test_pytest.py::test_dictionary_transformation[pdict1]' \
  test/test_pytest.py::test_strict_mode \
  test/test_pytest.py::test_boolean_in_child_object \
  test/test_pytest.py::test_justareference_example; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
