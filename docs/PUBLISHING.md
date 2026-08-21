# Publicação segura no GitHub

Esta lista documenta a preparação e a manutenção de uma versão pública.

## 1. Criar o repositório do Q.U.A.T.I.

A publicação oficial usa o endereço
<https://github.com/redp4w/quati-buscador-de-vagas-BR>. Um repositório novo
é preferível a transformar o JobHunterBR porque o nome do pacote, a navegação, o instalador, os
dados locais e toda a identidade já pertencem ao Q.U.A.T.I. O repositório antigo pode ser arquivado
depois que o ZIP da nova versão for testado; excluí-lo é opcional e remove também issues, ações e
links antigos.

O repositório foi criado sem README, licença ou `.gitignore` gerados pelo GitHub, pois esses arquivos
já existem no projeto. O aplicativo não altera nem publica conteúdo no GitHub.

Antes de publicar uma versão:

- confirme `Homepage`, `Repository`, `Issues` e `Documentation` em `[project.urls]`;
- confirme que o slug oficial permanece `quati-buscador-de-vagas-BR`;
- use a mesma URL nas notas da versão e nos perfis oficiais;
- confira todos os links relativos do README;
- evite manter endereços fictícios em arquivos públicos.

## 2. Aplicar a identidade

- Descrição: **Central local e open source para buscar vagas públicas no Brasil, comparar
  compatibilidade e preparar currículos para candidatura manual.**
- Imagem social: `docs/assets/github-social-preview.png`.
- Tópicos: `jobs`, `brazil`, `python`, `streamlit`, `playwright`, `privacy`, `sqlite`,
  `resume-builder`.
- Página inicial: README com a assinatura oficial.

As instruções completas estão em [BRAND.md](BRAND.md).

## 3. Limpar dados locais

1. Abra **Meu perfil → Dados pessoais → Apagar dados locais e começar do zero**.
2. Encerre o Q.U.A.T.I.
3. Confirme que `data` está vazia ou contém somente arquivos ignorados e descartáveis.
4. Revise `.env.example`; ele deve conter apenas nomes e exemplos públicos.

Evite forçar a inclusão de qualquer arquivo ignorado.

## 4. Revisar o conteúdo versionado

Antes do primeiro commit, procure:

- nomes, e-mails, telefones e endereços reais;
- chaves de API, tokens, cookies e senhas;
- URLs internas, IPs privados e caminhos do usuário;
- currículos, PDF, DOCX, bancos, logs e cofres;
- HTML ou descrições integrais coletadas de portais.

Abra também cada captura em `docs/assets` e confirme que ela não mostra nomes de pessoas ou
empresas, contatos, credenciais, caminhos locais nem buscas reais. As capturas públicas desta versão
foram produzidas com dados sintéticos e tiveram metadados removidos.

Confirme que `.gitignore` cobre `data`, `.env*`, `secrets.toml`, bancos, documentos, logs, chaves,
temporários e artefatos de build.

## 5. Validar a versão

No ambiente de desenvolvimento:

```text
uv lock --check
uv sync --python 3.12 --extra dev --frozen
uv run playwright install chromium
uv run ruff check .
uv run bandit -q -r src app_pages app.py
uv run pip-audit
uv run pytest
uv build
```

Também valide:

- `iniciar.cmd` em uma conta limpa do Windows 11;
- `install-linux.sh` em cada distribuição anunciada;
- iniciar, reabrir e confirmar o encerramento da porta ao fechar a última aba;
- importar um currículo sintético, buscar vagas e gerar PDF/DOCX;
- o conteúdo final do pacote criado em `dist`.

## 6. Configurar o GitHub

Ative:

- relato privado de vulnerabilidade;
- Dependabot alerts e security updates;
- secret scanning e push protection, quando disponíveis;
- proteção da branch principal;
- workflow `quality` para pull requests.

Na proteção da branch `main`, exija pull request, os checks `installers-linux`,
`installers-windows` e `test`, resolução das conversas e histórico linear. Em um projeto mantido por
uma pessoa, a aprovação de outra conta pode ficar desativada. Não permita force push nem exclusão.

Revise a lista de arquivos preparados antes de cada commit.

## 7. Criar a primeira versão

1. Aguarde o workflow `quality` concluir.
2. Crie uma tag semântica, começando pela série Alpha.
3. Publique notas com recursos, mudanças de dados, limitações e instruções de atualização.
4. Anexe um ZIP do código-fonte quando quiser destacar a instalação por clique.
5. Teste o ZIP baixado em uma pasta nova.

Somente depois desse teste, arquive o JobHunterBR em **Settings → General → Archive this
repository**. Se a exclusão ainda for desejada, faça-a apenas após manter uma cópia local e confirmar
que o novo repositório, as releases e o instalador estão acessíveis.

Uma chave encontrada depois do envio deve ser revogada e substituída. Remover apenas o arquivo do
commit mais recente não retira o segredo do histórico.
