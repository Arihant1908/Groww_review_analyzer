import pandas as pd, json, hashlib

def get_hash(text):
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()

df = pd.read_csv('out/reviews_themed.csv')
low_rated = df[df['rating'] <= 3]
cache = json.load(open('out/theme_cache.json', 'r'))
themes = json.load(open('config/themes.json', 'r', encoding='utf-8'))
themes = {k:v for k,v in themes.items() if k != 'unthemed'}

desc_list = []
for tid, t in themes.items():
    desc_list.append('- ' + tid + ': ' + t['name'] + ' - ' + t['definition'])
themes_desc = '\n'.join(desc_list)
ai_instructions = 'Rules:\n1. Return EXACTLY 1 or 2 theme IDs for each review.\n2. If it doesn\'t fit the 5 themes, use ["unthemed"].\n3. Return ONLY a valid JSON object mapping the string index "0", "1" etc. to the list of theme IDs.\n4. Reviews may be short, misspelled, or in Hinglish. Use the meaning, not exact keywords.'
fingerprint = get_hash(themes_desc + '\n' + ai_instructions)

a = 0
f = 0
for _, row in low_rated.iterrows():
    text = str(row['review']).strip()
    if not text: continue
    h = get_hash(text + '_' + fingerprint)
    if h in cache:
        layer = cache[h].get('layer', 'unknown')
        if layer == 'ai': a += 1
        elif layer == 'fallback': f += 1

print('AI layer:', a)
print('Fallback layer:', f)
