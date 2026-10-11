#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/filterparser/test_filterparser.py::TestParserV0_9_5::test_inputs \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_property_names \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_number_values \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_special_cases \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_property_names \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_number_values \
  tests/filterparser/test_filterparser.py::TestParserV0_9_5::test_parser_version \
  tests/filterparser/test_filterparser.py::TestParserV0_9_5::test_repr \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_empty \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_string_values \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_operators \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_id \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_string_operations \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_list_properties \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_properties \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_precedence \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_parser_version \
  tests/filterparser/test_filterparser.py::TestParserV1_0_0::test_repr \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_empty \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_string_values \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_simple_comparisons \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_id \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_operators \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_filtering_on_relationships \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_not_implemented \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_unaliased_length_operator \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_list_properties \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_known_properties \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_precedence \
  tests/filtertransformers/test_mongo.py::TestMongoTransformer::test_special_cases; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
