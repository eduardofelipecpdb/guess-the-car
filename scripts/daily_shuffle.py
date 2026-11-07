#!/usr/bin/env python3
"""
Script de Atualização e Shuffle Diário - Adivinhe o Carro (Canal VE)
Seleciona 3 carros por dia fazendo um embaralhamento (Deck Shuffle sem repetição)
a partir da lista de carros extraída de https://canalve.com.br/ficha-tecnica/.

Uso:
  python scripts/daily_shuffle.py              # Atualiza os 3 carros do dia (se mudou o dia)
  python scripts/daily_shuffle.py --force      # Força um novo sorteio imediato de 3 carros para hoje
  python scripts/daily_shuffle.py --reshuffle  # Reembaralha toda a fila de carros e sorteia 3 novos
  python scripts/daily_shuffle.py --sync       # Executa o scraper do Canal VE antes de atualizar o shuffle
"""

import os
import sys
import json
import random
import datetime
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CARS_JSON_PATH = os.path.join(DATA_DIR, "cars.json")
STATE_JSON_PATH = os.path.join(DATA_DIR, "shuffle_state.json")
DAILY_JSON_PATH = os.path.join(DATA_DIR, "daily.json")
GAME_DATA_JS_PATH = os.path.join(DATA_DIR, "game_data.js")

CARS_PER_DAY = 3
PREGENERATE_DAYS = 30


def load_cars() -> list[dict]:
    if not os.path.exists(CARS_JSON_PATH):
        raise FileNotFoundError(
            f"Arquivo {CARS_JSON_PATH} não encontrado. Execute primeiro: python scripts/scrape_cars.py"
        )
    with open(CARS_JSON_PATH, "r", encoding="utf-8") as f:
        cars = json.load(f)
    return [c for c in cars if c.get("image")]


