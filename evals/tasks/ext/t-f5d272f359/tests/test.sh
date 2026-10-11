#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/ut/test_factory.py::TestCache::test_new_invalid_cache_raises[None]' \
  tests/ut/test_factory.py::test_class_from_string \
  tests/ut/test_factory.py::test_create_simple_cache \
  tests/ut/test_factory.py::test_create_cache_with_everything \
  tests/ut/test_factory.py::TestCache::test_cache_types \
  'tests/ut/test_factory.py::TestCache::test_new[memory]' \
  'tests/ut/test_factory.py::TestCache::test_new[memcached]' \
  'tests/ut/test_factory.py::TestCache::test_new[redis]' \
  tests/ut/test_factory.py::TestCache::test_new_defaults_to_memory \
  'tests/ut/test_factory.py::TestCache::test_new_invalid_cache_raises[object]' \
  'tests/ut/test_factory.py::TestCache::test_get_scheme_class[memory]' \
  'tests/ut/test_factory.py::TestCache::test_get_scheme_class[memcached]' \
  'tests/ut/test_factory.py::TestCache::test_get_scheme_class[redis]' \
  tests/ut/test_factory.py::TestCache::test_get_scheme_class_invalid \
  'tests/ut/test_factory.py::TestCache::test_from_url_returns_cache_from_scheme[memory]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_returns_cache_from_scheme[memcached]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_returns_cache_from_scheme[redis]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://-expected_args0]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://localhost-expected_args1]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://localhost/-expected_args2]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://localhost:6379-expected_args3]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://localhost/?arg1=arg1&arg2=arg2-expected_args4]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://localhost:6379/?arg1=arg1&arg2=arg2-expected_args5]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis:///?arg1=arg1-expected_args6]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis:///?arg2=arg2-expected_args7]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://:password@localhost:6379-expected_args8]' \
  'tests/ut/test_factory.py::TestCache::test_from_url_calls_cache_with_args[redis://:password@localhost:6379?password=pass-expected_args9]' \
  tests/ut/test_factory.py::TestCache::test_calls_parse_uri_path_from_cache \
  tests/ut/test_factory.py::TestCache::test_from_url_invalid_protocol \
  tests/ut/test_factory.py::TestCacheHandler::test_add_new_entry \
  tests/ut/test_factory.py::TestCacheHandler::test_add_updates_existing_entry \
  tests/ut/test_factory.py::TestCacheHandler::test_get_wrong_alias \
  tests/ut/test_factory.py::TestCacheHandler::test_reuse_instance \
  tests/ut/test_factory.py::TestCacheHandler::test_create_not_reuse \
  tests/ut/test_factory.py::TestCacheHandler::test_create_extra_args \
  tests/ut/test_factory.py::TestCacheHandler::test_retrieve_cache \
  tests/ut/test_factory.py::TestCacheHandler::test_retrieve_cache_new_instance \
  tests/ut/test_factory.py::TestCacheHandler::test_multiple_caches \
  tests/ut/test_factory.py::TestCacheHandler::test_default_caches \
  tests/ut/test_factory.py::TestCacheHandler::test_get_alias_config \
  tests/ut/test_factory.py::TestCacheHandler::test_set_empty_config \
  tests/ut/test_factory.py::TestCacheHandler::test_set_config_updates_existing_values \
  tests/ut/test_factory.py::TestCacheHandler::test_set_config_removes_existing_caches \
  tests/ut/test_factory.py::TestCacheHandler::test_set_config_no_default \
  tests/ut/test_factory.py::TestCacheHandler::test_ensure_plugins_order; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
