#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_block__commmit_api_error[error1]' \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_make_lock \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_client \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_commit \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_commit_no_op \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_custom_retry \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_custom_timeout \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_client_api_publish_not_blocking_additional_publish_calls \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_starting \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_already_started \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_no_messages \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_blocking__commit_wrong_messageid_length \
  'tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_block__commmit_api_error[error0]' \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_block__commmit_retry_error \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_updating_batch_size \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_max_messages_zero \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_max_messages_enforced \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_max_bytes_enforced \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_exceed_max_messages \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_single_message_size_exceeds_server_size_limit \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_total_messages_size_exceeds_server_size_limit \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_publish_dict \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_cancel \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_do_not_commit_when_full_when_flag_is_off \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_batch_done_callback_called_on_success \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_batch_done_callback_called_on_publish_failure \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_batch_done_callback_called_on_publish_response_invalid \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_open_telemetry_commit_publish_rpc_span_none \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_open_telemetry_commit_publish_rpc_exception \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_opentelemetry_commit_sampling \
  tests/unit/pubsub_v1/publisher/batch/test_thread.py::test_opentelemetry_commit; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
