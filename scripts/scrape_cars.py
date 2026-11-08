#!/usr/bin/env python3
"""
Scraper Multi-Fonte de Fichas Técnicas e Fotos de Carros:
  1. Canal VE      (https://canalve.com.br/ficha-tecnica/)
  2. Carros na Web (https://www.carrosnaweb.com.br/catalogo.asp)
  3. iCarros       (https://www.icarros.com.br/catalogo/)

Extrai Marca, Modelo, Ano, Motorização, Carroceria, Potência, Torque, Autonomia/Consumo,
Velocidade Máxima, Tração, Peso e Porta-malas, e baixa as fotos localmente em data/images/.
"""

import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
CARS_JSON_PATH = os.path.join(DATA_DIR, "cars.json")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def fetch_url(url: str, binary: bool = False, timeout: int = 20, default_charset: str = "utf-8", referer: str = ""):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if binary:
            return data
        charset = resp.headers.get_content_charset() or default_charset
        return data.decode(charset, errors="ignore")


def download_image(image_url: str, prefix_id: str | int, slug: str, referer: str = "") -> str | None:
    if not image_url:
        return None
    ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"
    safe_slug = re.sub(r"[^a-z0-9\-]+", "-", slug.lower()).strip("-")[:60] or str(prefix_id)

    # Reutiliza caso já exista imagem baixada para o mesmo modelo
    if os.path.exists(IMAGES_DIR):
        for existing in os.listdir(IMAGES_DIR):
            if existing.endswith((f"-{safe_slug}.jpg", f"-{safe_slug}.webp", f"-{safe_slug}.png", f"-{safe_slug}.jpeg")):
                full_ex = os.path.join(IMAGES_DIR, existing)
                if os.path.getsize(full_ex) >= 1000:
                    return f"data/images/{existing}"

    img_filename = f"{prefix_id}-{safe_slug}{ext}"
    img_local_path = os.path.join(IMAGES_DIR, img_filename)

    if not os.path.exists(img_local_path) or os.path.getsize(img_local_path) < 1000:
        try:
            parsed = urllib.parse.urlsplit(image_url)
            safe_path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:@!$&'()*+,;=-._~")
            safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, safe_path, parsed.query, parsed.fragment))
            img_bytes = fetch_url(safe_url, binary=True, referer=referer)
            if not img_bytes or len(img_bytes) < 1000:
                return None
            with open(img_local_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"   [ERRO IMG] Falha ao baixar {image_url}: {e}")
            return None

    return f"data/images/{img_filename}"


def infer_body_type(name: str, current_body: str = "", height_mm: int = 0, trunk_l: int = 0) -> str:
    bt = (current_body or "").strip()
    if bt.lower() in ["hatchback", "hatch"]:
        return "Hatch"
    if bt and bt not in ["N/I", "N/D"]:
        return bt

    lname = name.lower()
    if any(w in lname for w in ["saveiro", "strada", "toro", "hilux", "ranger", "s10", "montana", "oroch", "amarok", "maverick", "titano", "rampage", "ram ", "f-150", "gladiator", "l200", "triton", "frontier"]):
        return "Picape"
    if any(w in lname for w in ["sedan", "sedã", "virtus", "cronos", "corolla ", "civic", "city", "sentra", "versa", "cerato", "jetta", "accord", "camry", "arrizo", "king", "seal ", "a3 sedan", "série 3", "320i", "330e", "classe c", "c200", "es 500", "es300"]):
        return "Sedã"
    if any(w in lname for w in ["polo", "onix", "hb20", "argo", "mobi", "kwid", "208", "c3 ", "dolphin", "ora 03", "golf", "yaris hatch", "i20", "mg4", "ex2"]):
        if "sedan" not in lname and "plus" not in lname:
            return "Hatch"
    if any(w in lname for w in ["suv", "commander", "compass", "renegade", "pulse", "fastback", "t-cross", "nivus", "taos", "tiguan", "creta", "tracker", "equinox", "trailblazer", "blazer", "kicks", "kardian", "duster", "hr-v", "zr-v", "cr-v", "corolla cross", "sw4", "rav4", "tiggo", "haval", "tank", "wey", "song", "yuan", "tan", "atto", "sealion", "omoda", "jaecoo", "g700", "eclipse cross", "outlander", "pajero", "2008", "3008", "c4 cactus", "aircross", "basalt", "tera", "id.4", "q3", "q5", "q6", "x1", "x3", "x5", "x6", "xc40", "xc60", "xc90", "ex30", "ec40", "c40", "cayenne", "macan", "niro", "sportage", "kona", "ioniq", "ex5"]):
        return "SUV"
    if any(w in lname for w in ["fiorino", "partner", "kangoo", "berlingo", "jumpy", "expert", "scudo", "ducato", "master", "sprinter", "transit", "daily", "delivery"]):
        return "Utilitário"
    if height_mm >= 1620:
        return "SUV"
    if trunk_l >= 440:
        return "Sedã"
    return "Hatch"


