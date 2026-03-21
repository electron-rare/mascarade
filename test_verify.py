#!/usr/bin/env python3
"""Verification script for ExecutionContext and NodeResult."""

from core.mascarade.node_engine.graph import ExecutionContext, NodeResult

# Test ExecutionContext instantiation
context = ExecutionContext(graph_id='g1', run_id='r1', node_id='n1')
assert context.graph_id == 'g1'
assert context.run_id == 'r1'
assert context.node_id == 'n1'

# Test NodeResult instantiation
result = NodeResult(node_id='n1', status='completed')
assert result.node_id == 'n1'
assert result.status == 'completed'

print('OK')