def build_unique_photo_deck(cars: list[dict], seed: int | None = None) -> list[int]:
    """
    Cria um baralho embaralhado de IDs de carros evitando fotos duplicadas no mesmo ciclo
    e espalhando marcas diferentes.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    # Agrupa por URL de imagem original para evitar sortear duas versões com a mesma foto seguida
    by_img = {}
    for c in cars:
        img_key = c.get("sourceImageUrl") or c.get("image")
        by_img.setdefault(img_key, []).append(c["id"])

    unique_ids = []
    for img_key, ids in by_img.items():
        unique_ids.append(rng.choice(ids))

    rng.shuffle(unique_ids)
    return unique_ids


def pick_three_distinct_brands(deck: list[int], cars_by_id: dict[int, dict]) -> list[int]:
    """
    Retira 3 carros do deck priorizando marcas diferentes no mesmo dia.
    """
    picked = []
    used_brands = set()
    remaining = []

    for cid in deck:
        if cid not in cars_by_id:
            continue
        car = cars_by_id[cid]
        brand = (car.get("brand") or "").lower()
        if len(picked) < CARS_PER_DAY and brand not in used_brands:
            picked.append(cid)
            used_brands.add(brand)
        else:
            remaining.append(cid)

    # Se não conseguiu 3 marcas distintas (fim do deck), completa com os próximos disponíveis
    while len(picked) < CARS_PER_DAY and remaining:
        picked.append(remaining.pop(0))

    # Atualiza o deck in-place com os restantes
    deck[:] = remaining
    return picked


def generate_daily_shuffle(force: bool = False, full_reshuffle: bool = False):
    cars = load_cars()
    if len(cars) < CARS_PER_DAY:
        raise ValueError(f"São necessários pelo menos {CARS_PER_DAY} carros em {CARS_JSON_PATH}.")

    cars_by_id = {c["id"]: c for c in cars}
    today_str = datetime.date.today().isoformat()

    state = {
        "lastUpdatedDate": None,
        "roundNumber": 0,
        "deck": [],
        "todayIds": [],
        "schedule": {},
        "history": [],
    }

    if os.path.exists(STATE_JSON_PATH) and not full_reshuffle:
        try:
            with open(STATE_JSON_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    state.update(loaded)
        except Exception as e:
            print(f"[AVISO] Estado anterior inválido, criando novo: {e}")

    # Filtra IDs que ainda existem no catálogo
    state["deck"] = [cid for cid in state.get("deck", []) if cid in cars_by_id]

    needs_new_draw = (
        force
        or full_reshuffle
        or state.get("lastUpdatedDate") != today_str
        or len(state.get("todayIds", [])) != CARS_PER_DAY
        or any(cid not in cars_by_id for cid in state.get("todayIds", []))
    )

    if needs_new_draw:
        # Se já havia um agendamento para hoje e não foi forçado, usa o agendado; caso contrário sorteia do deck
        scheduled_today = state.get("schedule", {}).get(today_str)
        if (
            not force
            and not full_reshuffle
            and scheduled_today
            and len(scheduled_today) == CARS_PER_DAY
            and all(cid in cars_by_id for cid in scheduled_today)
        ):
            today_ids = scheduled_today
        else:
            if len(state["deck"]) < CARS_PER_DAY:
                state["deck"] = build_unique_photo_deck(cars)
            today_ids = pick_three_distinct_brands(state["deck"], cars_by_id)

        state["todayIds"] = today_ids
        state["lastUpdatedDate"] = today_str
        state["roundNumber"] = int(state.get("roundNumber", 0)) + 1
        state.setdefault("schedule", {})[today_str] = today_ids
        state.setdefault("history", []).append(
            {
                "date": today_str,
                "round": state["roundNumber"],
                "carIds": today_ids,
                "updatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
        # Mantém histórico enxuto (últimos 90 registros)
        state["history"] = state["history"][-90:]
    else:
        today_ids = state["todayIds"]

    # Garante agenda pré-embaralhada para os próximos 30 dias (caso o site rode estático sem cron)
    schedule = state.setdefault("schedule", {})
    schedule[today_str] = today_ids
    base_date = datetime.date.today()
    for offset in range(1, PREGENERATE_DAYS + 1):
        d_str = (base_date + datetime.timedelta(days=offset)).isoformat()
        existing = schedule.get(d_str)
        if not existing or len(existing) != CARS_PER_DAY or any(cid not in cars_by_id for cid in existing) or full_reshuffle:
            if len(state["deck"]) < CARS_PER_DAY:
                state["deck"] = build_unique_photo_deck(cars)
            schedule[d_str] = pick_three_distinct_brands(state["deck"], cars_by_id)

    # Salva estado do shuffle
    with open(STATE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    today_cars = [cars_by_id[cid] for cid in today_ids]

    daily_payload = {
        "date": today_str,
        "roundNumber": state["roundNumber"],
        "updatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        "carsPerDay": CARS_PER_DAY,
        "totalCatalogCars": len(cars),
        "remainingInDeck": len(state["deck"]),
        "todayIds": today_ids,
        "todayCars": today_cars,
        "schedule": schedule,
    }

    with open(DAILY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(daily_payload, f, ensure_ascii=False, indent=2)

    # Gera também data/game_data.js para funcionar mesmo abrindo index.html direto (file://) sem servidor
    js_payload = {
        "daily": daily_payload,
        "cars": cars,
    }
    with open(GAME_DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write("// Arquivo gerado automaticamente por scripts/daily_shuffle.py\n")
        f.write("window.GUESS_THE_CAR_DATA = ")
        json.dump(js_payload, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print("=" * 65)
    print(f"SHUFFLE DIÁRIO ATUALIZADO ({today_str} | Rodada #{state['roundNumber']})")
    print(f"Catálogo total: {len(cars)} carros | Restantes no baralho atual: {len(state['deck'])}")
    print("-" * 65)
    for i, car in enumerate(today_cars, 1):
        print(f"  Carro #{i}: {car['name']} ({car['brand']} • {car['year']} • {car['powertrain']})")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Atualiza os 3 carros do dia com shuffle automático.")
    parser.add_argument("--force", action="store_true", help="Força o sorteio de 3 novos carros para hoje.")
    parser.add_argument("--reshuffle", action="store_true", help="Reembaralha todo o baralho e sorteia 3 novos carros.")
    parser.add_argument("--sync", action="store_true", help="Executa o scraper do Canal VE antes do shuffle.")
    args = parser.parse_args()

    if args.sync:
        import scrape_cars
        scrape_cars.main()

    generate_daily_shuffle(force=args.force, full_reshuffle=args.reshuffle)


if __name__ == "__main__":
    main()

