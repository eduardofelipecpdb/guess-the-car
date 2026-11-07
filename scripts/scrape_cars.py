#!/usr/bin/env python3
"""
Scraper de Fichas Técnicas e Fotos de Carros - Canal VE (https://canalve.com.br/ficha-tecnica/)
Obtém a lista completa de veículos da API/HTML do Canal VE, extrai toda a ficha técnica
(Marca, Modelo, Ano, Motorização, Carroceria, Potência, Torque, Autonomia, etc.)
e baixa as fotos em alta resolução para uso local no jogo "Adivinhe o Carro".
"""

import os
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
CARS_JSON_PATH = os.path.join(DATA_DIR, "cars.json")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_url(url: str, binary: bool = False, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return data if binary else data.decode("utf-8", errors="ignore")


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


def normalize_brand_and_name(brand: str, raw_name: str, link: str) -> tuple[str, str]:
    brand = (brand or "").strip()
    name = (raw_name or "").strip()

    # Remove prefixo "Sem Fabricante" caso tenha vindo de execução anterior
    name = re.sub(r"^Sem Fabricante\s+", "", name, flags=re.I).strip()

    if not brand or brand.lower() in ["sem fabricante", "n/i"]:
        m_brand = re.search(r"/ficha-tecnica/([^/]+)/", link)
        if m_brand and m_brand.group(1).lower() not in ["sem-fabricante"]:
            brand = m_brand.group(1).replace("-", " ").title()

    # Inferência pelo nome do modelo caso o post não tenha fabricante cadastrado no WP
    lower_name = name.lower()
    if not brand or brand.lower() in ["sem fabricante", "n/i"]:
        if "tiggo" in lower_name or "icar" in lower_name or "arrizo" in lower_name:
            brand = "Caoa Chery"
        elif "peugeot" in lower_name or "e-2008" in lower_name or "e-208" in lower_name:
            brand = "Peugeot"
        elif "byd" in lower_name or "dolphin" in lower_name or "yuan" in lower_name or "song" in lower_name:
            brand = "BYD"

    # Evita duplicar marca no nome (ex: "Omoda-Jaecoo Omoda E5" -> "Omoda E5" ou "Caoa Chery Tiggo 7 Pro PHEV")
    brand_tokens = [t.lower() for t in re.split(r"[\s\-]+", brand) if t]
    first_word = name.split()[0].lower() if name else ""
    if brand and first_word not in brand_tokens and not any(first_word.startswith(bt) for bt in brand_tokens):
        name = f"{brand} {name}"

    return brand or "N/I", name



def parse_vehicle_detail(item_meta: dict, fabricantes_map: dict) -> dict | None:
    post_id = item_meta["id"]
    slug = item_meta["slug"]
    link = item_meta["link"]

    fab_ids = item_meta.get("fabricante") or []
    brand_from_tax = fabricantes_map.get(fab_ids[0], "") if fab_ids else ""

    try:
        html = fetch_url(link)
    except Exception as e:
        print(f"[ERRO] Falha ao abrir {link}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Título e marca do cabeçalho
    h1 = soup.select_one("h1.vehicle-title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else item_meta.get("title", {}).get("rendered", slug)
    title = re.sub(r"^Tudo sobre (?:o |a )?", "", title, flags=re.I)
    title = re.sub(r":\s*Ficha técnica.*$", "", title, flags=re.I).strip()

    brand_el = soup.select_one(".vehicle-header__brand")
    brand = brand_el.get_text(strip=True) if brand_el else brand_from_tax

    # Imagem principal
    featured_img = soup.select_one(".vehicle-featured-image img.featured-img") or soup.select_one("img.wp-post-image")
    image_url = get_best_image_from_srcset(featured_img)
    if not image_url:
        # Tenta og:image
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]

    if not image_url:
        print(f"[AVISO] Sem imagem para {title} ({link})")
        return None

    # Extrair todas as seções spec-card
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
                    # Não sobrescreve Potência se já tiver Motor Elétrico, guarda ambos nas seções
                    if k not in specs:
                        specs[k] = v
        if sec_dict:
            sections[sec_title] = sec_dict

    # Campos principais pedidos pelo usuário: Marca, Ano, Motorização + extras para dicas
    modelo_ficha = specs.get("Fabricante/Modelo") or title
    ano = specs.get("Ano") or ""
    if not ano:
        m_yr = re.search(r"\b(202[0-9])\b", f"{title} {modelo_ficha}")
        if m_yr:
            ano = m_yr.group(1)

    if not brand:
        # Tenta extrair da URL /ficha-tecnica/<brand>/
        m_brand = re.search(r"/ficha-tecnica/([^/]+)/", link)
        if m_brand:
            brand = m_brand.group(1).replace("-", " ").title()

    motorizacao = specs.get("Motorização") or "Elétrico"
    carroceria = specs.get("Carroceria") or "N/I"
    lugares = specs.get("Lugares") or "N/I"
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

    # Nome limpo do modelo e marca normalizada
    raw_name = modelo_ficha if modelo_ficha else title
    brand, display_name = normalize_brand_and_name(brand, raw_name, link)

    # Download da imagem
    ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"
    clean_slug = re.sub(r"^tudo-sobre-?", "", slug) or str(post_id)
    img_filename = f"{post_id}-{clean_slug}{ext}"
    img_local_path = os.path.join(IMAGES_DIR, img_filename)

    if not os.path.exists(img_local_path) or os.path.getsize(img_local_path) < 1000:
        try:
            # codifica caracteres especiais na URL da imagem
            parsed = urllib.parse.urlsplit(image_url)
            safe_path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:@!$&'()*+,;=-._~")
            safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, safe_path, parsed.query, parsed.fragment))
            img_bytes = fetch_url(safe_url, binary=True)
            with open(img_local_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"[ERRO IMG] Falha ao baixar imagem {image_url}: {e}")
            return None

    return {
        "id": post_id,
        "slug": clean_slug,
        "name": display_name,
        "title": title,
        "brand": brand or "N/I",
        "year": ano or "N/I",
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
        "image": f"data/images/{img_filename}",
        "sourceImageUrl": image_url,
        "sourceUrl": link,
        "sections": sections,
    }


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print("1. Buscando lista de fabricantes no Canal VE...")
    fabricantes_map = {}
    try:
        fab_data = json.loads(fetch_url("https://canalve.com.br/wp-json/wp/v2/fabricante?per_page=100"))
        for f in fab_data:
            fabricantes_map[f["id"]] = f["name"]
        print(f"   -> {len(fabricantes_map)} fabricantes encontrados.")
    except Exception as e:
        print(f"   [AVISO] Não foi possível carregar fabricantes via API: {e}")

    print("2. Buscando lista de veículos em https://canalve.com.br/wp-json/wp/v2/veiculo ...")
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

    print(f"   -> {len(all_items)} veículos encontrados. Extraindo fichas técnicas e baixando fotos...")

    cars = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(parse_vehicle_detail, item, fabricantes_map): item for item in all_items}
        for idx, future in enumerate(as_completed(futures), 1):
            res = future.result()
            if res:
                cars.append(res)
                print(f"   [{idx}/{len(all_items)}] OK: {res['name']} ({res['brand']} | {res['year']} | {res['powertrain']})")
            else:
                print(f"   [{idx}/{len(all_items)}] PULADO")

    # Ordenar por ID decrescente
    cars.sort(key=lambda c: c["id"], reverse=True)

    with open(CARS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(cars, f, ensure_ascii=False, indent=2)

    print(f"\nConcluído! {len(cars)} carros salvos em {CARS_JSON_PATH}")
    print(f"Fotos salvas em {IMAGES_DIR}")


def normalize_existing_json():
    with open(CARS_JSON_PATH, "r", encoding="utf-8") as f:
        cars = json.load(f)
    for c in cars:
        brand, name = normalize_brand_and_name(c.get("brand", ""), c.get("name", ""), c.get("sourceUrl", ""))
        c["brand"] = brand
        c["name"] = name
    with open(CARS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(cars, f, ensure_ascii=False, indent=2)
    print(f"Normalizados {len(cars)} carros em {CARS_JSON_PATH}")


if __name__ == "__main__":
    import sys
    if "--normalize-only" in sys.argv and os.path.exists(CARS_JSON_PATH):
        normalize_existing_json()
    else:
        main()