def normalize_brand_and_name(brand: str, raw_name: str, link: str = "") -> tuple[str, str]:
    brand = (brand or "").strip()
    name = (raw_name or "").replace("\xa0", " ").strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"^Sem Fabricante\s+", "", name, flags=re.I).strip()

    if not brand or brand.lower() in ["sem fabricante", "n/i"]:
        m_brand = re.search(r"/ficha-tecnica/([^/]+)/", link)
        if m_brand and m_brand.group(1).lower() not in ["sem-fabricante"]:
            brand = m_brand.group(1).replace("-", " ").title()

    lower_name = name.lower()
    if not brand or brand.lower() in ["sem fabricante", "n/i"]:
        if "tiggo" in lower_name or "icar" in lower_name or "arrizo" in lower_name:
            brand = "Caoa Chery"
        elif "peugeot" in lower_name or "e-2008" in lower_name or "e-208" in lower_name:
            brand = "Peugeot"
        elif "byd" in lower_name or "dolphin" in lower_name or "yuan" in lower_name or "song" in lower_name:
            brand = "BYD"

    brand_map = {
        "vw": "Volkswagen",
        "volkswagen": "Volkswagen",
        "gm": "Chevrolet",
        "chevrolet": "Chevrolet",
        "byd": "BYD",
        "gwm": "GWM",
        "bmw": "BMW",
        "kia": "KIA",
        "jac": "JAC",
        "gac": "GAC",
        "mg": "MG Motors",
        "mg motors": "MG Motors",
        "caoa chery": "Caoa Chery",
        "caoa-chery": "Caoa Chery",
        "citroen": "Citroën",
        "citroën": "Citroën",
        "mercedes-benz": "Mercedes-Benz",
        "land-rover": "Land Rover",
    }
    if brand.lower() in brand_map:
        brand = brand_map[brand.lower()]

    brand_tokens = [t.lower() for t in re.split(r"[\s\-]+", brand) if t]
    first_word = name.split()[0].lower() if name else ""
    if brand and first_word not in brand_tokens and not any(first_word.startswith(bt) for bt in brand_tokens):
        name = f"{brand} {name}"

    return brand or "N/I", name


def normalize_specs(powertrain: str, body_type: str, name: str, sections: dict | None = None) -> tuple[str, str]:
    pt = (powertrain or "Flex").strip()
    bt = infer_body_type(name, body_type)

    has_combustao = "Motor Combustão" in (sections or {})
    motor_el = (sections or {}).get("Motor Elétrico", {})
    if pt.lower() == "elétrico" and has_combustao:
        lname = (name or "").lower()
        if any(k in lname for k in ["phev", "dm", "t8", "30e", "e-hybrid"]) or motor_el.get("Potência de recarga"):
            pt = "Híbrido Plug-in"
        else:
            pt = "Híbrido"
    return pt, bt


# =====================================================================
# FONTE 1: CANAL VE (https://canalve.com.br/ficha-tecnica/)
# =====================================================================
def get_best_image_from_srcset(img_tag) -> str:
    if not img_tag:
        return ""
    srcset = img_tag.get("srcset", "")
    best_url = img_tag.get("src", "") or img_tag.get("data-src", "")
    best_width = 0
    if srcset:
        for part in srcset.split(","):
            tokens = part.strip().split()
            if len(tokens) >= 2 and tokens[1].endswith("w"):
                try:
                    w = int(tokens[1][:-1])
                    if w > best_width:
                        best_width = w
                        best_url = tokens[0]
                except ValueError:
                    pass
    return best_url


