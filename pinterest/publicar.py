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

Por isso o cron roda 3x por dia (09h, 12h, 15h) e cada execucao consome uma linha.
Fileira de 3 = um dia, com teto movel de 3 fileiras a cada 7 dias.

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
BOARD_ATIVO = "Adam & Madeleine"

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
    """As PECAS_POR_FILEIRA primeiras linhas vivas da fila, em ordem.

    🔴 SO DEVOLVE FILEIRA COMPLETA. Meia fileira e o unico jeito de torcer a
    grade (a aba Criados e fluxo continuo de tres colunas, entao publicar 2 num
    dia empurra tudo que esta embaixo uma casa, pra sempre). Qualquer coisa que
    impeca as tres -- PAUSA no meio, fila curta -- devolve `alvos` VAZIA e o
    motivo em `parada`. Nada sai pela metade.
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
    for i, l in vivas[:PECAS_POR_FILEIRA]:
        if l.strip().upper().startswith(PAUSA):
            return linhas, [], (
                f"A PAUSA esta na posicao {len(alvos) + 1} da fileira: sairiam "
                f"{len(alvos)} pecas de {PECAS_POR_FILEIRA}, e meia fileira "
                f"desalinha tudo que esta embaixo. Nada publicado. Apagar a "
                f"linha {PAUSA!r} de {FILA} pra fileira sair inteira.")
        alvos.append((i, l))
    if len(alvos) < PECAS_POR_FILEIRA:
        return linhas, [], (
            f"So restam {len(alvos)} linha(s) viva(s) e a fileira precisa de "
            f"{PECAS_POR_FILEIRA}. Meia fileira desalinha a grade, entao nada "
            f"sai ate a fila voltar ao multiplo de 3.")
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
PECAS_POR_FILEIRA = 3      # a fileira tem tres pecas, nunca quatro
SEM_MARCA = ("quote-", "dialogue-", "still-")  # artes que ja trazem o titulo dentro
# 🔴 `still-` entrou em 02/09: o carimbo desliza pela borda de baixo, que e exatamente
#    onde mora a legenda do segundo frame do still. Aprovado por ela no briefing de 30/08.
#    O prefixo proprio tambem E a medida: o utm_content e o nome do arquivo, e em 30 dias
#    ele compara `still-` contra `quote-` e `dialogue-`.
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

    linhas, alvos, parada = proxima_fileira()
    if parada:
        print(parada)
        return

    agora = datetime.now(ZoneInfo(FUSO))
    ultima = max(datas_publicadas(), default=None)
    saidas_hoje = publicados_hoje(agora.date())

    # 🔴 UMA FILEIRA POR DIA. Antes o teto era "tres pecas por dia" porque cada
    # execucao soltava uma; agora a fileira sai inteira numa execucao so, entao
    # qualquer peca publicada hoje ja significa fileira feita.
    if not forcar and saidas_hoje:
        print(f"A fileira de hoje ja saiu ({saidas_hoje} pecas). "
              f"A proxima e amanha.")
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
        if horas < INTERVALO_FILEIRA_H:
            print(f"A fileira anterior saiu ha {horas:.0f}h. Minimo de "
                  f"{INTERVALO_FILEIRA_H}h entre fileiras.")
            return

    # 🔴 TETO MOVEL: no maximo 3 fileiras a cada 7 dias.
    # A cadencia e dela, decidida em 15/08 e reafirmada em 17/08: *"uma por dia
    # e demais, vai gastar antes de eu ter banco de mais"*. O gargalo do sistema
    # nao e publicar, e PRODUZIR ARTE. Janela movel, e nao dia fixo da semana,
    # porque dia fixo transforma qualquer tropeco em espera de dois dias.
    recentes = {d.date() for d in datas_publicadas()
                if (agora - d).days < JANELA_DIAS}
    if not forcar and len(recentes) >= FILEIRAS_POR_SEMANA:
        print(f"Ja sairam {len(recentes)} fileiras nos ultimos {JANELA_DIAS} "
              f"dias, que e o teto ({FILEIRAS_POR_SEMANA}/semana). A proxima "
              f"sai quando a mais antiga da janela vencer.")
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
        if board != BOARD_ATIVO:
            morre(f"a linha manda pro board {board!r}, mas a rota ativa e "
                  f"{BOARD_ATIVO!r} e TODA a fila tem que sair por ela.\n"
                  f"Mudar a rota e mudar BOARD_ATIVO, de proposito, depois de "
                  f"ler o porque no maquina-de-pin.md.")
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

    print(f"Fileira de {len(pecas)} pecas  ->  {pecas[0]['board']}  ({arquivo})")
    for pc in pecas:
        print(f"  {pc['nome']}")
        print(f"    {pc['titulo']}")
    restam = sum(1 for l in linhas[pecas[-1]["indice"] + 1:]
                 if l.strip() and not l.lstrip().startswith("#"))
    print(f"  restam na fila: {restam}  ({restam // PECAS_POR_FILEIRA} fileiras)")

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
