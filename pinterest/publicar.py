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

Desde 10/09/2026 sai UMA peca por dia, e a fileira de 3 fecha em tres dias. E o
que ela pediu e e o que torna varios boards seguros: um dia, um feed, uma peca.

O cron roda TODO DIA e quem decide e este script. Dia fixo da semana transformava
qualquer tropeco em espera de dois dias; com janela movel, o dia seguinte assume
sozinho sem nunca passar do teto.

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
from datetime import datetime, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

sys.path.insert(0, AQUI)
import marca                                   # noqa: E402  (precisa do AQUI)

FUSO = "America/Sao_Paulo"

# 🔴 DOIS ENDERECOS, e eles NAO se juntam. O site vive em `taymarais.com`; o
#    `taymarais.github.io` virou o deposito das imagens dos pins.
#
#    O LINK do pin tem que ir direto pro dominio. Ate 06/09/2026 ele ia pro
#    github.io, que so entao desviava por JavaScript: um salto a mais, que
#    depende de JS estar ligado, no unico clique que essa maquina toda existe
#    pra ganhar. Corrigido pros pins NOVOS. Os ja publicados nao se reescrevem.
#
#    ⚠️ A IMAGEM continua no github.io de proposito, e isto NAO e esquecimento:
#    o `guid` de cada item E a URL da imagem, e o Pinterest deduplica por ele.
#    Trocar a base das imagens daria guid novo pra peca ja publicada, e o
#    caminho de volta disso nao existe. Nao unificar.
SITE = "https://taymarais.com"
SITE_IMG = "https://taymarais.github.io"
BASE_IMG = f"{SITE_IMG}/pins"
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

# 🔴 A rota ativa. Toda peca da fila sai por aqui, e a trava em `main` recusa
# qualquer linha que aponte pra outro board. Os outros tres feeds continuam
# conectados e parados, prontos caso um dia o Pinterest volte a le-los.
# 🔴 A ROTA DEIXOU DE SER UMA SO em 10/09/2026, decisao dela: *"agora que nao
# precisa enviar so pra um feed, varia: Mads na Mads, Adam no Adam, quotes em
# Where The Ocean, foto de casal em romance"*.
#
# ⚠️ POR QUE ISTO ERA PROIBIDO, e ATE ONDE a prova alcanca. Sao DUAS medidas e
# elas nao dizem a mesma coisa:
#   17/08, 3 feeds -> publicou tudo, ORDEM TROCADA. Explicado: cada feed e
#          varrido uma vez por dia, no horario dele, entao 3 pecas soltas no
#          mesmo dia viram sorteio. **Uma peca por dia conserta exatamente isso**
#          -- e era o conserto ja escrito no maquina-de-pin.md em 18/08, antes de
#          o problema acontecer: "pra cada varredura diaria encontrar exatamente
#          uma peca nova".
#   20/08, 3 feeds -> NAO PUBLICOU EM DOIS DIAS. **Esta NAO esta explicada.**
#          Nosso lado foi conferido elo por elo (XML valido, imagens no lugar,
#          site republicado). Uma peca por dia nao promete nada contra ela.
#
# 🔴 POR ISSO A LISTA TEM DOIS BOARDS E NAO QUATRO. `Adam & Madeleine`
# (pins-couple.xml) e `Where The Ocean Ends` (pins-adam-madeleine.xml) sao os
# DOIS unicos feeds com publicacao bem-sucedida na historia deste repo -- o
# segundo e o feed do lote 1, de 13/08. Os que falharam em 20/08 foram
# `Adam Walker` e `Madeleine Bennett`, e eles ficam de fora ate haver medida.
#
# 📌 O TESTE, quando ela quiser abrir a segunda rota: mandar UMA peca de quote
# pro `Where The Ocean Ends` e conferir a grade dois dias depois. Se aparecer, a
# rota esta viva e da pra rotear mais. Se nao, a causa de 20/08 continua de pe e
# a fila inteira volta pro board unico -- que, de quebra, rende ~11x mais por pin.
#
# ⚠️ A trava continua de pe pra board que nao esta aqui. Board fora desta lista
# falha ALTO, porque item escrito em feed nao conectado nao vira pin e a fila
# para em silencio.
BOARDS_ATIVOS = {"Adam & Madeleine", "Where The Ocean Ends"}