def parse_canalve_detail(item_meta: dict, fabricantes_map: dict) -> dict | None:
    post_id = item_meta["id"]
    slug = item_meta["slug"]
    link = item_meta["link"]

    fab_ids = item_meta.get("fabricante") or []
    brand_from_tax = fabricantes_map.get(fab_ids[0], "") if fab_ids else ""

    try:
        html = fetch_url(link)
    except Exception as e:
        print(f"   [ERRO CanalVE] Falha ao abrir {link}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1.vehicle-title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else item_meta.get("title", {}).get("rendered", slug)
    title = re.sub(r"^Tudo sobre (?:o |a )?", "", title, flags=re.I)
    title = re.sub(r":\s*Ficha técnica.*$", "", title, flags=re.I).strip()

    brand_el = soup.select_one(".vehicle-header__brand")
    brand = brand_el.get_text(strip=True) if brand_el else brand_from_tax

    featured_img = soup.select_one(".vehicle-featured-image img.featured-img") or soup.select_one("img.wp-post-image")
    image_url = get_best_image_from_srcset(featured_img)
    if not image_url:
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
    if not image_url:
        return None

    specs = {}
    sections = {}
    for sec in soup.select("section.spec-card"):
        h2 = sec.find("h2")
        sec_title = h2.get_text(strip=True) if h2 else "Geral"
        sec_dict = {}
        for spec_item in sec.select(".spec-item"):
            dt = spec_item.find("dt")
            dd = spec_item.find("dd")
            if dt and dd:
                k = dt.get_text(strip=True).rstrip(":")
                v = dd.get_text(" ", strip=True)
                if k and v:
                    sec_dict[k] = v
                    if k not in specs:
                        specs[k] = v
        if sec_dict:
            sections[sec_title] = sec_dict

    modelo_ficha = specs.get("Fabricante/Modelo") or title
    ano = specs.get("Ano") or ""
    if not ano:
        m_yr = re.search(r"\b(202[0-9])\b", f"{title} {modelo_ficha}")
        if m_yr:
            ano = m_yr.group(1)

    raw_name = modelo_ficha if modelo_ficha else title
    brand, display_name = normalize_brand_and_name(brand, raw_name, link)

    motorizacao_raw = specs.get("Motorização") or "Elétrico"
    carroceria_raw = specs.get("Carroceria") or "N/I"
    motorizacao, carroceria = normalize_specs(motorizacao_raw, carroceria_raw, display_name, sections)

    lugares = specs.get("Lugares") or "5"
    tracao = specs.get("Tração") or "N/I"
    cambio = specs.get("Câmbio") or "Automático"
    peso = specs.get("Peso") or "N/I"
    porta_malas = specs.get("Porta-malas") or "N/I"

    motor_eletrico = sections.get("Motor Elétrico", {})
    motor_combustao = sections.get("Motor Combustão", {})

    potencia = motor_eletrico.get("Potência") or motor_combustao.get("Potência") or specs.get("Potência") or "N/I"
    torque = motor_eletrico.get("Torque") or motor_combustao.get("Torque") or specs.get("Torque") or "N/I"
    autonomia = motor_eletrico.get("Autonomia") or specs.get("Autonomia") or "N/I"
    bateria = motor_eletrico.get("Capacidade") or specs.get("Capacidade") or "N/I"
    vel_max = motor_eletrico.get("Velocidade Máxima") or motor_combustao.get("Velocidade Máxima") or specs.get("Velocidade Máxima") or "N/I"

    clean_slug = re.sub(r"^tudo-sobre-?", "", slug) or str(post_id)
    local_img = download_image(image_url, post_id, clean_slug, referer="https://canalve.com.br/")
    if not local_img:
        return None

    return {
        "id": int(post_id),
        "slug": clean_slug,
        "name": display_name,
        "title": title,
        "brand": brand,
        "year": ano or "2025",
        "powertrain": motorizacao,
        "bodyType": carroceria,
        "seats": lugares,
        "traction": tracao,
        "transmission": cambio,
        "power": potencia,
        "torque": torque,
        "range": autonomia,
        "battery": bateria,
        "topSpeed": vel_max,
        "weight": peso,
        "trunk": porta_malas,
        "image": local_img,
        "sourceImageUrl": image_url,
        "sourceUrl": link,
        "sourceSite": "Canal VE",
        "sections": sections,
    }


def scrape_canalve() -> list[dict]:
    print("\n[1/3] Escaneando Canal VE (https://canalve.com.br/ficha-tecnica/)...")
    fabricantes_map = {}
    try:
        fab_data = json.loads(fetch_url("https://canalve.com.br/wp-json/wp/v2/fabricante?per_page=100"))
        for f in fab_data:
            fabricantes_map[f["id"]] = f["name"]
    except Exception as e:
        print(f"   [AVISO] Falha ao buscar fabricantes do Canal VE: {e}")

    all_items = []
    page = 1
    while True:
        url = f"https://canalve.com.br/wp-json/wp/v2/veiculo?per_page=100&page={page}"
        try:
            batch = json.loads(fetch_url(url))
            if not batch:
                break
            all_items.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        except Exception:
            break

    print(f"   -> {len(all_items)} veículos encontrados no Canal VE.")
    cars = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(parse_canalve_detail, item, fabricantes_map): item for item in all_items}
        for idx, future in enumerate(as_completed(futures), 1):
            res = future.result()
            if res:
                cars.append(res)
                print(f"   [CanalVE {idx}/{len(all_items)}] OK: {res['name']} ({res['brand']} • {res['year']})")
    return cars


# =====================================================================
# FONTE 2: CARROS NA WEB (https://www.carrosnaweb.com.br/catalogo.asp)
# =====================================================================
def format_cnw_powertrain(propulsao: str, combustivel: str) -> str:
    p = (propulsao or "").lower()
    c = (combustivel or "").lower()
    if "elétrico" in p or "eletricidade" in c:
        return "Elétrico"
    if "plug-in" in p:
        return "Híbrido Plug-in"
    if "híbrido" in p or "hibrido" in p:
        return "Híbrido"
    if "diesel" in c:
        return "Diesel"
    if "álcool" in c or "alcool" in c or "flex" in c:
        return "Combustão (Flex)"
    if "gasolina" in c:
        return "Combustão (Gasolina)"
    return propulsao or combustivel or "Combustão"


