"""Read-only: extract file write/edit/read events from Claude transcripts.
Usage: python -I scan_events.py OUT.pkl transcript1.jsonl [...]
"""
import json, sys, pickle, os

out = sys.argv[1]
events = []  # (ts, session, kind, path, payload, tool_use_id)
results = {}  # tool_use_id -> (is_error, text)
for fp in sys.argv[2:]:
    sess = os.path.basename(fp).split('.')[0]
    with open(fp, encoding='utf-8', errors='replace') as f:
        for ln, line in enumerate(f):
            try:
                o = json.loads(line)
            except Exception:
                continue
            ts = o.get('timestamp', '')
            msg = o.get('message') or {}
            content = msg.get('content')
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get('type') == 'tool_use':
                    name = c.get('name'); inp = c.get('input') or {}
                    tid = c.get('id')
                    if name in ('Write', 'Edit', 'MultiEdit', 'Read', 'NotebookEdit'):
                        events.append((ts, sess, name, inp.get('file_path') or inp.get('notebook_path'), inp, tid, ln))
                    elif name in ('Bash', 'PowerShell'):
                        events.append((ts, sess, name, None, {'command': inp.get('command', '')}, tid, ln))
                elif c.get('type') == 'tool_result':
                    tid = c.get('tool_use_id')
                    cc = c.get('content')
                    if isinstance(cc, list):
                        txt = '\n'.join(x.get('text', '') for x in cc if isinstance(x, dict))
                    else:
                        txt = cc if isinstance(cc, str) else ''
                    results[tid] = (bool(c.get('is_error')), txt)
with open(out, 'wb') as f:
    pickle.dump({'events': events, 'results': results}, f)
print(len(events), 'events', len(results), 'results')
