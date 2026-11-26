"""Comando demo: sobe os três processos e encerra todos quando um deles para."""
import subprocess

from sentineltrade import cli


class ProcessoFalso:
    def __init__(self, args):
        self.args, self.encerrado = args, False

    def poll(self):
        return 1 if self.args[-1] == "api" or self.encerrado else None   # a API "cai" logo de início

    def terminate(self):
        self.encerrado = True

    def wait(self, timeout=None):
        return 0


def test_demo_sobe_os_tres_processos_e_encerra_os_demais(monkeypatch, config):
    criados = []
    monkeypatch.setattr(subprocess, "Popen", lambda args: criados.append(ProcessoFalso(args)) or criados[-1])
    monkeypatch.setattr(cli, "obter_configuracao", lambda: config)
    assert cli.main(["demo"]) == 0
    assert [p.args[-1] for p in criados] == ["processar", "api", "bff"]
    assert all(p.args[1:3] == ["-m", "sentineltrade.cli"] for p in criados)
    assert criados[0].encerrado and criados[2].encerrado
