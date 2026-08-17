#!/usr/bin/env python3
"""Publica UMA peca por execucao: tira a primeira linha viva de `fila.txt` e
escreve o <item> dentro do feed RSS do board dela.

Por que UMA e nao a fileira inteira
-----------------------------------
O Pinterest amarra cada feed a UM board, e a ordem so e garantida DENTRO de um
feed. Uma fileira de 3 que atravessa 3 boards vira 3 feeds lidos em horarios
independentes, e a ordem esquerda/meio/direita na grade do perfil passa a ser
sorteio. A unica alavanca que existe e o ATRASO: soltar uma peca por vez, com
horas entre elas, na ordem certa. Ai a certeza vem de fila, nao de sorte.

Por isso o cron roda 3x no dia de publicacao (09h, 12h, 15h) e cada execucao
consome uma linha. Fileira de 3 = um dia. 3 dias por semana = 9 pins/semana.

A ordem da fila e a ordem de PUBLICACAO, que e o inverso da grade: o perfil
mostra o mais novo primeiro, entao quem sai primeiro aparece por ultimo.

Fila vazia: sai limpo, sem commit. Board sem feed conectado: sai com ERRO de
proposito, sem consumir a linha -- o e-mail de falha do GitHub e o unico canal
que existe pra avisar a autora, e fila parada e melhor que pin no vazio.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

FUSO = "America/Sao_Paulo"
SITE = "https://taymarais.github.io"
BASE_IMG = f"{SITE}/pins"
DESTINO = f"{SITE}/books/where-the-ocean-ends.html"
UTM = "utm_source=Pinterest&utm_medium=organic"

FILA = os.path.join(AQUI, "fila.txt")
PUBLICADOS = os.path.join(AQUI, "publicados.txt")

# 🔴 Board -> arquivo do feed. NAO derivar por slug: `Adam & Madeleine` slugado
#    daria `adam---madeleine`, um arquivo novo que ninguem conectou, e o pin
#    morreria em silencio. E `pins-adam-madeleine.xml` NAO e o board do casal:
#    o nome do arquivo e heranca do lote 1 e esta conectado ao board do livro.
#    Trocar o nome do arquivo quebra a conexao dela. Nao renomear.
FEEDS = {
    "Where The Ocean Ends": "pins-adam-madeleine.xml",
    "Adam Walker": "pins-adam-walker.xml",
    "Madeleine Bennett": "pins-madeleine-bennett.xml",
    # 🔴 `pins-couple.xml`, e NAO `pins-adam-e-madeleine.xml`, que era o nome
    #    original: um `-e-` de diferenca do feed do livro fez a autora conectar o
    #    arquivo errado no minuto um (17/08). Nome de feed tem que ser
    #    inconfundivel NA TELA DO CELULAR, nao so correto.
    "Adam & Madeleine": "pins-couple.xml",
}

# Feed que existe no repo mas que ela ainda nao ligou em Configuracoes ->
# Publicar automaticamente. Item escrito aqui nao vira pin: espera, e quando a
# conexao acontece o Pinterest despeja tudo de uma vez e desmonta a grade.
NAO_CONECTADOS = {
    # Criado em 17/08 com um item so, a `quote-she-bites`, pra ela ter o que
    # conectar. Tirar daqui no minuto em que ela confirmar a conexao **desta
    # URL** -- na primeira tentativa ela conectou o feed do livro por engano, e
    # soltar a trava ali teria escrito pin de casal em feed nenhum.
    "pins-couple.xml",
}

TIPO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

CANAL = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Tay Marais | {board}</title>
    <link>{site}</link>
    <description>Where the Ocean Ends. Dual POV slow burn celebrity romance.</description>
    <language>en</language>
  </channel>
</rss>
"""


def morre(msg):
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(1)


def proxima_linha():
    """Primeira linha que nao e comentario nem vazia, com o indice dela."""
    if not os.path.exists(FILA):
        morre(f"{FILA} nao existe.")
    linhas = open(FILA, encoding="utf-8").read().splitlines()
    for i, linha in enumerate(linhas):
        if linha.strip() and not linha.lstrip().startswith("#"):
            return linhas, i, linha
    return linhas, None, None


def parse(linha):
    partes = [p.strip() for p in linha.split("|")]
    if len(partes) != 4 or not all(partes):
        morre("a linha precisa dos 4 campos preenchidos "
              f"(nome.jpg | titulo | descricao | board): {linha!r}")
    return partes


