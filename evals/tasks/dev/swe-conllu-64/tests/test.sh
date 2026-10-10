#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_parser.py::TestSerialize::test_non_str_metadata \
  tests/test_parser.py::TestParseConlluPlusFields::test_empty \
  tests/test_parser.py::TestParseConlluPlusFields::test_empty_columns \
  tests/test_parser.py::TestParseConlluPlusFields::test_simple \
  tests/test_parser.py::TestParseSentencesGenerator::test_empty \
  tests/test_parser.py::TestParseSentencesGenerator::test_ends_without_newline \
  tests/test_parser.py::TestParseSentencesGenerator::test_multiple_newlines \
  tests/test_parser.py::TestParseSentencesGenerator::test_newlines_with_tabs \
  tests/test_parser.py::TestParseSentencesGenerator::test_simple \
  tests/test_parser.py::TestParseTokenAndMetadata::test_custom_field_parsers \
  tests/test_parser.py::TestParseTokenAndMetadata::test_custom_fields \
  tests/test_parser.py::TestParseTokenAndMetadata::test_custom_metadata_parsers \
  tests/test_parser.py::TestParseTokenAndMetadata::test_default_field_parsers_when_undefined \
  tests/test_parser.py::TestParseTokenAndMetadata::test_empty \
  tests/test_parser.py::TestParseTokenAndMetadata::test_fallback_metadata_parser \
  tests/test_parser.py::TestParseTokenAndMetadata::test_fields_from_parse_become_defaults_in_tokenlist \
  tests/test_parser.py::TestParseTokenAndMetadata::test_invalid_metadata \
  tests/test_parser.py::TestParseTokenAndMetadata::test_newlines_in_sentence \
  tests/test_parser.py::TestParseTokenAndMetadata::test_one_to_many_custom_metadata_parser \
  tests/test_parser.py::TestParseLine::test_empty \
  tests/test_parser.py::TestParseLine::test_parse_custom_fieldparsers \
  tests/test_parser.py::TestParseLine::test_parse_fieldparsers_alias_two_ways \
  tests/test_parser.py::TestParseLine::test_parse_fieldparsers_alias_xupos \
  tests/test_parser.py::TestParseLine::test_parse_fieldparsers_alias_xupostag \
  tests/test_parser.py::TestParseLine::test_parse_fieldparsers_doesnt_alias_when_exists \
  tests/test_parser.py::TestParseLine::test_parse_line \
  tests/test_parser.py::TestParseLine::test_parse_line_fewer_columns \
  tests/test_parser.py::TestParseLine::test_parse_line_nullable_fields \
  tests/test_parser.py::TestParseLine::test_parse_line_only_id_head \
  tests/test_parser.py::TestParseLine::test_parse_line_two_spaces \
  tests/test_parser.py::TestParseLine::test_parse_line_with_spaces \
  tests/test_parser.py::TestParseLine::test_parse_line_without_spacing \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_multiple_equals \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_optional_value \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_optional_value_no_space \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_without_equals \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_without_space \
  tests/test_parser.py::TestParseCommentLine::test_parse_comment_line_without_square \
  tests/test_parser.py::TestParseCommentLine::test_parse_spaces_before_square \
  tests/test_parser.py::TestParseIntValue::test_parse_int_value \
  tests/test_parser.py::TestParseIDValue::test_decimal \
  tests/test_parser.py::TestParseIDValue::test_none \
  tests/test_parser.py::TestParseIDValue::test_range \
  tests/test_parser.py::TestParseIDValue::test_single \
  tests/test_parser.py::TestParsePairedListValue::test_parse_empty \
  tests/test_parser.py::TestParsePairedListValue::test_parse_invalid \
  tests/test_parser.py::TestParsePairedListValue::test_parse_paired_list \
  tests/test_parser.py::TestParseDictValue::test_parse_dict_value \
  tests/test_parser.py::TestParseNullableValue::test_parse_nullable_value \
  tests/test_parser.py::TestHeadToToken::test_decimal_ids_ignored \
  tests/test_parser.py::TestHeadToToken::test_missing_head \
  tests/test_parser.py::TestHeadToToken::test_negative_head \
  tests/test_parser.py::TestHeadToToken::test_none_head \
  tests/test_parser.py::TestHeadToToken::test_range_ids_ignored \
  tests/test_parser.py::TestHeadToToken::test_simple \
  tests/test_parser.py::TestSerializeField::test_list \
  tests/test_parser.py::TestSerializeField::test_none \
  tests/test_parser.py::TestSerializeField::test_ordered_dict \
  tests/test_parser.py::TestSerializeField::test_string \
  tests/test_parser.py::TestSerializeField::test_tuple \
  tests/test_parser.py::TestSerialize::test_identity_unicode \
  tests/test_parser.py::TestSerialize::test_metadata \
  tests/test_parser.py::TestSerialize::test_serialize_tricky_fields; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
