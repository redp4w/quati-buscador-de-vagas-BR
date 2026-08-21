# Módulos de inteligência artificial

A inteligência artificial trabalha apenas com texto: resumo, requisitos, palavras-chave e
sugestões para o currículo. O editor HTML/CSS local continua responsável pelo visual.

Abra **Inteligência artificial** para escolher um módulo. Na mesma tela ficam:

- autorização para enviar texto a um provedor externo;
- modelo e endereço do servidor;
- chave de API, quando aplicável;
- teste de conexão com uma mensagem neutra.

O Perfil salvo entra automaticamente como contexto do Assistente. Suas escolhas e a autorização
externa ficam salvas até que você as altere.

## Gemini

1. Crie uma chave no [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Escolha **Gemini API**.
3. Selecione o modelo e cole a chave.
4. Defina as autorizações.
5. Teste e salve.

O padrão atual é `gemini-3.5-flash-lite`, escolhido para tarefas curtas e baixo custo. O plano
gratuito tem limites variáveis, e o Google informa que pode usar o conteúdo para melhorar produtos.
Revise [preços e tratamento do nível](https://ai.google.dev/gemini-api/docs/pricing) antes de enviar
informações pessoais.

## Ollama

Instale o [Ollama](https://ollama.com/download), baixe um modelo adequado ao seu computador e
escolha **Ollama local** no Q.U.A.T.I. O endereço aceito fica em `localhost`, `127.0.0.1` ou `::1`.

Modelos pequenos usam menos memória, mas costumam produzir textos mais simples. Escolha o modelo de
acordo com a memória disponível no seu computador.

## API compatível com OpenAI

Servidores como llama.cpp, LM Studio, LocalAI e vLLM podem ser conectados quando implementam
`POST /chat/completions`.

- Em localhost, HTTP é aceito.
- Em rede externa, o endereço deve usar HTTPS público.
- Domínios são validados contra destinos privados e redirecionamentos inseguros.
- A chave e a autorização ficam no cofre de configuração.

## Prompt externo

Em **Preparar candidatura**, abra **Prompt do currículo — use onde quiser**. O aplicativo cria um arquivo de prompt
e remove nome, e-mail, telefone, links e endereço. Revise o conteúdo antes de copiá-lo para outra
ferramenta.

Esse modo serve para quem prefere escolher uma ferramenta diferente em cada vaga sem criar uma
integração permanente.

## Criar um novo módulo

1. Implemente `TextGenerator.generate(prompt) -> GeneratedText`.
2. Defina um `AIProviderModule` com nome, descrição, fábrica e regra de privacidade.
3. Registre o módulo em `AIProviderRegistry`.
4. Adicione campos específicos à tela apenas quando o protocolo exigir.
5. Teste tempo limite, tamanho de resposta, falha de rede e ausência de autorização.

Os módulos apenas retornam sugestões. Eles não podem executar comandos, editar arquivos, alterar o
perfil, mudar a compatibilidade ou enviar candidaturas.