def scrape_carrosnaweb(max_pages: int = 6) -> list[dict]:
    print(f"\n[2/3] Escaneando Carros na Web (https://www.carrosnaweb.com.br/catalogo.asp - {max_pages} páginas)...")
    catalog_entries = []
    seen_codes = set()
    seen_thumbs = set()

    for page in range(1, max_pages + 1):
        url = f"https://www.carrosnaweb.com.br/catalogo.asp?curpage={page}"
        try:
            html = fetch_url(url, default_charset="latin-1", referer="https://www.carrosnaweb.com.br/catalogo.asp")
        except Exception as e:
            print(f"   [AVISO] Falha na página {page} do Carros na Web: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            m = re.search(r"fichadetalhe\.asp\?codigo=(\d+)", a["href"])
            if not m:
                continue
            code = m.group(1)
            if code in seen_codes:
                continue
            img = a.find("img")
            if not img or not img.get("src"):
                continue
            thumb_src = img["src"].replace("\\", "/").lstrip("/")
            if "semfoto" in thumb_src.lower():
                continue
            full_img_url = "https://www.carrosnaweb.com.br/" + thumb_src.replace("/thumb/", "/")
            if full_img_url in seen_thumbs:
                continue
            seen_codes.add(code)
            seen_thumbs.add(full_img_url)
            catalog_entries.append({"code": code, "image_url": full_img_url})

    print(f"   -> {len(catalog_entries)} veículos únicos com foto coletados no Carros na Web. Extraindo fichas técnicas em lote...")

    cars = []
    # Processa em lotes de 4 via resultcompara.asp?modelos=ID1-ID2-ID3-ID4
    for i in range(0, len(catalog_entries), 4):
        batch = catalog_entries[i : i + 4]
        batch_codes = [x["code"] for x in batch]
        while len(batch_codes) < 4:
            batch_codes.append(catalog_entries[0]["code"])

        comp_url = f"https://www.carrosnaweb.com.br/resultcompara.asp?modelos={'-'.join(batch_codes)}"
        try:
            comp_html = fetch_url(comp_url, default_charset="latin-1", referer="https://www.carrosnaweb.com.br/catalogo.asp")
        except Exception as e:
            print(f"   [AVISO] Erro ao consultar lote {batch_codes}: {e}")
            continue

        comp_soup = BeautifulSoup(comp_html, "html.parser")
        rows_by_label = {}
        expected_cols = len(batch_codes) + 1
        for tr in comp_soup.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) == expected_cols:
                lbl = tds[0].get_text(" ", strip=True)
                vals = [td.get_text(" ", strip=True) for td in tds[1:]]
                if lbl and lbl not in rows_by_label:
                    rows_by_label[lbl] = vals

        def get_col(label: str, idx: int) -> str:
            arr = rows_by_label.get(label)
            if not arr or idx >= len(arr):
                return ""
            return arr[idx].strip()

        for col_idx, item in enumerate(batch):
            code = item["code"]
            fab = get_col("Fabricante", col_idx)
            mod = get_col("Modelo", col_idx)
            if not fab or not mod:
                continue

            ano_raw = get_col("Ano", col_idx)
            ano = ano_raw.split()[0] if ano_raw else "2026"
            prop = get_col("Propulsão", col_idx)
            comb = get_col("Combustível", col_idx)
            cfg = get_col("Configuração", col_idx)
            lug = get_col("Lugares", col_idx) or "5"
            pm = get_col("Porta-malas", col_idx).replace("litros", "L") or "N/I"
            tracao = get_col("Tração", col_idx) or "Dianteira"
            cambio = get_col("Câmbio", col_idx) or "Automático"
            vmax = get_col("Velocidade máxima", col_idx) or "N/I"
            torque_str = get_col("Torque máximo", col_idx) or get_col("Torque motor elétrico", col_idx) or "N/I"
            peso_torque_str = get_col("Peso/torque", col_idx)
            peso_pot_str = get_col("Peso/potência", col_idx)
            pot_el = get_col("Potência motor elétrico", col_idx)
            bateria = get_col("Capacidade da bateria", col_idx) or "N/I"
            autonomia = (
                get_col("Autonomia elétrica", col_idx)
                or get_col("Autonomia rodoviária", col_idx)
                or get_col("Consumo urbano", col_idx)
                or "N/I"
            )

            peso_calc = "N/I"
            pot_calc = "N/I"
            try:
                m_tq = re.search(r"([\d,]+)", torque_str)
                m_ptq = re.search(r"([\d,]+)", peso_torque_str)
                if m_tq and m_ptq:
                    tq_val = float(m_tq.group(1).replace(",", "."))
                    ptq_val = float(m_ptq.group(1).replace(",", "."))
                    peso_kg = round(tq_val * ptq_val)
                    peso_calc = f"{peso_kg} Kg"
                    m_ppot = re.search(r"([\d,]+)", peso_pot_str)
                    if m_ppot:
                        ppot_val = float(m_ppot.group(1).replace(",", "."))
                        pot_cv = round(peso_kg / ppot_val)
                        pot_calc = f"{pot_cv} cv"
            except Exception:
                pass

            if pot_el and pot_calc == "N/I":
                pot_calc = re.sub(r"\s*\(.*?\)", "", pot_el).strip()

            brand, display_name = normalize_brand_and_name(fab, f"{fab} {mod}")
            powertrain = format_cnw_powertrain(prop, comb)
            _, body_type = normalize_specs(powertrain, cfg, display_name)

            car_id = 100000 + int(code)
            slug = f"cnw-{code}-{brand}-{mod}"
            local_img = download_image(
                item["image_url"],
                f"cnw-{code}",
                f"{brand}-{mod}",
                referer="https://www.carrosnaweb.com.br/catalogo.asp",
            )
            if not local_img:
                continue

            car_obj = {
                "id": car_id,
                "slug": re.sub(r"[^a-z0-9\-]+", "-", slug.lower()).strip("-"),
                "name": display_name,
                "title": display_name,
                "brand": brand,
                "year": ano,
                "powertrain": powertrain,
                "bodyType": body_type,
                "seats": lug,
                "traction": tracao,
                "transmission": cambio,
                "power": pot_calc,
                "torque": re.sub(r"\s*\(.*?\)", "", torque_str).strip() or "N/I",
                "range": autonomia,
                "battery": bateria,
                "topSpeed": vmax,
                "weight": peso_calc,
                "trunk": pm,
                "image": local_img,
                "sourceImageUrl": item["image_url"],
                "sourceUrl": f"https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo={code}",
                "sourceSite": "Carros na Web",
                "sections": {},
            }
            cars.append(car_obj)
            print(f"   [CarrosNaWeb {len(cars)}] OK: {display_name} ({brand} • {ano} • {powertrain} • {body_type})")

    return cars


