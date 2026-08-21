# Instalação no Linux

## Plataformas suportadas

- Ubuntu 22.04, 24.04 e 26.04.
- Debian 12 e 13.
- Arquiteturas x86-64 e ARM64.
- Ambiente gráfico com navegador padrão.
- Pelo menos 2 GB livres.

Essas plataformas acompanham o suporte oficial atual do Playwright para Linux.

## Instalação guiada

1. Na página do projeto no GitHub, escolha **Code → Download ZIP**.
2. Extraia todo o ZIP para uma pasta permanente; não execute os arquivos dentro do ZIP.
3. Abra um terminal nessa pasta.
4. Inicie o instalador:

```bash
bash install-linux.sh
```

5. Leia a lista apresentada e confirme a autorização.
6. O script valida os arquivos do download e se há pelo menos 2 GB livres.
7. Informe a senha administrativa quando o sistema solicitar as bibliotecas do Chromium.
8. Abra **Q.U.A.T.I.** pelo menu de aplicativos.

O instalador configura uv, Python 3.12, as versões registradas em `uv.lock`, Chromium e suas
bibliotecas do sistema. O ambiente Python fica em `.venv`, dentro do projeto. O script também cria
o atalho **Q.U.A.T.I.** em `~/.local/share/applications` e um pequeno iniciador em
`~/.local/bin/quati-launch`.

## Iniciar e encerrar

- **Iniciar:** abra **Q.U.A.T.I.** no menu de aplicativos.
- **Encerrar:** use **Encerrar** no menu; fechar todas as abas também encerra a porta
  após cerca de 10 segundos.
- **Endereço local:** `http://127.0.0.1:8501`.

O processo grava diagnósticos em `data/runtime.log`. O arquivo só pode ser lido pela conta atual e
fica fora do Git.

## Reparar a instalação

Abra um terminal na pasta do projeto e execute novamente:

```bash
bash install-linux.sh
```

## Atualizar o projeto

1. Encerre o aplicativo.
2. Faça backup da pasta `data`.
3. Baixe e extraia a nova versão em outra pasta.
4. Restaure `data` após ler as notas da versão.
5. Execute `bash install-linux.sh` na nova pasta.

## Outras distribuições

O código Python pode funcionar em outras distribuições, mas a instalação das bibliotecas do
Chromium varia por sistema. Um pacote específico deve validar e instalar essas bibliotecas antes de
ser apresentado como suporte oficial.

O Kali Linux é uma distribuição rolling release e não entra na matriz oficial usada pelo
Playwright. Por isso, o instalador guiado encerra sem modificar o sistema. Não é seguro instalar
pacotes de outra distribuição automaticamente apenas para forçar compatibilidade.

## Desinstalar

1. Feche todas as abas do Q.U.A.T.I. e aguarde a porta encerrar.
2. Faça backup da pasta `data` se quiser conservar o histórico e os cofres.
3. Apague a pasta extraída do projeto.
4. Remova `~/.local/bin/quati-launch` e `~/.local/share/applications/quati.desktop`.

O uv, o Python gerenciado e o cache do Chromium não são removidos automaticamente, pois podem ser
compartilhados por outros projetos do usuário.

## Problemas comuns

### O atalho não aparece

Encerre a sessão gráfica e entre novamente. O arquivo é criado em
`~/.local/share/applications/quati.desktop`.

### A aplicação não abre

Confira `data/runtime.log` e execute `bash install-linux.sh` para reparar as dependências.

### A porta 8501 está ocupada

Feche todas as abas do Q.U.A.T.I. e aguarde alguns segundos. Se a porta continuar ocupada, outro
programa precisa ser encerrado.
