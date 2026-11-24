"""Controles operacionais da IA online: limite local de chamadas (custo), cache de respostas e registro de auditoria."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .errors import IAUsoExcedidoError


class LimiteUso:
    """Janela deslizante de 1 hora: protege contra laços/cliques repetidos que gerariam custo inesperado."""

    def __init__(self, max_por_hora: int, relogio: Callable[[], float] = time.monotonic):
        self.max, self._relogio, self._fila, self._lock = max_por_hora, relogio, deque(), threading.Lock()

    def _limpar(self, agora: float) -> None:
        while self._fila and agora - self._fila[0] >= 3600:
            self._fila.popleft()

    def registrar(self) -> None:
        with self._lock:
            agora = self._relogio()
            self._limpar(agora)
            if len(self._fila) >= self.max:
                espera = int(3600 - (agora - self._fila[0])) + 1
                raise IAUsoExcedidoError(f"Limite local de {self.max} chamadas por hora atingido.",
                                         sugestao="Aguarde ou aumente ESG_IA_MAX_CHAMADAS_HORA (atenção ao custo no provedor).", retry_after=espera)
            self._fila.append(agora)

    def usadas(self) -> int:
        with self._lock:
            self._limpar(self._relogio())
            return len(self._fila)


class CacheIA:
    """Cache em disco (JSON) por hash da requisição: repetir a mesma análise não gera nova cobrança e torna a demonstração reproduzível."""

    def __init__(self, pasta: Path, ativo: bool = True):
        self.pasta, self.ativo = Path(pasta), ativo

    @staticmethod
    def chave(*partes) -> str:
        return hashlib.sha256("\x1f".join(str(p) for p in partes).encode("utf-8")).hexdigest()

    def obter(self, chave: str) -> Optional[dict]:
        arq = self.pasta / f"{chave}.json"
        if not self.ativo or not arq.is_file():
            return None
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None                                           # arquivo corrompido = como se não existisse

    def salvar(self, chave: str, valor: dict) -> None:
        if not self.ativo:
            return
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / f"{chave}.json").write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


class AuditoriaIA:
    """Registro (JSONL) de toda geração: quem/qual modelo/qual prompt/custo em tokens/fidelidade — governança do uso de IA."""

    def __init__(self, caminho: Path):
        self.caminho, self._lock = Path(caminho), threading.Lock()

    def registrar(self, registro: dict) -> None:
        registro = {"em": datetime.now().isoformat(timespec="seconds"), **registro}
        with self._lock:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def ler(self, limite: int = 50) -> list:
        if not self.caminho.is_file():
            return []
        itens = []
        for linha in self.caminho.read_text(encoding="utf-8").splitlines():
            try:
                itens.append(json.loads(linha))
            except ValueError:
                continue
        return itens[-limite:][::-1]                              # mais recentes primeiro


class ClienteMedido:
    """Envolve um cliente de LLM: cada chamada passa pelo limite local e é contada."""

    def __init__(self, cliente, limite: LimiteUso):
        self._c, self._limite, self.chamadas = cliente, limite, 0

    @property
    def provedor(self):
        return self._c.provedor

    @property
    def modelo(self):
        return self._c.modelo

    def gerar(self, sistema, usuario, max_tokens=None):
        self._limite.registrar()
        self.chamadas += 1
        return self._c.gerar(sistema, usuario, max_tokens)
