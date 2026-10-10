#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_util.py::TestUtil::test_obj_or_str_invalid_obj_type \
  tests/test_util.py::TestUtil::test_obj_or_str_str \
  tests/test_util.py::TestUtil::test_clean_headers_authorization_stripped \
  tests/test_util.py::TestUtil::test_clean_headers_does_not_mutate_original_dict \
  tests/test_util.py::TestUtil::test_clean_headers_no_authorization \
  tests/test_util.py::TestUtil::test_clean_headers_strips_malformed_keys_correctly \
  tests/test_util.py::TestUtil::test_combine_kwargs_dict_list_dict \
  tests/test_util.py::TestUtil::test_combine_kwargs_empty \
  tests/test_util.py::TestUtil::test_combine_kwargs_multiple_dicts \
  tests/test_util.py::TestUtil::test_combine_kwargs_multiple_mixed \
  tests/test_util.py::TestUtil::test_combine_kwargs_multiple_nested_dicts \
  tests/test_util.py::TestUtil::test_combine_kwargs_nested_dict \
  tests/test_util.py::TestUtil::test_combine_kwargs_single \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_dict \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_generator_empty \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_generator_multiple_items \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_generator_single_item \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_list_empty \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_list_multiple_items \
  tests/test_util.py::TestUtil::test_combine_kwargs_single_list_single_item \
  tests/test_util.py::TestUtil::test_combine_kwargs_super_nested_dict \
  tests/test_util.py::TestUtil::test_combine_kwargs_the_gauntlet \
  tests/test_util.py::TestUtil::test_file_or_path_file \
  tests/test_util.py::TestUtil::test_file_or_path_invalid_path \
  tests/test_util.py::TestUtil::test_file_or_path_valid_path \
  tests/test_util.py::TestUtil::test_get_institution_url \
  tests/test_util.py::TestUtil::test_is_multivalued_bool \
  tests/test_util.py::TestUtil::test_is_multivalued_bytes \
  tests/test_util.py::TestUtil::test_is_multivalued_chain \
  tests/test_util.py::TestUtil::test_is_multivalued_dict \
  tests/test_util.py::TestUtil::test_is_multivalued_dict_items \
  tests/test_util.py::TestUtil::test_is_multivalued_dict_iter \
  tests/test_util.py::TestUtil::test_is_multivalued_dict_keys \
  tests/test_util.py::TestUtil::test_is_multivalued_dict_values \
  tests/test_util.py::TestUtil::test_is_multivalued_generator_call \
  tests/test_util.py::TestUtil::test_is_multivalued_generator_expr \
  tests/test_util.py::TestUtil::test_is_multivalued_integer \
  tests/test_util.py::TestUtil::test_is_multivalued_list \
  tests/test_util.py::TestUtil::test_is_multivalued_list_iter \
  tests/test_util.py::TestUtil::test_is_multivalued_set \
  tests/test_util.py::TestUtil::test_is_multivalued_set_iter \
  tests/test_util.py::TestUtil::test_is_multivalued_str \
  tests/test_util.py::TestUtil::test_is_multivalued_tuple \
  tests/test_util.py::TestUtil::test_is_multivalued_tuple_iter \
  tests/test_util.py::TestUtil::test_is_multivalued_unicode \
  tests/test_util.py::TestUtil::test_is_multivalued_zip \
  tests/test_util.py::TestUtil::test_normalize_bool_boolean \
  tests/test_util.py::TestUtil::test_normalize_bool_str_invalid \
  tests/test_util.py::TestUtil::test_normalize_bool_str_lower \
  tests/test_util.py::TestUtil::test_normalize_bool_str_upper \
  tests/test_util.py::TestUtil::test_obj_or_id_int \
  tests/test_util.py::TestUtil::test_obj_or_id_multiple_objs \
  tests/test_util.py::TestUtil::test_obj_or_id_nonuser_self \
  tests/test_util.py::TestUtil::test_obj_or_id_obj \
  tests/test_util.py::TestUtil::test_obj_or_id_obj_no_id \
  tests/test_util.py::TestUtil::test_obj_or_id_str_invalid \
  tests/test_util.py::TestUtil::test_obj_or_id_str_valid \
  tests/test_util.py::TestUtil::test_obj_or_id_user_self \
  tests/test_util.py::TestUtil::test_obj_or_str_invalid_attr_parameter \
  tests/test_util.py::TestUtil::test_obj_or_str_mult_obj \
  tests/test_util.py::TestUtil::test_obj_or_str_obj_attr \
  tests/test_util.py::TestUtil::test_obj_or_str_obj_no_attr; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
