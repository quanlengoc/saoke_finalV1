"""Quick test for match_datasets refactor — LEFT columns only, no RIGHT prefix."""
import pandas as pd
import numpy as np
from app.services.generic_matching_engine import GenericMatchingEngine, JoinType

# ===========================================================================
# Test 1: Basic matching — LEFT columns in result, RIGHT via index only
# ===========================================================================
print('=== Test 1: Basic matching (LEFT only) ===')

left = pd.DataFrame({
    'transaction_id': ['TXN001', 'TXN002', 'TXN003'],
    'amount': [100, 200, 300],
    'date': ['2026-01-01', '2026-01-02', '2026-01-03']
})

right = pd.DataFrame({
    'transaction_id': ['TXN001', 'TXN002', 'TXN999'],
    'bill_amount': [100, 250, 400],
    'service': ['SVC1', 'SVC2', 'SVC3']
})

engine = GenericMatchingEngine()
rules = {
    'match_type': 'expression',
    'rules': [],
    'key_match': {
        'left': {'parts': [{'type': 'column', 'value': 'transaction_id'}], 'transforms': ['strip']},
        'right': {'parts': [{'type': 'column', 'value': 'transaction_id'}], 'transforms': ['strip']}
    },
    'status_logic': {'all_match': 'MATCHED', 'no_key_match': 'NOT_FOUND'}
}

result = engine.match_datasets(left, right, 'b1', 'b4', rules, JoinType.LEFT)
print('Result columns:', list(result.columns))

# LEFT columns should be present (no prefix)
assert 'transaction_id' in result.columns, "LEFT col transaction_id should exist"
assert 'amount' in result.columns, "LEFT col amount should exist"
assert 'date' in result.columns, "LEFT col date should exist"

# RIGHT columns should NOT be present (no prefix)
assert 'b4_transaction_id' not in result.columns, "RIGHT cols should NOT have prefix"
assert 'b4_bill_amount' not in result.columns, "RIGHT cols should NOT have prefix"
assert 'b4_service' not in result.columns, "RIGHT cols should NOT have prefix"

# Index columns for lookup
assert 'b1_index' in result.columns
assert 'b4_index' in result.columns

# Status
assert len(result) == 3
assert (result['status'] == 'MATCHED').sum() == 2
assert (result['status'] == 'NOT_FOUND').sum() == 1

# TXN001 matched → b4_index should be valid
r0 = result.iloc[0]
assert r0['transaction_id'] == 'TXN001'
assert r0['status'] == 'MATCHED'
assert pd.notna(r0['b4_index'])  # Can look up RIGHT via this index

# TXN003 not found → b4_index should be NaN
r2 = result.iloc[2]
assert r2['transaction_id'] == 'TXN003'
assert r2['status'] == 'NOT_FOUND'
assert pd.isna(r2['b4_index'])

# Verify RIGHT data accessible via index lookup
matched_idx = int(r0['b4_index'])
assert right.iloc[matched_idx]['bill_amount'] == 100
assert right.iloc[matched_idx]['service'] == 'SVC1'

print('=== Test 1 PASSED ===\n')

# ===========================================================================
# Test 2: Chained matching — LEFT columns propagate for key matching
# Step 1: B1↔B4 → A1_1 (has B1 columns + b4_index)
# Step 2: A1_1↔B2 → A1 (A1_1's transaction_id from B1 is the match key)
# ===========================================================================
print('=== Test 2: Chained matching ===')

a1_1 = result.copy()  # Result from Step 1

b2 = pd.DataFrame({
    'transaction_id': ['TXN001', 'TXN003'],
    'refund_amount': [50, 0],
    'refund_date': ['2026-01-05', '2026-01-06']
})

rules2 = {
    'match_type': 'expression',
    'rules': [],
    'key_match': {
        'left': {'parts': [{'type': 'column', 'value': 'transaction_id'}], 'transforms': ['strip']},
        'right': {'parts': [{'type': 'column', 'value': 'transaction_id'}], 'transforms': ['strip']}
    },
    'status_logic': {'all_match': 'MATCHED', 'no_key_match': 'NOT_FOUND'}
}

result2 = engine.match_datasets(a1_1, b2, 'a1_1', 'b2', rules2, JoinType.LEFT)
print('Chained result columns:', list(result2.columns))

# LEFT columns from A1_1 propagated (including B1 cols + b4_index from step 1)
assert 'transaction_id' in result2.columns, "B1.transaction_id propagated through A1_1"
assert 'amount' in result2.columns, "B1.amount propagated through A1_1"
assert 'b4_index' in result2.columns, "B4 index propagated through chain"
assert 'b1_index' in result2.columns, "B1 index propagated through chain"

# New indices from step 2
assert 'a1_1_index' in result2.columns
assert 'b2_index' in result2.columns

# Match stats
assert len(result2) == 3
assert (result2['status'] == 'MATCHED').sum() == 2  # TXN001, TXN003
assert (result2['status'] == 'NOT_FOUND').sum() == 1  # TXN002

print('=== Test 2 PASSED ===\n')

# ===========================================================================
# Test 3: _resolve_column_value chain lookup simulation
# Output config asks for B4.bill_amount — resolve via:
# result2[a1_1_index] → A1_1[b4_index] → B4[bill_amount]
# ===========================================================================
print('=== Test 3: Chain lookup via _resolve_column_value ===')

from app.services.workflow_executor import WorkflowExecutor

# Create a minimal executor and inject datasets
class MockExecutor(WorkflowExecutor):
    def __init__(self):
        # Skip parent __init__, just set what we need
        from app.core.logging_config import BatchLogger
        self.logger = BatchLogger('test', 'test_batch')
        self.datasets = {
            'B1': left,
            'B4': right,
            'A1_1': a1_1,
            'B2': b2,
            'A1': result2,
        }

exec_mock = MockExecutor()

# Direct column (LEFT propagated)
vals = exec_mock._resolve_column_value(result2, 'B1', 'transaction_id')
assert vals is not None, "B1.transaction_id should resolve via direct column"
assert vals[0] == 'TXN001'

# Index lookup (B2 is RIGHT of step 2 → b2_index in result2)
vals = exec_mock._resolve_column_value(result2, 'B2', 'refund_amount')
assert vals is not None, "B2.refund_amount should resolve via b2_index"

# Chain lookup: B4.bill_amount via a1_1_index → A1_1.b4_index → B4
vals = exec_mock._resolve_column_value(result2, 'B4', 'bill_amount')
assert vals is not None, "B4.bill_amount should resolve via chain: a1_1_index→A1_1.b4_index→B4"
# Row 0: TXN001 → b4_index=0 → bill_amount=100
assert vals[0] == 100, f"Expected 100, got {vals[0]}"

print('=== Test 3 PASSED ===\n')
print('=== ALL TESTS PASSED ===')
