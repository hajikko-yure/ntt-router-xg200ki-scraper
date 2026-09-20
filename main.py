import os
import re
import sys
import csv
import io
import json
import datetime
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def load_env(env_path=".env"):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    env_vars[k] = v
                    os.environ[k] = v

    host = os.environ.get("ROUTER_HOST", "192.168.1.1")
    user = os.environ.get("ROUTER_USER", "user")
    password = os.environ.get("ROUTER_PASSWORD", "")
    return host, user, password

def parse_form_element(cell):
    parts = []
    for el in cell.descendants:
        if el.name == 'input':
            t = el.get('type', 'text').lower()
            if t in ('text', 'password', 'hidden'):
                val = el.get('value', '').strip()
                if val and val not in parts:
                    parts.append(val)
            elif t in ('checkbox', 'radio'):
                parent = el.find_parent('label')
                label = parent.get_text(strip=True) if parent else ""
                state = "[有効]" if el.has_attr('checked') else "[無効]"
                if label:
                    parts.append(f"{state} {label}")
                else:
                    parts.append(state)
        elif el.name == 'select':
            opt = el.find('option', selected=True)
            if opt:
                val = opt.get_text(strip=True)
                if val and val not in parts:
                    parts.append(val)
            else:
                all_opts = [o.get_text(strip=True) for o in el.find_all('option')]
                if len(all_opts) == 1:
                    parts.append(all_opts[0])
        elif el.name == 'textarea':
            val = el.get_text(strip=True)
            if val and val not in parts:
                parts.append(val)
        elif el.name is None:
            text = el.strip()
            if text and text not in parts:
                if el.parent and el.parent.name in ('label', 'option'):
                    continue
                parts.append(text)
    
    res = " ".join(parts).strip()
    res = re.sub(r"\s+", " ", res)
    return res

def parse_page_content(soup):
    page_data = {
        "title": "",
        "sections": []
    }
    
    title_el = soup.find('h1') or soup.find('title')
    if title_el:
        page_data["title"] = title_el.get_text(strip=True)

    for pre in soup.find_all('pre'):
        log_text = pre.get_text().strip()
        if log_text:
            sec_parent = pre.find_parent('div', class_='section')
            sec_title = ""
            if sec_parent:
                h2 = sec_parent.find(['h2', 'h3'])
                if h2:
                    sec_title = h2.get_text(strip=True)
            if not sec_title:
                sec_title = "ログ"
            
            page_data["sections"].append({
                "section_title": sec_title,
                "tables": [],
                "raw_texts": [log_text]
            })
        pre.decompose()

    data_divs = soup.find_all(id=lambda x: x and any(k in x.lower() for k in ['entrydata', 'listdata']))
    for d in data_divs:
        raw_csv = d.get_text(strip=True)
        if raw_csv:
            sec_parent = d.find_parent('div', class_='section') or soup
            headers = []
            target_table = sec_parent.find('table', class_='data')
            if target_table and target_table.find('thead'):
                for tr in target_table.find('thead').find_all('tr'):
                    headers = [parse_form_element(th) for th in tr.find_all(['th', 'td'])]
                    headers = [h for h in headers if h]

            records = [r.strip() for r in raw_csv.split(';') if r.strip()]
            csv_rows = []
            for rec in records:
                try:
                    reader = csv.reader(io.StringIO(rec))
                    row = next(reader, [])
                    if row:
                        csv_rows.append(row)
                except Exception:
                    pass

            if csv_rows:
                sec_title_el = sec_parent.find(['h2', 'h3'])
                sec_title = sec_title_el.get_text(strip=True) if sec_title_el else "一覧"
                page_data["sections"].append({
                    "section_title": sec_title,
                    "tables": [{
                        "headers": headers,
                        "rows": csv_rows
                    }],
                    "raw_texts": []
                })
        d.decompose()

    sections = soup.find_all('div', class_='section')
    if not sections and soup.body:
        sections = [soup.body]

    for sec in sections:
        sec_title_el = sec.find(['h2', 'h3'])
        sec_title = sec_title_el.get_text(strip=True) if sec_title_el else ""
        
        tables_data = []
        for table in sec.find_all('table'):
            if 'data' in table.get('class', []) and not table.find('tbody', id=lambda x: x and 'container' in x.lower()):
                continue

            table_rows = []
            headers = []
            
            thead = table.find('thead')
            if thead:
                for tr in thead.find_all('tr'):
                    headers = [parse_form_element(th) for th in tr.find_all(['th', 'td'])]
            
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                if tr.has_attr('hidden') or tr.get('style', '') == 'display: none;':
                    continue
                row_cells = [parse_form_element(c) for c in tr.find_all(['th', 'td'])]
                if any(row_cells):
                    table_rows.append(row_cells)
            
            if table_rows:
                tables_data.append({
                    "headers": headers,
                    "rows": table_rows
                })
        
        textareas = sec.find_all('textarea')
        raw_texts = [ta.get_text(strip=True) for ta in textareas if ta.get_text(strip=True)]
        
        if tables_data or raw_texts:
            page_data["sections"].append({
                "section_title": sec_title,
                "tables": tables_data,
                "raw_texts": raw_texts
            })

    return page_data

