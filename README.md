# 🚗 Adivinhe o Carro — Desafio Diário (Canal VE)

Jogo web responsivo onde você tenta adivinhar **3 carros por dia** a partir da foto com zoom progressivo e dicas da ficha técnica extraídas do portal [Canal VE — Ficha Técnica](https://canalve.com.br/ficha-tecnica/).

## ✨ Funcionalidades

- **Zoom Progressivo na Foto**: Começa com zoom de `3.5x` focado no carro e vai reduzindo (`2.7x` → `2.1x` → `1.6x` → `1.25x` → `1.08x` → `1.0x`) conforme o jogador erra ou pula tentativas.
- **Dicas Progressivas da Ficha Técnica**: A cada tentativa errada, uma nova informação da ficha técnica é revelada:
  1. **Carroceria, Lugares e Porta-malas**
  2. **Motorização (Elétrico, Híbrido, etc.), Potência e Tração**
  3. **Ano do Modelo, Autonomia e Velocidade Máxima**
  4. **Marca / Fabricante**
  5. **Iniciais do Modelo**
- **Comparação Estilo Wordle/Cardle**: Cada palpite mostra se você acertou a **Marca**, **Motorização**, **Carroceria** e se o **Ano** do carro misterioso é mais novo (`↑`) ou mais antigo (`↓`).
- **Catálogo e Fotos Baixados Localmente**: `86` veículos e suas fotos em alta resolução extraídos diretamente de `https://canalve.com.br/ficha-tecnica/`.
- **Shuffle Diário Automático (3 Carros por Dia)**: Sorteia 3 carros de marcas diferentes por dia usando um algoritmo de baralho (*Deck Shuffle* sem repetição até esgotar o catálogo).

## 🚀 Como Jogar / Executar

Você pode abrir o arquivo [`index.html`](./index.html) diretamente no navegador (duplo clique) ou iniciar um servidor local clicando em [`iniciar_jogo.bat`](./iniciar_jogo.bat):

```bash
python -m http.server 8080
# Acesse http://localhost:8080
```

## 🔄 Scripts de Extração e Shuffle Automático

### 1. Atualizar os 3 carros do dia (Shuffle)
```bash
# Atualiza os 3 carros do dia (se mudou a data)
python scripts/daily_shuffle.py

# Força o sorteio imediato de 3 novos carros para hoje
python scripts/daily_shuffle.py --force

# Reembaralha todo o baralho do zero e sorteia 3 novos carros
python scripts/daily_shuffle.py --reshuffle
```

### 2. Atualizar catálogo e fotos do site Canal VE
```bash
python scripts/scrape_cars.py
```
O script consulta a API e as páginas de ficha técnica de `https://canalve.com.br/ficha-tecnica/`, salva todas as especificações em `data/cars.json` e baixa as imagens em `data/images/`.

