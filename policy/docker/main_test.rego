# Unit tests for the Dockerfile policy set. Run with:
#   conftest verify -p policy/docker
# Input is the dockerfile parser's instruction array: [{Cmd, Value}, ...].
package main

import rego.v1

test_deny_latest_base if {
	count(deny) > 0 with input as [{"Cmd": "from", "Value": ["node:latest"]}]
}

test_deny_untagged_base if {
	count(deny) > 0 with input as [{"Cmd": "from", "Value": ["node"]}]
}

test_allow_pinned_nonroot if {
	count(deny) == 0 with input as [
		{"Cmd": "from", "Value": ["node:22-alpine", "AS", "runtime"]},
		{"Cmd": "user", "Value": ["appuser"]},
	]
}

test_deny_user_root if {
	count(deny) > 0 with input as [
		{"Cmd": "from", "Value": ["node:22-alpine"]},
		{"Cmd": "user", "Value": ["root"]},
	]
}

# root in a build stage, dropped to non-root in the final stage → allowed
test_allow_root_then_nonroot if {
	count(deny) == 0 with input as [
		{"Cmd": "from", "Value": ["apache/airflow:3.1.7-python3.11"]},
		{"Cmd": "user", "Value": ["root"]},
		{"Cmd": "user", "Value": ["airflow"]},
	]
}

test_deny_add_remote_url if {
	count(deny) > 0 with input as [
		{"Cmd": "from", "Value": ["node:22-alpine"]},
		{"Cmd": "add", "Value": ["https://example.com/x.tar", "/x"]},
	]
}

# scratch is exempt from the base-tag deny but still warns about no USER
test_warn_no_user_on_scratch if {
	count(deny) == 0 with input as [{"Cmd": "from", "Value": ["scratch"]}]
	count(warn) > 0 with input as [{"Cmd": "from", "Value": ["scratch"]}]
}
