# Análise técnica

Revisão: 15 de agosto de 2026.

## Aderência ao objetivo

O Q.U.A.T.I. continua alinhado ao objetivo: buscar vagas públicas brasileiras, comparar
oportunidades com um perfil, preparar documentos e abrir a candidatura original. O escopo separa
quatro responsabilidades: coleta pública, análise local, preparação do currículo e candidatura
manual.

As fontes automáticas cobrem vagas gerais e de tecnologia. Uma nova fonte entra depois da validação
de páginas públicas, termos, `robots.txt`, limites e estabilidade.

## Linguagens e formatos

| Item | Uso |
|---|---|
| Python 3.12+ | aplicação, plugins, domínio, IA, segurança e testes |
| SQL/SQLite | persistência de vagas públicas e atividade |
| PowerShell | instalador e atalhos do Windows |
| Bash | instalador e atalhos do Linux |
| HTML/CSS | visual editável do currículo |
| SVG/PNG/ICO | identidade visual e atalhos |
| TOML | pacote e dependências |
| YAML | catálogo de fontes, integração contínua, templates e Compose |
| Markdown | documentação pública |

## Tecnologias e momento de uso

| Tecnologia | Onde | Quando |
|---|---|---|
| Streamlit | `dashboard.py`, `ui/`, `app_pages/` | interface local |
| SQLite | `storage/sqlite.py` | vagas, coletas, histórico, alertas e agendamentos |
| Playwright/Chromium | `core/browser/`, `resumes/` | página dinâmica e exportação em PDF |
| Beautiful Soup | plugins | HTML e JSON-LD públicos |
| pypdf e python-docx | `resumes/` | importar, validar e exportar documentos |
| cryptography e keyring | `security.py` | cofres locais e chave do sistema |
| Pydantic | `config/` e modelos | validação e configuração tipada |
| PyYAML | `config/job_sources.yml` | leitura segura do catálogo público de fontes |
| httpx | `ai/providers.py`, `core/browser/` | módulos externos de texto e JSON público limitado |
| geonamescache | `location.py` | cidades, estados, país e distância offline |
| uv | `pyproject.toml` e `uv.lock` | Python, ambiente e dependências reproduzíveis |
| pytest, Ruff, Bandit e pip-audit | `tests/` e workflow | qualidade e segurança |
| Docker Compose | `compose.yaml` | modo isolado opcional |

## Fluxo técnico

1. O inicializador cria o ambiente, abre uma instância no loopback e acompanha as abas conectadas.
2. A sessão abre cofres independentes para Perfil, currículos, IA e APIs de busca opcionais.
3. Estado e cidade são selecionados e validados numa base geográfica local.
4. A busca gera URLs públicas para coleta ou links assistidos conforme o modo do portal.
5. Cada plugin valida HTTPS e domínio antes de solicitar conteúdo.
6. País, raio, modalidade e indicação PCD são validados antes da persistência.
7. O SQLite deduplica vagas e registra mudanças.
8. A compatibilidade usa apenas os dados salvos no perfil.
9. O texto sugerido fica separado do documento até ser aceito.
10. HTML/CSS controla a prévia e o Chromium imprime o PDF.
11. O navegador padrão abre o portal para a candidatura.

O catálogo YAML pode trocar endpoints públicos, mas não muda o modo de integração. URLs continuam
limitadas aos domínios oficiais declarados no código; segredos ficam fora do arquivo.

## Segurança por camada

| Camada | Risco tratado | Controles atuais |
|---|---|---|
| Inicialização | serviço duplicado, porta exposta ou processo órfão | uma instância, `127.0.0.1` e encerramento ao fechar a última aba |
| Rede | SSRF e redirecionamento lateral | HTTPS, hosts permitidos, DNS e bloqueio de IP privado |
| Streamlit | upload excessivo e requisição forjada | 10 MB, XSRF, CORS e detalhes de erro ocultos |
| Navegador | cookie, download e permissão | contexto efêmero, permissões e downloads bloqueados |
| Plugins | HTML hostil e paginação infinita | conteúdo tratado como dado e limites por fonte |
| Documentos | arquivo comprimido ou complexo | tamanho, páginas, ZIP e macros limitados |
| HTML/PDF | injeção ativa e recurso remoto | escape, modelo fixo, JavaScript e rede bloqueados |
| IA | envio indevido e resposta excessiva | autorização, destino validado, tempo e tamanho limitados |
| Cofres | corrupção e leitura excessiva | cifragem autenticada, gravação atômica e limites |
| Banco | injeção SQL | parâmetros e cláusulas estáticas |
| Repositório | segredo ou dado pessoal | regras de ignore, fixtures sintéticas e varredura antes do Git |

O código trata vagas, currículos e respostas de IA como dados. Os testes impedem mecanismos de
execução dinâmica no aplicativo.

## Testes funcionais

A suíte cobre:

- plugins e normalização de vagas;
- administração, engenharia civil, nutrição, cozinha e tecnologia;
- Adzuna por API oficial simulada, Sólides e InHire com JSON público;
- Empregos.com.br e Empregando Brasil com HTML real e fixtures sintéticas;
- senioridade, famílias profissionais e explicação da compatibilidade;
- Sorocaba, Itu, São Paulo, Rio de Janeiro, remoto nacional e país estrangeiro;
- Perfil, cofres, limpeza de dados locais e currículos;
- módulos de IA, consentimento e limites de resposta;
- páginas Streamlit, SQLite, agendamento e geração de documentos;
- segurança de URL, HTML, upload e execução;
- arquivos públicos, instaladores e regras para publicação.
- inicialização em Chromium, Chrome, Edge, Firefox e WebKit, inclusive em largura móvel.

O workflow executa lockfile, lint, análise estática de segurança, auditoria de dependências, testes e
build em cada push e pull request.

## Navegadores

Em 15 de agosto de 2026, a interface limpa abriu sem erro e sem rolagem horizontal em:

| Navegador testado | Resultado |
|---|---|
| Chromium do Playwright | aprovado em desktop e largura móvel |
| Google Chrome 151 | aprovado |
| Microsoft Edge 151 | aprovado |
| Firefox do Playwright | aprovado |
| WebKit do Playwright | aprovado em desktop e largura móvel |

O Opera não estava instalado no ambiente de teste. Como ele usa Chromium, a compatibilidade é
provável, mas permanece pendente de teste real. A interface pode abrir no navegador padrão; a
coleta permitida e a exportação de PDF usam o Chromium isolado do Playwright e não acessam a sessão
desse navegador.

## Limitações técnicas

- Seletores dependem das páginas publicadas pelos portais.
- Parsers de PDF/DOCX não recuperam com perfeição todo layout ou OCR.
- O cálculo geográfico depende do nome de cidade reconhecível na vaga.
- Uma sessão do sistema operacional já comprometida também compromete dados abertos na aplicação.
- APIs externas seguem políticas, disponibilidade e limites próprios.
- Atualizações ainda exigem baixar a nova versão e sincronizar o ambiente.

As decisões jurídicas e técnicas de cada fonte estão em
[Auditoria de portais](PORTAL_AUDIT.md).
