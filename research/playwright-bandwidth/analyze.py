"""Rebuild CSV tables and publication charts from immutable runner observations.
Usage: python analyze.py RUN_DIRECTORY OUTPUT_DIRECTORY
Charts require matplotlib; numerical exports use the standard library only.
"""
import csv, hashlib, json, math, statistics, sys
from pathlib import Path

def main():
    source, out = map(Path, sys.argv[1:3])
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((source/'manifest.json').read_text())
    pages = [json.loads(line) for line in (source/'pages.jsonl').read_text().splitlines()]
    attempt_path=source/'attempts.jsonl'
    if int(manifest['protocol'].split('.')[0]) >= 2:
        assert attempt_path.exists(), 'Protocol v2 requires every attempt'
    attempts=[json.loads(line) for line in attempt_path.read_text().splitlines()] if attempt_path.exists() else pages
    assert manifest['status'] == 'complete', 'Incomplete run'
    assert len(pages) == manifest['pages'] * manifest['repeats'] * 2
    if attempt_path.exists():
        key=lambda p:(p['repeat'],p['page'],p['arm'])
        assert {key(p) for p in attempts}=={key(p) for p in pages}
        for page in pages:
            group=[p for p in attempts if key(p)==key(page)]
            assert [p['attempt_idx'] for p in group] in [[1],[1,2]]
            assert group[-1]==page and group[-1]['accepted'] and not group[-1]['will_retry']
            assert all(not p['accepted'] and p['will_retry'] and p['validation_errors'] for p in group[:-1])
            assert sum(bool(p['accepted']) for p in group)==1
        assert manifest['attempt_count']==len(attempts)
        assert manifest['accepted_navigation_count']==len(pages)
        assert manifest['retry_count']==sum(p['attempt_idx']>1 for p in attempts)
        assert manifest['failed_attempt_count']==sum(not p['accepted'] for p in attempts)

    totals=[]
    for repeat in range(1, manifest['repeats']+1):
        for arm in ['full','lean']:
            group=[p for p in pages if p['repeat']==repeat and p['arm']==arm]
            assert len(group)==manifest['pages']
            assert sorted(p['page'] for p in group)==list(range(1,manifest['pages']+1))
            for p in group:
                assert len(p['rows'])==20
                assert math.isfinite(p['observed_bytes']) and p['observed_bytes']>=0
                assert sum(t['bytes'] for t in p['request_types'].values())==p['observed_bytes']
            assert not any(p['validation_errors'] or p['failed_requests'] or p['missing_sizes'] for p in group)
            records=[row for p in group for row in p['rows']]
            assert len(records)==len({r['url'] for r in records})==manifest['pages']*20
            attempt_group=[p for p in attempts if p['repeat']==repeat and p['arm']==arm]
            for p in attempt_group:
                assert math.isfinite(p['observed_bytes']) and p['observed_bytes']>=0
                assert p['missing_sizes']==0
                assert sum(t['bytes'] for t in p['request_types'].values())==p['observed_bytes']
            total=sum(p['observed_bytes'] for p in attempt_group)
            totals.append(dict(repeat=repeat,arm=arm,unique_records=len(records),observed_bytes=total,accepted_attempt_bytes=sum(p['observed_bytes'] for p in group),attempts=len(attempt_group),retry_attempts=len(attempt_group)-len(group),failed_requests=sum(p['failed_requests'] for p in attempt_group),decimal_mb=total/1e6,completed_requests=sum(p['completed_requests'] for p in attempt_group),blocked_requests=sum(p['intentionally_blocked_requests'] for p in attempt_group),modelled_usd_at_6_50=total/1e9*6.5,modelled_usd_at_2_50=total/1e9*2.5))
        a={r['url']:r for p in pages if p['repeat']==repeat and p['arm']=='full' for r in p['rows']}
        b={r['url']:r for p in pages if p['repeat']==repeat and p['arm']=='lean' for r in p['rows']}
        assert a==b, 'Full/lean records differ'
        for number in range(1,manifest['pages']+1):
            pair=[p for p in pages if p['repeat']==repeat and p['page']==number]
            assert len(pair)==2 and {p['arm'] for p in pair}=={'full','lean'}
            assert sorted(pair[0]['rows'],key=lambda r:r['url'])==sorted(pair[1]['rows'],key=lambda r:r['url'])
    def savecsv(name, rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    savecsv('repeat-totals.csv',totals)
    savecsv('page-observations.csv',[{k:p[k] for k in ['repeat','page','arm','started_at','observed_bytes','completed_requests','failed_requests','intentionally_blocked_requests','browser_policy_blocked_requests','missing_sizes','duration_ms','document_status']} for p in pages])
    savecsv('attempt-observations.csv',[dict(repeat=p['repeat'],page=p['page'],arm=p['arm'],attempt=p.get('attempt',p.get('attempt_idx',1)),accepted=not p['validation_errors'],observed_bytes=p['observed_bytes'],failed_requests=p['failed_requests'],browser_policy_blocked_requests=p['browser_policy_blocked_requests'],validation_errors=';'.join(p['validation_errors'])) for p in attempts])
    savecsv('records.csv',[dict(repeat=p['repeat'],arm=p['arm'],catalogue_page=p['page'],navigation_started_at=p['started_at'],**r) for p in pages for r in p['rows']])
    savings=[100*(1-totals[i+1]['observed_bytes']/totals[i]['observed_bytes']) for i in range(0,len(totals),2)]
    summary={'source_manifest':manifest,'totals':totals,'reduction_percent_each_repeat':savings,'median_reduction_percent':statistics.median(savings),'records_equal_within_every_pair':True,'actual_billed_bytes':None,'actual_billed_cost_usd':None,'attempt_count':len(attempts),'failed_attempt_count':sum(bool(p['validation_errors']) for p in attempts),'cost_basis':'Modelled from captured completed-request browser HTTP bytes across all attempts; partial failed transfers unmeasured, decimal GB, excludes transport overhead and compute; published rates are not invoices. $6.50/GB requires a $6.50 1GB purchase; $2.50/GB requires a $2500 1TB purchase.'}
    (out/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.color':'#1b1b1b','axes.labelcolor':'#60646c','axes.edgecolor':'#e0e1e6','svg.fonttype':'none'})
    colors=['#60646c','#198d82']
    fig,ax=plt.subplots(figsize=(12,6.75),layout='constrained'); fig.set_facecolor('#ffffff')
    ax.set_title('Same catalogue records, different transfer',loc='left',fontsize=23,pad=58,weight='bold')
    for j,arm in enumerate(['full','lean']):
        rows=[t for t in totals if t['arm']==arm]
        bars=ax.bar([t['repeat']+(j-.5)*.32 for t in rows],[t['decimal_mb'] for t in rows],width=.29,color=colors[j],label='Default resource loading' if arm=='full' else 'Block images, fonts, media')
        ax.bar_label(bars,fmt='%.2f',padding=5,fontsize=11)
    ax.set_xticks(range(1,manifest['repeats']+1),[f'Repeat {i}' for i in range(1,manifest['repeats']+1)])
    ax.set_ylabel('Browser-observed HTTP transfer (decimal MB)');ax.spines[['top','right']].set_visible(False);ax.set_ylim(bottom=0);ax.margins(y=.2);ax.legend(frameon=False,loc='lower left',bbox_to_anchor=(0,1.01),ncol=2,fontsize=11)
    fig.text(.01,-.025,f"ProxyLane | {manifest['pages']*20:,} catalogue records per arm per repeat | {manifest['started_at'][:10]} | Cache disabled | Billing not measured",fontsize=10,color='#60646c')
    for ext in ['png','svg']: fig.savefig(out/f'transfer-by-repeat.{ext}',dpi=160,bbox_inches='tight')
    plt.close(fig)
    types=sorted({t for p in attempts for t in p['request_types']})
    fig,ax=plt.subplots(figsize=(12,6.75),layout='constrained')
    for j,arm in enumerate(['full','lean']):
        values=[sum(p['request_types'].get(t,{}).get('bytes',0) for p in attempts if p['arm']==arm)/manifest['repeats']/1e6 for t in types]
        ax.barh([i+(j-.5)*.32 for i in range(len(types))],values,height=.29,color=colors[j],label='Default resource loading' if arm=='full' else 'Block images, fonts, media')
    ax.set_yticks(range(len(types)),types);ax.set_xlabel('Mean browser-observed HTTP transfer per catalogue (decimal MB)');ax.set_title('Where the bytes went',loc='left',fontsize=23,pad=24,weight='bold');ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False)
    fig.text(.01,-.025,'ProxyLane research | Resource types recorded by Playwright | Observed bytes, not provider invoice',fontsize=10,color='#60646c')
    for ext in ['png','svg']: fig.savefig(out/f'resource-breakdown.{ext}',dpi=160,bbox_inches='tight')
    plt.close(fig)
    (out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file()))
    print(json.dumps({'totals':totals,'savings':savings},indent=2))
if __name__=='__main__': main()
