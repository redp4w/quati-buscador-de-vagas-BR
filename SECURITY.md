# Segurança

## Relatar uma falha

Use **Security → Report a vulnerability** no GitHub. Informe a versão, o impacto e os passos mínimos
com dados sintéticos. Se puder, inclua uma sugestão de correção. Não abra uma issue pública com
currículos, chaves, URLs internas, dados pessoais ou detalhes exploráveis.

Se o relato privado ainda estiver indisponível, solicite sua ativação ao mantenedor sem revelar a
falha. Testes contra portais ou infraestrutura de terceiros exigem autorização desses responsáveis.

## Versões atendidas

Durante a fase Alpha, correções são aplicadas à versão mais recente da branch principal e à versão
publicada mais recente quando houver lançamento.

## Controles principais

- O servidor local escuta em `127.0.0.1`, com XSRF, CORS e limite de upload ativos.
- Inicializadores impedem instâncias duplicadas e validam o processo antes de encerrá-lo.
- URLs de coleta usam HTTPS, domínios permitidos e bloqueio de destinos privados.
- O navegador de coleta é efêmero e bloqueia perfil, download, permissões e service workers.
- Perfil, documentos e configuração de IA ficam em cofres locais independentes.
- SQL usa parâmetros; cláusulas variáveis são controladas pelo código.
- Dados entram no HTML por escape e o PDF é gerado sem JavaScript ou rede.
- Provedores externos exigem destino válido, limites e autorização salva.
- Vagas, currículos e respostas de IA são tratados como dados, sem execução dinâmica.
- O contêiner usa usuário sem privilégios, capacidades removidas e publicação no loopback.

## Regras para contribuições

- Use fixtures sintéticas.
- Mantenha `.env`, `data`, documentos, bancos, logs e chaves fora do Git.
- Restrinja novos plugins aos domínios oficiais mínimos.
- Defina limites de rede, tamanho e tempo.
- Atualize testes, documentação e avisos de terceiros.
- Mantenha login e candidatura no navegador de quem usa o aplicativo.

## Uso responsável

Respeite termos, `robots.txt`, limites e leis aplicáveis aos portais. O Q.U.A.T.I. foi projetado
para pesquisa pessoal limitada em páginas públicas, com revisão humana antes da candidatura.
