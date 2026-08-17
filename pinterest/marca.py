#!/usr/bin/env python3
"""Carimba `TAY MARAIS` numa foto, no ponto mais liso da borda de cima ou de baixo.

A especificacao e da autora (14/08/2026), e cada item dela e conserto de um erro
medido, nao gosto:

- **Texto `TAY MARAIS`, nao o titulo do livro.** As fotos do casal atravessam a
  saga inteira: carimbar o titulo do Livro 1 envelhece a peca no dia em que o
  Livro 2 sair, e o nome da autora e o que alguem digita pra achar tudo.
- **Montserrat SemiBold, nao Playfair.** A Playfair e didone: o traco fino
  desaparece sobre foto no corpo pequeno. Traco uniforme le no mesmo tamanho.
- **~1,5% da altura, versalete, espacado. NUNCA aumentar.** Legibilidade se compra
  com fonte e halo, nao com tamanho. A versao legivel ficou MENOR que a ilegivel.
- **Halo de luminancia oposta.** E o que faz texto pequeno sobreviver sobre foto
  sem escurecer nem crescer.
- **Desliza pela borda e para no ponto mais liso de todos.** Canto fixo nao
  escala: em 182 fotos diferentes a quina cai em cima de textura e a marca vira
  sujeira. Aconteceu duas vezes — no vao da escada e no cabo da lampada, que
  passava dentro da caixa e a quina "venceu" mesmo assim. Deslizando, o ruido da
  area escolhida caiu de 54 pra 3,5 na mesma foto.
- **A foto limpa e a fonte, a marcada e a saida.** O carimbo se aplica na hora de
  publicar, nunca no arquivo guardado: marca gravada no original e irreversivel, e
  mudar de ideia sobre fonte ou texto obrigaria a refazer as 182 na mao. Mesma
  relacao do manuscrito com o EPUB.
- **Arte de quote nao recebe carimbo:** ja traz o nome do livro.

Uso:
    python3 pinterest/marca.py pins/foto.jpg                 # -> pins/marcadas/
    python3 pinterest/marca.py pins/foto.jpg --saida x.jpg
    python3 pinterest/marca.py pins/*.jpg --contato          # folha de contato
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))

TEXTO = "TAY MARAIS"
FONTE = os.path.join(AQUI, "fontes", "Montserrat-SemiBold.ttf")

CORPO = 0.015          # altura da letra, fracao da altura da foto
RESPIRO = 0.045        # distancia da borda, fracao da altura
ESPACO = 0.28          # letter-spacing, fracao do corpo
HALO = 0.0016          # raio do halo, fracao da altura
CLARO = (234, 229, 222)    # creme da marca, pra fundo escuro
ESCURO = (26, 18, 16)      # quase-preto da marca, pra fundo claro
PASSOS = 24            # janelas testadas por borda ao deslizar


def _fonte(tamanho):
    try:
        f = ImageFont.truetype(FONTE, tamanho)
    except OSError:
        sys.exit(f"Fonte nao encontrada em {FONTE}. Rodar o workflow "
                 f"'Buscar fonte' uma vez pra ela entrar no repo.")
    try:                                   # se vier variavel, fixa no SemiBold
        f.set_variation_by_name("SemiBold")
    except (OSError, AttributeError):
        pass
    return f


def largura_espacada(fonte, texto, espaco):
    """Pillow nao tem letter-spacing: a largura e a soma dos glifos + o espaco."""
    total = sum(fonte.getlength(c) for c in texto)
    return total + espaco * (len(texto) - 1)


def desenha_espacado(draw, xy, texto, fonte, espaco, cor):
    x, y = xy
    for c in texto:
        draw.text((x, y), c, font=fonte, fill=cor)
        x += fonte.getlength(c) + espaco


def ruido(img, caixa):
    """Quanto a area 'briga' com texto: desvio padrao da luminancia, em cinza.

    E a medida certa porque o que mata a marca nao e a area ser clara ou escura,
    e ser IRREGULAR — cabo, grade, folhagem, textura de parede.
    """
    corte = img.crop(caixa).convert("L")
    n = corte.width * corte.height
    if not n:
        return float("inf")
    px = list(corte.getdata())
    media = sum(px) / n
    return (sum((p - media) ** 2 for p in px) / n) ** 0.5


def luminancia(img, caixa):
    corte = img.crop(caixa).convert("L")
    px = list(corte.getdata())
    return sum(px) / len(px) if px else 128


def melhor_lugar(img, larg, alt):
    """Desliza pela borda de cima e de baixo e devolve a janela mais LISA.

    Canto fixo nao escala, e testar so as quatro quinas tambem nao: a quina
    "vence" mesmo com um cabo passando dentro dela, porque nada esta competindo.
    """
    W, H = img.size
    respiro = int(RESPIRO * H)
    ys = [respiro, H - respiro - alt]
    livre = W - 2 * respiro - larg
    if livre <= 0:                      # foto estreita: centraliza e aceita
        return (max(0, (W - larg) // 2), ys[-1])

    melhor, nota = None, float("inf")
    for y in ys:
        for i in range(PASSOS):
            x = respiro + round(livre * i / (PASSOS - 1))
            caixa = (x, y, x + larg, y + alt)
            r = ruido(img, caixa)
            if r < nota:
                melhor, nota = (x, y), r
    return melhor


def marca(caminho, saida=None):
    img = Image.open(caminho)
    img = img.convert("RGB") if img.mode != "RGB" else img.copy()
    W, H = img.size

    fonte = _fonte(max(8, round(CORPO * H)))
    espaco = ESPACO * CORPO * H
    larg = round(largura_espacada(fonte, TEXTO, espaco))
    # A caixa do glifo maiusculo, nao a metrica da fonte: a metrica inclui
    # descendente, que `TAY MARAIS` nao tem, e a area medida sairia alta demais.
    cima, baixo = fonte.getbbox(TEXTO)[1], fonte.getbbox(TEXTO)[3]
    alt = round(baixo - cima)

    x, y = melhor_lugar(img, larg, alt)
    escura = luminancia(img, (x, y, x + larg, y + alt)) < 128
    cor, cor_halo = (CLARO, ESCURO) if escura else (ESCURO, CLARO)

    # Halo: o texto e desenhado numa camada propria, borrado, e volta por baixo.
    # Sombra dura marcaria a foto; o borrado so levanta o contraste local.
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    desenha_espacado(d, (x, y - cima), TEXTO, fonte, espaco, cor_halo + (190,))
    camada = camada.filter(ImageFilter.GaussianBlur(max(1.0, HALO * H)))
    img = Image.alpha_composite(img.convert("RGBA"), camada)

    d = ImageDraw.Draw(img)
    desenha_espacado(d, (x, y - cima), TEXTO, fonte, espaco, cor + (255,))

    if saida is None:
        pasta = os.path.join(os.path.dirname(caminho), "marcadas")
        os.makedirs(pasta, exist_ok=True)
        saida = os.path.join(pasta, os.path.basename(caminho))
    img.convert("RGB").save(saida, quality=92, subsampling=0)
    return saida, (x, y), ("escura" if escura else "clara")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fotos", nargs="+")
    p.add_argument("--saida", help="arquivo de saida (so com uma foto)")
    p.add_argument("--contato", metavar="ARQ",
                   help="junta as marcadas numa folha de contato pra ela olhar")
    a = p.parse_args()

    feitas = []
    for f in a.fotos:
        if os.path.basename(f).startswith("quote-"):
            print(f"pulando {os.path.basename(f)}: arte de quote ja traz o nome do livro")
            continue
        saida, (x, y), fundo = marca(f, a.saida if len(a.fotos) == 1 else None)
        print(f"{os.path.basename(f)}  ->  {saida}  (borda {'de cima' if y < 200 else 'de baixo'}, "
              f"x={x}, area {fundo})")
        feitas.append(saida)

    if a.contato and feitas:
        largura, col = 520, 3
        linhas = (len(feitas) + col - 1) // col
        fichas = [Image.open(f) for f in feitas]
        alt = max(round(largura * i.height / i.width) for i in fichas)
        folha = Image.new("RGB", (largura * col, alt * linhas), (18, 18, 18))
        for i, im in enumerate(fichas):
            im = im.resize((largura, round(largura * im.height / im.width)))
            folha.paste(im, ((i % col) * largura, (i // col) * alt))
        folha.save(a.contato, quality=90)
        print(f"folha de contato: {a.contato}")


if __name__ == "__main__":
    main()
