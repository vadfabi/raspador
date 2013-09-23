#coding: utf-8

"""
Os fields são simples extratores de dados baseados em expressões regulares.

Ao confrontar uma linha recebida para análise com sua expressão regular, o
campo verifica se há grupos de dados capturados, e então pode realizar algum
processamento e validações nestes dados. Se o campo considerar os dados
válidos, retorna o(s) dado(s). """

import re
from datetime import datetime
import collections


class BaseField(object):
    """
    Contém lógica de processamento para extrair dados através de expressões
    regulares, além de prover métodos utilitários que podem ser sobrescritos
    para customizações no tratamento dos dados.

    O comportamento do Campo pode ser ajustado através de diversos parâmetros:

    mascara

        O requisito mínimo para um campo é uma máscara em expressão regular,
        onde deve-se especificar um grupo para captura::

            >>> s = "02/01/2013 10:21:51           COO:022734"
            >>> campo = BaseField(mascara=r'COO:(\d+)')
            >>> campo.parse_block(s)
            '022734'

        O parâmetro mascara é o único posicional, e deste modo, seu nome pode
        ser omitido::

            >>> s = "02/01/2013 10:21:51           COO:022734"
            >>> campo = BaseField(r'COO:(\d+)')
            >>> campo.parse_block(s)
            '022734'


    ao_atribuir

        Recebe um callback para tratar o valor antes de ser retornado pelo
        campo.

            >>> s = "02/01/2013 10:21:51           COO:022734"
            >>> def dobro(valor):
            ...     return int(valor) * 2
            ...
            >>> campo = BaseField(r'COO:(\d+)', ao_atribuir=dobro)
            >>> campo.parse_block(s)  # 45468 = 2 x 22734
            45468

    grupos

        Permite escolher quais grupos capturados o campo deve processar como
        dados de entrada, utilizado para expressões regulares que utilizam
        grupos para correspondência da expressão regular, mas que apenas parte
        destes grupos possui informação útil.

        Pode-se informar um número inteiro, que será o índice do grupo,
        inicando em 0::

            >>> s = "Contador de Reduções Z:                     1246"
            >>> campo = BaseField(r'Contador de Reduç(ão|ões) Z:\s*(\d+)', \
                grupos=1, ao_atribuir=int)
            >>> campo.parse_block(s)
            1246

        Ou uma lista de inteiros::

            >>> s = "Data do movimento: 02/01/2013 10:21:51"
            >>> c = BaseField(r'^Data .*(movimento|cupom): (\d+)/(\d+)/(\d+)',\
                grupos=[1, 2, 3])
            >>> c.parse_block(s)
            ['02', '01', '2013']


    default

        Valor que será utilizado no :py:class:`~raspador.parser.Parser`
        , quando o campo não retornar valor após a análise das
        linhas recebidas.


    lista

        Quando especificado, retorna o valor como uma lista::

            >>> s = "02/01/2013 10:21:51           COO:022734"
            >>> campo = BaseField(r'COO:(\d+)', lista=True)
            >>> campo.parse_block(s)
            ['022734']

        Por convenção, quando um campo retorna uma lista, o
        :py:class:`~raspador.parser.Parser` acumula os valores
        retornados pelo campo.
    """
    def __init__(self, mascara=None, **kwargs):
        self.default = kwargs.get('default')
        self.lista = kwargs.get('lista', False)
        self.mascara = mascara
        self.ao_atribuir = kwargs.get('ao_atribuir')
        self.grupos = kwargs.get('grupos', [])

        if self.ao_atribuir and \
                not isinstance(self.ao_atribuir, collections.Callable):
            raise TypeError('O callback ao_atribuir não é uma função.')

        if not hasattr(self.grupos, '__iter__'):
            self.grupos = (self.grupos,)

        self._iniciar()

    @property
    def _metodo_busca(self):
        return self.mascara.findall

    def _iniciar(self):
        "Ponto para inicialização especial nas classes descendentes"
        pass

    def assign_parser(self, parser):
        """
        Recebe uma referência fraca de
        :py:class:`~raspador.parser.Parser`
        """
        self.parser = parser

    def _resultado_valido(self, valor):
        return bool(valor)

    def _converter(self, valor):
        if self.grupos:
            if len(valor) == 1:   # não é desejado uma tupla,
                valor = valor[0]  # se houver apenas um item
            tamanho = len(valor)
            valor = [valor[i] for i in self.grupos if i < tamanho]

        if len(valor) == 1:   # não é desejado uma tupla,
            valor = valor[0]  # se houver apenas um item
        return valor

    def to_python(self, valor):
        """
        Converte o valor recebido palo parser para o tipo de dado
        nativo do python
        """
        return valor

    @property
    def mascara(self):
        return self._mascara

    @mascara.setter
    def mascara(self, valor):
        self._mascara = re.compile(valor, re.UNICODE) if valor else None

    def anexar_na_classe(self, cls, name):
        self.cls = cls

    def parse_block(self, linha):
        if self.mascara:
            valor = self._metodo_busca(linha)
            if self._resultado_valido(valor):
                valor = self._converter(valor)
                valor = self.to_python(valor)
                if self.ao_atribuir:
                    valor = self.ao_atribuir(valor)
                if valor is not None and self.lista \
                        and not isinstance(valor, list):
                    valor = [valor]
                return valor


class StringField(BaseField):
    def to_python(self, valor):
        return str(valor).strip()


class FloatField(BaseField):
    def to_python(self, valor):
        valor = valor.replace('.', '')
        valor = valor.replace(',', '.')
        return float(valor)


class IntegerField(BaseField):
    def to_python(self, valor):
        return int(valor)


class BooleanField(BaseField):
    """
    Retorna verdadeiro se a Regex bater com uma linha completa, e
    se ao menos algum valor for capturado.
    """
    def _iniciar(self):
        self.default = False

    @property
    def _metodo_busca(self):
        return self.mascara.match

    def _converter(self, valor):
        res = valor.groups() if valor else False
        return super(BooleanField, self)._converter(res)

    def _resultado_valido(self, valor):
        return valor and (valor.groups())

    def to_python(self, valor):
        return bool(valor)


class DateField(BaseField):
    """
    Campo que mantém dados no formato de data,
    representado em Python por datetine.date.

    Formato:
        Veja http://docs.python.org/library/datetime.html para detalhes.
    """

    def __init__(self, mascara=None, **kwargs):
        """
        formato='%d/%m/%Y'
        """
        super(DateField, self).__init__(mascara=mascara, **kwargs)
        self.formato = kwargs.get('formato', '%d/%m/%Y')

    def to_python(self, valor):
        return datetime.strptime(valor, self.formato).date()


class DateTimeField(BaseField):
    """
    Campo que mantém dados no formato de data/hora,
    representado em Python por datetine.datetime.

    Formato:
        Veja http://docs.python.org/library/datetime.html para detalhes.
    """

    def __init__(self, mascara=None, **kwargs):
        """
        formato='%d/%m/%Y %H:%M:%S'
        """
        super(DateTimeField, self).__init__(mascara=mascara, **kwargs)
        self.formato = kwargs.get('formato', '%d/%m/%Y %H:%M:%S')

    def to_python(self, valor):
        return datetime.strptime(valor, self.formato)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
