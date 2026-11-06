import unittest
from pathlib import Path
import pandas as pd
from refund_ops import reference, date, load_and_reconcile, ComplaintAI, draft_reply

class RefundTests(unittest.TestCase):
    def test_reference_and_dates(self):
        self.assertEqual(reference(' rf 1750 '), 'RF-1750')
        self.assertEqual(reference('RF1750'), 'RF-1750')
        self.assertEqual(reference('RF-1313 (revised)'), 'RF-1313')
        self.assertIsNone(reference(None))
        self.assertEqual(date('04-03-2026'), pd.Timestamp('2026-03-04'))
        self.assertTrue(pd.isna(date('not a date')))

    @unittest.skipUnless(list(Path(__file__).parent.glob('*.xlsx')), 'Source workbook intentionally excluded from public repository')
    def test_real_data_integrity(self):
        c,e,m,s = load_and_reconcile(next(Path(__file__).parent.glob('*.xlsx')))
        self.assertTrue(c.case_id.is_unique)
        self.assertEqual(len(e), 155)
        self.assertEqual(int(m.requests_logged.sum()), s['support_cases'])
        self.assertEqual(int(c.escalation_count.sum()) + s['escalations_without_reference'], len(e))
        for ref in ['RF-1098','RF-1099']:
            row = c.set_index('case_id').loc[ref]
            self.assertFalse(row.support_present)
            self.assertFalse(row.finance_present)
            self.assertIn('absent_from_both_trackers', row.issues)
        false_closed = c[c.issues.str.contains('support_closed_without_finance_paid')]
        self.assertTrue(false_closed.support_status.eq('Closed').all())
        self.assertTrue(false_closed.finance_status.ne('Refund Done').all())
        self.assertTrue(m.loc['2026-02'].isna()['escalations_raised'])
        self.assertNotIn('paid', draft_reply({'case_id':'RF-1','finance_present':False}).lower().replace('payment',''))

    def test_ai_abstains_on_unknown_text(self):
        self.assertTrue(ComplaintAI().classify('xyzzy qwerty')['review_required'])

    def test_generated_demo_pipeline(self):
        from demo_data import demo_tables
        c,e,m,s = load_and_reconcile(demo_tables())
        self.assertEqual(len(c),10)
        self.assertEqual(s['quality']['support']['pasted_duplicates_removed'],1)
        self.assertEqual(s['escalations_without_reference'],1)
        self.assertEqual(s['issue_counts']['missing_finance_record'],2)
        self.assertIn('conflicting_duplicate_id',c.set_index('case_id').loc['RF-9006','issues'])
        self.assertNotIn('support_closed_without_finance_paid',c.set_index('case_id').loc['RF-9006','issues'])
        self.assertIn('multiple records', draft_reply(c.set_index('case_id').loc['RF-9006'].to_dict() | {'case_id':'RF-9006'}))
        self.assertEqual(len(e),2)

if __name__ == '__main__':
    unittest.main()