# Primeira linha viva da fila igual a isto = o robo passa a vez, sem erro e sem
# commit. Serve pra segurar a publicacao sem desligar o cron nem mexer em codigo:
# apagar a linha e o suficiente pra voltar. Existe porque fileira publicada nao
# se reordena -- quando ha duvida se a fileira anterior fechou, a resposta certa
# e esperar, e esperar tem que custar uma linha, nao uma sessao.
PAUSA = "PAUSA"

TIPO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        # 🔴 VIDEO E TESTE, ligado em 29/08 a pedido dela. NAO se sabe se a
        # publicacao automatica por RSS do Pinterest aceita video: a tela dele
        # fala de "pins", nao de formato, e a documentacao nao esta acessivel
        # daqui. Se ele ignorar o item, ignora EM SILENCIO -- por isso o teste
        # sai com o video no MEIO de uma fileira e uma PAUSA logo depois, pra
        # ela conferir antes da terceira peca fechar a fileira. Fileira que
        # fecha com 3 pins esta alinhada mesmo se o video nao for um deles.
        ".mp4": "video/mp4"}

# `medium` do Media RSS: o Pinterest usa isso pra saber o que esta recebendo, e
# `medium="image"` num .mp4 seria mentira. Derivado do tipo, nunca hardcoded.
def medium(tipo):
    return "video" if tipo.startswith("video/") else "image"

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


