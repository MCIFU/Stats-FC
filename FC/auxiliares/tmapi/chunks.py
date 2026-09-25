import json,glob,re,os,sys
D='/root/.claude/projects/-home-claude/4370b94a-5ff7-5a8b-bfe5-23383ce006dc/tool-results/'
def load(prefix):
    parts={}
    for f in glob.glob(D+'mcp-remote-devices-Claude_Browser__javascript_tool-*.txt'):
        a=json.load(open(f)); t=a[0]['text']
        try: v,_=json.JSONDecoder(strict=False).raw_decode(t.strip())
        except Exception: continue
        if isinstance(v,str) and v.startswith(prefix):
            m=re.match(re.escape(prefix)+r'(\d+)@',v); parts[int(m.group(1))]=(os.path.getmtime(f),v[m.end():])
    return parts
if __name__=='__main__':
    p=load(sys.argv[1]); print(sorted(p)); 
    txt=''.join(p[i][1] for i in sorted(p)); open(sys.argv[2],'w').write(txt); print(len(txt))
