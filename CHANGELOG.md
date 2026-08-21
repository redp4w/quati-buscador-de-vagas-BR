# Histórico de versões

Todas as mudanças relevantes deste projeto são registradas aqui. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões usam
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.3.0] — 2026-08-21

### Adicionado

- busca livre e busca por perfil com compatibilidade mínima configurada em 70%;
- separação entre fontes automáticas, assistidas e coleta por URL pública;
- menu dividido entre trabalho, perfil, configurações e acompanhamento;
- página própria para Adzuna e catálogo de fontes;
- encerramento direto do app e liberação automática da porta ao fechar a última aba;
- recuperação de acesso por redefinição somente dos cofres privados;
- gerador reproduzível dos assets oficiais em `tools/build_brand_assets.py`.

### Alterado

- projeto, pacote e dados locais migrados de JobHunterBR para Q.U.A.T.I.;
- identidade visual refeita na estética keygen/underground dos anos 2000;
- menu preto e vermelho com assinatura horizontal animada;
- acesso inicial centralizado, sem barra de rolagem, título redundante ou mínimo obrigatório de senha;
- início com desmaterialização orgânica e luz interna, menu com varredura e loading com ciclo real de caminhada;
- caminhada corrigida para as oito poses originais em ordem, sem interpolação generativa;
- tabela de vagas com ações mais legíveis nas duas primeiras colunas;
- documentação de instalação, privacidade, criptografia, fluxo e publicação revisada.
- dependências de manutenção atualizadas, incluindo Streamlit 1.62, pypdf 6.16.1, Ruff 0.16.4 e a
  ação `setup-uv` revisada pelo Dependabot.

### Segurança

- perfil, currículos e configurações sensíveis permanecem em cofres locais cifrados;
- o servidor escuta somente em `127.0.0.1`;
- chaves, currículos, bancos, logs e dados pessoais continuam excluídos do Git.
- pypdf atualizado para incluir os limites e a detecção de ciclos das correções de segurança 6.16.x.

[0.3.0]: https://github.com/redp4w/quati-buscador-de-vagas-BR/releases/tag/v0.3.0
