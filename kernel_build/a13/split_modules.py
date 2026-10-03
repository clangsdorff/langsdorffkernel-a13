import os, re, sys

kmods, ref_load, extra_load, regex_file, out_first, out_second = sys.argv[1:7]

built = {}
for root, _, files in os.walk(kmods):
    for f in files:
        if f.endswith('.ko'):
            built[f] = os.path.join(root, f)

dep = {}
for l in open(os.path.join(kmods, 'modules.dep')):
    k, v = l.split(':', 1)
    dep[os.path.basename(k)] = [os.path.basename(x) for x in v.split()]

softpre = {}
sd = os.path.join(kmods, 'modules.softdep')
if os.path.exists(sd):
    alias = {m[:-3].replace('-', '_'): m for m in built}
    for l in open(sd):
        p = l.split()
        if len(p) < 3 or p[0] != 'softdep':
            continue
        m = alias.get(p[1].replace('-', '_'))
        pre, mode = [], None
        for x in p[2:]:
            if x in ('pre:', 'post:'):
                mode = x
            elif mode == 'pre:' and alias.get(x.replace('-', '_')):
                pre.append(alias[x.replace('-', '_')])
        if m:
            softpre[m] = pre

order = []
for src in (ref_load, extra_load):
    for l in open(src):
        m = l.strip()
        if m and not m.startswith('#') and m in built and m not in order:
            order.append(m)

pat = re.compile('|'.join(l.strip() for l in open(regex_file) if l.strip() and not l.startswith('#')))
second = {m for m in order if pat.match(m)}
changed = True
while changed:
    changed = False
    for m in order:
        if m not in second and any(d in second for d in dep.get(m, []) + softpre.get(m, [])):
            second.add(m)
            changed = True
first = {m for m in order if m not in second}

stack = list(first)
while stack:
    m = stack.pop()
    for d in dep.get(m, []) + softpre.get(m, []):
        if d not in first:
            first.add(d)
            stack.append(d)

required = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), 'first_stage.required')) if l.strip()]
lost = [m for m in required if m in built and m not in first]
if lost:
    sys.exit('first-stage modules pushed out: ' + ' '.join(lost))

missing = [m for m in first if m not in built]
if missing:
    sys.exit('missing modules: ' + ' '.join(missing))

def ordered(sel):
    out, seen = [], set()
    def visit(m):
        if m in seen:
            return
        seen.add(m)
        for d in dep.get(m, []) + softpre.get(m, []):
            if d in sel:
                visit(d)
        out.append(m)
    for m in order:
        if m in sel:
            visit(m)
    for m in sorted(sel):
        visit(m)
    return out

f1 = ordered(first)
f2 = ordered({m for m in order if m not in first})
print('moved to vendor_dlkm by dependency: ' + ' '.join(sorted(m for m in second if not pat.match(m))))
open(out_first, 'w').write('\n'.join(f1) + '\n')
open(out_second, 'w').write('\n'.join(f2) + '\n')
print('first-stage: %d modules, %d bytes' % (len(f1), sum(os.path.getsize(built[m]) for m in f1)))
print('vendor_dlkm: %d modules, %d bytes' % (len(f2), sum(os.path.getsize(built[m]) for m in f2)))
