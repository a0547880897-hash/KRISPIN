import json, sys
batch=json.load(open(sys.argv[1],encoding='utf-8'))
scan=json.load(open('expenses_scan.json',encoding='utf-8')) if __import__('os').path.exists('expenses_scan.json') else {}
scan.update(batch)
json.dump(scan,open('expenses_scan.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('merged',len(batch),'-> total scanned:',len([k for k in scan if not k.startswith('_')]))
