# Evidências

Esta pasta reúne as provas do andamento do projeto pedidas na Fase 1.

| Evidência | Como gerar |
|---|---|
| Estrutura de pastas | Print da página inicial do repositório no GitHub ou saída de `tree /F` (Windows) |
| Histórico de commits | Print de `git log --oneline --graph` ou da aba *Commits* do GitHub |
| Participação dos integrantes | Print de `git shortlog -sn` ou da aba *Insights → Contributors* |
| Documentação versionada | Print do histórico de um arquivo de `docs/` (botão *History* no GitHub) |
| Ausência de segredos | Relatório de `gitleaks detect --source .` |

## Arquivos desta pasta

| Arquivo | Conteúdo |
|---|---|
| `testes-pytest.txt` | Resultado da suíte de testes automatizados |
| `bandit.txt` | Análise estática de segurança do código |
| `pip-audit.txt` | Verificação de vulnerabilidades conhecidas nas dependências |
| `ponta-a-ponta.txt` | Roteiro e resultado de um uso completo da API com o processador |
