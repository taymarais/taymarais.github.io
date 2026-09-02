#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta a tela Feed do painel: A GRADE, do jeito que a aba Criados desenha.

🔴 POR QUE ESTE ARQUIVO EXISTE. O painel e um artifact de ~7 MB com centenas de
imagens embutidas em base64. Editar isso a mao e como operar no escuro: em 02/09
uma troca de bloco engoliu 24 fileiras inteiras sem erro nenhum, e a autora so
descobriu porque OLHOU. A grade nao pode ser escrita a mao. Ela e DERIVADA de
`publicados.txt` + `fila.txt`, e este arquivo e a unica forma de deriva-la.

🔴 A GRADE E O INVERSO DA LINHA DO TEMPO, NOS DOIS SENTIDOS. A aba Criados mostra
o mais novo primeiro, em tres colunas. Entao quem sai PRIMEIRO na publicacao
aparece por ULTIMO na grade -- e isso vale tambem DENTRO da fileira: a primeira
peca da fila e a da direita. Inverter so as fileiras, e nao as pecas, desenha uma
grade que nao existe. Ver o `[::-1]` em `grade()`.

🔴 A LINHA DO TEMPO E publicados + fila, nessa ordem, e as duas TEM que fechar em
multiplo de 3. Se uma delas nao fechar, a fileira que cruza a linha d'agua fica
com pecas dos dois lados e a grade inteira desalinha a partir dali. O programa
para em vez de desenhar errado.

Uso:
    python3 pinterest/painel.py                 # resumo: o que sai, quando, e os ecos
    python3 pinterest/painel.py --grade         # o bloco HTML da tela Feed, no stdout
    python3 pinterest/painel.py --eco           # so a copy repetida, fileira por fileira
    python3 pinterest/painel.py --conferir X    # confere um painel.html contra as fontes

