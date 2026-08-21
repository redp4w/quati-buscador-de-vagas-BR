# Plugins de portais

Um plugin converte uma página pública para o modelo interno de vaga. Depois disso, a busca aplica as
regras de país, distância, modalidade, deduplicação e histórico a todas as fontes.

## Contrato

Cada plugin deve:

1. declarar `name`, `display_name` e `allowed_hosts`;
2. aceitar somente URLs HTTPS validadas por `validate_public_https_url`;
3. limitar páginas, tamanho, redirecionamentos e tempo;
4. retornar `JobInput` normalizado;
5. preencher cargo, empresa, local e descrição com dados publicados pela fonte;
6. falhar de forma isolada;
7. usar fixtures sintéticas nos testes;
8. marcar `experimental = True` quando a página ainda for instável.

`PublicStructuredPlugin` atende páginas com JSON-LD `JobPosting` e links públicos. Fontes dinâmicas
podem especializar seletores e paginação.

## Modos ativos

Adzuna, Gupy, LinkedIn, Indeed, Mindsight, Lato Jobs, Vagas.com, Sólides, InHire,
Empregos.com.br e Empregando Brasil participam da coleta automática. A Adzuna usa a API oficial
quando `app_id` e `app_key` estão no cofre local; Sólides usa a busca JSON pública; InHire usa uma
resposta JSON pública por empresa configurada; as demais usam páginas ou respostas públicas
limitadas e falham de forma isolada.

Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee e Workable usam as interfaces públicas
documentadas pelos próprios fornecedores. Esses conectores não varrem empresas: cada página
precisa estar declarada em `config/job_sources.yml`. A configuração inicial inclui empresas com
atuação no Brasil e pode ser revisada por pull request.

O painel avançado também aceita uma URL individual da Sólides em `/vaga/` ou `/vacancies/`.
Workday aceita uma página pública específica.

Jobbol, ProgramaThor e BNE usam busca assistida. Endereços e páginas públicas de empresas ficam em
`config/job_sources.yml`, enquanto o modo de cada fonte
permanece no código. Alterar o YAML sozinho nunca ativa um coletor novo.

## Criar um plugin

1. Confirme termos de uso, `robots.txt`, páginas públicas e regras compatíveis com agregação
   limitada. Um `Allow` não substitui uma proibição nos termos.
2. Herde de `JobPlugin` ou `PublicStructuredPlugin`.
3. Restrinja `allowed_hosts` ao menor conjunto oficial possível.
4. Valide a URL inicial e todos os links extraídos.
5. Normalize a saída com `JobInput`.
6. Registre a classe em `plugins/registry.py`.
7. Adicione testes para vaga válida, HTML vazio, link externo e paginação máxima.
8. Documente portal, limites, empresa inicial e comportamento de falha.

Use [a auditoria atual](PORTAL_AUDIT.md) como modelo. Se as regras não forem claras, mantenha o
portal como atalho externo até obter autorização.

## Limites do contrato

Plugins operam sobre páginas públicas. Login, cookies, credenciais, CAPTCHA, perfil persistente,
encurtadores e CDNs genéricas ficam fora dos domínios permitidos. Uma integração interrompida deve
retornar erro controlado ou lista vazia, sem ampliar o escopo de rede.
