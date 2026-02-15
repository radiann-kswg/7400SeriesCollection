User: 現在所持している7400シリーズロジックICのうち、カテゴリが`01_buffers_invertars`～`04_xor_xnor_gates`に相当するすべてのロジック番号のパーツについて、チートシートとサンプル回路の解説資料を`./usage/06_encoders_decoders/74x141`フォルダ内を参考に生成してください。
また、パーツの仕様についてはデータシートの情報を堅実・安全に取得するようお願いします。
なお この作業が正確に実行されることをuserが確認した際は、この作業と指示を今後も継続的に行えるようCopilot指示書も更新する予定です。

GitHub Copilot: 進め方を固めるために、まず(1)参考にする 74x141 の既存ドキュメント構成を確認し、(2)入手履歴とカテゴリJSONから「所持済み＆カテゴリ01〜04」の対象パーツ一覧を機械的に抽出、(3)usage配下に既に資料があるかを突き合わせて「新規生成が必要な数」と概算行数を出します。その上で、500行超えが見込まれる場合は実行前に確認を入れ、生成スクリプトの適用/最小改修で一括生成します。

Created 5 todos

まずは参照元の `74x141` フォルダの中身と、生成に使っていそうなテンプレ/スクリプトを確認します。

[](./usage/06_encoders_decoders/74x141) の読み取り

[](./usage/_templates) の読み取り

`**/usage/06_encoders_decoders/74x141/**/*.md` に一致するファイルを検索しました。一致 7

`**/scripts/generate_usage_cheatsheets.py` に一致するファイルを検索しました。1 件の一致

74x141は「チートシート(74x141.md)＋複数のサンプル回路(01*〜06*)」構成ですね。次に 74x141.md とサンプルの書き方を読んで、同じ雛形で01〜04カテゴリの所持パーツに展開できるか判断します。

[](./usage/06_encoders_decoders/74x141/74x141.md) の読み取り

