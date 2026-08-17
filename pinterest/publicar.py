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
NAO_CONECTADOS = set()   # os quatro estao conectados desde 17/08/2026

# Primeira linha viva da fila igual a isto = o robo passa a vez, sem erro e sem
# commit. Serve pra segurar a publicacao sem desligar o cron nem mexer em codigo:
# apagar a linha e o suficiente pra voltar. Existe porque fileira publicada nao
# se reordena -- quando ha duvida se a fileira anterior fechou, a resposta certa
# e esperar, e esperar tem que custar uma linha, nao uma sessao.
PAUSA = "PAUSA"

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
    ficou 4 dias no ar com 3 itens publicados sem repetir nenhum.

    ⚠️ Por isso mesmo, REENVIAR uma peca que ja publicou uma vez exige guid novo.
    Nao se sabe se o Pinterest esquece o guid quando o pin e apagado na mao, e
    apostar que esquece custaria a peca nao voltar -- em silencio. A fila marca
    reenvio com `nome.jpg#sufixo`: o sufixo entra no guid e a imagem continua a
    mesma."""
    nome, _, sufixo = nome.partition("#")
    ext = os.path.splitext(nome)[1].lower()
    tipo = TIPO.get(ext) or morre(f"extensao nao aceita: {nome}")
    img = f"{BASE_IMG}/{nome}"
    guid = f"{img}#{sufixo}" if sufixo else img
    juncao = "&" if "?" in DESTINO else "?"
    link = f"{DESTINO}{juncao}{UTM}&utm_content={os.path.splitext(nome)[0]}"
    return "\n".join([
        "    <item>",
        f"      <title>{escape(titulo)}</title>",
        f"      <description>{escape(descricao)}</description>",
        f"      <link>{escape(link)}</link>",
        f'      <guid isPermaLink="false">{escape(guid)}</guid>',
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


GAP_MINIMO_MIN = 90        # minutos entre duas pecas da MESMA fileira
INTERVALO_FILEIRA_H = 36   # horas minimas entre uma fileira e a proxima
FILEIRAS_POR_SEMANA = 3    # teto movel: fileiras nos ultimos 7 dias
JANELA_DIAS = 7


def datas_publicadas():
    if not os.path.exists(PUBLICADOS):
        return []
    fora = []
    for l in open(PUBLICADOS, encoding="utf-8"):
        try:
            fora.append(datetime.strptime(l[:16], "%Y-%m-%d %H:%M")
                        .replace(tzinfo=ZoneInfo(FUSO)))
        except ValueError:
            continue        # comentario, linha vazia, cabecalho
    return fora


def publicados_hoje(hoje):
    return sum(1 for d in datas_publicadas() if d.date() == hoje)


def main():
    simular = "--simular" in sys.argv
    forcar = "--forcar" in sys.argv

    linhas, indice, linha = proxima_linha()
    if indice is None:
        print("Fila vazia. Nada a publicar, nada a comitar.")
        return

    # 🔴 FILEIRA NAO COMECA NO MEIO DO DIA.
    # A grade da aba Criados e fluxo continuo de tres colunas, entao fileira so
    # existe enquanto o total de pins criados for multiplo de 3: publicar 2 pecas
    # num dia desalinha TUDO que esta embaixo ate a terceira sair, e pin
    # publicado nao se reordena. Se o primeiro horario do dia foi perdido (pausa,
    # falha de rede, cron atrasado), o dia inteiro passa em vez de sair pela
    # metade. Perder um dia custa nada; deixar a grade torta custa o desenho dela.
    agora = datetime.now(ZoneInfo(FUSO))
    ultima = max(datas_publicadas(), default=None)
    comecando = publicados_hoje(agora.date()) == 0

    if not forcar and comecando:
        # --- Este run COMECARIA uma fileira nova. Duas condicoes. ---

        # 🔴 1. Fileira nao comeca no meio do dia.
        # A grade da aba Criados e fluxo continuo de tres colunas, entao fileira
        # so existe enquanto o total de pins criados for multiplo de 3. Comecar
        # as 12h deixaria a fileira pela metade ate amanha, e pin publicado nao
        # se reordena. Perder um dia custa nada; meia fileira custa o desenho.
        if agora.hour >= 11:
            print(f"Sao {agora:%H:%M} e nada saiu hoje: o primeiro horario "
                  f"(09h) ja passou. O dia inteiro passa em vez de sair meia "
                  f"fileira — amanha as 09h ela sai completa.")
            return

        # 2. Folga minima entre fileiras.
        if ultima and (agora - ultima).total_seconds() / 3600 < INTERVALO_FILEIRA_H:
            horas = (agora - ultima).total_seconds() / 3600
            print(f"A fileira anterior saiu ha {horas:.0f}h. Minimo de "
                  f"{INTERVALO_FILEIRA_H}h entre fileiras.")
            return

        # 🔴 3. TETO MOVEL: no maximo 3 fileiras a cada 7 dias.
        # A cadencia e dela, decidida em 15/08 e reafirmada em 17/08: *"uma por
        # dia e demais, vai gastar antes de eu ter banco de mais"*. O gargalo do
        # sistema nao e publicar, e PRODUZIR ARTE — o estoque de foto sobra, o de
        # arte nao existe. Publicar rapido nao acelera nada, so esvazia a fila
        # antes de ela ter o proximo lote pronto.
        # Janela movel, e nao dia fixo da semana, porque dia fixo transforma
        # qualquer tropeco em espera de dois dias: perdeu a segunda, so na quarta.
        # Assim um dia perdido e recuperado sozinho, sem passar do teto.
        recentes = {d.date() for d in datas_publicadas()
                    if (agora - d).days < JANELA_DIAS}
        if len(recentes) >= FILEIRAS_POR_SEMANA:
            print(f"Ja sairam {len(recentes)} fileiras nos ultimos {JANELA_DIAS} "
                  f"dias, que e o teto ({FILEIRAS_POR_SEMANA}/semana). A proxima "
                  f"sai quando a mais antiga da janela vencer.")
            return

    # 🔴 DUAS PECAS COLADAS = ORDEM NO SORTEIO.
    # O cron do GitHub nao e pontual: pode atrasar meia hora e mais, e duas
    # execucoes atrasadas se juntam. A ordem da fileira depende de o Pinterest
    # ler os feeds ENTRE uma peca e a outra, entao peca solta minutos depois da
    # anterior perde a unica garantia que o sistema tem. Medido em 17/08: ~1h de
    # vantagem foi suficiente pra determinar a ordem; 90 min e a margem.
    if not forcar and ultima and not comecando:
        faltam = GAP_MINIMO_MIN - (agora - ultima).total_seconds() / 60
        if faltam > 0:
            print(f"A peca anterior saiu {int(GAP_MINIMO_MIN - faltam)} min atras. "
                  f"Esperando {int(faltam)} min pra nao publicar duas colada, que "
                  f"joga a ordem da fileira no sorteio.")
            return

    if linha.strip().upper().startswith(PAUSA):
        print(f"Fila em PAUSA: {linha.strip()}\n"
              f"Nada publicado, nada comitado. Apagar a linha '{PAUSA}' de "
              f"{FILA} pra voltar a publicar.")
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

    arquivo_img = nome.split("#")[0]      # `nome.jpg#r2` e reenvio, ver item_xml
    if not os.path.exists(os.path.join(RAIZ, "pins", arquivo_img)):
        morre(f"pins/{arquivo_img} nao existe no repo. Pin com imagem 404 e pin morto.")

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
