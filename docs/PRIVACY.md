# Privacidade

## Princípio

O Q.U.A.T.I. coleta vagas públicas e guarda seus dados profissionais no próprio computador. Para
enviar qualquer texto a um serviço externo, você precisa configurar o módulo e autorizar o envio.

## Dados locais

| Caminho | Conteúdo |
|---|---|
| `data/quati.sqlite3` | vagas públicas, coletas, histórico, alertas e agendamentos |
| `data/candidate-profile.enc` | Perfil profissional |
| `data/candidate-resumes.enc` | currículos originais e texto extraído |
| `data/ai-configuration.enc` | módulo, modelo, autorizações e chave de API |
| `data/job-source-configuration.enc` | chaves opcionais de APIs de vagas |
| `data/runtime.log` e `data/runtime-error.log` | diagnóstico local da inicialização |

A pasta `data` é ignorada pelo Git.

Os campos de uma busca comum permanecem na memória da sessão. O SQLite registra as vagas públicas,
as execuções e os endereços consultados; uma busca só vira configuração persistente quando é salva
como agendamento. O caminho avançado `QUATI_DB` move o SQLite, e os cofres ficam ao lado dele.

O SQLite não é cifrado. Ele não recebe o Perfil, o conteúdo dos currículos nem as credenciais das
fontes e da IA. Ainda assim, histórico, vagas selecionadas e agendamentos podem revelar interesses
profissionais; trate o backup como dado privado.

## Proteção dos cofres

Cada gravação cria um salt aleatório de 16 bytes e deriva uma chave com Argon2id, configurado com
64 MiB de memória, três passagens e quatro trilhas. Fernet fornece cifragem autenticada: além de
ocultar o conteúdo, detecta senha incorreta ou arquivo alterado. O arquivo novo é sincronizado e
substitui o anterior de forma atômica. O leitor mantém compatibilidade com cofres PBKDF2 de versões
anteriores e os regrava imediatamente em Argon2id após uma abertura bem-sucedida.

Se você usar uma senha, ela fica apenas na memória enquanto a sessão estiver aberta. Sem senha, o
app cria uma chave aleatória e a guarda no cofre seguro da conta do sistema operacional. Não existe
chave mestra, cópia remota nem mecanismo de recuperação mantido pelo projeto.

**Esqueci a senha** não decifra os dados: remove os quatro cofres privados e a chave local para
permitir um novo perfil. O SQLite de vagas públicas e histórico é preservado. Esse desenho evita
uma porta dos fundos; quem usa senha própria deve guardá-la num gerenciador de senhas.

Um backup feito sem senha pode depender dos arquivos e do cofre da mesma conta do sistema. Um
backup com senha depende da senha escolhida. Em ambos os casos, guarde a cópia em local privado.

## Navegador e portais

A coleta abre páginas públicas em um navegador temporário ou consulta uma API oficial restrita ao
domínio da fonte. Nenhum dos dois usa perfil persistente, proxy do ambiente, conta de candidato,
sessão ou cookie.

A Adzuna exige credenciais da API. Elas ficam cifradas no cofre local, entram apenas na requisição
à Adzuna e não são gravadas no histórico, no SQLite, no YAML ou nos logs.

Ao aplicar, o Q.U.A.T.I. abre a URL original no navegador padrão. Você revisa e envia o formulário
diretamente no portal.

Na busca assistida, o app monta uma URL pública com os filtros aceitos pelo portal. Nenhum cookie
ou resultado da página retorna ao Q.U.A.T.I.

## Inteligência artificial

| Modo | Tratamento |
|---|---|
| Gemini | envia texto autorizado à API do Google |
| Ollama | envia texto a um servidor no loopback |
| API compatível local | envia texto ao endereço local configurado |
| API compatível externa | exige HTTPS público e autorização salva |
| Prompt externo | cria um arquivo local com contato e endereço removidos |

A compatibilidade é calculada localmente, e nenhuma sugestão entra automaticamente no currículo.
No plano gratuito do Gemini, o Google informa que pode usar o conteúdo para melhorar produtos;
consulte os termos atuais antes de ativá-lo.

## Currículos gerados

O modelo HTML não carrega JavaScript, fontes, imagens ou estilos externos. O Chromium imprime o PDF
com rede, downloads, permissões e service workers bloqueados. Metadados de autor são removidos.

## Localização

País e distância são calculados com dados GeoNames locais. A localização da pesquisa é enviada aos
portais selecionados que aceitam esse filtro; o endereço completo do Perfil não é usado como
consulta de mapa.

## Memória e exclusão

**Bloquear** remove da sessão as chaves e o conteúdo aberto. **Apagar dados locais e começar
do zero** fecha o banco e apaga os cofres, o SQLite, arquivos auxiliares e a chave local após sua
confirmação.

Em computador compartilhado, use **Bloquear** e feche todas as abas do Q.U.A.T.I. O
inicializador encerra o serviço local e a porta logo depois que a última aba é fechada. O comando
**Encerrar** no menu solicita o fechamento imediato de toda a instância local.