def generate_text_report(data):
    lines = []
    lines.append(f"# {data['model']} 設定・状態レポート")
    lines.append(f"- 取得日時: {data['timestamp']}")
    lines.append(f"- ホスト: {data['host']}")
    lines.append(f"- 機種: {data['model']}")
    lines.append(f"- ファームウェア: {data['firmware']}")
    lines.append("")

    current_cat = None
    for page in data["pages"]:
        cat = page.get("menu_category") or "一般設定"
        if cat != current_cat:
            current_cat = cat
            lines.append(f"\n# {current_cat}\n")
        
        page_title = page.get("title") or page.get("menu_name")
        lines.append(f"## {page_title} ({page['menu_name']})")
        lines.append(f"URL: {page['url']}\n")
        
        for sec in page.get("sections", []):
            if sec.get("section_title"):
                lines.append(f"### {sec['section_title']}")
            
            for tbl in sec.get("tables", []):
                rows = tbl.get("rows", [])
                if not rows:
                    continue
                
                is_kv = all(len(r) == 2 for r in rows) and not tbl.get("headers")
                if is_kv:
                    for r in rows:
                        k = r[0].strip()
                        v = r[1].strip() if len(r) > 1 else ""
                        lines.append(f"- {k}: {v}")
                else:
                    headers = tbl.get("headers")
                    table_data_rows = rows
                    if not headers and rows:
                        headers = [f"項目{i+1}" for i in range(len(rows[0]))]

                    if headers:
                        max_cols = max(len(headers), max((len(r) for r in table_data_rows), default=0))
                        if len(headers) < max_cols:
                            headers += [f"列{i+1}" for i in range(len(headers), max_cols)]
                        
                        lines.append("| " + " | ".join(headers) + " |")
                        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                        for r in table_data_rows:
                            padded = r + [""] * (len(headers) - len(r))
                            lines.append("| " + " | ".join(padded[:len(headers)]) + " |")
                lines.append("")
            
            for raw_text in sec.get("raw_texts", []):
                lines.append("```")
                lines.append(raw_text)
                lines.append("```\n")

    return "\n".join(lines)

def main():
    host, user, password = load_env()
    print(f"Connecting to http://{host}/ ({user})...")
    
    session = requests.Session()
    session.auth = HTTPBasicAuth(user, password)
    base_url = f"http://{host}"
    
    menu_url = f"{base_url}/cgi-bin/getMenu.cgi"
    resp = session.get(menu_url, timeout=10)
    resp.encoding = "utf-8"
    
    menu_soup = BeautifulSoup(resp.text, 'html.parser')
    
    model_name = "XG-200KI"
    fw_ver = ""
    case_el = menu_soup.find(class_="case_name")
    if case_el:
        model_name = case_el.get_text(strip=True)
    fw_el = menu_soup.find(class_="fwnum")
    if fw_el:
        fw_ver = fw_el.get_text(strip=True)
        
    print(f"Device: {model_name} (Firmware: {fw_ver})")
    
    exclude_keys = [
        "maintenance_password",
        "maintenance_initialize",
        "maintenance_reboot",
        "maintenance_ping",
        "maintenance_upnp_clear",
        "maintenance_config"
    ]
    
    targets = []
    for li in menu_soup.find_all('li'):
        a = li.find('a', href=True)
        if a:
            href = a['href']
            text = a.get_text(strip=True)
            if any(k in href for k in exclude_keys):
                continue
            
            category = ""
            parent_li = li.find_parent('li')
            if parent_li:
                cat_a = parent_li.find('a', class_='menu-node')
                if cat_a:
                    category = cat_a.get_text(strip=True)
            
            if not any(t['href'] == href for t in targets):
                targets.append({
                    "category": category,
                    "name": text,
                    "href": href
                })
                
    print(f"Found {len(targets)} pages.")
    
    collected_data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model_name,
        "firmware": fw_ver,
        "host": host,
        "pages": []
    }
    
    for idx, item in enumerate(targets, 1):
        url = f"{base_url}{item['href']}" if item['href'].startswith('/') else f"{base_url}/{item['href']}"
        cat_disp = f"[{item['category']}] " if item['category'] else ""
        print(f"[{idx}/{len(targets)}] Fetching {cat_disp}{item['name']}...")
        try:
            r = session.get(url, timeout=10)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, 'html.parser')
            parsed = parse_page_content(soup)
            parsed["menu_category"] = item["category"]
            parsed["menu_name"] = item["name"]
            parsed["url"] = url
            collected_data["pages"].append(parsed)
        except Exception as e:
            print(f"  Error ({url}): {e}")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    report_text = generate_text_report(collected_data)
    
    txt_file = os.path.join(output_dir, "router_settings_report.txt")
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"Saved: {txt_file}")

    md_file = os.path.join(output_dir, "router_settings_report.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"Saved: {md_file}")

    json_file = os.path.join(output_dir, "router_settings.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(collected_data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {json_file}")

if __name__ == "__main__":
    main()