[](./usage/06_encoders_decoders/74x141/01_simple_nixie_tube_demo.md#1-1) の 1 から 260 行を読み取り

[](./usage/_templates/logic-ic-cheatsheet.md) の読み取り

[](./scripts/generate_usage_cheatsheets.py#1-1) の 1 から 260 行を読み取り

所持品×カテゴリ01〜04の対象パーツ数と、usageに既に資料があるかを自動集計します（この段階ではファイル生成はまだしません）。

Configuring a Python Environment
Completed with input: {
"resourcePath": "d:\\VisualStudio Code Userfile\\7400SeriesCollection"
}

Ran terminal command: "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" - << 'PY'
import json
from pathlib import Path

root = Path('D:/VisualStudio Code Userfile/7400SeriesCollection')

overview = json.loads((root/'overview/7400_series_ic_overview.json').read_text(encoding='utf-8'))
history = json.loads((root/'getstarting/7400_series_ic_collection_acquisition_history.json').read_text(encoding='utf-8'))

# owned partnumbers = entries that have any gotten items in any bucket

owned = set()
for item in history:
if not isinstance(item, dict):
continue
pn = str(item.get('PartNumber','')).strip()
if not pn:
continue
got = []
for k in ('GottenItemsMN_CMOS','GottenItemsMN_TTL','GottenItemsMN_Other'):
v = item.get(k, [])
if isinstance(v, list):
got += [x for x in v if str(x).strip()]
if got:
owned.add(pn)

# map pn -> category

pn_to_cat = {}
for item in overview:
pn = str(item.get('PartNumber','')).strip()
if pn:
pn_to_cat[pn] = str(item.get('Category','99_other')).strip() or '99_other'

# target categories

cats = {f'{i:02d}\_buffers_inverters' for i in [1]} | {f'{i:02d}\_nand_and_gates' for i in [2]} | {f'{i:02d}\_nor_or_gates' for i in [3]} | {f'{i:02d}\_xor_xnor_gates' for i in [4]}

# find owned parts that are in those categories

owned_targets = sorted([pn for pn in owned if pn_to_cat.get(pn) in cats])

# check usage existence

usage_root = root/'usage'
missing_cheatsheet = []
existing_cheatsheet = []
missing_samples = []

for pn in owned_targets:
cat = pn_to_cat[pn]
part_dir = usage_root/cat/pn
cheat = part_dir/f'{pn}.md'
if cheat.exists():
existing_cheatsheet.append(pn)
else:
missing_cheatsheet.append(pn)

    # heuristic: sample circuit docs (01_*.md) presence
    samples = sorted(part_dir.glob('0[1-9]_*.md'))
    if len(samples)==0:
        missing_samples.append(pn)

print('Owned targets count:', len(owned*targets))
print('Targets:', owned_targets)
print('Existing cheatsheets:', len(existing_cheatsheet))
print('Missing cheatsheets:', len(missing_cheatsheet))
print('Missing samples (no 01*..):', len(missing_samples))
print('Missing cheatsheets list:', missing_cheatsheet)
print('Missing samples list:', missing_samples)
PY

[](file:///c%3A/Users/s-chi/AppData/Roaming/Code/User/workspaceStorage/9a4c4185478247ba4ab7d88fda37a155/GitHub.copilot-chat/chat-session-resources/d6f17b86-ad75-4e11-8914-767d1a8f9cc0/call_LhIXqNnJVEvvBRP0EwIXokwF__vscode-1771121513973/content.txt#1-1) の 1 から 200 行を読み取り

Ran terminal command: $code = @'
import json
from pathlib import Path

root = Path(r'D:/VisualStudio Code Userfile/7400SeriesCollection')
overview = json.loads((root/'overview/7400_series_ic_overview.json').read_text(encoding='utf-8'))
history = json.loads((root/'getstarting/7400_series_ic_collection_acquisition_history.json').read_text(encoding='utf-8'))

owned = set()
for item in history:
if not isinstance(item, dict):
continue
pn = str(item.get('PartNumber','')).strip()
if not pn:
continue
got = []
for k in ('GottenItemsMN_CMOS','GottenItemsMN_TTL','GottenItemsMN_Other'):
v = item.get(k, [])
if isinstance(v, list):
got += [str(x).strip() for x in v if str(x).strip()]
if got:
owned.add(pn)

pn_to_cat = {}
for item in overview:
pn = str(item.get('PartNumber','')).strip()
if pn:
pn_to_cat[pn] = str(item.get('Category','99_other')).strip() or '99_other'

cats = {
'01_buffers_inverters',
'02_nand_and_gates',
'03_nor_or_gates',
'04_xor_xnor_gates',
}

owned_targets = sorted([pn for pn in owned if pn_to_cat.get(pn) in cats])

usage_root = root/'usage'
missing_cheatsheet = []
existing_cheatsheet = []
missing_samples = []

for pn in owned_targets:
cat = pn_to_cat[pn]
part_dir = usage_root/cat/pn
cheat = part_dir/f'{pn}.md'
if cheat.exists():
existing_cheatsheet.append(pn)
else:
missing_cheatsheet.append(pn)

    samples = sorted(part_dir.glob('0[1-9]_*.md'))
    if len(samples) == 0:
        missing_samples.append(pn)

out = {
'owned_targets': owned_targets,
'existing_cheatsheet': existing_cheatsheet,
'missing_cheatsheet': missing_cheatsheet,
'missing_samples': missing_samples,
}

(root/'.temp').mkdir(exist_ok=True)
(root/'.temp/owned_targets_01_04.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

print('Owned targets count:', len(owned_targets))
print('Existing cheatsheets:', len(existing_cheatsheet))
print('Missing cheatsheets:', len(missing_cheatsheet))
print('Missing samples:', len(missing_samples))
print('Wrote: .temp/owned_targets_01_04.json')
'@
& "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" -c $code

Ran terminal command: exit()

[](./.temp/report_owned_targets_01_04.py) が作成されました

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/report_owned_targets_01_04.py

Starting: _既存usage有無と差分算出_ (3/5)

[](./.temp/owned_targets_01_04.json#1-1) の 1 から 200 行を読み取り

[](./datasheets/datasheet_sources.json#1-1) の 1 から 120 行を読み取り

3 件の質問をしました (生成範囲, 精度方針, 上書き)

`**/datasheets/_download/**/sn74s00*.pdf` に一致するファイルを検索しました。一致するものはありません

`**/datasheets/_download/**/SN74S00*.PDF` に一致するファイルを検索しました。一致するものはありません

[](./scripts/check_datasheet_sources.py#1-1) の 1 から 260 行を読み取り

Python 環境情報をフェッチしています
Completed with input: {
"resourcePath": "d:\\VisualStudio Code Userfile\\7400SeriesCollection"
}

パッチを生成中 (31 行)、[](./.temp/report_owned_targets_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/report_owned_targets_01_04.py

[](./.temp/owned_targets_01_04.json#180-180) の 180 から 240 行を読み取り

`**/datasheets/_download/**/TC74HC00AF*.PDF` に一致するファイルを検索しました。一致するものはありません

[](./datasheets/_download/TOSHIBA) の読み取り

pypdf==6.0.0 を Python 3.14.0 (.venv) にインストールしています
Completed with input: {
"packageList": [
"pypdf==6.0.0"
],
"resourcePath": "d:\\VisualStudio Code Userfile\\7400SeriesCollection"
}

[](./.temp/test_pdf_extract.py) が作成されました

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py

パッチを生成中 (45 行)、[](./.temp/test_pdf_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py

正規表現 `--download|download_dir|datasheet_fetch` (`**/scripts/check_datasheet_sources.py`) を検索し、結果は 5 件でした

[](./scripts/check_datasheet_sources.py#420-420) の 420 から 720 行を読み取り

[](./datasheets/_download/PHILIPS%28NXPSemiconductors%29) の読み取り

パッチを生成中 (32 行)、[](./.temp/test_pdf_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py datasheets/\_download/PHILIPS(NXPSemiconductors)/74HC86.PDF

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py "datasheets/\_download/PHILIPS(NXPSemiconductors)/74HC86.PDF"

[](./datasheets/_download/FAIRCHILD%28FairchildSemiconductor%29) の読み取り

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py "datasheets/\_download/TOSHIBA/TC74HC240AP,TC74HC241AP,TC74HC244AP.PDF"

Ran terminal command: $out = ".temp/datasheet_fetch/tmp_sn74hc00.pdf"; New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null; Invoke-WebRequest -Uri "https://www.ti.com/lit/ds/symlink/sn74hc00.pdf" -OutFile $out; Write-Host "Downloaded:" $out; Write-Host "Bytes:" (Get-Item $out).Length

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/test_pdf_extract.py .temp/datasheet_fetch/tmp_sn74hc00.pdf

[](./.temp/owned_targets_01_04.json#240-240) の 240 から 446 行を読み取り

[](./scripts/generate_usage_samples_owned_01_04.py) が作成されました

[](./work-in-progress/2026-02-15_generate_samples_owned_01-04.md) が作成されました

Starting: _生成方針を確定し実装_ (4/5)

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download

Awaited terminal completion

最後のターミナル コマンドを取得しました

`**/usage/02_nand_and_gates/74x00/01_basic_function_demo.md` に一致するファイルを検索しました。1 件の一致

`**/usage/{01_buffers_inverters,02_nand_and_gates,03_nor_or_gates,04_xor_xnor_gates}/**/01_basic_function_demo.md` に一致するファイルを検索しました。一致 52

[](./usage/02_nand_and_gates/74x00/01_basic_function_demo.md) の読み取り

[](./usage/04_xor_xnor_gates/74x86/01_basic_function_demo.md) の読み取り

[](./usage/02_nand_and_gates/74x50/01_basic_function_demo.md) の読み取り

[](./usage/01_buffers_inverters/74x240/01_basic_function_demo.md) の読み取り

パッチを生成中 (172 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --force

[](./scripts/generate_usage_samples_owned_01_04.py#300-300) の 300 から 420 行を読み取り

パッチを生成中 (19 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --force

[](./scripts/generate_usage_samples_owned_01_04.py#332-332) の 332 から 360 行を読み取り

パッチを生成中 (26 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

[](./scripts/generate_usage_samples_owned_01_04.py#338-338) の 338 から 360 行を読み取り

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --force

[](./usage/02_nand_and_gates/74x00/01_basic_function_demo.md) の読み取り

パッチを生成中 (84 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --force

[](./usage/02_nand_and_gates/74x00/01_basic_function_demo.md) の読み取り

`**/.temp/datasheet_fetch/generated_samples/TI/SN74HC00N.pdf` に一致するファイルを検索しました。一致するものはありません

`**/.temp/datasheet_fetch/generated_samples/TI/*.pdf` に一致するファイルを検索しました。一致するものはありません

[](./.temp) の読み取り

[](./.temp/datasheet_fetch) の読み取り

[](./.temp/datasheet_fetch/generated_samples) の読み取り

[](./.temp/datasheet_fetch/generated_samples/TI) の読み取り

[](./.temp/debug_pin_extract.py) が作成されました

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py

パッチを生成中 (35 行)、[](./.temp/debug_pin_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py

パッチを生成中 (17 行)、[](./.temp/debug_pin_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py

Using "パッチの適用"

パッチを生成中 (30 行)、[](./.temp/debug_pin_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py

パッチを生成中 (15 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --force

[](./usage/02_nand_and_gates/74x00/01_basic_function_demo.md) の読み取り

[](./usage/04_xor_xnor_gates/74x86/01_basic_function_demo.md#40-40) の 40 から 60 行を読み取り

チェックされた [](./scripts/generate_usage_samples_owned_01_04.py)、問題は見つかりませんでした

テキスト `自動抽出によるピン配置確定ができませんでした` (`**/usage/{01_buffers_inverters,02_nand_and_gates,03_nor_or_gates,04_xor_xnor_gates}/**/01_basic_function_demo.md`) を検索し、結果は 37 件でした

[](./usage/04_xor_xnor_gates/74x86/01_basic_function_demo.md#20-20) の 20 から 60 行を読み取り

パッチを生成中 (14 行)、[](./.temp/debug_pin_extract.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py .temp/datasheet_fetch/generated_samples/TI/SN74HC86N.pdf

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74HC86N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

Summarized conversation history状況把握できました。次に、`SN74HC86N` は抽出自体は成功しているので、(1) 生成スクリプト側の `relative_to()` を堅牢化（デバッグ/将来の相対パスでも落ちない）しつつ、(2) `--force` で再生成して「要一次資料」スタブを減らせるか確認します。まずスクリプトの該当箇所を確認します。

[](./scripts/generate_usage_samples_owned_01_04.py#1-1) の 1 から 240 行を読み取り

[](./scripts/generate_usage_samples_owned_01_04.py#240-240) の 240 から 520 行を読み取り

いま見た限り、`relative_to(REPO_ROOT)` が「デバッグで相対パスを渡したとき」に落ちるのが主因です。ここはスクリプト側を堅牢化して、相対/絶対どちらでも安全に “抽出元パス表示” できるように直します。次に `--force` 再生成で既存のスタブを更新できますが、これは変更量が500行を超える可能性が高いので、その前に確認します。まずはスクリプトだけ小さくパッチします。

パッチを生成中 (47 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

テキスト `自動抽出によるピン配置確定ができませんでした` (`**/usage/{01_buffers_inverters,02_nand_and_gates,03_nor_or_gates,04_xor_xnor_gates}/**/*.md`) を検索し、結果は 36 件でした

[](./usage/04_xor_xnor_gates/74x86/01_basic_function_demo.md) の読み取り

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" -c "import json; d=json.load(open('.temp/owned_targets_01_04.json','r',encoding='utf-8')); m=d.get('owned_exact_items',{});
for k in ['74x240','74x244','74x34','74x37','74x07','74x03','74x09']:
print(k, m.get(k))"

Ran terminal command: Test-Path .temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf; Test-Path .temp/datasheet_fetch/generated_samples/TI/SN74HC244N.pdf; Test-Path .temp/datasheet_fetch/generated_samples/TI/SN7403.pdf

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

テキスト `argparse` (`**/scripts/generate_usage_samples_owned_01_04.py`) を検索し、結果は 2 件でした

[](./scripts/generate_usage_samples_owned_01_04.py#520-520) の 520 から 608 行を読み取り

パッチを生成中 (108 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

[](./.temp/debug_pin_extract.py) の読み取り

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" - <<'PY'
from pypdf import PdfReader
import re
from pathlib import Path
pdf=Path('.temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf')
reader=PdfReader(str(pdf))
text=reader.pages[2].extract_text() or ''
print('has Pin Functions?', 'Pin Functions' in text)

# replicate parser bits

tokens=text.split()
print('Pin in tokens', 'Pin' in tokens, 'Functions' in tokens)

# find start

start_idx=None
for i in range(len(tokens)-2):
if tokens[i].lower()=='pin' and tokens[i+1].lower().startswith('function'):
start_idx=i;break
if tokens[i].lower()=='pin' and tokens[i+1].lower()=='functions':
start_idx=i;break
print('start_idx', start_idx, tokens[start_idx:start_idx+5] if start_idx is not None else None)
stop_words={'pin','pins','pin(s)','no.','no','name','i/o','io','description'}

def normalize_name(raw:str)->str:
s=(raw or '').strip().strip(',;:.')
s=re.sub(r"\(\d+\)$","",s)
return s

def is*pin_name(tok:str)->bool:
name=normalize_name(tok)
if not name: return False
lower=name.lower()
if lower in stop_words: return False
upper=name.upper()
if upper in {'NC','GND','VCC','VDD','VSS'}: return True
if not re.fullmatch(r"[0-9A-Za-z/*-]+", name):
return False
return bool(re.search(r"[A-Za-z]", name))

mapping={}
for i in range(start_idx, len(tokens)-1):
t0=tokens[i]; t1=tokens[i+1]
if is_pin_name(t0) and t1.isdigit():
pin=int(t1)
if 0<pin<=64:
mapping.setdefault(pin, normalize_name(t0))
continue
if t0.isdigit() and is_pin_name(t1):
pin=int(t0)
if 0<pin<=64:
mapping.setdefault(pin, normalize_name(t1))
continue
print('mapping size', len(mapping))
print('first few', sorted(mapping.items())[:5])
vals={v.upper() for v in mapping.values()}
print('has GND', 'GND' in vals, 'has VCC', 'VCC' in vals)
print('pin_count', max(mapping) if mapping else None)
PY

[](file:///c%3A/Users/s-chi/AppData/Roaming/Code/User/workspaceStorage/9a4c4185478247ba4ab7d88fda37a155/GitHub.copilot-chat/chat-session-resources/d6f17b86-ad75-4e11-8914-767d1a8f9cc0/call_n1f03ZaSohsCNVklr9RyL4br__vscode-1771121514072/content.txt#1-1) の 1 から 120 行を読み取り

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" -c "from pypdf import PdfReader; import re; from pathlib import Path; pdf=Path('.temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf'); r=PdfReader(str(pdf)); text=r.pages[2].extract_text() or ''; tokens=text.split(); print('Pin Functions' in text); print('Pin' in tokens, 'Functions' in tokens); start=None
for i in range(len(tokens)-2):
if tokens[i].lower()=='pin' and tokens[i+1].lower().startswith('function'):
start=i; break
if tokens[i].lower()=='pin' and tokens[i+1].lower()=='functions':
start=i; break
print('start', start, tokens[start:start+6] if start is not None else None)
stop={'pin','pins','pin(s)','no.','no','name','i/o','io','description'}

def norm(s):
s=(s or '').strip().strip(',;:.');
return re.sub(r'\(\d+\)$','',s)

def isname(tok):
name=norm(tok)
if not name: return False
if name.lower() in stop: return False
if name.upper() in {'NC','GND','VCC','VDD','VSS'}: return True
if not re.fullmatch(r'[0-9A-Za-z/_-]+', name): return False
return bool(re.search(r'[A-Za-z]', name))

m={}
for i in range(start, len(tokens)-1):
t0=tokens[i]; t1=tokens[i+1]
if isname(t0) and t1.isdigit():
pin=int(t1);
if 0<pin<=64: m.setdefault(pin, norm(t0));
continue
if t0.isdigit() and isname(t1):
pin=int(t0);
if 0<pin<=64: m.setdefault(pin, norm(t1));
continue
print('size', len(m), 'max', max(m) if m else None)
vals={v.upper() for v in m.values()}; print('GND' in vals, 'VCC' in vals)
print(sorted(m.items())[:8])"

Ran terminal command: exit()

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" -c @'
from pypdf import PdfReader
import re
from pathlib import Path
pdf = Path('.temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf')
r = PdfReader(str(pdf))
text = r.pages[2].extract_text() or ''
tokens = text.split()
print('Pin Functions' in text)
print('Pin' in tokens, 'Functions' in tokens)
start = None
for i in range(len(tokens) - 2):
if tokens[i].lower() == 'pin' and tokens[i + 1].lower().startswith('function'):
start = i
break
if tokens[i].lower() == 'pin' and tokens[i + 1].lower() == 'functions':
start = i
break
print('start', start, tokens[start:start+6] if start is not None else None)

stop = {'pin','pins','pin(s)','no.','no','name','i/o','io','description'}

def norm(s: str) -> str:
s = (s or '').strip().strip(',;:.')
return re.sub(r'\(\d+\)$', '', s)

def isname(tok: str) -> bool:
name = norm(tok)
if not name:
return False
if name.lower() in stop:
return False
if name.upper() in {'NC','GND','VCC','VDD','VSS'}:
return True
if not re.fullmatch(r'[0-9A-Za-z/_-]+', name):
return False
return bool(re.search(r'[A-Za-z]', name))

m = {}
for i in range(start, len(tokens) - 1):
t0 = tokens[i]
t1 = tokens[i + 1]
if isname(t0) and t1.isdigit():
pin = int(t1)
if 0 < pin <= 64:
m.setdefault(pin, norm(t0))
continue
if t0.isdigit() and isname(t1):
pin = int(t0)
if 0 < pin <= 64:
m.setdefault(pin, norm(t1))
continue

print('size', len(m), 'max', max(m) if m else None)
vals = {v.upper() for v in m.values()}
print('has GND/VCC', 'GND' in vals, 'VCC' in vals)
print('head', sorted(m.items())[:10])
'@

パッチを生成中 (93 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74LS240N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download

Awaited terminal completion

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download

最後のターミナル コマンドを取得しました

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" -V

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3

Ran terminal command: Get-Process python -ErrorAction SilentlyContinue | Select-Object -First 10 Id,ProcessName,Path

Ran terminal command: Write-Output "hi"

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3

Awaited terminal completion

バックグラウンド ターミナル出力を確認しました

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 | Out-File -FilePath .temp/sample_gen_probe.txt -Encoding utf8

[](./.temp/sample_gen_probe.txt) の読み取り

パッチを生成中 (37 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 | Out-File -FilePath .temp/sample_gen_probe.txt -Encoding utf8

Awaited terminal completion

[](./.temp/sample_gen_probe.txt) の読み取り

パッチを生成中 (23 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 --force --part 74x240

[](./usage/01_buffers_inverters/74x240/01_basic_function_demo.md) の読み取り

パッチを生成中 (34 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 --force --part 74x240

反復処理を続行しますか?
[object Object]

Made changes.

User: @agent 続行: "反復処理を続行しますか?"

GitHub Copilot: [](./usage/01_buffers_inverters/74x240/01_basic_function_demo.md#82-82) の 82 から 82 行を読み取り

テキスト `データシートURL` (`**/usage/01_buffers_inverters/74x240/01_basic_function_demo.md`) を検索し、結果は 1 件でした

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 --force --part 74x244

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74HC244N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

パッチを生成中 (92 行)、[](./scripts/generate_usage_samples_owned_01_04.py) 内

```

```

Ran terminal command: $p = (Resolve-Path ".temp/datasheet_fetch/generated_samples/TI/SN74HC244N.pdf").Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 --force --part 74x244

テキスト `ピン配置（要一次資料）` (`**/usage/01_buffers_inverters/74x244/01_basic_function_demo.md`) を検索し、結果はありませんでした

テキスト `自動抽出によるピン配置確定ができませんでした` (`**/usage/{01_buffers_inverters,02_nand_and_gates,03_nor_or_gates,04_xor_xnor_gates}/**/01_basic_function_demo.md`) を検索し、結果は 34 件でした

Ran terminal command: & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/generate_usage_samples_owned_01_04.py --download --timeout 3 --force --part 74x34

Ran terminal command: Test-Path .temp/datasheet_fetch/generated_samples/TI/SN74LS34N.pdf; if (Test-Path .temp/datasheet_fetch/generated_samples/TI/SN74LS34N.pdf) { $p=(Resolve-Path .temp/datasheet_fetch/generated_samples/TI/SN74LS34N.pdf).Path; & "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" .temp/debug_pin_extract.py $p }

`**/datasheets/_download/**/74HC07*.PDF` に一致するファイルを検索しました。一致するものはありません

Ran terminal command: $parts = @('74x37','74x38','74x40','74x36','74x23','74x26','74x136','74x265','74x386');
python_exe = "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe";
$parts | ForEach-Object {
$pn = $_
  & $python_exe -c "import json; d=json.load(open('.temp/owned_targets_01_04.json','r',encoding='utf-8')); print('$pn', d['owned_exact_items'].get('$pn'))"
}

チェックされた [](./scripts/generate_usage_samples_owned_01_04.py)、問題は見つかりませんでした

今回のボトルネック（TI系PDFの「Pin Functions」表の形式差）を潰して、ピン表の抽出カバレッジを上げました。

- 変更: generate_usage_samples_owned_01_04.py
  - `relative_to()` 依存をやめてパス表示を堅牢化（デバッグでも落ちない）
  - TIの表形式3パターンに対応（NAME→PIN / PIN→NAME / “NO. NAME”ヘッダのみ）
  - `1 OE` のように分割されたピン名を `1OE` に結合して抽出
  - TI symlink URL を `.temp/.../*.pdf.url.txt` にキャッシュ（再実行のURLプローブを削減）
  - 検証用に `--part 74xNN` を追加（個別再生成できる）
- 検証: 例として 01_basic_function_demo.md と 01_basic_function_demo.md はスタブ→抽出ピン表へ更新できました
- 現状: 「ピン配置（要一次資料）」スタブはまだ34件残っています（多くはPDF未取得/URL不在の可能性があります）

次どう進めますか？

- 全52件をまとめて `--force` 再生成（差分が500行超える可能性が高い）までこちらで実行してOKですか？
  - 実行コマンド: `python generate_usage_samples_owned_01_04.py --download --timeout 3 --force`
- まずは安全に、抽出できる見込みが高いものから個別に潰す（`--part` で指定）方が良ければ、その方針で回します。

Made changes.
