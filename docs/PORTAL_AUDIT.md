# Catálogo e auditoria de fontes

Revisão: 20 de agosto de 2026.

Este é o catálogo conhecido do projeto, não uma promessa de cobrir todos os sites existentes. Ele
reúne portais brasileiros, agregadores e plataformas de recrutamento já citados ou avaliados. Uma
página pública não autoriza automaticamente sua cópia: a classificação considera documentação,
termos, `robots.txt`, acesso sem conta, estabilidade e limites técnicos.

O Q.U.A.T.I. não contorna login, CAPTCHA, bloqueio, sessão, limite ou API privada. Cookies e contas
do navegador não são usados pelos coletores.

## Modos

- **automática:** a fonte oferece API, feed ou página pública compatível; o app lê apenas anúncios;
- **por URL:** uma vaga ou página específica pode ser importada, sem busca geral;
- **assistida:** o app prepara os filtros e abre o portal, mas não lê os resultados;
- **no navegador:** o endereço oficial fica catalogado, sem automação.

## Busca automática geral

| Fonte | Como funciona | Limite atual |
|---|---|---|
| [Adzuna](https://www.adzuna.com.br/) | [API oficial](https://developer.adzuna.com/overview) com `app_id` e `app_key` próprios | até 50 resultados por consulta; sem chave pública de teste |
| [Gupy](https://portal.gupy.io/job-search/) | pesquisa e quadros públicos de empresas, sem conta | consulta limitada por cargo |
| [LinkedIn](https://www.linkedin.com/jobs/) | anúncios públicos de emprego, sem sessão do candidato | consulta limitada e falha isolada |
| [Indeed](https://br.indeed.com/) | anúncios públicos brasileiros, sem área autenticada | consulta limitada e experimental |
| [Mindsight](https://mindsight.com.br/) | vagas públicas e posições de empresas parceiras | consulta limitada por cargo |
| [Lato Jobs](https://www.latojobs.com/) | vagas públicas de tecnologia no Brasil | consulta limitada por cargo |
| [Vagas.com](https://www.vagas.com.br/) | páginas públicas abertas do portal | consulta limitada por cargo |
| [Empregos.com.br](https://www.empregos.com.br/) | uma página pública de resultados, sem conta ou sub-recursos | uma consulta por cargo |
| [Empregando Brasil](https://empregandobrasil.com.br/) | HTML público; a rota `/api/search` bloqueada não é usada | até três páginas por consulta |
| [Sólides Vagas](https://vagas.solides.com.br/vagas) | endpoint JSON público usado pela página oficial, sem conta | até três páginas de dez vagas por consulta |
| [InHire](https://www.inhire.com.br/produto) | resposta JSON pública de empresas declaradas no YAML | uma consulta por empresa |

## Plataformas com API pública por empresa

Essas fontes não oferecem busca global. O app consulta apenas empresas presentes em
`config/job_sources.yml`, aplica cargo, texto, local, modalidade e PCD localmente e abre a vaga no
site original.

| Plataforma | Interface usada | Situação |
|---|---|---|
| [Greenhouse](https://developers.greenhouse.io/job-board.html) | Job Board API pública, sem autenticação em `GET` | automática |
| [Lever](https://github.com/lever/postings-api) | Postings API pública; até três páginas de 100 anúncios | automática |
| [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api) | Job Postings API pública | automática quando houver empresa configurada |
| [SmartRecruiters](https://developers.smartrecruiters.com/docs/endpoints) | Posting API pública com filtro `country=br` | automática |
| [Recruitee](https://docs.recruitee.com/reference/intro-to-careers-site-api) | Careers Site API pública, sem autenticação | automática quando houver empresa configurada |
| [Workable](https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page) | endpoint público de vagas publicadas | automática quando houver empresa configurada |

O catálogo inicial inclui iFood, Grupo QuintoAndar, XP Inc. e Stone no Greenhouse; CI&T no Lever;
Bosch Brasil e SGS Brasil no SmartRecruiters; Share People Hub e Resid Club no InHire. Honda e
Teltec Solutions permanecem como atalhos assistidos da Gupy.

Os testes ao vivo são pequenos e manuais. Uma empresa que remova ou troque o quadro é desativada
até nova validação; o coletor não tenta descobrir identificadores ocultos.

## Busca por URL

| Fonte | Decisão |
|---|---|
| [Sólides Vagas](https://vagas.solides.com.br/vagas) | Além da busca automática, aceita uma vaga individual pública em `/vaga/` ou `/vacancies/`. |
| [Workday](https://www.myworkdayjobs.com/) | Uma página pública informada no painel avançado pode ser lida por HTML estruturado; não há varredura global. |

## Busca assistida

| Portal | Resultado da revisão |
|---|---|
| [Jobbol](https://www.jobbol.com.br/) | O `robots.txt` aceita páginas de cargos, mas os [termos](https://www.jobbol.com.br/termos-uso) restringem reprodução e testes automatizados receberam HTTP 403. |
| [ProgramaThor](https://programathor.com.br/jobs) | A página aceita filtros, mas as regras publicadas restringem robôs de coleta. |
| [BNE](https://www.bne.com.br/) | Os termos não permitem ferramentas para coletar dados do site. |

## Demais portais catalogados

Essas fontes abrem no navegador. Elas só mudam de modo depois de uma nova revisão e de testes
limitados.

| Grupo | Fontes |
|---|---|
| Emprego geral | BURH, 99jobs, Trabalha Brasil, Catho, beBee, Infojobs, Jooble e Revelo |
| Tecnologia e remoto | GeekHunter, trampos, Vagas Remotas, APInfo e Remotar |
| Estágio e formação | CIEE, Nube e IEL |
| Inclusão | PCD.com.br; o filtro PCD também funciona nas fontes automáticas quando o anúncio declara elegibilidade |
| Outros agregadores | Glassdoor |

Entre as restrições já confirmadas estão: [99jobs](https://99jobs.com/pages/terms),
[PCD.com.br](https://www.pcd.com.br/termos-de-uso),
[trampos](https://www.trampos.co/termos),
[Infojobs](https://www.infojobs.com.br/legal/aviso-legal-para-candidatos__15727.aspx),
[GeekHunter](https://www.geekhunter.com/pt/termos-de-uso) e
[Vagas Remotas](https://vagasremotas.net/termos-e-servicos/). Um `Allow` no `robots.txt` não
substitui os termos do serviço.

## Plataformas catalogadas sem conector

| Plataforma | Estado |
|---|---|
| Personio | Possui feed XML opcional por empresa, mas depende de ativação pelo empregador. |
| Quickin, Abler, Pandapé e Recrutei | As páginas variam por empresa; ainda não há interface pública comum validada. |
| BambooHR | A interface pública não foi validada para o escopo brasileiro. |
| SAP SuccessFactors e Oracle Recruiting | Tenants e rotas variam; permanecem como referências de ATS. |

## Ferramentas externas avaliadas

- [JobSpy](https://github.com/speedyapply/JobSpy) não foi incorporado. A licença do código não
  concede autorização para raspar LinkedIn, Indeed ou Glassdoor.
- [Crawl4AI](https://github.com/unclecode/crawl4ai) não foi incorporado. Ele duplicaria a camada de
  navegador e adicionaria recursos de proxy e evasão fora do escopo.
- O padrão [Schema.org `JobPosting`](https://schema.org/JobPosting) é lido diretamente pelo app.
Nenhum código desses repositórios foi copiado.

## Filtro PCD

O filtro exige uma declaração explícita como `PCD` ou `pessoa com deficiência` no título ou na
descrição. Sem essa indicação, o app não presume elegibilidade. A escolha vale apenas para a busca
atual e não é gravada no perfil.
