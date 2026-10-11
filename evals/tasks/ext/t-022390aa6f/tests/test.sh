#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_proto_data \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_basic_invoke \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_coroutine_basic_invoke \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_generic_client_unknown_protocol \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_global_timeout_setting_is_honored \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_GET_with_duplicate_query_params \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_GET_with_query_params \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_PUT_with_body \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_PUT_with_bytes_body \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_PUT_with_content_type \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_error_returned \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_metadata \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_non_dapr_error \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_protobuf_response_case_insensitive \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_protobuf_response_with_suffix \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_with_api_token \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_invoke_method_with_tracer \
  tests/clients/test_http_service_invocation_client.py::DaprInvocationHttpClientTests::test_timeout_exception_thrown_when_timeout_reached; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