# =====================================================================
# FONTE 3: ICARROS (https://www.icarros.com.br/catalogo/)
# =====================================================================
ICARROS_TARGET_BRANDS = [
    "fiat",
    "volkswagen",
    "chevrolet",
    "toyota",
    "hyundai",
    "jeep",
    "renault",
    "honda",
    "nissan",
    "peugeot",
    "citroen",
    "ford",
    "mitsubishi",
    "bmw",
    "audi",
    "kia",
]


def extract_first_number(text: str, suffix: str = "") -> str:
    if not text or "N/D" in text:
        return "N/I"
    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    if not nums:
        return "N/I"
    val = nums[0].replace(".", ",")
    return f"{val}{suffix}"


def clean_icarros_model_title(raw_h1: str, brand_slug: str) -> tuple[str, str, str]:
    """Retorna (brand_name, clean_display_name, year)."""
    txt = (raw_h1 or "").strip()
    m_yr = re.findall(r"\b(20[12][0-9])\b", txt)
    year = m_yr[-1] if m_yr else "2026"

    # Remove sufixos repetitivos de câmbio/ano do título longo do iCarros
    clean = re.sub(r"\b20[12][0-9]\b", "", txt)
    clean = re.sub(r"\b(Auto|Aut|cvt|mhev|bev|phev|hev|\(Aut\))\b", "", clean, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip(" -")

    # Mantém Marca + Modelo + Versão concisa (até 5 palavras)
    words = clean.split()
    if len(words) > 5:
        clean = " ".join(words[:5])

    brand_guess = brand_slug.replace("-", " ").title()
    brand, display_name = normalize_brand_and_name(brand_guess, clean)
    return brand, display_name, year


def parse_icarros_model_page(url_Info: tuple[str, str, str]) -> dict | None:
    rel_url, brand_slug, fallback_img = url_Info
    full_url = urllib.parse.urljoin("https://www.icarros.com.br", rel_url)

    try:
        html = fetch_url(full_url, default_charset="utf-8", referer="https://www.icarros.com.br/catalogo/")
    except Exception as e:
        print(f"   [AVISO iCarros] Erro ao abrir {full_url}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    raw_title = h1.get_text(" ", strip=True) if h1 else ""
    if not raw_title and soup.title:
        raw_title = soup.title.get_text(" ", strip=True).split(" - ")[0]
    if not raw_title:
        return None

    brand, display_name, year = clean_icarros_model_title(raw_title, brand_slug)

    # Imagem da galeria (com fallback entre imagens do slider e imagem do card)
    slider_imgs = [
        img.get("src") or img.get("data-src")
        for img in soup.select("img.slider-image-item")
        if (img.get("src") or img.get("data-src"))
    ]
    candidate_imgs = []
    for u in slider_imgs[:3] + ([fallback_img] if fallback_img else []):
        if not u or "gif_transparente" in u:
            continue
        if u.endswith(".webp"):
            candidate_imgs.append(u[:-5] + (".png" if "imgmodelo" in u else ".jpg"))
        candidate_imgs.append(u)
    if not candidate_imgs:
        return None

    # Extrair especificações de .technical-sheet-item
    specs = {}
    for item in soup.select(".technical-sheet-item"):
        spans = [s.get_text(" ", strip=True) for s in item.find_all("span") if s.get_text(strip=True)]
        if len(spans) >= 2:
            k = spans[0]
            v = spans[-1]
            if k not in specs:
                specs[k] = v

    comb_raw = (specs.get("Combustível") or "").lower()
    raw_lower = raw_title.lower()
    if "bev" in raw_lower or "elétrico" in comb_raw or "eletrico" in comb_raw:
        powertrain = "Elétrico"
    elif "phev" in raw_lower:
        powertrain = "Híbrido Plug-in"
    elif "mhev" in raw_lower or "hybrid" in raw_lower or "híbrido" in comb_raw:
        powertrain = "Híbrido"
    elif "diesel" in comb_raw:
        powertrain = "Diesel"
    elif "álcool" in comb_raw and "gasolina" in comb_raw:
        powertrain = "Combustão (Flex)"
    elif "gasolina" in comb_raw:
        powertrain = "Combustão (Gasolina)"
    else:
        powertrain = "Combustão (Flex)"

    altura_str = specs.get("Altura (mm)", "0")
    porta_malas_str = specs.get("Porta-malas (L)", "0")
    try:
        altura_mm = int(re.findall(r"\d+", altura_str)[0])
    except Exception:
        altura_mm = 0
    try:
        trunk_l = int(re.findall(r"\d+", porta_malas_str)[0])
    except Exception:
        trunk_l = 0

    body_type = infer_body_type(display_name, "", altura_mm, trunk_l)
    potencia = extract_first_number(specs.get("Potência (cv)", ""), " cv")
    torque = extract_first_number(specs.get("Torque (kgf.m)", ""), " kgfm")
    vel_max = extract_first_number(specs.get("Velocidade max. (km/h)", ""), " Km/h")
    consumo_cid = extract_first_number(specs.get("Consumo cidade (km/l)", "") or specs.get("Consumo cidade (km/litro)", ""), " km/l")
    peso = extract_first_number(specs.get("Peso (kg)", ""), " Kg")
    porta_malas = f"{trunk_l} L" if trunk_l > 0 else "N/I"
    lugares = extract_first_number(specs.get("Ocupantes", ""), "")
    if lugares == "N/I":
        lugares = "5"
    cambio_raw = specs.get("Câmbio") or "Automático"
    cambio = "Manual" if "manual" in cambio_raw.lower() and "autom" not in cambio_raw.lower() else "Automático"
    tracao_raw = specs.get("Tração") or ""
    tracao = tracao_raw.capitalize() if tracao_raw and tracao_raw != "N/D" else "Dianteira"

    # Gera ID numérico determinístico a partir do caminho da URL
    import zlib
    url_hash = (zlib.crc32(rel_url.encode("utf-8")) & 0xFFFFFFFF) % 80000 + 200000
    slug_part = rel_url.rstrip("/").split("/")[-1]
    local_img = None
    image_url = ""
    for cand_url in candidate_imgs:
        local_img = download_image(
            cand_url,
            f"ic-{url_hash}",
            f"{brand_slug}-{slug_part}",
            referer="https://www.icarros.com.br/catalogo/",
        )
        if local_img:
            image_url = cand_url
            break
    if not local_img:
        return None

    return {
        "id": url_hash,
        "slug": f"ic-{brand_slug}-{slug_part}"[:60],
        "name": display_name,
        "title": raw_title,
        "brand": brand,
        "year": year,
        "powertrain": powertrain,
        "bodyType": body_type,
        "seats": lugares,
        "traction": tracao,
        "transmission": cambio,
        "power": potencia,
        "torque": torque,
        "range": consumo_cid,
        "battery": "N/I",
        "topSpeed": vel_max,
        "weight": peso,
        "trunk": porta_malas,
        "image": local_img,
        "sourceImageUrl": image_url,
        "sourceUrl": full_url,
        "sourceSite": "iCarros",
        "sections": {},
    }


def scrape_icarros(max_models: int = 55) -> list[dict]:
    print(f"\n[3/3] Escaneando iCarros (https://www.icarros.com.br/catalogo/ - até {max_models} modelos)...")
    model_targets = []
    seen_paths = set()

    # 1. Coleta os lançamentos da página principal do catálogo
    try:
        home_html = fetch_url("https://www.icarros.com.br/catalogo/")
        soup_home = BeautifulSoup(home_html, "html.parser")
        for a in soup_home.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/catalogo/marcas/") and href not in seen_paths:
                parts = href.strip("/").split("/")
                if len(parts) >= 4:
                    seen_paths.add(href)
                    model_targets.append((href, parts[2], ""))
    except Exception as e:
        print(f"   [AVISO] Erro na home do catálogo iCarros: {e}")

    # 2. Navega pelas marcas principais para coletar modelos variados
    for brand_slug in ICARROS_TARGET_BRANDS:
        if len(model_targets) >= max_models:
            break
        brand_url = f"https://www.icarros.com.br/catalogo/marcas/{brand_slug}"
        try:
            b_html = fetch_url(brand_url, referer="https://www.icarros.com.br/catalogo/")
            b_soup = BeautifulSoup(b_html, "html.parser")
            for a in b_soup.select("a.complete-ad-card"):
                href = a.get("href", "")
                if not href or href in seen_paths:
                    continue
                if any(skip in href for skip in ["/delivery", "/ducato", "/scudo", "/fiorino", "/master", "/sprinter", "/daily", "/transit"]):
                    continue
                img_el = a.select_one(".card-image img")
                fallback_img = ""
                if img_el:
                    fallback_img = img_el.get("data-src") or img_el.get("src") or ""
                seen_paths.add(href)
                model_targets.append((href, brand_slug, fallback_img))
                if len(model_targets) >= max_models:
                    break
        except Exception as e:
            print(f"   [AVISO] Erro na marca {brand_slug} do iCarros: {e}")

    print(f"   -> {len(model_targets)} páginas de modelos selecionadas no iCarros. Extraindo fichas e fotos...")
    cars = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(parse_icarros_model_page, t): t for t in model_targets}
        for idx, future in enumerate(as_completed(futures), 1):
            res = future.result()
            if res:
                cars.append(res)
                print(f"   [iCarros {len(cars)}/{len(model_targets)}] OK: {res['name']} ({res['brand']} • {res['year']} • {res['bodyType']})")

    return cars


# =====================================================================
# CONSOLIDAÇÃO E DEDUPLICAÇÃO
# =====================================================================
def deduplicate_catalog(cars: list[dict]) -> list[dict]:
    """
    Evita duplicatas exatas de nome ou de imagem, preservando a ordem (Canal VE -> Carros na Web -> iCarros).
    """
    unique = []
    seen_names = set()
    seen_imgs = set()

    for c in cars:
        norm_name = re.sub(r"[^a-z0-9]+", "", c["name"].lower())
        img_key = c.get("sourceImageUrl") or c.get("image")
        if norm_name in seen_names or img_key in seen_imgs:
            continue
        seen_names.add(norm_name)
        seen_imgs.add(img_key)
        unique.append(c)

    return unique


CNW_CACHED_FALLBACK = [
    {"id": 149061, "slug": "cnw-49061-chevrolet-onix-sedan-eco-1-0-turbo-at", "name": "Chevrolet Onix Sedan Eco 1.0 Turbo AT", "title": "Chevrolet Onix Sedan Eco 1.0 Turbo AT", "brand": "Chevrolet", "year": "2027", "powertrain": "Combustão (Flex)", "bodyType": "Sedã", "seats": "5", "traction": "Dianteira", "transmission": "Automático", "power": "121 cv", "torque": "18,9 kgfm", "range": "488 km", "battery": "N/I", "topSpeed": "180 km/h", "weight": "1102 Kg", "trunk": "500 L", "image": "data/images/cnw-49061-chevrolet-onix-sedan-eco-1-0-turbo-at.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/Onix-Sedan-Turbo-AT-2026-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=49061", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 149021, "slug": "cnw-49021-chevrolet-onix-eco-1-0-turbo-at", "name": "Chevrolet Onix Eco 1.0 Turbo AT", "title": "Chevrolet Onix Eco 1.0 Turbo AT", "brand": "Chevrolet", "year": "2027", "powertrain": "Combustão (Flex)", "bodyType": "Hatch", "seats": "5", "traction": "Dianteira", "transmission": "Automático", "power": "121 cv", "torque": "18,9 kgfm", "range": "470 km", "battery": "N/I", "topSpeed": "180 km/h", "weight": "1085 Kg", "trunk": "303 L", "image": "data/images/cnw-49021-chevrolet-onix-eco-1-0-turbo-at.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/onix-eco-2027-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=49021", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 152317, "slug": "cnw-52317-volkswagen-saveiro-robust-etanol-1-6-cs", "name": "Volkswagen Saveiro Robust Etanol 1.6 CS", "title": "Volkswagen Saveiro Robust Etanol 1.6 CS", "brand": "Volkswagen", "year": "2027", "powertrain": "Combustão (Flex)", "bodyType": "Picape", "seats": "2", "traction": "Dianteira", "transmission": "Manual", "power": "116 cv", "torque": "16,1 kgfm", "range": "490 km", "battery": "N/I", "topSpeed": "181 km/h", "weight": "1075 Kg", "trunk": "924 L", "image": "data/images/cnw-52317-volkswagen-saveiro-robust-etanol-1-6-cs.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/saveiro-robust-cs-2024-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=52317", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 148669, "slug": "cnw-48669-gac-aion-ut-elite", "name": "GAC Aion UT Elite", "title": "GAC Aion UT Elite", "brand": "GAC", "year": "2027", "powertrain": "Elétrico", "bodyType": "Hatch", "seats": "5", "traction": "Dianteira", "transmission": "Automático", "power": "136 cv", "torque": "21,4 kgfm", "range": "350 km", "battery": "44 kWh", "topSpeed": "150 km/h", "weight": "1510 Kg", "trunk": "440 L", "image": "data/images/cnw-48669-gac-aion-ut-elite.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/Aion-UT-2026-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=48669", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 147777, "slug": "cnw-47777-dongfeng-vigo-urban-plus", "name": "Dongfeng Vigo Urban Plus", "title": "Dongfeng Vigo Urban Plus", "brand": "Dongfeng", "year": "2027", "powertrain": "Elétrico", "bodyType": "SUV", "seats": "5", "traction": "Dianteira", "transmission": "Automático", "power": "95 cv", "torque": "16,3 kgfm", "range": "300 km", "battery": "42 kWh", "topSpeed": "140 km/h", "weight": "1380 Kg", "trunk": "326 L", "image": "data/images/cnw-47777-dongfeng-vigo-urban-plus.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/Vigo-2026-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=47777", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 147796, "slug": "cnw-47796-baic-arcfox-t1-pro", "name": "BAIC Arcfox T1 Pro", "title": "BAIC Arcfox T1 Pro", "brand": "BAIC", "year": "2027", "powertrain": "Elétrico", "bodyType": "Hatch", "seats": "5", "traction": "Dianteira", "transmission": "Automático", "power": "163 cv", "torque": "24,5 kgfm", "range": "320 km", "battery": "48 kWh", "topSpeed": "155 km/h", "weight": "1490 Kg", "trunk": "380 L", "image": "data/images/cnw-47796-baic-arcfox-t1-pro.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/Arcfox-T1-2026-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=47796", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 151145, "slug": "cnw-51145-renault-kardian-vibe-1-0", "name": "Renault Kardian Vibe 1.0", "title": "Renault Kardian Vibe 1.0", "brand": "Renault", "year": "2027", "powertrain": "Combustão (Flex)", "bodyType": "SUV", "seats": "5", "traction": "Dianteira", "transmission": "Manual", "power": "125 cv", "torque": "22,4 kgfm", "range": "450 km", "battery": "N/I", "topSpeed": "180 km/h", "weight": "1186 Kg", "trunk": "358 L", "image": "data/images/cnw-51145-renault-kardian-vibe-1-0.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/kardian-vibe-2026-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=51145", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 151919, "slug": "cnw-51919-omoda-qq-ev", "name": "Omoda QQ EV", "title": "Omoda QQ EV", "brand": "Omoda", "year": "2027", "powertrain": "Elétrico", "bodyType": "Hatch", "seats": "4", "traction": "Traseira", "transmission": "Automático", "power": "75 cv", "torque": "15,3 kgfm", "range": "250 km", "battery": "30 kWh", "topSpeed": "120 km/h", "weight": "1120 Kg", "trunk": "220 L", "image": "data/images/cnw-51919-omoda-qq-ev.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/qq-ev-2027-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=51919", "sourceSite": "Carros na Web", "sections": {}},
    {"id": 151009, "slug": "cnw-51009-leapmotor-b05-bev", "name": "Leapmotor B05 BEV", "title": "Leapmotor B05 BEV", "brand": "Leapmotor", "year": "2027", "powertrain": "Elétrico", "bodyType": "Hatch", "seats": "5", "traction": "Traseira", "transmission": "Automático", "power": "218 cv", "torque": "24,5 kgfm", "range": "420 km", "battery": "56 kWh", "topSpeed": "170 km/h", "weight": "1615 Kg", "trunk": "410 L", "image": "data/images/cnw-51009-leapmotor-b05-bev.jpg", "sourceImageUrl": "https://www.carrosnaweb.com.br/imagensbd007/b05-2027-1.jpg", "sourceUrl": "https://www.carrosnaweb.com.br/fichadetalhe.asp?codigo=51009", "sourceSite": "Carros na Web", "sections": {}},
]


def normalize_existing_json():
    with open(CARS_JSON_PATH, "r", encoding="utf-8") as f:
        cars = json.load(f)
    for c in cars:
        brand, name = normalize_brand_and_name(c.get("brand", ""), c.get("name", ""), c.get("sourceUrl", ""))
        pt, bt = normalize_specs(c.get("powertrain", ""), c.get("bodyType", ""), name, c.get("sections", {}))
        c["brand"] = brand
        c["name"] = name
        c["powertrain"] = pt
        c["bodyType"] = bt
        if not c.get("sourceSite"):
            url = c.get("sourceUrl", "")
            if "carrosnaweb" in url:
                c["sourceSite"] = "Carros na Web"
            elif "icarros" in url:
                c["sourceSite"] = "iCarros"
            else:
                c["sourceSite"] = "Canal VE"
    for fb in CNW_CACHED_FALLBACK:
        if os.path.exists(os.path.join(BASE_DIR, fb["image"])):
            cars.append(fb)
    cars = deduplicate_catalog(cars)
    with open(CARS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(cars, f, ensure_ascii=False, indent=2)
    print(f"Normalizados {len(cars)} carros em {CARS_JSON_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Scraper multi-fonte (Canal VE, Carros na Web, iCarros).")
    parser.add_argument(
        "--sources",
        default="canalve,carrosnaweb,icarros",
        help="Fontes separadas por vírgula: canalve,carrosnaweb,icarros",
    )
    parser.add_argument("--cnw-pages", type=int, default=6, help="Número de páginas do catálogo Carros na Web (padrão: 6)")
    parser.add_argument("--icarros-limit", type=int, default=55, help="Limite de modelos do catálogo iCarros (padrão: 55)")
    parser.add_argument("--normalize-only", action="store_true", help="Apenas normaliza o cars.json existente")
    args = parser.parse_args()

    if args.normalize_only and os.path.exists(CARS_JSON_PATH):
        normalize_existing_json()
        return

    os.makedirs(IMAGES_DIR, exist_ok=True)
    selected_sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    # Preserva os carros já existentes em cars.json que continuam com imagem válida em disco
    existing_cars = []
    if os.path.exists(CARS_JSON_PATH):
        try:
            with open(CARS_JSON_PATH, "r", encoding="utf-8") as f:
                old_cars = json.load(f)
            for oc in old_cars:
                img_rel = oc.get("image", "")
                if img_rel and os.path.exists(os.path.join(BASE_DIR, img_rel)):
                    existing_cars.append(oc)
        except Exception:
            pass

    scraped_cars = []
    if "canalve" in selected_sources:
        scraped_cars.extend(scrape_canalve())
    if "carrosnaweb" in selected_sources:
        scraped_cars.extend(scrape_carrosnaweb(max_pages=args.cnw_pages))
    if "icarros" in selected_sources:
        scraped_cars.extend(scrape_icarros(max_models=args.icarros_limit))

    # Combina os recém-escaneados com os existentes (evitando perder dados caso algum portal limite requisições)
    final_cars = deduplicate_catalog(scraped_cars + existing_cars)

    with open(CARS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(final_cars, f, ensure_ascii=False, indent=2)

    from collections import Counter
    by_site = Counter(c.get("sourceSite", "Canal VE") for c in final_cars)
    print("\n" + "=" * 65)
    print(f"SCAN CONCLUÍDO! Total no catálogo: {len(final_cars)} carros únicos")
    for site_name, count in by_site.items():
        print(f"  • {site_name}: {count} carros")
    print(f"Arquivo salvo em: {CARS_JSON_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    main()
