import unittest
from pilot.metrics import analyze, STAGES

class PilotTests(unittest.TestCase):
    def row(self, uid, done=9):
        record = {'participant_id':uid,'recommendation_relevant':'5','skill_improved':'yes','willingness_to_pay_eur':'12'}
        record.update({stage: 'yes' if i < done else '' for i,stage in enumerate(STAGES)})
        return record
    def test_complete(self):
        report = analyze([self.row('anonymous-a')])
        self.assertEqual(report['journeys_completed'],1)
        self.assertEqual(report['recommendation_relevant_4_or_5_rate'],1.0)
        self.assertFalse(report['target_reached'])
    def test_no_consent_excluded(self):
        record = self.row('anonymous-a',0)
        self.assertEqual(analyze([record])['participants_consented'],0)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError): analyze([self.row('a'),self.row('a')])
    def test_sequence_rejected(self):
        record=self.row('a',2)
        record['project_verified']='yes'
        with self.assertRaises(ValueError): analyze([record])
    def test_twenty(self):
        self.assertTrue(analyze([self.row(str(i)) for i in range(20)])['target_reached'])

if __name__ == '__main__': unittest.main()
