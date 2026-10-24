import os, sys

kmods, ref_load, extra_load, out_load = sys.argv[1:5]

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

sel = set(order)
stack = list(sel)
while stack:
    m = stack.pop()
    for d in dep.get(m, []) + softpre.get(m, []):
        if d not in sel:
            sel.add(d)
            stack.append(d)

required = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), 'first_stage.required')) if l.strip()]
lost = [m for m in required if m in built and m not in sel]
if lost:
    sys.exit('first-stage modules missing from the load list: ' + ' '.join(lost))

missing = [m for m in sel if m not in built]
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

f = ordered(sel)
open(out_load, 'w').write('\n'.join(f) + '\n')
print('ramdisk: %d modules, %d bytes' % (len(f), sum(os.path.getsize(built[m]) for m in f)))
