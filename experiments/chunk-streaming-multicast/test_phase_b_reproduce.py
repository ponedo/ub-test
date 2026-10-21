#!/usr/bin/env python3
"""Pure wrapper dispatch tests, not simulator or native protocol evidence."""
import unittest
from unittest.mock import patch
import phase_b_reproduce as wrapper


def inputs():
    return ('synthetic-output',dict(id='F03',fault='ack-once',fault_role='stage1',required_witnesses=['fault_tpack']),
            dict(hybrid_groups=[dict(graph_role='stage1',members=[dict(task=128),dict(task=129)])]),[],{})


class FreshWrapperContracts(unittest.TestCase):
    def test_non_ack_fault_uses_original_function_and_arguments(self):
        for fault in ('data-once','taack-once','duplicate-once'):
            args=list(inputs());args[1]['fault']=fault
            with patch.object(wrapper,'_ORIGINAL_FAULT_WITNESS',return_value={'original':True}) as original,patch.object(wrapper.ack_oracle,'check_directory') as oracle:
                self.assertEqual(wrapper.fault_witness(*args),{'original':True})
                original.assert_called_once_with(*args);oracle.assert_not_called()

    def test_f03_calls_reviewed_oracle_and_writes_fresh_witness(self):
        proof=dict(status='PASS',coverage={'fault_tpack':True},fixture_bound_no_wrap_psns=list(range(12)))
        with patch.object(wrapper.phase_b,'csv_rows',return_value=[dict(kind='drop',task='128')]),patch.object(wrapper.ack_oracle,'check_directory',return_value=proof) as oracle,patch.object(wrapper,'write') as write:
            self.assertEqual(wrapper.fault_witness(*inputs()),{'fault_tpack':True})
            oracle.assert_called_once_with('synthetic-output')
            self.assertEqual(write.call_args.args[0].name,'f03-cumulative-ack-witness.json')
            self.assertEqual(write.call_args.args[1]['kind'],'FRESH_RUNTIME_CUMULATIVE_ACK_WITNESS')

    def test_other_ack_rows_are_not_silently_generalized(self):
        for key,value in [('id','F99'),('fault_role','stage2'),('required_witnesses',['different'])]:
            args=list(inputs());args[1][key]=value
            with self.assertRaisesRegex(ValueError,'scoped to declared F03'):
                wrapper.fault_witness(*args)

    def test_common_fault_hop_and_multi_target_requirements_retained(self):
        for mutation in ('wrong-hop','singleton','multiple-drops'):
            args=list(inputs());drops=[dict(kind='drop',task='128')]
            if mutation=='wrong-hop':args[2]['hybrid_groups'][0]['graph_role']='stage2'
            elif mutation=='singleton':args[2]['hybrid_groups'][0]['members'].pop()
            else:drops.append(dict(kind='drop',task='129'))
            with patch.object(wrapper.phase_b,'csv_rows',return_value=drops),patch.object(wrapper.ack_oracle,'check_directory') as oracle,self.assertRaises(ValueError):
                wrapper.fault_witness(*args)
            oracle.assert_not_called()

    def test_oracle_failure_is_not_completion_or_retry_fallback(self):
        with patch.object(wrapper.phase_b,'csv_rows',return_value=[dict(kind='drop',task='128')]),patch.object(wrapper.ack_oracle,'check_directory',side_effect=ValueError('No covering same-TP ACK')),patch.object(wrapper,'write') as write,self.assertRaisesRegex(ValueError,'same-TP'):
            wrapper.fault_witness(*inputs())
        write.assert_not_called()

    def test_main_delegates_existing_cli_and_restores_dispatch(self):
        original=wrapper.phase_b.fault_witness
        def delegated():self.assertIs(wrapper.phase_b.fault_witness,wrapper.fault_witness)
        with patch.object(wrapper.phase_b,'main',side_effect=delegated) as main:
            wrapper.main();main.assert_called_once_with()
        self.assertIs(wrapper.phase_b.fault_witness,original)

    def test_failure_restores_original_dispatch(self):
        original=wrapper.phase_b.fault_witness
        with patch.object(wrapper.phase_b,'main',side_effect=ValueError('STOPPED')),self.assertRaisesRegex(ValueError,'STOPPED'):
            wrapper.main()
        self.assertIs(wrapper.phase_b.fault_witness,original)

if __name__=='__main__':unittest.main(verbosity=2)