def proxima_fileira():
    """As PECAS_POR_DIA primeiras linhas vivas da fila, em ordem.

    🔴 SO DEVOLVE O LOTE DO DIA COMPLETO. Com PECAS_POR_DIA = 1 isso e trivial:
    sai a peca ou nao sai nada. Os dois guardas abaixo (PAUSA no meio do lote,
    fila mais curta que o lote) so voltam a ter trabalho se PECAS_POR_DIA subir
    de novo -- e ai valem pelo motivo antigo: lote pela metade empurra tudo que
    esta embaixo uma casa na aba Criados, pra sempre. Nao apagar so porque hoje
    nao disparam.
    """
    if not os.path.exists(FILA):
        morre(f"{FILA} nao existe.")
    linhas = open(FILA, encoding="utf-8").read().splitlines()
    vivas = [(i, l) for i, l in enumerate(linhas)
             if l.strip() and not l.lstrip().startswith("#")]
    if not vivas:
        return linhas, [], "Fila vazia. Nada a publicar, nada a comitar."
    if vivas[0][1].strip().upper().startswith(PAUSA):
        return linhas, [], (f"Fila em PAUSA: {vivas[0][1].strip()}\n"
                            f"Nada publicado, nada comitado. Apagar a linha "
                            f"{PAUSA!r} de {FILA} pra voltar a publicar.")
    alvos = []
    for i, l in vivas[:PECAS_POR_DIA]:
        if l.strip().upper().startswith(PAUSA):
            return linhas, [], (
                f"A PAUSA esta na posicao {len(alvos) + 1} do lote do dia: "
                f"sairiam {len(alvos)} pecas de {PECAS_POR_DIA}, e lote pela "
                f"metade desalinha tudo que esta embaixo. Nada publicado. "
                f"Apagar a linha {PAUSA!r} de {FILA} pro lote sair inteiro.")
        alvos.append((i, l))
    if len(alvos) < PECAS_POR_DIA:
        return linhas, [], (
            f"So restam {len(alvos)} linha(s) viva(s) e o lote do dia precisa "
            f"de {PECAS_POR_DIA}. Lote pela metade desalinha a grade, entao "
            f"nada sai ate a fila voltar ao multiplo de {PECAS_POR_DIA}.")
    return linhas, alvos, None


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
    # `utm_content` sai do nome do arquivo, SEM a pasta: a foto marcada mora em
    # `marcadas/`, e `utm_content=marcadas/adam-...` sujaria o relatorio e
    # quebraria a comparacao com as pecas publicadas antes da marca existir.
    link = (f"{DESTINO}{juncao}{UTM}"
            f"&utm_content={os.path.splitext(os.path.basename(nome))[0]}")
    return "\n".join([
        "    <item>",
        f"      <title>{escape(titulo)}</title>",
        f"      <description>{escape(descricao)}</description>",
        f"      <link>{escape(link)}</link>",
        f'      <guid isPermaLink="false">{escape(guid)}</guid>',
        f"      <pubDate>{format_datetime(quando)}</pubDate>",
        f'      <enclosure url="{escape(img)}" type="{tipo}" length="0"/>',
        f'      <media:content url="{escape(img)}" medium="{medium(tipo)}" '
        f'type="{tipo}"/>',
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


# 🔴 O GAP DE 90 MIN FOI APOSENTADO EM 31/08, junto com o corte das 11h.
# Ele existia pra garantir a ORDEM quando a fileira se espalhava por tres feeds
# lidos em horarios independentes: sem folga entre as pecas, a ordem virava
# sorteio. Desde 22/08 toda a fila sai por UM feed so, e dentro de um feed a
# ordem e garantida por CONSTRUCAO -- o Pinterest le os <item> do mais antigo
# pro mais novo, entao ordem no arquivo e ordem no ar. Espacar deixou de comprar
# garantia e passou a custar a fileira inteira: as tres pecas dependiam de tres
# execucoes de cron, e o cron do GitHub nao entrega tres.
# 🔴 UMA PECA POR DIA desde 10/09/2026, decisao dela: *"pode fazer a fileira
# sair em dias seguidos a partir de agora, uma postagem por dia sempre"*.
# Antes a fileira de 3 saia inteira numa execucao. Mudou por duas razoes:
#   1. O video da Jen Vazquez (transcrito em `dados/transcricoes/campanha/` do
#      repo do estudio) mede que o Pinterest premia CONSTANCIA, nao pico: alguns
#      pins bons todo dia batem 20 na segunda e silencio o resto da semana.
#   2. E e o que torna MULTI-BOARD seguro. Uma peca por dia significa que so UM
#      feed recebe item naquele dia, entao a ordem da aba Criados continua sendo
#      a ordem da fila mesmo com a fila espalhada por varios boards. Era esta a
#      razao da trava de rota, e ela cai por construcao, nao por descuido.
PECAS_POR_DIA = 1
# 🔴 UMA PECA POR SABADO desde 11/09/2026, e a razao e a CONTA, nao o gosto.
# Ela: *"uma peca por sabado e melhor mesmo."*
#
# O `plano-de-producao.py` mediu: com fileira de 3, a linha de conversao pedia
# **57 pecas** ate 19/01 e existiam 6. Faltavam 51 -- mais que a fila narrativa
# inteira, e sao as pecas mais caras do sistema (foto + frase + botao, montadas
# uma a uma no `pecas-cta.py`). Com uma por sabado cai pra 19, que e fazivel.
#
# ⚠️ E O QUE SE PERDE, pra ficar registrado: a forma `livro · CASAL+CTA · livro`
# (regra 1-k do `estrategia-de-feed.md`) era uma fileira desenhada pra ser lida
# lado a lado. Ela vale na GRADE do perfil, e a grade so importa pra quem visita
# o perfil. A linha de conversao existe pelo CLIQUE, e clique nao precisa de
# fileira montada. A decisao foi dela, sabendo disso.
PECAS_PROMO = 1
SEM_MARCA = ("quote-", "dialogue-", "still-", "promo-")  # artes que ja trazem o titulo dentro
# 🔴 `still-` entrou em 02/09: o carimbo desliza pela borda de baixo, que e exatamente
#    onde mora a legenda do segundo frame do still. Aprovado por ela no briefing de 30/08.
#    O prefixo proprio tambem E a medida: o utm_content e o nome do arquivo, e em 30 dias
#    ele compara `still-` contra `quote-` e `dialogue-`.
# 🔴 14h, E O NUMERO TEM MOTIVO — 20h estava errado e teria custado dias.
# A trava que garante "uma por dia" e o `publicados_hoje` logo acima, que e por
# DIA DE CALENDARIO. Esta aqui so impede duas pecas coladas. So que o cron mais
# tarde publica 15h17 BRT e o mais cedo do dia seguinte roda 08h07 BRT: 16h49 de
# distancia. Com 20h, todo dia que a peca saisse depois das 12h17 BRT bloquearia
# as tres primeiras tentativas do dia seguinte -- e como o cron do GitHub atrasa
# e descarta execucao (medido de 26 a 30/08: 1 ou 2 entregas por dia em vez de
# 5), sobrar so as duas ultimas e como perder o dia. 14h fica abaixo das 16h49 e
# nunca briga com o proprio cron.
INTERVALO_H = 14           # horas minimas entre uma peca e a proxima
PECAS_POR_SEMANA = 7       # teto movel: dias com publicacao nos ultimos 7
JANELA_DIAS = 7

# ─── A LINHA DE CONVERSAO (decidida por ela em 07/09/2026) ──────────────────
# 🔴 SABADO E DA FILEIRA PROMOCIONAL. Ela: *"nos comecamos a todo sabado, para
#    que no domingo ja estejam na plataforma."* Nesse dia o robo le a fila promo
#    e a fila narrativa NAO roda.
#
# 📌 E POR QUE ISSO NAO TIRA O LUGAR DE NINGUEM, que era a condicao dela:
#    o teto da narrativa e "3 fileiras nos ultimos 7 dias" — janela MOVEL, nao
#    dia fixo. Reservar o sabado deixa seis dias pra colocar as tres, e nenhuma
#    se perde. Se o teto fosse por dia da semana, isto custaria uma fileira.
#
# ⚠️ O DESENHO E TROCAR OS DOIS ARQUIVOS, e so. As tres travas do robo (uma
#    peca por dia, 14h entre pecas, teto de 7/7) leem FILA e PUBLICADOS —
#    apontando as duas pro par promo, as tres passam a valer pra esta linha
#    sozinha, sem nenhuma condicional nova espalhada pelo main.
FILA_PROMO = os.path.join(AQUI, "fila-promo.txt")
PUBLICADOS_PROMO = os.path.join(AQUI, "publicados-promo.txt")
DIA_PROMO = 5              # 0=segunda ... 5=sabado


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
    global FILA, PUBLICADOS, PECAS_POR_DIA
    simular = "--simular" in sys.argv
    forcar = "--forcar" in sys.argv
    agora = datetime.now(ZoneInfo(FUSO))

    # Sabado, ou `--promo` na mao: a rodada e da linha de conversao.
    promo = "--promo" in sys.argv or agora.weekday() == DIA_PROMO
    if promo:
        if not os.path.exists(FILA_PROMO):
            print(f"Rodada promocional, mas {FILA_PROMO} nao existe. "
                  f"Nada publicado, e a fila narrativa nao roda no sabado.")
            return
        FILA, PUBLICADOS = FILA_PROMO, PUBLICADOS_PROMO
        PECAS_POR_DIA = PECAS_PROMO     # a fileira promo sai inteira, ver acima
        print(f"Rodada PROMOCIONAL (linha de conversao), "
              f"{PECAS_POR_DIA} peca(s) no sabado.")

    linhas, alvos, parada = proxima_fileira()
    if parada:
        print(parada)
        return

    ultima = max(datas_publicadas(), default=None)
    saidas_hoje = publicados_hoje(agora.date())

    # 🔴 UMA FILEIRA POR DIA. Antes o teto era "tres pecas por dia" porque cada
    # execucao soltava uma; hoje o lote do dia E uma peca, entao qualquer peca
    # publicada hoje ja significa o dia feito.
    if not forcar and saidas_hoje:
        print(f"A peca de hoje ja saiu ({saidas_hoje}). A proxima e amanha.")
        return

    # 🔴 O CORTE DAS 11h MORREU EM 31/08, e a razao importa.
    # Ele existia pra fileira nao comecar tarde e ficar pela metade: as tres
    # pecas dependiam de TRES execucoes espacadas, entao comecar as 12h deixava
    # a grade torta ate o dia seguinte. Como agora a fileira sai inteira numa
    # execucao, comecar tarde nao deixa nada pela metade -- e o corte tinha
    # virado a causa do problema, nao a protecao contra ele.
    #
    # MEDIDO EM 31/08, nas Actions: de 26 a 30/08 o cron do GitHub entregou 1 ou
    # 2 execucoes por dia em vez de 5, atrasadas de 4 a 9 HORAS. Nenhuma caiu
    # antes das 11h. Resultado: cinco dias de rodadas VERDES, com o script
    # imprimindo "o dia inteiro passa", e zero pins. Somar tentativas de manha
    # (o conserto de 30/08) nao resolve: o GitHub nao roda de manha.

    if not forcar and ultima:
        horas = (agora - ultima).total_seconds() / 3600
        if horas < INTERVALO_H:
            print(f"A peca anterior saiu ha {horas:.0f}h. Minimo de "
                  f"{INTERVALO_H}h entre pecas.")
            return

    # 🔴 TETO MOVEL: no maximo 3 fileiras a cada 7 dias.
    # A cadencia e dela, decidida em 15/08 e reafirmada em 17/08: *"uma por dia
    # e demais, vai gastar antes de eu ter banco de mais"*. O gargalo do sistema
    # nao e publicar, e PRODUZIR ARTE. Janela movel, e nao dia fixo da semana,
    # porque dia fixo transforma qualquer tropeco em espera de dois dias.
    recentes = {d.date() for d in datas_publicadas()
                if (agora - d).days < JANELA_DIAS}
    if not forcar and len(recentes) >= PECAS_POR_SEMANA:
        print(f"Ja houve publicacao em {len(recentes)} dos ultimos "
              f"{JANELA_DIAS} dias, que e o teto ({PECAS_POR_SEMANA}/semana). "
              f"A proxima sai quando a mais antiga da janela vencer.")
        return

    # 🔴 VALIDA AS TRES ANTES DE ESCREVER QUALQUER UMA. Tudo ou nada: uma peca
    # escrita e duas recusadas seria exatamente a meia fileira que o resto deste
    # arquivo existe pra impedir.
    pecas, arquivo = [], None
    for indice, linha in alvos:
        nome, titulo, descricao, board = parse(linha)
        if board not in FEEDS:
            morre(f"board {board!r} nao esta no mapa. Boards validos: "
                  f"{', '.join(sorted(FEEDS))}. Corrigir a linha na fila.")
        # 🔴 TRAVA DE ROTA. Fileira espalhada por varios feeds nao publica --
        # medido duas vezes, em 17 e 20/08. Uma sessao futura vai olhar uma foto
        # do Adam e "consertar" o board pra `Adam Walker` achando que ajuda, e a
        # fila para EM SILENCIO. Por isso a rota falha alto.
        if board not in BOARDS_ATIVOS:
            morre(f"a linha manda pro board {board!r}, que nao esta nas rotas "
                  f"ativas ({', '.join(sorted(BOARDS_ATIVOS))}).\n"
                  f"Abrir uma rota nova e acrescentar o board em BOARDS_ATIVOS, "
                  f"de proposito, depois de ler o porque no maquina-de-pin.md.")
        if arquivo is None:
            arquivo = FEEDS[board]
        if FEEDS[board] in NAO_CONECTADOS:
            morre(f"o feed {FEEDS[board]} ({board}) ainda nao esta conectado no "
                  f"Pinterest. Fila PARADA de proposito: item escrito num feed "
                  f"desconectado nao vira pin, e quando a conexao acontecer o "
                  f"Pinterest despeja tudo de uma vez e desmonta a grade.")
        arquivo_img = nome.split("#")[0]      # `nome.jpg#r2` e reenvio
        if not os.path.exists(os.path.join(RAIZ, "pins", arquivo_img)):
            morre(f"pins/{arquivo_img} nao existe no repo. "
                  f"Pin com imagem 404 e pin morto, e a fileira inteira para.")
        pecas.append(dict(indice=indice, linha=linha, nome=nome, titulo=titulo,
                          descricao=descricao, board=board, img=arquivo_img))

    # ---- carimbo e montagem dos tres <item>, ja validados ----
    itens = []
    for k, pc in enumerate(pecas):
        origem = os.path.join(RAIZ, "pins", pc["img"])
        # A marca d'agua entra AQUI, na publicacao, nunca no arquivo guardado:
        # marca gravada no original e irreversivel. Arte de quote e de dialogo
        # nao recebem (ja trazem o nome do livro dentro), e video tambem nao --
        # carimbar exigiria reencodar a cada publicacao.
        e_video = TIPO.get(os.path.splitext(pc["img"])[1].lower(), "").startswith("video/")
        if not pc["img"].startswith(SEM_MARCA) and not e_video and not simular:
            try:
                marca.marca(origem)
                pc["nome"] = f"marcadas/{pc['img']}" + (
                    f"#{pc['nome'].split('#')[1]}" if "#" in pc["nome"] else "")
            except Exception as e:
                # Foto sem marca e melhor que fileira parada: a marca e
                # assinatura, nao requisito. Mas o aviso tem que aparecer no log.
                print(f"AVISO: nao consegui carimbar {pc['img']} ({e}). "
                      f"Publicando a foto limpa.")
        # Um minuto entre os pubDate: a ordem ja vem da posicao no arquivo, mas
        # data igual nos tres seria informacao a menos por nada.
        pc["quando"] = agora + timedelta(minutes=k)
        itens.append(item_xml(pc["nome"], pc["titulo"], pc["descricao"], pc["quando"]))

    caminho = os.path.join(RAIZ, arquivo)
    novo = escreve_no_feed(caminho, pecas[0]["board"], "\n".join(itens))

    try:
        ET.fromstring(novo)
    except ET.ParseError as e:
        morre(f"o feed sairia com XML quebrado ({e}). Nada foi escrito.")

    print(f"{len(pecas)} peca(s)  ->  {pecas[0]['board']}  ({arquivo})")
    for pc in pecas:
        print(f"  {pc['nome']}")
        print(f"    {pc['titulo']}")
    restam = sum(1 for l in linhas[pecas[-1]["indice"] + 1:]
                 if l.strip() and not l.lstrip().startswith("#"))
    unidade = "sabado(s)" if promo else "dias"
    print(f"  restam na fila: {restam}  "
          f"({restam // PECAS_POR_DIA} {unidade})")

    if simular:
        print("\n--simular: nada foi escrito.")
        return

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(novo)

    # De tras pra frente: apagar do inicio remexeria os indices seguintes.
    for pc in sorted(pecas, key=lambda x: x["indice"], reverse=True):
        del linhas[pc["indice"]]
    with open(FILA, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas).rstrip("\n") + "\n")

    with open(PUBLICADOS, "a", encoding="utf-8") as f:
        for pc in pecas:
            f.write(f"{pc['quando']:%Y-%m-%d %H:%M} | {pc['linha'].strip()}\n")

    # Mensagem de commit sai por aqui, sem apostrofo nem barra: texto da fila
    # interpolado direto num `run:` do workflow e injecao de shell.
    resumo = re.sub(r"[^A-Za-z0-9 ._&-]", "",
                    f"fileira de {len(pecas)} -> {pecas[0]['board']}")
    saida = os.environ.get("GITHUB_OUTPUT")
    if saida:
        with open(saida, "a", encoding="utf-8") as f:
            f.write(f"resumo={resumo}\n")


if __name__ == "__main__":
    main()
