# Instalação no Windows

## Requisitos

- Windows 11 atualizado.
- Instalador de Aplicativos da Microsoft atualizado.
- Conexão com a internet durante a instalação.
- Permissão para instalar componentes no usuário atual.
- Pelo menos 2 GB livres.

## Instalação por clique

1. Na página do projeto no GitHub, escolha **Code → Download ZIP**.
2. Aguarde o arquivo terminar de baixar e abra a pasta **Downloads**.
3. Clique com o botão direito no ZIP e escolha **Extrair tudo**.
4. Mova a pasta extraída para um local permanente, como `Documentos\QUATI`. Não use o aplicativo
   dentro do ZIP nem em `Arquivos de Programas`.
5. Dentro da pasta extraída, abra `iniciar.cmd`.
6. Leia a lista de componentes e escolha **Sim** para autorizar a instalação.
7. Aguarde as cinco etapas. O processo pode demorar no primeiro uso por causa do Chromium.
8. Quando aparecer **Q.U.A.T.I. pronto**, use o atalho criado na Área de Trabalho. O iniciador já
   abrirá a primeira tela no navegador.

Com sua autorização, o instalador baixa:

- uv, pelo catálogo oficial do Instalador de Aplicativos do Windows;
- Python 3.12, gerenciado pelo uv;
- as versões registradas em `uv.lock`;
- Chromium, pelo Playwright.

Antes de modificar o ambiente, o script confere se o ZIP foi extraído por completo e se existem ao
menos 2 GB livres. As bibliotecas Python ficam em `.venv`, dentro da pasta do projeto. O Python e o
uv são instalados para o usuário atual, e o Chromium fica no cache do Playwright dessa mesma conta.

`iniciar.cmd` é o único ponto de entrada: na primeira execução ele chama
`scripts\install-windows.ps1`; nas seguintes, apenas valida e abre a instalação existente. O script
também cria atalhos na Área de Trabalho e no menu Iniciar.

A aplicação abre no navegador em `http://127.0.0.1:8501`. Esse endereço aceita conexões apenas do
próprio computador.

## Iniciar e encerrar

- **Iniciar:** abra `iniciar.cmd` ou **Q.U.A.T.I.** na Área de Trabalho/menu Iniciar.
- **Encerrar:** use **Encerrar** no menu. Fechar todas as abas também encerra a porta
  automaticamente após cerca de 10 segundos.
- **Reabrir a tela:** use o mesmo atalho; uma segunda instância não será criada.

Se houver mais de uma aba aberta, o servidor continua ativo até a última ser fechada. Em um
computador compartilhado, use também **Bloquear** antes de fechar a aba.

## Reparar a instalação

Abra um PowerShell na pasta do projeto e execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

O instalador reutiliza os componentes válidos e sincroniza as versões registradas no projeto.

## Atualizar o projeto

A versão atual usa atualização manual:

1. Faça backup da pasta `data` com a aplicação encerrada.
2. Baixe a nova versão publicada no GitHub.
3. Extraia-a em uma nova pasta.
4. Mova o backup de `data` para a nova pasta.
5. Execute `iniciar.cmd`.

Leia as notas da versão antes de restaurar o backup quando houver mudança de formato de dados.

## Desinstalar

1. Feche todas as abas do Q.U.A.T.I. e aguarde a porta encerrar.
2. Faça backup de `data` se quiser conservar seu histórico e seus cofres.
3. Apague a pasta extraída do projeto.
4. Remova o atalho **Q.U.A.T.I.** da Área de Trabalho e do menu Iniciar, se ainda existirem.

O uv, o Python gerenciado e o cache do Chromium são compartilhados por usuário e não são removidos
automaticamente, para não afetar outros projetos.

## Problemas comuns

### O Instalador de Aplicativos precisa ser atualizado

Abra a Microsoft Store, procure **Instalador de Aplicativos**, atualize o componente e execute o
instalador do Q.U.A.T.I. novamente.

### A página mostra um erro genérico

Feche todas as abas do Q.U.A.T.I. e abra `iniciar.cmd` novamente. Se continuar, consulte
`data\runtime-error.log` e execute `scripts\install-windows.ps1` com o PowerShell. O instalador
encerra uma versão antiga antes de atualizar os arquivos.

### A porta 8501 está ocupada

Abra `iniciar.cmd` novamente. O iniciador reconhece uma instância anterior do próprio Q.U.A.T.I. e
reabre a página, mesmo quando o Streamlit expõe a porta por um processo-filho. Use **Encerrar
Q.U.A.T.I.** para liberar a porta. A mensagem de conflito só deve aparecer se outro programa for o
dono real da porta.

### A instalação foi interrompida

Verifique a conexão, mantenha espaço livre para Python, bibliotecas e Chromium e abra
`iniciar.cmd` novamente.

### O PDF não foi gerado

Execute `scripts\install-windows.ps1` com o PowerShell para sincronizar o Chromium usado pela
exportação.
