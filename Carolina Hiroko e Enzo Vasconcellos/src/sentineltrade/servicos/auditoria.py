"""Trilha de auditoria imutável com hash encadeado (RF-11, RNF-20, RNF-22, RN-14).

Cada registro guarda o hash do anterior; alterar qualquer registro quebra a cadeia, o que a
verificação detecta. O banco também impede UPDATE e DELETE (gatilhos em schema.sql).
O registro é feito na mesma transação da operação: se não puder ser gravado, a operação é desfeita.
"""
from __future__ import annotations

import hashlib
import json

from ..dominio.enums import Perfil
from ..logs import correlation_id, mascarar
from ..persistencia.repositorios import RegistroAuditoria
from ..persistencia.sqlite import para_texto
from ..relogio import Relogio
from .comum import exigir_perfil

HASH_INICIAL = "0" * 64


def calcular_hash(hash_anterior: str, data_hora: str, ator: str, acao: str, entidade: str,
                  entidade_id: str | None, resultado: str, detalhes: str | None, correlacao: str) -> str:
    conteudo = json.dumps([hash_anterior, data_hora, ator, acao, entidade, entidade_id, resultado, detalhes,
                           correlacao], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


class ServicoAuditoria:
    def __init__(self, fabrica_uow, relogio: Relogio) -> None:
        self._uow = fabrica_uow
        self._relogio = relogio

    def registrar(self, uow, *, ator: str, acao: str, entidade: str, entidade_id: object | None,
                  resultado: str, detalhes: dict | None = None) -> None:
        agora = self._relogio.agora()
        texto_detalhes = (json.dumps(mascarar(detalhes), ensure_ascii=False, default=str)[:500]
                          if detalhes else None)
        anterior = uow.auditoria.ultimo_hash() or HASH_INICIAL
        id_texto = None if entidade_id is None else str(entidade_id)
        correlacao = correlation_id.get()[:64]
        data_texto = para_texto(agora)
        hash_novo = calcular_hash(anterior, data_texto, ator[:64], acao[:64], entidade[:32], id_texto,
                                  resultado[:64], texto_detalhes, correlacao)
        uow.auditoria.inserir(RegistroAuditoria(None, agora, ator[:64], acao[:64], entidade[:32], id_texto,
                                                resultado[:64], texto_detalhes, correlacao, anterior, hash_novo))

    # ---- consulta (Auditor) ---------------------------------------------------------------
    def listar(self, usuario, *, entidade: str | None, entidade_id: str | None, limite: int, deslocamento: int):
        exigir_perfil(usuario, Perfil.AUDITOR)
        with self._uow(somente_leitura=True) as uow:
            return uow.auditoria.listar(entidade=entidade, entidade_id=entidade_id, limite=limite,
                                        deslocamento=deslocamento)

    def verificar_cadeia(self, usuario=None, *, exigir=True) -> tuple[bool, int | None, int]:
        """Recalcula a cadeia. Devolve (íntegra, id do primeiro registro inválido, total verificado)."""
        if exigir:
            exigir_perfil(usuario, Perfil.AUDITOR)
        with self._uow(somente_leitura=True) as uow:
            registros = uow.auditoria.todos_em_ordem()
        anterior = HASH_INICIAL
        for r in registros:
            esperado = calcular_hash(anterior, para_texto(r.data_hora), r.ator, r.acao, r.entidade, r.entidade_id,
                                     r.resultado, r.detalhes, r.correlation_id)
            if r.hash_anterior != anterior or r.hash != esperado:
                return False, r.id, len(registros)
            anterior = r.hash
        return True, None, len(registros)
