# Componentes e extensões

## Componentes do núcleo

| Projeto | Uso no Q.U.A.T.I. |
|---|---|
| Streamlit | interface local |
| Playwright e Chromium | páginas dinâmicas e exportação do currículo em PDF |
| Beautiful Soup | leitura conservadora de HTML e JSON-LD público |
| SQLite | vagas, histórico, alertas e agendamentos |
| GeoNames/geonamescache | país e distância entre cidades sem geocodificação externa |
| cryptography e keyring | cofres locais e chave protegida pelo sistema |
| pypdf e python-docx | importação e exportação de currículos |

Esses componentes são instalados pelo fluxo guiado e suas versões ficam registradas em `uv.lock`.

## Extensões opcionais

| Projeto ou interface | Possível uso |
|---|---|
| Gemini | sugestões de texto por API |
| Ollama | sugestões usando um modelo local |
| llama.cpp | servidor local leve pela interface compatível com OpenAI |
| LM Studio, LocalAI e vLLM | outros servidores compatíveis com OpenAI |
| Reactive Resume | editor visual externo em uma integração futura |
| Docling | OCR e leitura de currículos escaneados em uma extensão futura |
| Docker Compose | execução isolada e automação periódica |

Ative apenas as extensões que você pretende usar. Cada uma deve informar onde processa os dados e
continuar separada do fluxo principal.

## Portais

| Portal | Suporte atual |
|---|---|
| InHire | busca automática nas empresas declaradas no catálogo |
| Adzuna | busca automática pela API oficial, com credenciais próprias cifradas localmente |
| Empregos.com.br | uma página pública de resultados |
| Empregando Brasil | busca pública, sem `/api/search` |
| Sólides | busca pública automática e importação de uma URL individual |
| Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee e Workable | API pública por empresa catalogada |
| Workday | coleta avançada por URL pública compatível |
| Gupy, LinkedIn, Indeed, Mindsight, Lato Jobs e Vagas.com | busca automática pública e isolada |
| Jobbol, ProgramaThor e BNE | busca assistida, sem coleta |
| GeekHunter, Catho, Glassdoor e demais fontes restritas | abertura no navegador |

Um novo portal só entra por plugin depois da análise de páginas públicas, termos, `robots.txt`,
limites de requisição e estabilidade. O contrato não inclui cookies, senhas, CAPTCHA nem sessões
autenticadas.

A decisão por portal e as fontes oficiais consultadas ficam em
[Auditoria de portais](PORTAL_AUDIT.md).

JobSpy e Crawl4AI foram avaliados, mas não incorporados. Eles não alteram as permissões dos portais;
o segundo também duplicaria o navegador e o parser que já existem no projeto. A Adzuna usa sua
API oficial diretamente, sem incorporar outro repositório.

## Critérios para uma nova dependência

- Resolver uma necessidade presente no fluxo.
- Ter licença livre compatível e avisos de atribuição claros.
- Permitir execução sob demanda, com portas vinculadas ao loopback quando aplicável.
- Aceitar limites de tempo, tamanho e rede definidos pelo aplicativo.
- Ser testável com dados sintéticos e sem uma conta pessoal.

## Referências

- <https://playwright.dev/python/>
- <https://docs.streamlit.io/>
- <https://github.com/ollama/ollama>
- <https://github.com/ggml-org/llama.cpp>
- <https://github.com/AmruthPillai/Reactive-Resume>
