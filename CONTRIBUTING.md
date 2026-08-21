# Contribuindo

Contribuições pequenas, bem explicadas e testadas são bem-vindas. Use dados sintéticos em exemplos,
testes e relatos de erro.

## Preparar o ambiente de desenvolvimento

1. Crie um fork no GitHub.
2. Copie a URL HTTPS apresentada no seu fork.
3. Clone o fork e entre na pasta.
4. Instale o ambiente:

```text
uv sync --python 3.12 --extra dev --frozen
uv run playwright install chromium
```

## Validar a mudança

```text
uv lock --check
uv run ruff check .
uv run bandit -q -r src app_pages app.py
uv run pip-audit
uv run pytest
uv build
```

Ao abrir o pull request:

- explique o problema, a solução e os testes;
- mantenha o escopo pequeno;
- atualize a documentação e os avisos de licença;
- preserve a candidatura manual e a separação entre texto e layout;
- remova credenciais, dados pessoais, vagas copiadas e arquivos locais.

## Novos portais

Documente páginas públicas, termos, `robots.txt`, limites e comportamento de falha. Restrinja o
plugin a domínios oficiais e adicione fixtures sintéticas. Login, CAPTCHA, cookies e sessão
persistente ficam fora da integração.

## Dependências

Uma nova dependência precisa ter finalidade clara, licença compatível, versão limitada e uma revisão
do impacto em segurança. Atualize `uv.lock` e `THIRD_PARTY_NOTICES.md`.

## Segurança

Falhas de segurança seguem o canal privado descrito em [SECURITY.md](SECURITY.md). Evite issues,
pull requests e demonstrações públicas com detalhes exploráveis.
