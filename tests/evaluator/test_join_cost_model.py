"""Independent cost-policy checks using documented VM costs and actual CLI runs.

The 8 examples + 11 fixed workloads deliberately match benchmark_joins.py's
published corpus, copied here without importing benchmark or optimizer code.
Only raw VM execution supplies results/cycles; fixture byte lengths supply the
independent documented-cost calculation.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
ARCHIVED_PROFILE=ROOT/'experiments/profile_optimizer.py'
sys.path.insert(0,str(ROOT))
import evaluator as ev

JOIN_TOKEN=re.compile(rb'(?im)^([ \t]*)(NLJOIN|HJOIN)(?=[ \t])')


def force_policy(source,op):
    return JOIN_TOKEN.sub(lambda m:m.group(1)+op.encode('ascii'),source)


def dataset(left,right,kind='INT'):
    return {name:ev.table([('k',kind)],[[value] for value in values])
            for name,values in [('l',left),('r',right)]}


def fixed_workloads():
    numeric=lambda n:dataset(list(range(n)),list(range(n)))
    strings=['x'*80+str(i) for i in range(64)]
    skew=['']*63+['x'*10000]
    return [
        ('numeric_tiny','HJOIN',dataset([0,1],[0,1,2]),None,False),
        ('numeric_large','NLJOIN',numeric(64),None,False),
        ('numeric_tie','HJOIN',numeric(12),None,False),
        ('empty_left','HJOIN',dataset([],list(range(32))),None,False),
        ('duplicates_null_equal','HJOIN',dataset([None,None,1,1,2],[None,1,1,2]),None,True),
        ('string_asymmetric','HJOIN',dataset(['x'*1024]*32,['x']*32,'STR'),None,False),
        ('string_large','NLJOIN',dataset(strings,strings,'STR'),None,False),
        ('string_skew_matching_stats','NLJOIN',dataset(skew,skew,'STR'),None,False),
        ('stale_large_estimate_tiny_actual','NLJOIN',numeric(2),numeric(64),False),
        ('stale_tiny_estimate_large_actual','HJOIN',numeric(64),numeric(2),False),
        ('unknown_stats_large','NLJOIN',numeric(64),'omit_stats',False),
    ]


def source_for(op,nulleq=False):
    return ('LOAD x,l.k\nLOAD y,r.k\n'+op+' a,b,x,y'+(',NULLEQ' if nulleq else '')+'\nOUT a,b\n').encode()


def raw_cost(data,op,pairs):
    """Exactly docs/cycles.md, including4 base cycles per each of4 instructions."""
    left=[r[0] for r in data['l']['rows']]
    right=[r[0] for r in data['r']['rows']]
    size=lambda x:len(x.encode('utf8')) if isinstance(x,str) else 0
    common=16+len(left)+len(right)+2*pairs
    if op=='NLJOIN':
        return common+sum(1+min(size(a),size(b)) for a in left for b in right)
    return common+sum(6+size(v) for v in left+right)


def command(argv,deadline=None):
    result=ev.run_process(argv,60,deadline or time.monotonic()+65)
    if result.issue or result.returncode:
        raise AssertionError((list(map(str,argv)),result.issue,result.returncode,result.stderr[:500]))
    return result.stdout


def measure_suite(optimizer=None):
    """Same19 programs/data for selected, forcedNL and forcedH; frozen schemas."""
    results=[]
    selected_command=[ROOT/'optimize','--joins-only'] if optimizer is None else [optimizer]
    with tempfile.TemporaryDirectory(prefix='cost-policy-check-') as folder:
        folder=Path(folder)
        original=folder/'original.mini'
        candidate=folder/'candidate.mini'
        data_file=folder/'data.json'
        schema_file=folder/'schema.json'
        # Actual executable policies, not direct in-process output substitutions.
        policies={}
        for op in ('NLJOIN','HJOIN'):
            policy=folder/op
            policy.write_text('#!'+sys.executable+'\nimport re,sys\ns=open(sys.argv[1],"rb").read()\n'
                              'p=re.compile(rb"(?im)^([ \\t]*)(NLJOIN|HJOIN)(?=[ \\t])")\n'
                              'sys.stdout.buffer.write(p.sub(lambda m:m.group(1)+'+repr(op.encode())+',s))\n')
            policy.chmod(0o755)
            policies[op]=[policy]
        inputs=[]
        example_data=json.loads((ROOT/'examples/data.json').read_text())
        for i in range(1,9):
            name=f'q{i:04d}'
            inputs.append((name,(ROOT/'examples/programs'/f'{name}.mini').read_bytes(),example_data,None,None))
        for name,op,data,stats,nulleq in fixed_workloads():
            inputs.append((name,source_for(op,nulleq),data,stats,op))
        for name,source,data,stats,initial in inputs:
            original.write_bytes(source)
            data_file.write_text(json.dumps(stats if isinstance(stats,dict) else data))
            schema=json.loads(command([ROOT/'bin/minivm','--schema',data_file]))
            if stats=='omit_stats':
                schema={n:{k:v for k,v in t.items() if k!='stats'} for n,t in schema.items()}
            schema_file.write_text(json.dumps(schema))
            data_file.write_text(json.dumps(data))
            expected=ev.parse_result(command([ROOT/'bin/minivm',original,data_file]))
            cycles={}
            selections={}
            for label,executable in [('selected',selected_command),*policies.items()]:
                emitted=command([*executable,original,schema_file])
                # Replacing every join opcode by the same marker must yield
                # byte-identical sources, preserving operands/flags and literals.
                if force_policy(source,'NLJOIN')!=force_policy(emitted,'NLJOIN'):
                    raise AssertionError(name+': changed non-opcode bytes under '+label)
                if label!='selected' and emitted!=force_policy(source,label):
                    raise AssertionError(name+': forcing policy changed wrong tokens')
                candidate.write_bytes(emitted)
                actual=ev.parse_result(command([ROOT/'bin/minivm',candidate,data_file]))
                if expected['ncols']!=actual['ncols'] or expected['rows']!=actual['rows']:
                    raise AssertionError(name+': '+label+' result changed')
                cycles[label]=actual['cycles']
                selections[label]=[m.group(2).decode().upper() for m in JOIN_TOKEN.finditer(emitted)]
                if initial and label!='selected':
                    calculated=raw_cost(data,label,len(actual['rows']))
                    if calculated!=actual['cycles']:
                        raise AssertionError((name,label,'documented cycle mismatch',calculated,actual['cycles']))
            results.append(dict(name=name,original=expected['cycles'],cycles=cycles,join_opcodes=selections,
                                estimates='missing' if stats=='omit_stats' else 'stale' if stats else 'matching'))
    return results


class CostPolicyTests(unittest.TestCase):
    def test_same_fixed_corpus_selected_and_forced_policies(self):
        rows=measure_suite()
        self.assertEqual(len(rows),19)
        self.assertEqual(len([r for r in rows if r['name'].startswith('q')]),8)
        skew=next(r for r in rows if r['name']=='string_skew_matching_stats')
        self.assertEqual(skew['cycles']['NLJOIN'],22180)
        self.assertEqual(skew['cycles']['HJOIN'],28852)
        self.assertLess(skew['cycles']['NLJOIN'],skew['cycles']['HJOIN'])

    def test_forcing_policy_preserves_flags_spacing_and_literal_contents(self):
        source="LOAD a,l.k\r\nFILL s,'NLJOIN a,b,x,y\u2028HJOIN c,d,x,y',a\r\n\thJoIn a, b, x, y, NULLEQ ; annotation\r\nOUT a,b".encode()
        changed=force_policy(source,'NLJOIN')
        self.assertEqual(changed,source.replace(b'\thJoIn',b'\tNLJOIN'))
        self.assertEqual(force_policy(changed,'HJOIN'),source.replace(b'\thJoIn',b'\tHJOIN'))

    def test_documented_string_cost_uses_utf8_and_null_zero_bytes(self):
        data=dataset(['é',None,''],['猫',None,''],'STR')
        # 3x3 pairs, min byte contributions min(2,3)=2, all others0.
        self.assertEqual(raw_cost(data,'NLJOIN',0),16+6+9+2)
        self.assertEqual(raw_cost(data,'HJOIN',0),16+6+36+2+3)


class StringProfileHoldoutTests(unittest.TestCase):
    """Retained experimental model assumptions, tested against its archived CLI."""
    def probe(self,data,*,prefix='',initial='NLJOIN',nulleq=False,mutate=None):
        with tempfile.TemporaryDirectory(prefix='string-cost-holdout-') as directory:
            directory=Path(directory)
            original=directory/'original.mini'
            candidate=directory/'candidate.mini'
            data_file=directory/'data.json'
            schema_file=directory/'schema.json'
            source=source_for(initial,nulleq).replace(initial.encode()+b' a,b,x,y',prefix.encode()+initial.encode()+b' a,b,x,y')
            original.write_bytes(source)
            data_file.write_text(json.dumps(data))
            schema=json.loads(command([ROOT/'bin/minivm','--schema',data_file]))
            if mutate:
                mutate(schema)
            schema_file.write_text(json.dumps(schema))
            emitted=command([ARCHIVED_PROFILE,original,schema_file])
            self.assertEqual(force_policy(source,'NLJOIN'),force_policy(emitted,'NLJOIN'))
            matches=list(JOIN_TOKEN.finditer(emitted))
            self.assertEqual(len(matches),1)
            choice=matches[0].group(2).decode().upper()
            expected=ev.parse_result(command([ROOT/'bin/minivm',original,data_file]))
            measured={}
            for name,code in [('selected',emitted),('NLJOIN',force_policy(source,'NLJOIN')),('HJOIN',force_policy(source,'HJOIN'))]:
                candidate.write_bytes(code)
                actual=ev.parse_result(command([ROOT/'bin/minivm',candidate,data_file]))
                self.assertEqual(expected['ncols'],actual['ncols'])
                self.assertEqual(expected['rows'],actual['rows'])
                measured[name]=actual['cycles']
            return choice,measured

    def test_common_skew_selects_nested_with_matching_stats(self):
        values=['']*63+['x'*10000]
        choice,cost=self.probe(dataset(values,values,'STR'))
        self.assertEqual(choice,'NLJOIN')
        self.assertEqual(cost['NLJOIN'],22180)
        self.assertEqual(cost['HJOIN'],28852)

    def test_null_frequency_is_zero_byte_mass_with_both_null_policies(self):
        values=[None]*63+['x'*10000]
        for nulleq in (False,True):
            with self.subTest(nulleq=nulleq):
                choice,cost=self.probe(dataset(values,values,'STR'),nulleq=nulleq)
                self.assertEqual(choice,'NLJOIN')
                self.assertLess(cost['NLJOIN'],cost['HJOIN'])

    def test_common_full_distribution_counts_utf8_bytes(self):
        values=['']*5+['猫'*4]*3
        choice,cost=self.probe(dataset(values,values,'STR'))
        self.assertEqual((cost['NLJOIN'],cost['HJOIN']),(272,268))
        self.assertEqual(choice,'HJOIN')

    def test_single_integer_residual_recovers_rounded_average(self):
        # avg_bytes=4.12 although totalUTF8bytes=66; only66 lies inside the
        # rounded mean's +/-0.005*16 total-byte interval.
        values=['']*15+['猫'*22]
        choice,cost=self.probe(dataset(values,values,'STR'),initial='HJOIN')
        self.assertEqual(choice,'NLJOIN')
        self.assertEqual(cost['HJOIN']-cost['NLJOIN'],2)

    def test_homogeneous_uncommon_tail_and_complete_common_rounding(self):
        values=['']*60+['a'*2500,'b'*2500,'c'*2500,'d'*2500]
        choice,cost=self.probe(dataset(values,values,'STR'))
        self.assertEqual(choice,'HJOIN')
        self.assertLess(cost['HJOIN'],cost['NLJOIN'])
        # Nonintegral mean2.67, but all lengths/counts are present in common.
        values=['é']*2+['猫']*4
        choice,cost=self.probe(dataset(values,values,'STR'))
        self.assertEqual(cost['selected'],min(cost['NLJOIN'],cost['HJOIN']))

    def test_malformed_or_missing_profile_uses_valid_scalar_fallback(self):
        values=['']*63+['x'*10000]
        bad_common=[None,'bad',[[None,63]],[['',True]],[['',65]],[['',1.5]],
                    [['',63],['',1]],[['',63,0]],[['',0]],[['',-1]]]
        for common in bad_common:
            def mutate(schema,value=common):
                for t in schema.values():
                    t['stats']['columns']['k']['common']=value
            with self.subTest(common=common):
                choice,_=self.probe(dataset(values,values,'STR'),mutate=mutate)
                self.assertEqual(choice,'HJOIN')
        def remove_common(schema):
            for t in schema.values():
                del t['stats']['columns']['k']['common']
        choice,_=self.probe(dataset(values,values,'STR'),mutate=remove_common)
        self.assertEqual(choice,'HJOIN')

    def test_unmodeled_derived_distributions_drop_profiles(self):
        values=['']*63+['x'*10000]
        prefixes=['RTRIM x,x\nRTRIM y,y\n',
                  'SLICE x,x,64\nSLICE y,y,64\n',
                  'IOTA i,x\nIOTA j,y\nGATHER x,x,i\nGATHER y,y,j\n']
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                choice,_=self.probe(dataset(values,values,'STR'),prefix=prefix)
                self.assertEqual(choice,'HJOIN')

    def test_ambiguous_integer_tail_near_cost_tie_keeps_original_policy(self):
        # avg116.02*128=14850.56; +/-0.64 permits tail totals14850 or14851.
        # Actual NL is2cycles cheaper, inside the declared uncertainty band.
        values=['']*127+['x'*14850]
        for initial in ('NLJOIN','HJOIN'):
            with self.subTest(initial=initial):
                choice,cost=self.probe(dataset(values,values,'STR'),initial=initial)
                self.assertEqual(choice,initial)
                self.assertEqual(cost['HJOIN']-cost['NLJOIN'],2)

    def test_literal_fill_uses_literal_utf8_length(self):
        data=dataset(['']*4,['']*4,'STR')
        prefix="FILL x,'猫猫',x\nFILL y,'猫猫',y\n"
        choice,cost=self.probe(data,prefix=prefix)
        self.assertEqual(choice,'HJOIN')
        self.assertLess(cost['HJOIN'],cost['NLJOIN'])

    def test_untrusted_estimates_do_not_crash_or_change_program_operands(self):
        values=['']*63+['x'*10000]
        variants=[('rows',None),('rows',-1),('rows',True),('rows',1.5),
                  ('nulls',65),('nulls',True),('nulls',-1),
                  ('avg_bytes',None),('avg_bytes',-1),('avg_bytes','bad')]
        for field,value in variants:
            def mutate(schema,f=field,v=value):
                for t in schema.values():
                    if f=='rows':
                        t['stats'][f]=v
                    else:
                        t['stats']['columns']['k'][f]=v
            with self.subTest(field=field,value=value):
                self.probe(dataset(values,values,'STR'),mutate=mutate,nulleq=True)
        def omit_stats(schema):
            for t in schema.values():
                del t['stats']
        choice,_=self.probe(dataset(values,values,'STR'),mutate=omit_stats)
        self.assertEqual(choice,'NLJOIN')


if __name__=='__main__':
    unittest.main()
