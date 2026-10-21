"""Offline incident-analysis regression tests with entirely synthetic inputs."""
import unittest
from netdiag.analysis import analyze

SAMPLE = {
    'interfaces': [{'name': 'eth0', 'ipv4': ['192.0.2.10']}],
    'default_gateway': '192.0.2.1',
    'dns_servers': ['203.0.113.53'],
    'collection_errors': [],
}

class IncidentAnalysisRegressions(unittest.TestCase):
    def test_dns_failure_produces_specific_troubleshooting_guidance(self):
        result=analyze(SAMPLE, [{'name':'DNS resolution','status':'FAIL'}])
        self.assertEqual(result['overall_status'],'FAIL')
        self.assertTrue(any('DNS lookup failed' in x for x in result['findings']))

    def test_icmp_warning_does_not_claim_total_outage(self):
        result=analyze(SAMPLE, [{'name':'ICMP ping','status':'WARN'}])
        self.assertEqual(result['overall_status'],'WARN')
        self.assertTrue(any('ICMP may be filtered' in x for x in result['findings']))

    def test_gateway_absence_gets_independent_guidance(self):
        network={**SAMPLE,'default_gateway':None}
        result=analyze(network, [{'name':'DNS resolution','status':'PASS'}])
        self.assertTrue(any('Default gateway was not detected' in x for x in result['findings']))

    def test_all_skipped_records_are_information_not_pass(self):
        tests=[{'name':name,'status':'SKIP'} for name in ('DNS resolution','ICMP ping')]
        self.assertEqual(analyze(SAMPLE, tests)['overall_status'],'INFO')

if __name__=='__main__':
    unittest.main()
