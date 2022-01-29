#https://github.com/lidiaelopezh/NLP_GIA_FIEE.git

#//////////////////////////////////////////////////////////////////////////////#
#  Lista de librerias de apoyo
#//////////////////////////////////////////////////////////////////////////////#

import re
import os
from unicodedata import normalize
import fitz
from io import StringIO
from os import listdir


#/////////////////////////////////////////////////////////////////////////////////////////////#
#  Funciones para identificar el texto presente en el PDF e etiquetar por estilos de fuentes
#/////////////////////////////////////////////////////////////////////////////////////////////#

def itemgetter(*items):
    """
    Devuelve un objeto invocable que obtiene un elemento de su operando
    utilizando el método _getitem_() del operando. Si se especifican varios
    elementos, devuelve una tupla de valores de búsqueda.
    :param items: índice del elemento a invocar
    :return: elemento invocado
    """
    if len(items) == 1:
        item = items[0]

        def g(obj):
            return obj[item]
    else:
        def g(obj):
            return tuple(obj[item] for item in items)
    return g


def fonts(doc, granularity=True):
    """
    Emplea la libreria PyMuPDF para leer los archivos pdf, que lee
    pagina por pagina  el documento del tipo PDF y guarda su contenido en un block.
    Crea un diccionario con los diferentes estilos y atributos encontrados
    en los tramos de texto, ordenandolos según el número de tramos en el que
    fue usado cada uno de ellos.
    :param doc: documento PDF a procesar
    :param granularity: usada para diferenciar las letras por
                        atributos como 'fuente', 'flags' y 'color'
    :return: diccionario con los estilo de fuentes encontrados y las veces que fue usado,
             información de los estilos de fuente
    """
    pages = doc.pageCount

    styles = {}
    font_counts = {}

    for i in range(pages):
        page = doc.loadPage(i)
        blocks = page.getText("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # bloque con type = 0 contiene texto
                for l in b["lines"]:  # lista de lineas de texto
                    for s in l["spans"]:  # lista de tramos
                        # """font: nombre de la fuente (str)
                        # size: tamaño de fuente (float)
                        # flags: características de fuente (int)
                        # text: texto (str)"""
                        if granularity:
                            identifier = "{0}_{1}_{2}_{3}".format(s['size'], s['flags'], s['font'], s['color'])
                            styles[identifier] = {'size': s['size'], 'flags': s['flags'], 'font': s['font'],
                                                  'color': s['color']}
                        else:
                            identifier = "{0}".format(s['size'])
                            styles[identifier] = {'size': s['size'], 'font': s['font']}

                        font_counts[identifier] = font_counts.get(identifier, 0) + 1  # count the fonts usage

    font_counts = sorted(font_counts.items(), key=itemgetter(1), reverse=True)

    if len(font_counts) < 1:
        raise ValueError("Zero discriminating fonts found!")

    return font_counts, styles


def font_tags(font_counts, styles):
    """
    Creamos etiquetas para cada uno de los tamaños de fuente encontrados
    para poder diferenciar el tamaño de letra usado en los parrafos, titulos
    y la de los encabezdos de pagina, las cuales son <p>, <h> y <s> respectivamente.
    Además creamos etiquetas para identificar si la fuente esta en negrita o no (tipo de flag),
    usando <b> y <c> respectivamente.
    :param font_counts: lista de (font_size, count) = (tamaño de fuente , cantidad de tramos),
                        para todas las fuentes del documento.
    :param styles: todos los estilos de fuente del documento
    :return: diccionario de todas las etiquetas de los elementos (tramos) basadas
             en el tamaño y flag de la fuente.
    """
    p_style = styles[font_counts[0][0]]  # obtiene los estilos de fuentes con mayor cantidad
    p_size = p_style['size']  # obtiene los tamaños de fuente con mayor cantidad
    p_flag = p_style['flags']  # obtiene la caracteristica de fuente (cursiva, negrita, etc) con mayor cantidad

    # ordenando los tamaños de fuente de mayor a menor, para que podamos agregar el número entero correcto a cada etiqueta
    font_sizes = []
    for (font_info, count) in font_counts:
        font_size = font_info.split('_')[0]
        font_sizes.append(float(font_size))
    font_sizes.sort(reverse=True)

    # Detectando la variabilidad de flags y ordenandolos a la cantidad encontrada en un parrafo
    font_flags = []
    for (font_info, count) in font_counts:
        font_flag = font_info.split('_')[1]
        font_flags.append(float(font_flag))
    font_flags.sort(reverse=True)

    # Agregando las etiquetas considerando el tamaño de fuente
    idx = 0
    size_tag = {}
    for size in font_sizes:
        idx += 1
        if size == p_size:
            idx = 0
            size_tag[size] = '<p>'
        if size > p_size:
            size_tag[size] = '<h{0}>'.format(idx)
        elif size < p_size:
            size_tag[size] = '<s{0}>'.format(idx)

    # Agregando las etiquetas considerando el tipo de flag
    flag_tag = {}

    for flag in font_flags:
        if flag == p_flag:
            # idy = 0
            flag_tag[flag] = '<c>'
        if flag > p_flag:
            flag_tag[flag] = '<b>'
        else:
            flag_tag[flag] = '<c>'
    return size_tag, flag_tag


def headers_para(doc, size_tag, flag_tag):
    """
    Elimina los encabezados y párrafos
    Atribuyeno cada una de las etiquetas a un tipo de fuente las agregamos al texto
    extraido del documento PDF
    :param doc: documento PDF
    :param size_tag: etiqueta para cada tamaño de fuente (<h>, <p> o <s>)
    :param flag_tag: etiqueta para expresar si esta en negrita (<b>) o no (<c>)
    :return: lista de textos con las etiquetas agregadas a los tramos segun tipo de fuente
    """
    pages = doc.pageCount
    header_para = []  # encabezados y parrafos (lista)
    first = True  # del primer encabezado (operador booleano)
    previous_s = {}
    for i in range(pages):
        page = doc.loadPage(i)
        blocks = page.getText("dict")["blocks"]
        for b in blocks:  # itera a través de los bloques de texto
            if b['type'] == 0:  # en este caso el bloque contiene texto
                block_string = ""  # texto encontrado en el bloque
                for l in b["lines"]:  # itera a través de las líneas de texto
                    for s in l["spans"]:  # itera a través de los tramos de texto
                        if s['text'].strip():  # eliminando espacios en blanco
                            if first:
                                previous_s = s
                                first = False
                                block_string = size_tag[s['size']] + flag_tag[s['flags']] + " " + s['text']
                            else:
                                if s['size'] == previous_s['size']:  # coincide fuente con el intervalo previo
                                    if block_string and all((c == "|") for c in block_string):
                                        # block_string solo contiene pipe
                                        block_string = "|" + s['text']
                                    if block_string == "":
                                        # nuevo bloque ha comenzado, agrego etiqueta de tamaño
                                        block_string = " " + size_tag[s['size']] + flag_tag[s['flags']] + " " + s[
                                            'text']
                                    else:  # en el mismo bloque concatena cadenas
                                        block_string += " " + size_tag[s['size']] + flag_tag[s['flags']] + " " + s[
                                            'text']
                                else:
                                    header_para.append(block_string)
                                    block_string = " " + size_tag[s['size']] + flag_tag[s['flags']] + " " + s['text']
                                previous_s = s
                    # inicia nuevo bloque, indicando con un pipe
                    block_string += ""
                header_para.append(block_string)
    return header_para

def convertpdf_txt(filename):
    """
    Convierte el archivo PDF a texto plano, procesa el texto para dividirlas por resoluciones
    y finalmente da una lista de aquellas relacionadas a designaciones o ceses
    :param pdf_file_path: ruta del archivo PDF
    :param lista_palabras_a_corregir: ruta de lista de palabras adicionales a corregir
    :param lista_palabras_de_corrección: ruta de lista de palabras adicionales de corrección
    :return: lista de resoluciones que contienen designaciones y ceses
    """
    # Ingresar ruta del documento a analizar
    doc = fitz.open(filename)

    # Analizando el pdf en busqueda de tipos de fuentes y sus caracteristicas
    font_counts, styles = fonts(doc, granularity=True)
    # Etiquetas para el tamaño y estilo de letra
    size_tag, flag_tag = font_tags(font_counts, styles)
    # Etiquetas aplicadas en el texto del pdf
    texto = headers_para(doc, size_tag, flag_tag)
    doc.close()

    txt = texto
    txt_temp = []
    
    for line in txt:
      if line != '':
        txt_temp.append(line)
    return txt_temp