Precisa de Pillow, igual ao `publicar.py`.
"""

import argparse
import base64
import html
import io
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PINS = os.path.join(RAIZ, "pins")

FUSO = "America/Sao_Paulo"
INTERVALO_FILEIRA_H = 36        # tem que bater com o publicar.py
LARGURA, ALTURA = 190, 285      # miniatura: 2:3, o formato do pin
QUALIDADE = 72


def morre(msg):
    print("ERRO: " + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- as fontes
def vivas(caminho):
    """Linhas que valem: sem comentario, sem vazio."""
    with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f
                if l.strip() and not l.lstrip().startswith("#")]


def linha_do_tempo():
    """O que ja saiu, depois o que ainda vai sair. A ordem da PUBLICACAO."""
    pub = []
    for l in vivas("pinterest/publicados.txt"):
        p = [x.strip() for x in l.split("|")]
        if len(p) < 4:
            morre("linha de publicados.txt sem os 4 campos: " + l[:60])
        pub.append({"estado": "ar", "quando": p[0], "nome": p[1],
                    "tit": p[2], "des": p[3]})

    fila = []
    for i, l in enumerate(vivas("pinterest/fila.txt"), 1):
        if l.strip() == "PAUSA":
            continue                      # a pausa nao e peca, e um freio
        p = [x.strip() for x in l.split("|")]
        if len(p) < 4:
            morre("linha de fila.txt sem os 4 campos: " + l[:60])
        fila.append({"estado": "fila", "pos": i, "nome": p[0],
                     "tit": p[1], "des": p[2]})

    for nome, lista in (("publicados", pub), ("fila", fila)):
        if len(lista) % 3:
            morre("%s tem %d pecas, que nao fecha em fileiras de 3. "
                  "A grade desalinha a partir dai." % (nome, len(lista)))
    return pub, fila


def grade(pub, fila):
    """As fileiras como o perfil desenha: o inverso da linha do tempo, em trios."""
    tudo = (pub + fila)[::-1]
    return [tudo[i:i + 3] for i in range(0, len(tudo), 3)]


def proxima_data():
    """Quando a proxima fileira pode sair, pelas mesmas travas do publicar.py."""
    pub = vivas("pinterest/publicados.txt")
    if not pub:
        return "hoje"
    ultima = datetime.strptime(pub[-1].split("|")[0].strip(), "%Y-%m-%d %H:%M")
    ultima = ultima.replace(tzinfo=ZoneInfo(FUSO))
    livre = ultima + timedelta(hours=INTERVALO_FILEIRA_H)
    agora = datetime.now(ZoneInfo(FUSO))
    dia = max(livre, agora)
    if dia.date() == agora.date() and agora >= livre:
        return "hoje"
    return dia.strftime("%d/%m")


# ------------------------------------------------------- eco de copy na fileira
# Palavras que aparecem em quase toda copy: repetir "romance" nao e eco, e o
# genero. So conta o que a leitora leria como repeticao de verdade.
PARAR = set("""a an the and or but of to in on at for with from by is are was were
be been being this that these those it its he she they them him her his hers their
you your i me my we us our not no nor as if then than so too very just only own
same can will now had has have does did do one two three four all any both each few
more most other some such into out up down over about chapters here dual pov slow
burn romance celebrity hollywood book movie star night what who when where how why
anyone anybody nobody something anything nothing""".split())


def palavras(t):
    t = t.lower().split("chapters 1 and 2")[0]
    return set(w for w in re.findall(r"[a-z']{3,}", t) if w not in PARAR)


def ecos(fila):
    """Copy repetida dentro da mesma fileira.

    Dois pesos, porque doem diferente: FORTE e palavra repetida no TITULO, que e
    o que aparece embaixo do pin na grade. FRACO e so a etiqueta de genero
    repetida na descricao, que quase ninguem le. Tratar os dois igual faz a
    autora ignorar os dois.
    """
    achados = {}
    for r in range(len(fila) // 3):
        tres = fila[r * 3:(r + 1) * 3]
        tit = [palavras(x["tit"]) for x in tres]
        des = [palavras(x["des"]) for x in tres]
        forte, fraco = {}, {}
        for a in range(3):
            for b in range(a + 1, 3):
                for w in tit[a] & tit[b]:
                    forte.setdefault(w, set()).update([a, b])
                for w in des[a] & des[b]:
                    fraco.setdefault(w, set()).update([a, b])
        if forte or fraco:
            achados[r + 1] = {"forte": forte, "fraco": fraco, "pecas": tres}
    return achados


# ------------------------------------------------------------------ miniaturas
_CACHE = {}


def miniatura(nome):
    """base64 de uma miniatura 2:3. Video ganha quadro proprio: nenhum navegador
    aqui decodifica H.264, e sumir da grade seria pior que um bloco com o play."""
    arq = nome.split("#")[0]                      # `nome.jpg#r2` e reenvio
    if arq in _CACHE:
        return _CACHE[arq]
    from PIL import Image, ImageDraw

    caminho = os.path.join(PINS, arq)
    if not os.path.exists(caminho):
        morre("peca citada nas fontes mas ausente de pins/: " + arq)

    if arq.lower().endswith((".mp4", ".mov")):
        im = Image.new("RGB", (LARGURA, ALTURA), (18, 14, 12))
        d = ImageDraw.Draw(im)
        d.polygon([(80, 118), (80, 168), (122, 143)], fill=(212, 163, 150))
        d.text((52, 190), "VIDEO", fill=(201, 184, 167))
    else:
        im = Image.open(caminho).convert("RGB")
        im.thumbnail((LARGURA, ALTURA), Image.LANCZOS)

    b = io.BytesIO()
    im.save(b, "JPEG", quality=QUALIDADE, optimize=True)
    _CACHE[arq] = base64.b64encode(b.getvalue()).decode()
    return _CACHE[arq]


# ------------------------------------------------------------------- o desenho
def e(t):
    return html.escape(str(t), quote=True)


def celula(x, marca):
    nome = x["nome"]
    if x["estado"] == "ar":
        etiqueta = '<span class="tag t-ar">no ar</span>'
        classe = ""
        extra = " · publicado " + x["quando"][:10]
    else:
        etiqueta = '<span class="tag t-fila">na fila</span>'
        classe = (" e-still" if nome.startswith("still-") else
                  " e-eco" if marca == "forte" else
                  " e-brando" if marca == "fraco" else "")
        extra = ""
    if "#r2" in nome:
        etiqueta += '<span class="tag t-r2">reenvio</span>'

    # 🔴 O traco vai como CARACTERE. `data-c` cai em textContent na lupa, entao
    #    entidade HTML apareceria crua pra ela ("&mdash;").
    copy = "%s — %s %s%s" % (nome, x["tit"], x["des"], extra)
    rotulo = nome.split("#")[0].rsplit(".", 1)[0]
    return ('<div class="cel%s" tabindex="0" role="button" data-c="%s">'
            '<img src="data:image/jpeg;base64,%s" alt="">'
            '%s<span class="nm">%s</span></div>'
            % (classe, e(copy), miniatura(nome), etiqueta, e(rotulo)))


def aviso_html(ec):
    partes = []
    if ec["forte"]:
        partes.append("Palavra repetida no <b>t&iacute;tulo</b>: <b>%s</b>. "
                      "S&atilde;o as de moldura vermelha."
                      % "</b>, <b>".join(sorted(ec["forte"])))
    if ec["fraco"]:
        partes.append("Etiqueta de g&ecirc;nero repetida na descri&ccedil;&atilde;o: "
                      "<b>%s</b>. Pesa menos &mdash; a descri&ccedil;&atilde;o quase "
                      "n&atilde;o aparece na grade."
                      % "</b>, <b>".join(sorted(ec["fraco"])))
    return ('<div class="pl-alerta%s">%s Copy j&aacute; aprovada por voc&ecirc; '
            '&mdash; s&oacute; troco se voc&ecirc; mandar.</div>'
            % ("" if ec["forte"] else " br", " ".join(partes)))


def bloco_grade():
    pub, fila = linha_do_tempo()
    ec = ecos(fila)
    quando = proxima_data()

    # posicao na fila -> peso do eco, pra pintar a moldura
    marca = {}
    for r, a in ec.items():
        for w, ks in a["forte"].items():
            for k in ks:
                marca[a["pecas"][k]["pos"]] = "forte"
        for w, ks in a["fraco"].items():
            for k in ks:
                marca.setdefault(a["pecas"][k]["pos"], "fraco")

    o = ['<h2>A grade como vai ficar</h2>'
         '<p class="leg">Fileiras de 3, mais novo em cima &mdash; do jeito que a aba '
         'Criados desenha. A ordem &eacute; o <b>inverso da fila</b>: quem sai primeiro '
         'na publica&ccedil;&atilde;o aparece por &uacute;ltimo na grade. As <b>%d de '
         'cima</b> ainda v&atilde;o sair, as <b>%d de baixo</b> j&aacute; est&atilde;o no '
         'ar. <b>Clique em qualquer pe&ccedil;a</b> pra ver ela grande com a copy. '
         'Moldura <b class="mv">verde</b> &eacute; still, <b class="mr">vermelha</b> '
         '&eacute; palavra repetida no t&iacute;tulo, <b class="ma">amarela</b> &eacute; '
         's&oacute; etiqueta de g&ecirc;nero repetida.</p>' % (len(fila), len(pub))]

    # 🔴 A proxima fileira fica no TOPO, repetida. Ela e a unica coisa que a
    #    autora precisa toda vez, e no lugar certo da grade ela cai depois de 19
    #    fileiras de rolagem -- foi exatamente a reclamacao dela em 02/09.
    if fila:
        prox = fila[0:3][::-1]
        o.append('<div class="proxima"><div class="cab">'
                 '<span class="selo">a pr&oacute;xima a sair</span><b>sai %s</b>'
                 '<span class="obs">&mdash; a trava de %dh entre fileiras manda no '
                 'resto</span></div><div class="trio">%s</div></div>'
                 % (quando, INTERVALO_FILEIRA_H,
                    "".join(celula(x, marca.get(x.get("pos"))) for x in prox)))

    cortou = False
    for fileira in grade(pub, fila):
        cabeca = fileira[0]
        if cabeca["estado"] == "fila":
            r = (cabeca["pos"] + 2) // 3
            faixa = ('<span class="ja">a pr&oacute;xima a sair &middot; %s</span>' % quando
                     if r == 1 else '<span>%d&#170; a sair</span>' % r)
            o.append('<div class="faixa vai">%s<hr></div>' % faixa)
            o.append('<div class="trio">%s</div>'
                     % "".join(celula(x, marca.get(x.get("pos"))) for x in fileira))
            if r in ec:
                o.append(aviso_html(ec[r]))
        else:
            if not cortou:
                cortou = True
                o.append('<div class="linhadagua">'
                         '<span>daqui pra baixo j&aacute; est&aacute; no ar</span></div>')
            o.append('<div class="faixa"><span>no ar &middot; %s</span><hr></div>'
                     % cabeca["quando"][:10])
            o.append('<div class="trio">%s</div>'
                     % "".join(celula(x, None) for x in fileira))
    return "".join(o)


# -------------------------------------------------------------------- conferir
def conferir(caminho):
    """A tela Feed do painel bate com as fontes? Peca por peca, na ordem."""
    pub, fila = linha_do_tempo()
    esperado = [x["nome"].split("#")[0].rsplit(".", 1)[0]
                for x in (pub + fila)[::-1]]

    with open(caminho, encoding="utf-8") as f:
        doc = f.read()
    try:
        i = doc.index('<section id="feed">')
        j = doc.index("</section>", i)
    except ValueError:
        morre("nao achei a tela Feed em " + caminho)
    tela = doc[i:j]
    corpo = tela[tela.index('<div class="faixa'):]      # pula o bloco "a proxima"
    visto = [html.unescape(m) for m in re.findall(r'<span class="nm">([^<]+)</span>', corpo)]

    problemas = []
    if len(visto) != len(esperado):
        problemas.append("a grade tem %d pecas, as fontes tem %d"
                         % (len(visto), len(esperado)))
    for k, (a, b) in enumerate(zip(visto, esperado)):
        if a != b:
            problemas.append("posicao %d: a tela mostra %r, a fila diz %r" % (k + 1, a, b))
    if re.search(r'alt="[^"]+"', tela):
        problemas.append("miniatura com alt escrito: o navegador pinta esse texto "
                         "enquanto a imagem nao decodifica (o fantasma de 02/09)")

    if problemas:
        for p in problemas[:12]:
            print("  x  " + p)
        print("\n%d problema(s). O painel NAO bate com as fontes." % len(problemas))
        return 1
    print("  ok  %d pecas, na ordem exata das fontes" % len(visto))
    print("  ok  nenhuma miniatura pinta texto durante o decode")
    return 0


# ------------------------------------------------------------------------ main
def resumo():
    pub, fila = linha_do_tempo()
    print("no ar   %3d pecas em %2d fileiras" % (len(pub), len(pub) // 3))
    print("na fila %3d pecas em %2d fileiras" % (len(fila), len(fila) // 3))
    print("grade   %3d pecas em %2d fileiras" % (len(pub) + len(fila),
                                                 (len(pub) + len(fila)) // 3))
    print("\na proxima fileira sai %s:" % proxima_data())
    for x in fila[:3]:
        print("   %d. %s" % (x["pos"], x["nome"]))
    ec = ecos(fila)
    print("\ncopy repetida em %d fileira(s): %s"
          % (len(ec), ", ".join(str(r) for r in sorted(ec)) or "nenhuma"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grade", action="store_true",
                    help="escreve o bloco HTML da tela Feed no stdout")
    ap.add_argument("--eco", action="store_true",
                    help="lista a copy repetida, fileira por fileira")
    ap.add_argument("--conferir", metavar="PAINEL.HTML",
                    help="confere um painel salvo contra publicados.txt + fila.txt")
    a = ap.parse_args()

    if a.conferir:
        sys.exit(conferir(a.conferir))
    if a.grade:
        sys.stdout.write(bloco_grade())
        return
    if a.eco:
        _, fila = linha_do_tempo()
        ec = ecos(fila)
        if not ec:
            print("nenhuma copy repetida.")
            return
        for r in sorted(ec):
            print("fileira %d" % r)
            for peso in ("forte", "fraco"):
                for w, ks in sorted(ec[r][peso].items()):
                    quais = ", ".join(ec[r]["pecas"][k]["nome"] for k in sorted(ks))
                    print("   %-6s %-12s %s" % (peso, w, quais))
        return
    resumo()


if __name__ == "__main__":
    main()