def item_xml(nome, titulo, descricao, quando):
    """<item> no formato exato dos feeds que ja publicaram. O guid e a URL da
    imagem: o Pinterest deduplica por ele, e foi por isso que o feed do lote 1
    ficou 4 dias no ar com 3 itens publicados sem repetir nenhum."""
    ext = os.path.splitext(nome)[1].lower()
    tipo = TIPO.get(ext) or morre(f"extensao nao aceita: {nome}")
    img = f"{BASE_IMG}/{nome}"
    juncao = "&" if "?" in DESTINO else "?"
    link = f"{DESTINO}{juncao}{UTM}&utm_content={os.path.splitext(nome)[0]}"
    return "\n".join([
        "    <item>",
        f"      <title>{escape(titulo)}</title>",
        f"      <description>{escape(descricao)}</description>",
        f"      <link>{escape(link)}</link>",
        f'      <guid isPermaLink="false">{escape(img)}</guid>',
        f"      <pubDate>{format_datetime(quando)}</pubDate>",
        f'      <enclosure url="{escape(img)}" type="{tipo}" length="0"/>',
        f'      <media:content url="{escape(img)}" medium="image" type="{tipo}"/>',
        "    </item>",
    ])


def escreve_no_feed(caminho, board, item):
    if os.path.exists(caminho):
        texto = open(caminho, encoding="utf-8").read()
    else:
        # `Adam & Madeleine` tem `&` no nome: sem escapar, o canal nasce com XML
        # invalido e o Pinterest recusa o feed inteiro.
        texto = CANAL.format(board=escape(board), site=SITE)
    if "</channel>" not in texto:
        morre(f"{caminho} nao parece um feed RSS: falta </channel>.")
    # Item novo entra no FIM do canal. O Pinterest publica do mais antigo pro
    # mais novo, entao ordem no arquivo = ordem no ar.
    cabeca, _, cauda = texto.rpartition("</channel>")
    return cabeca.rstrip() + "\n" + item + "\n  </channel>" + cauda


def main():
    simular = "--simular" in sys.argv

    linhas, indice, linha = proxima_linha()
    if indice is None:
        print("Fila vazia. Nada a publicar, nada a comitar.")
        return

    nome, titulo, descricao, board = parse(linha)

    if board not in FEEDS:
        morre(f"board {board!r} nao esta no mapa. Boards validos: "
              f"{', '.join(sorted(FEEDS))}. Corrigir a linha na fila.")
    arquivo = FEEDS[board]
    if arquivo in NAO_CONECTADOS:
        morre(f"o feed {arquivo} ({board}) ainda nao esta conectado no "
              f"Pinterest. Fila PARADA de proposito: item escrito num feed "
              f"desconectado nao vira pin, e quando a conexao acontecer o "
              f"Pinterest despeja tudo de uma vez e desmonta a grade. "
              f"Conectar {SITE}/{arquivo} no board '{board}' e rodar de novo.")

    imagem = os.path.join(RAIZ, "pins", nome)
    if not os.path.exists(imagem):
        morre(f"pins/{nome} nao existe no repo. Pin com imagem 404 e pin morto.")

    agora = datetime.now(ZoneInfo(FUSO))
    caminho = os.path.join(RAIZ, arquivo)
    novo = escreve_no_feed(caminho, board, item_xml(nome, titulo, descricao, agora))

    try:
        ET.fromstring(novo)
    except ET.ParseError as e:
        morre(f"o feed sairia com XML quebrado ({e}). Nada foi escrito.")

    print(f"{nome}  ->  {board}  ({arquivo})")
    print(f"  titulo: {titulo}")
    print(f"  restam na fila: {sum(1 for l in linhas[indice + 1:] if l.strip() and not l.lstrip().startswith('#'))}")

    if simular:
        print("\n--simular: nada foi escrito.")
        return

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(novo)

    del linhas[indice]
    with open(FILA, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas).rstrip("\n") + "\n")

    with open(PUBLICADOS, "a", encoding="utf-8") as f:
        f.write(f"{agora:%Y-%m-%d %H:%M} | {linha.strip()}\n")

    # Mensagem de commit sai por aqui, sem apostrofo nem barra: texto da fila
    # interpolado direto num `run:` do workflow e injecao de shell.
    resumo = re.sub(r"[^A-Za-z0-9 ._&-]", "", f"{nome} -> {board}")
    saida = os.environ.get("GITHUB_OUTPUT")
    if saida:
        with open(saida, "a", encoding="utf-8") as f:
            f.write(f"resumo={resumo}\n")


if __name__ == "__main__":
    main()
