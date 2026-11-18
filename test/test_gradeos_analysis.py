from pathlib import Path
import unittest

from scripts.python import gradeos_analysis as bridge


class GradeOSAnalysisTests(unittest.TestCase):
    def test_existing_gradeos_functions_keep_unavailable_out_and_do_not_invent_point_evidence(self):
        item = {'item_id':'Z(c)', 'criteria':'A justified comparison.', 'max_score':4}
        bundle = {'result_set_hash':'source', 'cohort_context':{'unique_answer_sources':1},
                  'rubric':{'artifact':{'items':[item]}}, 'records':[
                    {'student_id':'first','grade':{'total_score':2,'max_score':4,
                     'items':[{'item_id':'Z(c)','score':2,'max_score':4}]}},
                    {'student_id':'unavailable','grade':None}]}
        result = bridge.analyze(bundle)
        self.assertEqual(result['gradeos_class_report']['scored_student_count'],1)
        self.assertEqual(result['gradeos_class_report']['average_score'],2)
        self.assertEqual(result['gradeos_class_report']['score_distribution']['D'],1)
        self.assertEqual(result['coverage']['excluded_from_numeric_audit'],['unavailable'])
        self.assertEqual(result['gradeos_global_logic_audit']['point_audits'],[])
        self.assertTrue(all(Path(m['source_path']).exists() for m in result['methods']))

    def test_no_complete_results_has_no_numeric_average(self):
        result = bridge.analyze({'result_set_hash':'empty','cohort_context':{},
            'rubric':{'artifact':{'items':[]}},'records':[{'student_id':'unknown','grade':None}]})
        self.assertIsNone(result['gradeos_class_report']['average_score'])
        self.assertIsNone(result['harness_repeatability']['mean'])


if __name__ == '__main__': unittest.main()
